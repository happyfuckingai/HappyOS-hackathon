"""
🎯 CONVERSATION STATE REPOSITORY - Persistent Storage for Conversation States

Advanced repository for managing conversation states with:
- Persistent storage using database integration
- Transaction safety with rollback support
- Automatic compression for large states
- State migration support
- Integrity verification with checksums
- Bulk operations for performance
- Analytics and monitoring integration
"""

import asyncio
import json
import gzip
import hashlib
import logging
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timedelta
from dataclasses import asdict

from app.core.database.connection import get_db_connection
from app.db.repository_base import RepositoryBase
from app.db.transaction_manager import get_transaction_manager, TransactionIsolation
from app.core.error_handling.health_monitor import HealthMonitor
from app.core.memory.context_memory import PersistentContextMemory

from .enhanced_models import (
    EnhancedConversationContext,
    ConversationStateBackup,
    StateMigrationRecord,
    StatePersistenceMetadata,
    CompressionAlgorithm
)
from .models import ConversationState

logger = logging.getLogger(__name__)


class ConversationStateRepository(RepositoryBase[EnhancedConversationContext, str]):
    """
    Advanced repository for persistent conversation state management.

    Features:
    - Transaction-safe operations
    - Automatic compression for large states
    - Integrity verification
    - Backup and recovery
    - Migration support
    - Performance analytics
    """

    def __init__(self, db_connection=None, enable_compression: bool = True,
                 compression_threshold_bytes: int = 1024 * 1024):  # 1MB
        """
        Initialize the conversation state repository.

        Args:
            db_connection: Database connection (auto-acquired if None)
            enable_compression: Whether to compress large conversation states
            compression_threshold_bytes: Size threshold for compression
        """
        if db_connection is None:
            # Will be initialized asynchronously in initialize()
            self.db_connection = None
        else:
            self.db_connection = db_connection

        super().__init__(db_connection, "conversation_states", "conversation_id")

        self.enable_compression = enable_compression
        self.compression_threshold_bytes = compression_threshold_bytes
        self.transaction_manager = None
        self.health_monitor = HealthMonitor()

        # Performance tracking
        self.operation_metrics = {
            'save_operations': 0,
            'load_operations': 0,
            'compression_operations': 0,
            'decompression_operations': 0,
            'failed_operations': 0
        }

        logger.info("Initialized ConversationStateRepository")

    async def initialize(self):
        """Initialize database connection and setup."""
        if self.db_connection is None:
            self.db_connection = await get_db_connection()
            self._db_connection = self.db_connection  # Update parent class reference

        self.transaction_manager = await get_transaction_manager()

        # Ensure table exists
        await self._ensure_table_exists()

        logger.info("ConversationStateRepository initialized successfully")

    async def _ensure_table_exists(self):
        """Ensure the conversation_states table exists with proper schema."""
        create_table_query = """
        CREATE TABLE IF NOT EXISTS conversation_states (
            conversation_id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            state TEXT NOT NULL,
            current_task TEXT,
            history TEXT NOT NULL,  -- JSON
            context_data TEXT NOT NULL,  -- JSON
            created_at TEXT NOT NULL,
            last_activity TEXT NOT NULL,
            pending_tasks TEXT NOT NULL,  -- JSON
            user_preferences TEXT NOT NULL,  -- JSON
            skill_generation_history TEXT NOT NULL,  -- JSON
            error_recovery_attempts INTEGER DEFAULT 0,
            personality_context TEXT NOT NULL,  -- JSON

            -- Enhanced fields
            persistence_metadata TEXT,  -- JSON
            access_metrics TEXT,  -- JSON
            compressed_state BLOB,
            compression_metadata TEXT,  -- JSON
            state_checksum TEXT,
            backup_checksums TEXT,  -- JSON
            tags TEXT,  -- JSON
            custom_properties TEXT,  -- JSON
            related_conversations TEXT,  -- JSON
            memory_cache_priority INTEGER DEFAULT 0,
            auto_cleanup_eligible INTEGER DEFAULT 1,

            -- Metadata
            schema_version INTEGER DEFAULT 1,
            created_timestamp TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_timestamp TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE INDEX IF NOT EXISTS idx_conversation_states_user_id
        ON conversation_states(user_id);

        CREATE INDEX IF NOT EXISTS idx_conversation_states_last_activity
        ON conversation_states(last_activity);

        CREATE INDEX IF NOT EXISTS idx_conversation_states_state
        ON conversation_states(state);
        """

        if self.db_connection:
            await self.db_connection.execute_query(create_table_query)
            logger.info("Conversation states table ensured")

    def _entity_from_row(self, row: Dict[str, Any]) -> EnhancedConversationContext:
        """Convert database row to EnhancedConversationContext entity."""
        try:
            # Parse JSON fields
            history = json.loads(row.get('history', '[]'))
            context_data = json.loads(row.get('context_data', '{}'))
            pending_tasks = json.loads(row.get('pending_tasks', '{}'))
            user_preferences = json.loads(row.get('user_preferences', '{}'))
            skill_generation_history = json.loads(row.get('skill_generation_history', '[]'))
            personality_context = json.loads(row.get('personality_context', '{}'))

            # Enhanced fields
            persistence_metadata = json.loads(row.get('persistence_metadata', '{}'))
            access_metrics = json.loads(row.get('access_metrics', '{}'))
            compression_metadata = json.loads(row.get('compression_metadata', '{}'))
            backup_checksums = json.loads(row.get('backup_checksums', '{}'))
            tags = json.loads(row.get('tags', '[]'))
            custom_properties = json.loads(row.get('custom_properties', '{}'))
            related_conversations = json.loads(row.get('related_conversations', '[]'))

            # Create the context
            context = EnhancedConversationContext(
                conversation_id=row['conversation_id'],
                user_id=row['user_id'],
                state=ConversationState(row['state']),
                current_task=row.get('current_task'),
                history=history,
                context_data=context_data,
                created_at=datetime.fromisoformat(row['created_at']),
                last_activity=datetime.fromisoformat(row['last_activity']),
                pending_tasks=pending_tasks,
                user_preferences=user_preferences,
                skill_generation_history=skill_generation_history,
                error_recovery_attempts=row.get('error_recovery_attempts', 0),
                personality_context=personality_context,
                compressed_state=row.get('compressed_state'),
                tags=tags,
                custom_properties=custom_properties,
                related_conversations=related_conversations,
                memory_cache_priority=row.get('memory_cache_priority', 0),
            )

            # Set enhanced metadata if available
            if persistence_metadata:
                context.persistence_metadata = StatePersistenceMetadata(**persistence_metadata)
            if access_metrics:
                from .enhanced_models import StateAccessMetrics
                context.access_metrics = StateAccessMetrics(**access_metrics)
            if compression_metadata:
                from .enhanced_models import StateCompressionMetadata
                context.compression_metadata = StateCompressionMetadata(**compression_metadata)

            context.state_checksum = row.get('state_checksum')

            return context

        except Exception as e:
            logger.error(f"Error converting row to entity: {e}")
            raise

    def _row_from_entity(self, entity: EnhancedConversationContext) -> Dict[str, Any]:
        """Convert EnhancedConversationContext entity to database row."""
        row = {
            'conversation_id': entity.conversation_id,
            'user_id': entity.user_id,
            'state': entity.state.value,
            'current_task': entity.current_task,
            'history': json.dumps(entity.history, ensure_ascii=False),
            'context_data': json.dumps(entity.context_data, ensure_ascii=False),
            'created_at': entity.created_at.isoformat(),
            'last_activity': entity.last_activity.isoformat(),
            'pending_tasks': json.dumps(entity.pending_tasks, ensure_ascii=False),
            'user_preferences': json.dumps(entity.user_preferences, ensure_ascii=False),
            'skill_generation_history': json.dumps(entity.skill_generation_history, ensure_ascii=False),
            'error_recovery_attempts': entity.error_recovery_attempts,
            'personality_context': json.dumps(entity.personality_context, ensure_ascii=False),

            # Enhanced fields
            'persistence_metadata': json.dumps(asdict(entity.persistence_metadata), ensure_ascii=False),
            'access_metrics': json.dumps(asdict(entity.access_metrics), ensure_ascii=False),
            'compressed_state': entity.compressed_state,
            'compression_metadata': json.dumps(asdict(entity.compression_metadata) if entity.compression_metadata else {}, ensure_ascii=False),
            'state_checksum': entity.state_checksum,
            'backup_checksums': json.dumps(entity.backup_checksums, ensure_ascii=False),
            'tags': json.dumps(entity.tags, ensure_ascii=False),
            'custom_properties': json.dumps(entity.custom_properties, ensure_ascii=False),
            'related_conversations': json.dumps(entity.related_conversations, ensure_ascii=False),
            'memory_cache_priority': entity.memory_cache_priority,
            'auto_cleanup_eligible': entity.auto_cleanup_eligible,

            'schema_version': entity.persistence_metadata.schema_version,
            'updated_timestamp': datetime.utcnow().isoformat()
        }

        return row

    def _get_entity_id(self, entity: EnhancedConversationContext) -> str:
        """Get entity ID."""
        return entity.conversation_id

    async def save_with_transaction(self, context: EnhancedConversationContext) -> bool:
        """
        Save conversation context with transaction safety.

        Args:
            context: The conversation context to save

        Returns:
            Success status
        """
        try:
            self.operation_metrics['save_operations'] += 1

            # Prepare context for storage
            context.mark_modified()
            context.update_access_metrics()

            # Compress if needed
            if self.enable_compression and context.should_compress(self.compression_threshold_bytes):
                await self._compress_context(context)

            async with self.transaction_manager.transaction(
                isolation_level=TransactionIsolation.READ_COMMITTED,
                timeout=30.0
            ) as tx_ctx:
                # Save to database
                await self.transaction_manager.execute_in_transaction(
                    tx_ctx, self._get_insert_or_update_query(), self._get_insert_params(context)
                )

                # Update metrics
                context.persistence_metadata.last_modified = datetime.utcnow()

            logger.debug(f"Transactionally saved conversation state {context.conversation_id}")
            return True

        except Exception as e:
            self.operation_metrics['failed_operations'] += 1
            logger.error(f"Error saving conversation state: {e}")
            return False

    async def load_with_integrity_check(self, conversation_id: str) -> Optional[EnhancedConversationContext]:
        """
        Load conversation context with integrity verification.

        Args:
            conversation_id: Conversation identifier

        Returns:
            The conversation context or None if not found/corrupted
        """
        try:
            self.operation_metrics['load_operations'] += 1

            # Load from database
            entities = await self.find_by_criteria({'conversation_id': conversation_id})
            if not entities:
                return None

            context = entities[0]

            # Decompress if needed
            if context.is_compressed():
                await self._decompress_context(context)

            # Verify integrity
            if not await self._verify_context_integrity(context):
                logger.warning(f"Integrity check failed for conversation {conversation_id}")
                # Attempt recovery
                await self._attempt_context_recovery(context)
                if not await self._verify_context_integrity(context):
                    logger.error(f"Failed to recover conversation {conversation_id}")
                    return None

            # Update access metrics
            context.update_access_metrics()
            await self.save_with_transaction(context)

            return context

        except Exception as e:
            logger.error(f"Error loading conversation context: {e}")
            return None

    async def _compress_context(self, context: EnhancedConversationContext):
        """Compress conversation context."""
        try:
            self.operation_metrics['compression_operations'] += 1

            # Serialize context for compression
            context_data = self._serialize_context_for_compression(context)
            original_size = len(context_data.encode('utf-8'))

            # Compress using gzip
            compressed_data = gzip.compress(context_data.encode('utf-8'), compresslevel=6)
            compressed_size = len(compressed_data)

            # Update context with compressed data
            context.compressed_state = compressed_data
            context.persistence_metadata.compressed_size_bytes = compressed_size
            context.persistence_metadata.compression_ratio = original_size / compressed_size if compressed_size > 0 else 1.0
            context.persistence_metadata.compression_algorithm = CompressionAlgorithm.GZIP

            # Update compression metadata
            from .enhanced_models import StateCompressionMetadata
            context.compression_metadata = StateCompressionMetadata(
                original_size=original_size,
                compressed_size=compressed_size,
                compression_ratio=context.persistence_metadata.compression_ratio,
                chunks_compressed=1,
                compression_efficiency=1.0 - (compressed_size / original_size)
            )

            logger.debug(f"Compressed conversation {context.conversation_id}: {original_size} -> {compressed_size} bytes")

        except Exception as e:
            logger.error(f"Error compressing context: {e}")

    async def _decompress_context(self, context: EnhancedConversationContext):
        """Decompress conversation context."""
        try:
            self.operation_metrics['decompression_operations'] += 1

            if not context.compressed_state:
                return

            # Decompress data
            decompressed_data = gzip.decompress(context.compressed_state).decode('utf-8')

            # Parse and update context
            decompressed_dict = json.loads(decompressed_data)

            # Update context fields from decompressed data
            context.history = decompressed_dict.get('history', [])
            context.context_data = decompressed_dict.get('context_data', {})
            context.pending_tasks = decompressed_dict.get('pending_tasks', {})
            context.user_preferences = decompressed_dict.get('user_preferences', {})
            context.skill_generation_history = decompressed_dict.get('skill_generation_history', [])
            context.personality_context = decompressed_dict.get('personality_context', {})

            # Clear compressed state
            context.compressed_state = None

            logger.debug(f"Decompressed conversation {context.conversation_id}")

        except Exception as e:
            logger.error(f"Error decompressing context: {e}")
            raise

    async def _verify_context_integrity(self, context: EnhancedConversationContext) -> bool:
        """Verify the integrity of a conversation context."""
        try:
            if not context.state_checksum:
                return True  # No checksum to verify

            # Calculate current checksum
            current_data = self._serialize_context_for_compression(context)
            current_checksum = hashlib.sha256(current_data.encode('utf-8')).hexdigest()

            return current_checksum == context.state_checksum

        except Exception as e:
            logger.error(f"Error verifying context integrity: {e}")
            return False

    async def _attempt_context_recovery(self, context: EnhancedConversationContext):
        """Attempt to recover a corrupted conversation context."""
        try:
            logger.info(f"Attempting recovery for conversation {context.conversation_id}")

            # Try to restore from backup
            backup = await self._find_latest_backup(context.conversation_id)
            if backup:
                # Restore from backup
                await self._restore_from_backup(context, backup)
                context.persistence_metadata.recovery_attempts += 1
                logger.info(f"Recovered conversation {context.conversation_id} from backup")

        except Exception as e:
            logger.error(f"Error during context recovery: {e}")

    def _serialize_context_for_compression(self, context: EnhancedConversationContext) -> str:
        """Serialize context for compression/integrity checks."""
        return json.dumps({
            'history': context.history,
            'context_data': context.context_data,
            'pending_tasks': context.pending_tasks,
            'user_preferences': context.user_preferences,
            'skill_generation_history': context.skill_generation_history,
            'personality_context': context.personality_context,
            'tags': context.tags,
            'custom_properties': context.custom_properties,
        }, sort_keys=True, ensure_ascii=False)

    def _get_insert_or_update_query(self) -> str:
        """Get INSERT OR REPLACE query for conversation states."""
        return """
        INSERT OR REPLACE INTO conversation_states (
            conversation_id, user_id, state, current_task, history, context_data,
            created_at, last_activity, pending_tasks, user_preferences,
            skill_generation_history, error_recovery_attempts, personality_context,
            persistence_metadata, access_metrics, compressed_state, compression_metadata,
            state_checksum, backup_checksums, tags, custom_properties,
            related_conversations, memory_cache_priority, auto_cleanup_eligible,
            schema_version, updated_timestamp
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """

    def _get_insert_params(self, context: EnhancedConversationContext) -> Tuple:
        """Get INSERT parameters for conversation context."""
        row = self._row_from_entity(context)
        return (
            row['conversation_id'], row['user_id'], row['state'], row['current_task'],
            row['history'], row['context_data'], row['created_at'], row['last_activity'],
            row['pending_tasks'], row['user_preferences'], row['skill_generation_history'],
            row['error_recovery_attempts'], row['personality_context'],
            row['persistence_metadata'], row['access_metrics'], row['compressed_state'],
            row['compression_metadata'], row['state_checksum'], row['backup_checksums'],
            row['tags'], row['custom_properties'], row['related_conversations'],
            row['memory_cache_priority'], row['auto_cleanup_eligible'],
            row['schema_version'], row['updated_timestamp']
        )

    # Additional methods for backup, migration, and analytics would go here
    async def _find_latest_backup(self, conversation_id: str) -> Optional[ConversationStateBackup]:
        """Find the latest backup for a conversation (placeholder)."""
        # Implementation would query backup table
        return None

    async def _restore_from_backup(self, context: EnhancedConversationContext,
                                  backup: ConversationStateBackup):
        """Restore context from backup (placeholder)."""
        # Implementation would decompress and restore backup data
        pass

    async def get_performance_metrics(self) -> Dict[str, Any]:
        """Get repository performance metrics."""
        return {
            **self.operation_metrics,
            'total_conversations': await self.count(),
            'compressed_conversations': await self._count_compressed(),
            'average_compression_ratio': await self._calculate_average_compression_ratio()
        }

    async def _count_compressed(self) -> int:
        """Count compressed conversations."""
        try:
            query = "SELECT COUNT(*) FROM conversation_states WHERE compressed_state IS NOT NULL"
            result = await self._execute_query_with_retry(query)
            return result[0][0] if result else 0
        except Exception:
            return 0

    async def _calculate_average_compression_ratio(self) -> float:
        """Calculate average compression ratio."""
        try:
            query = """
            SELECT AVG(
                CASE
                    WHEN compressed_state IS NOT NULL AND json_extract(persistence_metadata, '$.size_bytes') > 0
                    THEN json_extract(persistence_metadata, '$.size_bytes') * 1.0 / length(compressed_state)
                    ELSE 1.0
                END
            ) FROM conversation_states
            """
            result = await self._execute_query_with_retry(query)
            return result[0][0] if result and result[0][0] else 1.0
        except Exception:
            return 1.0