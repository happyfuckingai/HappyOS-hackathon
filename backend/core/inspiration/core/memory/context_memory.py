import asyncio
import logging
import json
import gzip
import hashlib
import shutil
from typing import Dict, Any, Optional, List, Callable
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from pathlib import Path
import os
import tempfile

from app.core.database.connection import get_db_connection
from app.db.repository_base import RepositoryBase
from app.db.transaction_manager import get_transaction_manager, TransactionIsolation
from app.core.error_handling.health_monitor import HealthMonitor

logger = logging.getLogger(__name__)

@dataclass
class ContextEntry:
    """Database entity for context memory entries."""
    id: Optional[int] = None
    conversation_id: str = ""
    user_input: str = ""
    context_data: str = ""  # JSON string
    compressed_data: Optional[bytes] = None  # Gzipped data for large entries
    timestamp: datetime = field(default_factory=datetime.utcnow)
    access_count: int = 0
    last_accessed: datetime = field(default_factory=datetime.utcnow)
    is_compressed: bool = False
    size_bytes: int = 0
    checksum: Optional[str] = None  # SHA256 checksum for data integrity
    version: int = 1  # Schema version for migrations


@dataclass
class CleanupPolicy:
    """Configurable cleanup policy for memory management."""
    max_age_days: int = 90
    max_access_count: int = 10
    min_relevance_score: float = 0.1
    compression_age_days: int = 7
    compression_access_threshold: int = 5
    compression_size_kb: int = 50


@dataclass
class MemoryAlert:
    """Memory usage alert configuration."""
    threshold_mb: float = 80.0
    critical_threshold_mb: float = 95.0
    alert_callback: Optional[Callable[[str, Dict[str, Any]], None]] = None


class ContextMemory:
    """
    A simple placeholder for the context memory system.
    In a real implementation, this would connect to a database or a more
    sophisticated in-memory store like Redis.
    """
    def __init__(self):
        self._memory: Dict[str, Dict[str, Any]] = {}
        logger.info("Initialized basic ContextMemory.")

    def save_context(self, conversation_id: str, user_input: str, context_data: Dict[str, Any]):
        """Saves the context for a given conversation."""
        if conversation_id not in self._memory:
            self._memory[conversation_id] = {"history": []}

        self._memory[conversation_id]["history"].append({
            "user_input": user_input,
            "context_data": context_data
        })
        logger.debug(f"Saved context for conversation {conversation_id}")

    def get_context(self, conversation_id: str) -> Dict[str, Any]:
        """Retrieves the context for a given conversation."""
        return self._memory.get(conversation_id, {})


class ContextRepository(RepositoryBase[ContextEntry, int]):
    """Repository for persistent context storage."""

    def __init__(self, db_connection):
        super().__init__(db_connection, "context_entries", "id")

    def _entity_from_row(self, row: Dict[str, Any]) -> ContextEntry:
        """Convert database row to ContextEntry entity."""
        if self.db_connection.config.database_type == "sqlite":
            return ContextEntry(
                id=row[0],
                conversation_id=row[1],
                user_input=row[2],
                context_data=row[3],
                compressed_data=row[4] if len(row) > 4 else None,
                timestamp=datetime.fromisoformat(row[5]) if row[5] else datetime.utcnow(),
                access_count=row[6] if len(row) > 6 else 0,
                last_accessed=datetime.fromisoformat(row[7]) if len(row) > 7 and row[7] else datetime.utcnow(),
                is_compressed=row[8] if len(row) > 8 else False,
                size_bytes=row[9] if len(row) > 9 else 0,
                checksum=row[10] if len(row) > 10 else None,
                version=row[11] if len(row) > 11 else 1
            )
        else:
            return ContextEntry(
                id=row.get('id'),
                conversation_id=row.get('conversation_id', ''),
                user_input=row.get('user_input', ''),
                context_data=row.get('context_data', ''),
                compressed_data=row.get('compressed_data'),
                timestamp=row.get('timestamp', datetime.utcnow()),
                access_count=row.get('access_count', 0),
                last_accessed=row.get('last_accessed', datetime.utcnow()),
                is_compressed=row.get('is_compressed', False),
                size_bytes=row.get('size_bytes', 0),
                checksum=row.get('checksum'),
                version=row.get('version', 1)
            )

    def _row_from_entity(self, entity: ContextEntry) -> Dict[str, Any]:
        """Convert ContextEntry entity to database row."""
        row = {
            'conversation_id': entity.conversation_id,
            'user_input': entity.user_input,
            'context_data': entity.context_data,
            'compressed_data': entity.compressed_data,
            'timestamp': entity.timestamp.isoformat(),
            'access_count': entity.access_count,
            'last_accessed': entity.last_accessed.isoformat(),
            'is_compressed': entity.is_compressed,
            'size_bytes': entity.size_bytes,
            'checksum': entity.checksum,
            'version': entity.version
        }

        if entity.id:
            row['id'] = entity.id

        return row

    def _get_entity_id(self, entity: ContextEntry) -> Optional[int]:
        """Get entity ID."""
        return entity.id

    async def find_by_conversation(self, conversation_id: str, limit: int = 50) -> List[ContextEntry]:
        """Find context entries for a specific conversation."""
        try:
            query = """
            SELECT * FROM context_entries
            WHERE conversation_id = ?
            ORDER BY timestamp DESC
            LIMIT ?
            """
            params = (conversation_id, limit)

            result = await self._execute_query_with_retry(query, params)
            return [self._entity_from_row(row) for row in result]

        except Exception as e:
            logger.error(f"Error finding context by conversation {conversation_id}: {e}")
            raise

    async def get_conversation_stats(self, conversation_id: str) -> Dict[str, Any]:
        """Get statistics for a conversation."""
        try:
            query = """
            SELECT
                COUNT(*) as total_entries,
                SUM(size_bytes) as total_size,
                AVG(access_count) as avg_access,
                MAX(timestamp) as last_updated
            FROM context_entries
            WHERE conversation_id = ?
            """
            params = (conversation_id,)

            result = await self._execute_query_with_retry(query, params)
            if result:
                row = result[0]
                return {
                    'total_entries': row[0] if self.db_connection.config.database_type == "sqlite" else row['total_entries'],
                    'total_size_bytes': row[1] if self.db_connection.config.database_type == "sqlite" else row['total_size'] or 0,
                    'avg_access_count': row[2] if self.db_connection.config.database_type == "sqlite" else row['avg_access'] or 0,
                    'last_updated': row[3] if self.db_connection.config.database_type == "sqlite" else row['last_updated']
                }
            return {'total_entries': 0, 'total_size_bytes': 0, 'avg_access_count': 0, 'last_updated': None}

        except Exception as e:
            logger.error(f"Error getting conversation stats for {conversation_id}: {e}")
            return {'total_entries': 0, 'total_size_bytes': 0, 'avg_access_count': 0, 'last_updated': None}


class PersistentContextMemory(ContextMemory):
    """
    Persistent context memory with database integration, automatic backup,
    recovery, and memory compression for large conversations.
    """

    def __init__(self, enable_compression: bool = True, max_memory_size_mb: float = 100.0,
                 backup_interval_hours: int = 24):
        """
        Initialize persistent context memory.

        Args:
            enable_compression: Whether to compress large context data
            max_memory_size_mb: Maximum memory size before compression
            backup_interval_hours: Hours between automatic backups
        """
        super().__init__()

        self.enable_compression = enable_compression
        self.max_memory_size_mb = max_memory_size_mb
        self.backup_interval_hours = backup_interval_hours
        self.compression_threshold_bytes = 1024 * 1024  # 1MB

        # Database and repository
        self.db_connection = None
        self.repository: Optional[ContextRepository] = None

        # Health monitoring
        self.health_monitor = HealthMonitor()

        # Backup management
        self.last_backup = None
        self.backup_path = Path("data/backups/context_memory")

        # Background tasks
        self._backup_task: Optional[asyncio.Task] = None
        self._maintenance_task: Optional[asyncio.Task] = None

        # In-memory cache for frequently accessed conversations
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._cache_max_size = 50

        # Enhanced persistence features
        self.transaction_manager = None
        self.cleanup_policy = CleanupPolicy()
        self.memory_alert = MemoryAlert()
        self._data_integrity_enabled = True
        self._migration_manager = None
        self._last_integrity_check = None
        self._memory_monitoring_enabled = True
        self._defragmentation_enabled = True

        logger.info("Initialized PersistentContextMemory")

    async def initialize(self):
        """Initialize database connection and setup."""
        try:
            self.db_connection = await get_db_connection()
            self.repository = ContextRepository(self.db_connection)

            # Ensure backup directory exists
            self.backup_path.mkdir(parents=True, exist_ok=True)

            # Start background tasks
            await self._start_background_tasks()

            # Load recent conversations into cache
            await self._load_recent_conversations()

            logger.info("PersistentContextMemory initialized successfully")

        except Exception as e:
            logger.error(f"Failed to initialize PersistentContextMemory: {e}")
            raise

    async def shutdown(self):
        """Shutdown and cleanup resources."""
        # Stop background tasks
        if self._backup_task:
            self._backup_task.cancel()
            try:
                await self._backup_task
            except asyncio.CancelledError:
                pass

        if self._maintenance_task:
            self._maintenance_task.cancel()
            try:
                await self._maintenance_task
            except asyncio.CancelledError:
                pass

        # Final backup
        try:
            await self._perform_backup()
        except Exception as e:
            logger.error(f"Error during final backup: {e}")

        logger.info("PersistentContextMemory shutdown complete")

    async def save_context(self, conversation_id: str, user_input: str, context_data: Dict[str, Any]):
        """Save context with persistence and compression."""
        try:
            # Call parent method for in-memory storage
            super().save_context(conversation_id, user_input, context_data)

            # Prepare data for database storage
            context_json = json.dumps(context_data)
            size_bytes = len(context_json.encode('utf-8'))

            # Compress if enabled and data is large
            compressed_data = None
            is_compressed = False

            if self.enable_compression and size_bytes > self.compression_threshold_bytes:
                compressed_data = gzip.compress(context_json.encode('utf-8'))
                is_compressed = True
                logger.debug(f"Compressed context data for conversation {conversation_id}")

            # Create database entry
            entry = ContextEntry(
                conversation_id=conversation_id,
                user_input=user_input,
                context_data=context_json if not is_compressed else "",
                compressed_data=compressed_data,
                is_compressed=is_compressed,
                size_bytes=size_bytes
            )

            # Save to database
            if self.repository:
                await self.repository.save(entry)

            # Update cache
            self._update_cache(conversation_id, context_data)

            # Check memory usage and compress if needed
            await self._check_and_compress_memory()

            logger.debug(f"Persisted context for conversation {conversation_id}")

        except Exception as e:
            logger.error(f"Error saving persistent context: {e}")
            # Fallback to parent method only
            super().save_context(conversation_id, user_input, context_data)

    async def get_context(self, conversation_id: str) -> Dict[str, Any]:
        """Retrieve context with cache and database fallback."""
        try:
            # Check cache first
            if conversation_id in self._cache:
                logger.debug(f"Context cache hit for conversation {conversation_id}")
                return self._cache[conversation_id]

            # Check in-memory storage
            memory_context = super().get_context(conversation_id)
            if memory_context:
                self._update_cache(conversation_id, memory_context)
                return memory_context

            # Load from database
            if self.repository:
                entries = await self.repository.find_by_conversation(conversation_id, limit=100)

                if entries:
                    # Reconstruct conversation history
                    history = []
                    for entry in sorted(entries, key=lambda x: x.timestamp):
                        # Decompress if needed
                        context_data = entry.context_data
                        if entry.is_compressed and entry.compressed_data:
                            try:
                                context_data = gzip.decompress(entry.compressed_data).decode('utf-8')
                            except Exception as e:
                                logger.error(f"Error decompressing context data: {e}")
                                continue

                        try:
                            context_dict = json.loads(context_data)
                            history.append({
                                "user_input": entry.user_input,
                                "context_data": context_dict,
                                "timestamp": entry.timestamp.isoformat()
                            })
                        except json.JSONDecodeError as e:
                            logger.error(f"Error parsing context JSON: {e}")
                            continue

                    reconstructed_context = {"history": history}

                    # Update in-memory storage and cache
                    self._memory[conversation_id] = reconstructed_context
                    self._update_cache(conversation_id, reconstructed_context)

                    # Update access statistics
                    for entry in entries:
                        entry.access_count += 1
                        entry.last_accessed = datetime.utcnow()
                        await self.repository.save(entry)

                    logger.debug(f"Loaded context from database for conversation {conversation_id}")
                    return reconstructed_context

            return {}

        except Exception as e:
            logger.error(f"Error retrieving persistent context: {e}")
            # Fallback to parent method
            return super().get_context(conversation_id)

    async def get_conversation_stats(self, conversation_id: str) -> Dict[str, Any]:
        """Get comprehensive statistics for a conversation."""
        try:
            if self.repository:
                db_stats = await self.repository.get_conversation_stats(conversation_id)

                # Add cache and memory info
                memory_entries = len(self._memory.get(conversation_id, {}).get("history", []))
                in_cache = conversation_id in self._cache

                return {
                    **db_stats,
                    'in_memory_entries': memory_entries,
                    'in_cache': in_cache,
                    'total_accessible_entries': db_stats['total_entries'] + memory_entries
                }

            return {'total_entries': 0, 'total_size_bytes': 0, 'avg_access_count': 0,
                   'last_updated': None, 'in_memory_entries': 0, 'in_cache': False,
                   'total_accessible_entries': 0}

        except Exception as e:
            logger.error(f"Error getting conversation stats: {e}")
            return {'error': str(e)}

    async def compress_conversation(self, conversation_id: str):
        """Compress old entries for a conversation to save space."""
        try:
            if not self.repository:
                return

            # Get all entries for conversation
            entries = await self.repository.find_by_conversation(conversation_id, limit=1000)

            # Compress entries older than 7 days that haven't been accessed recently
            cutoff_date = datetime.utcnow() - timedelta(days=7)
            compressed_count = 0

            for entry in entries:
                should_compress = (
                    not entry.is_compressed and
                    entry.timestamp < cutoff_date and
                    entry.access_count < 5 and
                    entry.size_bytes > 50000  # > 50KB
                )

                if should_compress:
                    try:
                        # Compress the context data
                        compressed_data = gzip.compress(entry.context_data.encode('utf-8'))
                        entry.compressed_data = compressed_data
                        entry.context_data = ""  # Clear original data
                        entry.is_compressed = True

                        await self.repository.save(entry)
                        compressed_count += 1

                    except Exception as e:
                        logger.error(f"Error compressing entry {entry.id}: {e}")

            if compressed_count > 0:
                logger.info(f"Compressed {compressed_count} entries for conversation {conversation_id}")

        except Exception as e:
            logger.error(f"Error compressing conversation {conversation_id}: {e}")

    async def backup_conversations(self, conversation_ids: Optional[List[str]] = None):
        """Create backup of conversation data."""
        try:
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            backup_file = self.backup_path / f"context_backup_{timestamp}.json.gz"

            backup_data = {
                'timestamp': datetime.utcnow().isoformat(),
                'conversations': {}
            }

            # Determine which conversations to backup
            target_conversations = conversation_ids or list(self._memory.keys())

            for conv_id in target_conversations:
                # Get conversation data
                context = await self.get_context(conv_id)
                if context:
                    # Get database stats
                    stats = await self.get_conversation_stats(conv_id)

                    backup_data['conversations'][conv_id] = {
                        'context': context,
                        'stats': stats,
                        'backup_timestamp': datetime.utcnow().isoformat()
                    }

            # Write compressed backup
            with gzip.open(backup_file, 'wt', encoding='utf-8') as f:
                json.dump(backup_data, f, ensure_ascii=False, indent=2)

            self.last_backup = datetime.utcnow()
            logger.info(f"Created backup: {backup_file}")

            return str(backup_file)

        except Exception as e:
            logger.error(f"Error creating backup: {e}")
            raise

    async def restore_from_backup(self, backup_file: str):
        """Restore conversations from backup file."""
        try:
            with gzip.open(backup_file, 'rt', encoding='utf-8') as f:
                backup_data = json.load(f)

            restored_count = 0
            for conv_id, conv_data in backup_data.get('conversations', {}).items():
                context = conv_data.get('context', {})
                if context:
                    # Restore to memory
                    self._memory[conv_id] = context
                    self._update_cache(conv_id, context)

                    # Note: Database entries would need to be restored separately
                    # This is a memory-only restore for quick recovery

                    restored_count += 1

            logger.info(f"Restored {restored_count} conversations from backup")
            return restored_count

        except Exception as e:
            logger.error(f"Error restoring from backup: {e}")
            raise

    async def cleanup_old_conversations(self, days_old: int = 30):
        """Remove conversations that haven't been accessed for specified days."""
        try:
            if not self.repository:
                return

            cutoff_date = datetime.utcnow() - timedelta(days=days_old)

            # Find old conversations in database
            query = """
            SELECT DISTINCT conversation_id
            FROM context_entries
            WHERE last_accessed < ?
            AND access_count < 10
            """
            params = (cutoff_date.isoformat(),)

            result = await self.repository._execute_query_with_retry(query, params)
            old_conversation_ids = [row[0] for row in result]

            # Remove from database
            deleted_count = 0
            for conv_id in old_conversation_ids:
                query = "DELETE FROM context_entries WHERE conversation_id = ?"
                params = (conv_id,)

                await self.repository._execute_query_with_retry(query, params)

                # Remove from memory and cache if present
                if conv_id in self._memory:
                    del self._memory[conv_id]
                if conv_id in self._cache:
                    del self._cache[conv_id]

                deleted_count += 1

            if deleted_count > 0:
                logger.info(f"Cleaned up {deleted_count} old conversations")

            return deleted_count

        except Exception as e:
            logger.error(f"Error cleaning up old conversations: {e}")
            return 0

    def _update_cache(self, conversation_id: str, context_data: Dict[str, Any]):
        """Update cache with conversation data."""
        # Implement LRU-style cache
        if len(self._cache) >= self._cache_max_size:
            # Remove oldest entry (simple FIFO for now)
            oldest_key = next(iter(self._cache))
            del self._cache[oldest_key]

        self._cache[conversation_id] = context_data.copy()

    async def _check_and_compress_memory(self):
        """Check memory usage and compress if needed."""
        try:
            # Estimate memory usage
            memory_usage = sum(
                len(json.dumps(context).encode('utf-8'))
                for context in self._memory.values()
            ) / (1024 * 1024)  # MB

            if memory_usage > self.max_memory_size_mb:
                logger.info(f"Memory usage ({memory_usage:.1f}MB) exceeds limit, compressing...")

                # Compress conversations with most entries first
                conversations_by_size = sorted(
                    [(conv_id, len(context.get('history', [])))
                     for conv_id, context in self._memory.items()],
                    key=lambda x: x[1],
                    reverse=True
                )

                # Compress top 20% of conversations
                compress_count = max(1, len(conversations_by_size) // 5)
                for conv_id, _ in conversations_by_size[:compress_count]:
                    await self.compress_conversation(conv_id)

        except Exception as e:
            logger.error(f"Error checking memory usage: {e}")

    async def _load_recent_conversations(self):
        """Load recently accessed conversations into memory."""
        try:
            if not self.repository:
                return

            # Load conversations accessed in last 24 hours
            cutoff_date = datetime.utcnow() - timedelta(hours=24)

            query = """
            SELECT DISTINCT conversation_id
            FROM context_entries
            WHERE last_accessed > ?
            ORDER BY last_accessed DESC
            LIMIT 20
            """
            params = (cutoff_date.isoformat(),)

            result = await self.repository._execute_query_with_retry(query, params)
            recent_conv_ids = [row[0] for row in result]

            # Load these conversations
            for conv_id in recent_conv_ids:
                await self.get_context(conv_id)  # This will load from DB and cache

            logger.info(f"Loaded {len(recent_conv_ids)} recent conversations into memory")

        except Exception as e:
            logger.error(f"Error loading recent conversations: {e}")

    async def _start_background_tasks(self):
        """Start background maintenance tasks."""
        if self.backup_interval_hours > 0:
            self._backup_task = asyncio.create_task(self._backup_worker())

        self._maintenance_task = asyncio.create_task(self._maintenance_worker())

    async def _backup_worker(self):
        """Background backup worker."""
        while True:
            try:
                await asyncio.sleep(self.backup_interval_hours * 3600)  # Convert hours to seconds
                await self._perform_backup()

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Backup worker error: {e}")
                await asyncio.sleep(3600)  # Retry in 1 hour

    async def _maintenance_worker(self):
        """Background maintenance worker."""
        while True:
            try:
                await asyncio.sleep(3600)  # Run every hour

                # Perform maintenance tasks
                await self._check_and_compress_memory()

                # Cleanup old conversations (older than 90 days)
                await self.cleanup_old_conversations(days_old=90)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Maintenance worker error: {e}")
                await asyncio.sleep(600)  # Retry in 10 minutes

    async def _perform_backup(self):
        """Perform automatic backup."""
        try:
            # Backup important conversations (accessed recently and frequently)
            query = """
            SELECT conversation_id, COUNT(*) as access_count
            FROM context_entries
            WHERE last_accessed > ?
            GROUP BY conversation_id
            HAVING access_count > 5
            ORDER BY access_count DESC
            LIMIT 50
            """
            cutoff_date = (datetime.utcnow() - timedelta(days=7)).isoformat()
            params = (cutoff_date,)

            result = await self.repository._execute_query_with_retry(query, params)
            important_conv_ids = [row[0] for row in result]

            if important_conv_ids:
                backup_file = await self.backup_conversations(important_conv_ids)
                logger.info(f"Automatic backup created: {backup_file}")

        except Exception as e:
            logger.error(f"Error performing automatic backup: {e}")

    # ===== ENHANCED PERSISTENCE METHODS =====

    async def save_context_transactional(self, conversation_id: str, user_input: str,
                                       context_data: Dict[str, Any]) -> bool:
        """
        Save context with transaction safety and data integrity.

        Args:
            conversation_id: Conversation identifier
            user_input: User input text
            context_data: Context data to store

        Returns:
            Success status
        """
        if not self.transaction_manager:
            self.transaction_manager = await get_transaction_manager()

        try:
            async with self.transaction_manager.transaction(
                isolation_level=TransactionIsolation.READ_COMMITTED,
                timeout=10.0
            ) as tx_ctx:
                # Prepare data with integrity checks
                context_json = json.dumps(context_data, sort_keys=True)
                checksum = hashlib.sha256(context_json.encode('utf-8')).hexdigest()
                size_bytes = len(context_json.encode('utf-8'))

                # Validate data integrity if enabled
                if self._data_integrity_enabled:
                    await self._validate_data_integrity(context_data)

                # Compress if needed
                compressed_data = None
                is_compressed = False
                if self.enable_compression and size_bytes > self.compression_threshold_bytes:
                    compressed_data = gzip.compress(context_json.encode('utf-8'))
                    is_compressed = True

                # Create entry with integrity data
                entry = ContextEntry(
                    conversation_id=conversation_id,
                    user_input=user_input,
                    context_data=context_json if not is_compressed else "",
                    compressed_data=compressed_data,
                    is_compressed=is_compressed,
                    size_bytes=size_bytes,
                    checksum=checksum,
                    version=1
                )

                # Save with transaction
                await self.transaction_manager.execute_in_transaction(
                    tx_ctx, self._get_insert_query(), self._get_insert_params(entry)
                )

                # Update in-memory storage
                super().save_context(conversation_id, user_input, context_data)
                self._update_cache(conversation_id, context_data)

                logger.debug(f"Transactionally saved context for {conversation_id}")
                return True

        except Exception as e:
            logger.error(f"Error in transactional save: {e}")
            # Fallback to non-transactional save
            await self.save_context(conversation_id, user_input, context_data)
            return False

    async def get_context_with_integrity_check(self, conversation_id: str) -> Dict[str, Any]:
        """
        Retrieve context with data integrity verification.

        Args:
            conversation_id: Conversation identifier

        Returns:
            Context data with integrity status
        """
        try:
            context = await self.get_context(conversation_id)

            if not context or not self._data_integrity_enabled:
                return context

            # Verify integrity of loaded data
            integrity_status = await self._verify_conversation_integrity(conversation_id)

            if not integrity_status['is_valid']:
                logger.warning(f"Data integrity issues detected for {conversation_id}: {integrity_status['issues']}")
                # Attempt recovery
                await self._recover_corrupted_data(conversation_id)

            return {
                **context,
                '_integrity_status': integrity_status
            }

        except Exception as e:
            logger.error(f"Error in integrity-checked retrieval: {e}")
            return await self.get_context(conversation_id)

    async def create_incremental_backup(self, conversation_ids: Optional[List[str]] = None) -> str:
        """
        Create incremental backup with data integrity verification.

        Args:
            conversation_ids: Specific conversations to backup

        Returns:
            Backup file path
        """
        try:
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            backup_file = self.backup_path / f"incremental_backup_{timestamp}.json.gz"

            # Get last backup timestamp for incremental
            last_backup_time = self._get_last_backup_timestamp()

            backup_data = {
                'backup_type': 'incremental',
                'timestamp': datetime.utcnow().isoformat(),
                'since_timestamp': last_backup_time.isoformat() if last_backup_time else None,
                'conversations': {},
                'integrity_checksums': {}
            }

            # Determine conversations to backup
            target_conversations = conversation_ids or await self._get_modified_conversations_since(last_backup_time)

            for conv_id in target_conversations:
                context = await self.get_context(conv_id)
                if context:
                    stats = await self.get_conversation_stats(conv_id)

                    # Include integrity checksums
                    integrity = await self._calculate_conversation_checksum(conv_id)

                    backup_data['conversations'][conv_id] = {
                        'context': context,
                        'stats': stats,
                        'backup_timestamp': datetime.utcnow().isoformat()
                    }
                    backup_data['integrity_checksums'][conv_id] = integrity

            # Write compressed backup
            with gzip.open(backup_file, 'wt', encoding='utf-8') as f:
                json.dump(backup_data, f, ensure_ascii=False, indent=2)

            self.last_backup = datetime.utcnow()
            logger.info(f"Created incremental backup: {backup_file}")

            return str(backup_file)

        except Exception as e:
            logger.error(f"Error creating incremental backup: {e}")
            raise

    async def restore_with_integrity_check(self, backup_file: str, verify_integrity: bool = True) -> Dict[str, Any]:
        """
        Restore from backup with integrity verification.

        Args:
            backup_file: Backup file path
            verify_integrity: Whether to verify data integrity

        Returns:
            Restore results
        """
        try:
            with gzip.open(backup_file, 'rt', encoding='utf-8') as f:
                backup_data = json.load(f)

            restore_results = {
                'restored_conversations': 0,
                'skipped_corrupted': 0,
                'integrity_verified': 0,
                'errors': []
            }

            for conv_id, conv_data in backup_data.get('conversations', {}).items():
                try:
                    context = conv_data.get('context', {})

                    # Verify integrity if enabled
                    if verify_integrity and 'integrity_checksums' in backup_data:
                        expected_checksum = backup_data['integrity_checksums'].get(conv_id)
                        if expected_checksum:
                            actual_checksum = await self._calculate_conversation_checksum_from_data(context)
                            if actual_checksum != expected_checksum:
                                logger.warning(f"Integrity check failed for {conv_id}, skipping")
                                restore_results['skipped_corrupted'] += 1
                                continue
                            restore_results['integrity_verified'] += 1

                    # Restore to memory
                    self._memory[conv_id] = context
                    self._update_cache(conv_id, context)

                    restore_results['restored_conversations'] += 1

                except Exception as e:
                    logger.error(f"Error restoring conversation {conv_id}: {e}")
                    restore_results['errors'].append(f"{conv_id}: {str(e)}")

            logger.info(f"Restore completed: {restore_results}")
            return restore_results

        except Exception as e:
            logger.error(f"Error during integrity-checked restore: {e}")
            raise

    async def configurable_cleanup(self, policy: Optional[CleanupPolicy] = None) -> Dict[str, Any]:
        """
        Perform configurable cleanup based on policy.

        Args:
            policy: Cleanup policy to use

        Returns:
            Cleanup results
        """
        cleanup_policy = policy or self.cleanup_policy

        try:
            results = {
                'conversations_removed': 0,
                'entries_compressed': 0,
                'entries_deleted': 0,
                'space_saved_bytes': 0
            }

            if not self.repository:
                return results

            # Find conversations matching cleanup criteria
            cutoff_date = datetime.utcnow() - timedelta(days=cleanup_policy.max_age_days)

            query = """
            SELECT DISTINCT conversation_id,
                   COUNT(*) as entry_count,
                   AVG(access_count) as avg_access,
                   MAX(last_accessed) as last_access
            FROM context_entries
            GROUP BY conversation_id
            HAVING AVG(access_count) < ? OR MAX(last_accessed) < ?
            """
            params = (cleanup_policy.max_access_count, cutoff_date.isoformat())

            result = await self.repository._execute_query_with_retry(query, params)
            conversations_to_check = [row[0] for row in result]

            for conv_id in conversations_to_check:
                try:
                    # Get detailed stats
                    stats = await self.get_conversation_stats(conv_id)
                    entries = await self.repository.find_by_conversation(conv_id, limit=1000)

                    # Apply cleanup policy
                    cleanup_decision = await self._evaluate_cleanup_decision(entries, cleanup_policy)

                    if cleanup_decision['action'] == 'delete_conversation':
                        # Delete entire conversation
                        deleted_count = await self._delete_conversation(conv_id)
                        results['conversations_removed'] += 1
                        results['entries_deleted'] += deleted_count

                    elif cleanup_decision['action'] == 'compress_entries':
                        # Compress old entries
                        compressed = await self._compress_entries_by_policy(entries, cleanup_policy)
                        results['entries_compressed'] += compressed

                    results['space_saved_bytes'] += cleanup_decision.get('space_saved', 0)

                except Exception as e:
                    logger.error(f"Error cleaning conversation {conv_id}: {e}")

            logger.info(f"Configurable cleanup completed: {results}")
            return results

        except Exception as e:
            logger.error(f"Error in configurable cleanup: {e}")
            return {'error': str(e)}

    async def migrate_data_schema(self, target_version: int) -> Dict[str, Any]:
        """
        Migrate data to new schema version.

        Args:
            target_version: Target schema version

        Returns:
            Migration results
        """
        try:
            migration_results = {
                'entries_migrated': 0,
                'errors': [],
                'from_version': None,
                'to_version': target_version
            }

            if not self.repository:
                return migration_results

            # Get current schema version
            current_version = await self._get_current_schema_version()
            migration_results['from_version'] = current_version

            if current_version >= target_version:
                logger.info(f"Schema already at version {target_version}")
                return migration_results

            # Perform migrations step by step
            for version in range(current_version + 1, target_version + 1):
                try:
                    step_result = await self._perform_schema_migration_step(version)
                    migration_results['entries_migrated'] += step_result
                    logger.info(f"Migrated to schema version {version}")

                except Exception as e:
                    error_msg = f"Migration to version {version} failed: {e}"
                    logger.error(error_msg)
                    migration_results['errors'].append(error_msg)
                    break

            return migration_results

        except Exception as e:
            logger.error(f"Error in schema migration: {e}")
            return {'error': str(e)}

    async def monitor_memory_usage(self) -> Dict[str, Any]:
        """
        Monitor memory usage and trigger alerts if needed.

        Returns:
            Memory monitoring results
        """
        try:
            # Calculate current memory usage
            memory_stats = await self._calculate_memory_usage()

            # Check against thresholds
            alerts_triggered = []

            if memory_stats['total_mb'] > self.memory_alert.critical_threshold_mb:
                alerts_triggered.append('critical')
                logger.critical(f"Critical memory usage: {memory_stats['total_mb']:.1f}MB")
            elif memory_stats['total_mb'] > self.memory_alert.threshold_mb:
                alerts_triggered.append('warning')
                logger.warning(f"High memory usage: {memory_stats['total_mb']:.1f}MB")

            # Trigger alert callback if configured
            if alerts_triggered and self.memory_alert.alert_callback:
                alert_data = {
                    'alerts': alerts_triggered,
                    'memory_stats': memory_stats,
                    'timestamp': datetime.utcnow().isoformat()
                }
                try:
                    await self.memory_alert.alert_callback("memory_alert", alert_data)
                except Exception as e:
                    logger.error(f"Error in memory alert callback: {e}")

            # Auto-cleanup if critical
            if 'critical' in alerts_triggered:
                logger.info("Triggering emergency cleanup due to critical memory usage")
                await self.configurable_cleanup()

            return {
                'memory_stats': memory_stats,
                'alerts_triggered': alerts_triggered,
                'threshold_mb': self.memory_alert.threshold_mb,
                'critical_threshold_mb': self.memory_alert.critical_threshold_mb
            }

        except Exception as e:
            logger.error(f"Error monitoring memory usage: {e}")
            return {'error': str(e)}

    async def defragment_database(self) -> Dict[str, Any]:
        """
        Defragment database for optimal performance.

        Returns:
            Defragmentation results
        """
        try:
            if not self._defragmentation_enabled or not self.db_connection:
                return {'status': 'disabled'}

            results = {
                'tables_optimized': 0,
                'space_reclaimed_bytes': 0,
                'performance_improved': False
            }

            # SQLite VACUUM operation
            if self.db_connection.config.database_type == "sqlite":
                db_path = self.db_connection.config.database_path
                temp_db = f"{db_path}.tmp"

                try:
                    # Create optimized copy
                    await self.db_connection.execute_query("VACUUM INTO ?", (temp_db,))

                    # Replace original with optimized
                    shutil.move(temp_db, db_path)

                    results['tables_optimized'] = 1
                    results['performance_improved'] = True

                    logger.info("Database defragmentation completed")

                except Exception as e:
                    logger.error(f"Error during SQLite defragmentation: {e}")
                    if os.path.exists(temp_db):
                        os.remove(temp_db)

            # PostgreSQL CLUSTER operation (if supported)
            elif self.db_connection.config.database_type == "postgresql":
                try:
                    # Cluster tables for better performance
                    await self.db_connection.execute_query("CLUSTER context_entries")
                    results['tables_optimized'] = 1
                    results['performance_improved'] = True

                except Exception as e:
                    logger.error(f"Error during PostgreSQL clustering: {e}")

            return results

        except Exception as e:
            logger.error(f"Error in database defragmentation: {e}")
            return {'error': str(e)}

    # ===== HELPER METHODS =====

    async def _validate_data_integrity(self, data: Dict[str, Any]):
        """Validate data integrity before storage."""
        if not isinstance(data, dict):
            raise ValueError("Context data must be a dictionary")

        # Check for required fields
        if 'history' not in data and not data:
            raise ValueError("Context data must contain history or be non-empty")

        # Check data size limits
        data_size = len(json.dumps(data).encode('utf-8'))
        if data_size > 10 * 1024 * 1024:  # 10MB limit
            raise ValueError(f"Context data too large: {data_size} bytes")

    async def _verify_conversation_integrity(self, conversation_id: str) -> Dict[str, Any]:
        """Verify integrity of conversation data."""
        try:
            entries = await self.repository.find_by_conversation(conversation_id, limit=1000)

            integrity_status = {
                'is_valid': True,
                'issues': [],
                'entries_checked': len(entries),
                'corrupted_entries': 0
            }

            for entry in entries:
                if entry.checksum:
                    # Recalculate checksum
                    data_to_check = entry.context_data if not entry.is_compressed else entry.compressed_data
                    if entry.is_compressed and entry.compressed_data:
                        # Decompress for checksum verification
                        try:
                            data_to_check = gzip.decompress(entry.compressed_data).decode('utf-8')
                        except Exception:
                            integrity_status['issues'].append(f"Failed to decompress entry {entry.id}")
                            integrity_status['corrupted_entries'] += 1
                            continue

                    calculated_checksum = hashlib.sha256(data_to_check.encode('utf-8')).hexdigest()

                    if calculated_checksum != entry.checksum:
                        integrity_status['issues'].append(f"Checksum mismatch for entry {entry.id}")
                        integrity_status['corrupted_entries'] += 1

            integrity_status['is_valid'] = integrity_status['corrupted_entries'] == 0

            return integrity_status

        except Exception as e:
            logger.error(f"Error verifying conversation integrity: {e}")
            return {'is_valid': False, 'issues': [str(e)], 'entries_checked': 0, 'corrupted_entries': 0}

    async def _recover_corrupted_data(self, conversation_id: str):
        """Attempt to recover corrupted conversation data."""
        try:
            logger.info(f"Attempting data recovery for conversation {conversation_id}")

            # Try to restore from backup
            backup_files = sorted(self.backup_path.glob("*.json.gz"), reverse=True)
            for backup_file in backup_files[:5]:  # Check last 5 backups
                try:
                    restore_result = await self.restore_with_integrity_check(str(backup_file))
                    if restore_result.get('restored_conversations', 0) > 0:
                        logger.info(f"Successfully recovered {conversation_id} from backup")
                        return
                except Exception:
                    continue

            # If backup recovery fails, mark conversation for cleanup
            logger.warning(f"Could not recover {conversation_id}, marking for cleanup")

        except Exception as e:
            logger.error(f"Error during data recovery: {e}")

    def _get_insert_query(self) -> str:
        """Get INSERT query for context entries."""
        return """
        INSERT INTO context_entries
        (conversation_id, user_input, context_data, compressed_data, timestamp,
         access_count, last_accessed, is_compressed, size_bytes, checksum, version)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """

    def _get_insert_params(self, entry: ContextEntry) -> tuple:
        """Get INSERT parameters for context entry."""
        return (
            entry.conversation_id,
            entry.user_input,
            entry.context_data,
            entry.compressed_data,
            entry.timestamp.isoformat(),
            entry.access_count,
            entry.last_accessed.isoformat(),
            entry.is_compressed,
            entry.size_bytes,
            entry.checksum,
            entry.version
        )

    async def _get_modified_conversations_since(self, since_time: Optional[datetime]) -> List[str]:
        """Get conversations modified since timestamp."""
        if not since_time or not self.repository:
            return list(self._memory.keys())

        try:
            query = "SELECT DISTINCT conversation_id FROM context_entries WHERE timestamp > ?"
            params = (since_time.isoformat(),)

            result = await self.repository._execute_query_with_retry(query, params)
            return [row[0] for row in result]

        except Exception as e:
            logger.error(f"Error getting modified conversations: {e}")
            return list(self._memory.keys())

    def _get_last_backup_timestamp(self) -> Optional[datetime]:
        """Get timestamp of last backup."""
        try:
            backup_files = list(self.backup_path.glob("*.json.gz"))
            if not backup_files:
                return None

            # Extract timestamps from filenames
            timestamps = []
            for file_path in backup_files:
                filename = file_path.name
                # Extract timestamp from filename (format: backup_YYYYMMDD_HHMMSS.json.gz)
                if '_backup_' in filename or '_incremental_' in filename:
                    try:
                        timestamp_str = filename.split('_')[-2] + filename.split('_')[-1].split('.')[0]
                        timestamp = datetime.strptime(timestamp_str, "%Y%m%d%H%M%S")
                        timestamps.append(timestamp)
                    except (ValueError, IndexError):
                        continue

            return max(timestamps) if timestamps else None

        except Exception as e:
            logger.error(f"Error getting last backup timestamp: {e}")
            return None

    async def _calculate_conversation_checksum(self, conversation_id: str) -> Optional[str]:
        """Calculate checksum for entire conversation."""
        try:
            entries = await self.repository.find_by_conversation(conversation_id, limit=1000)
            if not entries:
                return None

            # Create deterministic representation
            entry_data = []
            for entry in sorted(entries, key=lambda e: e.timestamp):
                data = entry.context_data if not entry.is_compressed else entry.compressed_data
                entry_data.append(f"{entry.timestamp.isoformat()}:{data}")

            combined_data = "|".join(entry_data)
            return hashlib.sha256(combined_data.encode('utf-8')).hexdigest()

        except Exception as e:
            logger.error(f"Error calculating conversation checksum: {e}")
            return None

    async def _calculate_conversation_checksum_from_data(self, context_data: Dict[str, Any]) -> Optional[str]:
        """Calculate checksum from context data."""
        try:
            # Create deterministic JSON representation
            json_str = json.dumps(context_data, sort_keys=True)
            return hashlib.sha256(json_str.encode('utf-8')).hexdigest()
        except Exception as e:
            logger.error(f"Error calculating checksum from data: {e}")
            return None

    async def _evaluate_cleanup_decision(self, entries: List[ContextEntry],
                                       policy: CleanupPolicy) -> Dict[str, Any]:
        """Evaluate cleanup decision for conversation."""
        try:
            if not entries:
                return {'action': 'no_action'}

            # Calculate metrics
            avg_access = sum(e.access_count for e in entries) / len(entries)
            oldest_entry = min(entries, key=lambda e: e.timestamp)
            newest_entry = max(entries, key=lambda e: e.timestamp)

            age_days = (datetime.utcnow() - oldest_entry.timestamp).days
            total_size = sum(e.size_bytes for e in entries)

            # Decision logic
            if avg_access < policy.min_relevance_score and age_days > policy.max_age_days:
                return {
                    'action': 'delete_conversation',
                    'reason': 'low_relevance_and_old',
                    'space_saved': total_size
                }

            # Check for compression candidates
            compressible_entries = [
                e for e in entries
                if not e.is_compressed and
                (datetime.utcnow() - e.timestamp).days > policy.compression_age_days and
                e.access_count < policy.compression_access_threshold and
                e.size_bytes > policy.compression_size_kb * 1024
            ]

            if compressible_entries:
                return {
                    'action': 'compress_entries',
                    'entries_to_compress': len(compressible_entries),
                    'space_saved': sum(e.size_bytes * 0.7 for e in compressible_entries)  # Estimate 70% compression
                }

            return {'action': 'keep', 'reason': 'active_conversation'}

        except Exception as e:
            logger.error(f"Error evaluating cleanup decision: {e}")
            return {'action': 'keep', 'reason': 'error'}

    async def _delete_conversation(self, conversation_id: str) -> int:
        """Delete entire conversation from database."""
        try:
            if not self.repository:
                return 0

            query = "DELETE FROM context_entries WHERE conversation_id = ?"
            params = (conversation_id,)

            result = await self.repository._execute_query_with_retry(query, params)

            # Remove from memory and cache
            if conversation_id in self._memory:
                del self._memory[conversation_id]
            if conversation_id in self._cache:
                del self._cache[conversation_id]

            # Return number of deleted entries (approximate)
            return getattr(result, 'rowcount', 1)

        except Exception as e:
            logger.error(f"Error deleting conversation {conversation_id}: {e}")
            return 0

    async def _compress_entries_by_policy(self, entries: List[ContextEntry],
                                        policy: CleanupPolicy) -> int:
        """Compress entries according to policy."""
        try:
            compressed_count = 0

            for entry in entries:
                should_compress = (
                    not entry.is_compressed and
                    (datetime.utcnow() - entry.timestamp).days > policy.compression_age_days and
                    entry.access_count < policy.compression_access_threshold and
                    entry.size_bytes > policy.compression_size_kb * 1024
                )

                if should_compress:
                    try:
                        # Compress the data
                        compressed_data = gzip.compress(entry.context_data.encode('utf-8'))
                        entry.compressed_data = compressed_data
                        entry.context_data = ""
                        entry.is_compressed = True

                        await self.repository.save(entry)
                        compressed_count += 1

                    except Exception as e:
                        logger.error(f"Error compressing entry {entry.id}: {e}")

            return compressed_count

        except Exception as e:
            logger.error(f"Error in policy-based compression: {e}")
            return 0

    async def _get_current_schema_version(self) -> int:
        """Get current schema version."""
        try:
            # Check if version table exists and get version
            query = "SELECT version FROM schema_version ORDER BY id DESC LIMIT 1"
            result = await self.repository._execute_query_with_retry(query)

            if result:
                return result[0][0] if isinstance(result[0], (list, tuple)) else result[0]
            else:
                return 0  # Assume version 0 if no version table

        except Exception:
            # Version table doesn't exist, assume version 0
            return 0

    async def _perform_schema_migration_step(self, target_version: int) -> int:
        """Perform a single schema migration step."""
        try:
            migrated_count = 0

            if target_version == 1:
                # Migration to version 1: Add checksum and version columns
                if self.db_connection.config.database_type == "sqlite":
                    await self.db_connection.execute_query(
                        "ALTER TABLE context_entries ADD COLUMN checksum TEXT"
                    )
                    await self.db_connection.execute_query(
                        "ALTER TABLE context_entries ADD COLUMN version INTEGER DEFAULT 1"
                    )
                # Note: PostgreSQL ALTER TABLE would be handled differently

                # Populate checksums for existing entries
                entries = await self.repository.find_by_conversation("all", limit=10000)  # Get all
                for entry in entries:
                    if not entry.checksum:
                        data = entry.context_data if not entry.is_compressed else entry.compressed_data
                        if entry.is_compressed and entry.compressed_data:
                            try:
                                data = gzip.decompress(entry.compressed_data).decode('utf-8')
                            except Exception:
                                continue

                        entry.checksum = hashlib.sha256(data.encode('utf-8')).hexdigest()
                        entry.version = 1
                        await self.repository.save(entry)
                        migrated_count += 1

            # Add more migration steps as needed for future versions

            return migrated_count

        except Exception as e:
            logger.error(f"Error in migration step {target_version}: {e}")
            raise

    async def _calculate_memory_usage(self) -> Dict[str, Any]:
        """Calculate current memory usage statistics."""
        try:
            # In-memory usage
            memory_usage = sum(
                len(json.dumps(context).encode('utf-8'))
                for context in self._memory.values()
            ) / (1024 * 1024)  # MB

            # Cache usage
            cache_usage = sum(
                len(json.dumps(context).encode('utf-8'))
                for context in self._cache.values()
            ) / (1024 * 1024)  # MB

            # Database usage (approximate)
            db_usage = 0.0
            if self.repository:
                try:
                    query = "SELECT SUM(size_bytes) FROM context_entries"
                    result = await self.repository._execute_query_with_retry(query)
                    if result and result[0]:
                        db_usage = (result[0][0] or 0) / (1024 * 1024)  # MB
                except Exception:
                    pass

            return {
                'memory_mb': memory_usage,
                'cache_mb': cache_usage,
                'database_mb': db_usage,
                'total_mb': memory_usage + cache_usage + db_usage,
                'conversations_in_memory': len(self._memory),
                'conversations_in_cache': len(self._cache),
                'timestamp': datetime.utcnow().isoformat()
            }

        except Exception as e:
            logger.error(f"Error calculating memory usage: {e}")
            return {
                'memory_mb': 0.0,
                'cache_mb': 0.0,
                'database_mb': 0.0,
                'total_mb': 0.0,
                'error': str(e)
            }
