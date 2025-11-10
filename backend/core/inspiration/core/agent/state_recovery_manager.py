"""
🎯 STATE RECOVERY MANAGER - Automatic Recovery for Conversation States

Advanced recovery system for handling corrupted or lost conversation states:
- Automatic detection of state corruption
- Backup-based recovery mechanisms
- Graceful degradation for partial failures
- Recovery analytics and reporting
- Self-healing capabilities
"""

import asyncio
import json
import logging
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timedelta
from pathlib import Path

from app.core.error_handling.health_monitor import HealthMonitor
from app.core.memory.context_memory import PersistentContextMemory

from .enhanced_models import (
    EnhancedConversationContext,
    ConversationStateBackup,
    StateMigrationRecord
)
from .conversation_state_repository import ConversationStateRepository

logger = logging.getLogger(__name__)


class RecoveryStrategy:
    """Defines recovery strategies for different failure scenarios."""

    def __init__(self, name: str, priority: int, description: str):
        self.name = name
        self.priority = priority
        self.description = description

    async def execute(self, context: EnhancedConversationContext,
                     recovery_manager: 'StateRecoveryManager') -> bool:
        """Execute the recovery strategy."""
        raise NotImplementedError("Subclasses must implement execute method")


class BackupRecoveryStrategy(RecoveryStrategy):
    """Recover from the latest available backup."""

    def __init__(self):
        super().__init__("backup_recovery", 1, "Recover from latest backup")

    async def execute(self, context: EnhancedConversationContext,
                     recovery_manager: 'StateRecoveryManager') -> bool:
        """Execute backup-based recovery."""
        try:
            backup = await recovery_manager._find_latest_backup(context.conversation_id)
            if backup:
                await recovery_manager._restore_from_backup(context, backup)
                context.persistence_metadata.recovery_attempts += 1
                logger.info(f"Successfully recovered {context.conversation_id} from backup")
                return True
            else:
                logger.warning(f"No backup found for conversation {context.conversation_id}")
                return False
        except Exception as e:
            logger.error(f"Backup recovery failed for {context.conversation_id}: {e}")
            return False


class FallbackRecoveryStrategy(RecoveryStrategy):
    """Create a minimal fallback state with essential information."""

    def __init__(self):
        super().__init__("fallback_state", 2, "Create minimal fallback state")

    async def execute(self, context: EnhancedConversationContext,
                     recovery_manager: 'StateRecoveryManager') -> bool:
        """Execute fallback state creation."""
        try:
            # Create minimal state preserving essential information
            minimal_context = {
                'conversation_id': context.conversation_id,
                'user_id': context.user_id,
                'state': 'idle',
                'error_recovery_attempts': context.error_recovery_attempts + 1,
                'recovery_timestamp': datetime.utcnow().isoformat(),
                'recovery_reason': 'corruption_detected'
            }

            # Update context with minimal state
            context.state = context.state.IDLE
            context.history = [{'type': 'recovery', 'timestamp': datetime.utcnow().isoformat(),
                              'message': 'State recovered from corruption'}]
            context.context_data = {'recovered': True, 'recovery_time': datetime.utcnow().isoformat()}
            context.error_recovery_attempts += 1

            logger.info(f"Created fallback state for conversation {context.conversation_id}")
            return True

        except Exception as e:
            logger.error(f"Fallback recovery failed for {context.conversation_id}: {e}")
            return False


class StateRecoveryManager:
    """
    Advanced recovery manager for conversation states.

    Features:
    - Automatic corruption detection
    - Multiple recovery strategies
    - Recovery analytics and reporting
    - Self-healing capabilities
    - Graceful degradation
    """

    def __init__(self, repository: ConversationStateRepository,
                 backup_directory: str = "data/backups/states",
                 max_recovery_attempts: int = 3):
        """
        Initialize the state recovery manager.

        Args:
            repository: Conversation state repository
            backup_directory: Directory for state backups
            max_recovery_attempts: Maximum recovery attempts per state
        """
        self.repository = repository
        self.backup_directory = Path(backup_directory)
        self.max_recovery_attempts = max_recovery_attempts

        self.health_monitor = HealthMonitor()

        # Recovery strategies in priority order
        self.recovery_strategies = [
            BackupRecoveryStrategy(),
            FallbackRecoveryStrategy()
        ]

        # Recovery metrics
        self.recovery_metrics = {
            'total_recovery_attempts': 0,
            'successful_recoveries': 0,
            'failed_recoveries': 0,
            'corruption_detected': 0,
            'backup_recoveries': 0,
            'fallback_recoveries': 0
        }

        # Ensure backup directory exists
        self.backup_directory.mkdir(parents=True, exist_ok=True)

        logger.info("Initialized StateRecoveryManager")

    async def detect_and_recover_corruption(self, context: EnhancedConversationContext) -> bool:
        """
        Detect corruption in conversation state and attempt recovery.

        Args:
            context: The conversation context to check

        Returns:
            True if recovery was successful or no corruption detected
        """
        try:
            self.recovery_metrics['total_recovery_attempts'] += 1

            # Check for corruption
            is_corrupt = await self._detect_corruption(context)
            if not is_corrupt:
                return True

            self.recovery_metrics['corruption_detected'] += 1
            logger.warning(f"Corruption detected in conversation {context.conversation_id}")

            # Check recovery limits
            if context.persistence_metadata.recovery_attempts >= self.max_recovery_attempts:
                logger.error(f"Maximum recovery attempts exceeded for {context.conversation_id}")
                await self._mark_unrecoverable(context)
                return False

            # Attempt recovery using strategies
            recovery_success = await self._attempt_recovery(context)

            if recovery_success:
                self.recovery_metrics['successful_recoveries'] += 1
                context.persistence_metadata.corruption_detected = False
                logger.info(f"Successfully recovered conversation {context.conversation_id}")
            else:
                self.recovery_metrics['failed_recoveries'] += 1
                logger.error(f"Failed to recover conversation {context.conversation_id}")
                await self._mark_unrecoverable(context)

            return recovery_success

        except Exception as e:
            logger.error(f"Error in corruption detection/recovery: {e}")
            return False

    async def _detect_corruption(self, context: EnhancedConversationContext) -> bool:
        """
        Detect various forms of corruption in conversation state.

        Args:
            context: The conversation context to check

        Returns:
            True if corruption is detected
        """
        try:
            corruption_indicators = []

            # Check 1: Checksum verification
            if context.state_checksum:
                if not await self.repository._verify_context_integrity(context):
                    corruption_indicators.append("checksum_mismatch")

            # Check 2: Data consistency
            if not self._validate_data_consistency(context):
                corruption_indicators.append("data_inconsistency")

            # Check 3: Size anomalies
            if self._detect_size_anomalies(context):
                corruption_indicators.append("size_anomaly")

            # Check 4: Timestamp anomalies
            if self._detect_timestamp_anomalies(context):
                corruption_indicators.append("timestamp_anomaly")

            # Check 5: Structural integrity
            if not self._validate_structural_integrity(context):
                corruption_indicators.append("structural_issue")

            if corruption_indicators:
                logger.warning(f"Corruption indicators for {context.conversation_id}: {corruption_indicators}")
                context.persistence_metadata.corruption_detected = True
                return True

            return False

        except Exception as e:
            logger.error(f"Error detecting corruption: {e}")
            return True  # Assume corruption if detection fails

    def _validate_data_consistency(self, context: EnhancedConversationContext) -> bool:
        """Validate data consistency within the context."""
        try:
            # Check required fields
            required_fields = ['conversation_id', 'user_id', 'state', 'history', 'context_data']
            for field in required_fields:
                if not hasattr(context, field):
                    return False

            # Validate conversation_id format
            if not isinstance(context.conversation_id, str) or len(context.conversation_id) < 10:
                return False

            # Validate state enum
            if not isinstance(context.state, type(context.state.IDLE)):
                return False

            # Validate timestamps
            if not isinstance(context.created_at, datetime):
                return False
            if not isinstance(context.last_activity, datetime):
                return False

            return True

        except Exception:
            return False

    def _detect_size_anomalies(self, context: EnhancedConversationContext) -> bool:
        """Detect anomalous size patterns that might indicate corruption."""
        try:
            # Check for unreasonably large sizes
            max_reasonable_size = 50 * 1024 * 1024  # 50MB
            if context.persistence_metadata.size_bytes > max_reasonable_size:
                return True

            # Check for zero or negative sizes
            if context.persistence_metadata.size_bytes <= 0:
                return True

            # Check compression ratio anomalies
            if context.persistence_metadata.compression_ratio > 100:
                return True

            return False

        except Exception:
            return True

    def _detect_timestamp_anomalies(self, context: EnhancedConversationContext) -> bool:
        """Detect timestamp anomalies."""
        try:
            now = datetime.utcnow()

            # Check if created_at is in the future
            if context.created_at > now:
                return True

            # Check if last_activity is before created_at
            if context.last_activity < context.created_at:
                return True

            # Check if timestamps are unreasonably old (more than 1 year ago)
            one_year_ago = now - timedelta(days=365)
            if context.created_at < one_year_ago:
                return True

            return False

        except Exception:
            return True

    def _validate_structural_integrity(self, context: EnhancedConversationContext) -> bool:
        """Validate the structural integrity of the context."""
        try:
            # Validate history structure
            if not isinstance(context.history, list):
                return False

            for item in context.history:
                if not isinstance(item, dict):
                    return False
                if 'type' not in item or 'timestamp' not in item:
                    return False

            # Validate context_data structure
            if not isinstance(context.context_data, dict):
                return False

            # Validate pending_tasks structure
            if not isinstance(context.pending_tasks, dict):
                return False

            return True

        except Exception:
            return False

    async def _attempt_recovery(self, context: EnhancedConversationContext) -> bool:
        """
        Attempt recovery using available strategies.

        Args:
            context: The corrupted context to recover

        Returns:
            True if recovery was successful
        """
        # Try recovery strategies in priority order
        for strategy in self.recovery_strategies:
            try:
                logger.info(f"Attempting recovery strategy '{strategy.name}' for {context.conversation_id}")
                success = await strategy.execute(context, self)

                if success:
                    # Update metrics based on strategy
                    if isinstance(strategy, BackupRecoveryStrategy):
                        self.recovery_metrics['backup_recoveries'] += 1
                    elif isinstance(strategy, FallbackRecoveryStrategy):
                        self.recovery_metrics['fallback_recoveries'] += 1

                    return True

            except Exception as e:
                logger.error(f"Recovery strategy '{strategy.name}' failed: {e}")
                continue

        return False

    async def _mark_unrecoverable(self, context: EnhancedConversationContext):
        """Mark a conversation state as unrecoverable."""
        try:
            context.persistence_metadata.corruption_detected = True
            context.state = context.state.ERROR_RECOVERY

            # Add recovery failure note to history
            context.history.append({
                'type': 'recovery_failure',
                'timestamp': datetime.utcnow().isoformat(),
                'message': 'Conversation state marked as unrecoverable',
                'attempts': context.persistence_metadata.recovery_attempts
            })

            # Save the unrecoverable state
            await self.repository.save_with_transaction(context)

            logger.warning(f"Marked conversation {context.conversation_id} as unrecoverable")

        except Exception as e:
            logger.error(f"Error marking conversation as unrecoverable: {e}")

    async def create_backup(self, context: EnhancedConversationContext) -> Optional[str]:
        """
        Create a backup of the conversation state.

        Args:
            context: The context to backup

        Returns:
            Backup file path if successful, None otherwise
        """
        try:
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            backup_id = f"{context.conversation_id}_{timestamp}"
            backup_file = self.backup_directory / f"{backup_id}.json.gz"

            # Serialize context for backup
            backup_data = {
                'conversation_id': context.conversation_id,
                'backup_id': backup_id,
                'timestamp': datetime.utcnow().isoformat(),
                'schema_version': context.persistence_metadata.schema_version,
                'context': self.repository._serialize_context_for_compression(context),
                'metadata': {
                    'size_bytes': context.persistence_metadata.size_bytes,
                    'checksum': context.state_checksum,
                    'compression_ratio': context.persistence_metadata.compression_ratio
                }
            }

            # Write compressed backup
            import gzip
            with gzip.open(backup_file, 'wt', encoding='utf-8') as f:
                json.dump(backup_data, f, ensure_ascii=False, indent=2)

            # Update context with backup reference
            context.persistence_metadata.backup_versions.append(backup_id)

            logger.info(f"Created backup for conversation {context.conversation_id}: {backup_file}")
            return str(backup_file)

        except Exception as e:
            logger.error(f"Error creating backup: {e}")
            return None

    async def _find_latest_backup(self, conversation_id: str) -> Optional[ConversationStateBackup]:
        """
        Find the latest backup for a conversation.

        Args:
            conversation_id: The conversation ID

        Returns:
            The latest backup or None
        """
        try:
            # Look for backup files
            backup_files = list(self.backup_directory.glob(f"{conversation_id}_*.json.gz"))
            if not backup_files:
                return None

            # Find the most recent backup
            latest_backup = max(backup_files, key=lambda f: f.stat().st_mtime)

            # Load backup data
            import gzip
            with gzip.open(latest_backup, 'rt', encoding='utf-8') as f:
                backup_data = json.load(f)

            # Create backup object
            backup = ConversationStateBackup(
                conversation_id=conversation_id,
                backup_id=backup_data['backup_id'],
                timestamp=datetime.fromisoformat(backup_data['timestamp']),
                backup_data=backup_data['context'].encode('utf-8'),  # Compressed context
                checksum=backup_data['metadata'].get('checksum'),
                schema_version=backup_data['schema_version']
            )

            return backup

        except Exception as e:
            logger.error(f"Error finding latest backup: {e}")
            return None

    async def _restore_from_backup(self, context: EnhancedConversationContext,
                                  backup: ConversationStateBackup):
        """
        Restore context from backup.

        Args:
            context: The context to restore into
            backup: The backup to restore from
        """
        try:
            # Parse backup data
            backup_context = json.loads(backup.backup_data.decode('utf-8'))

            # Restore context fields
            context.history = backup_context.get('history', [])
            context.context_data = backup_context.get('context_data', {})
            context.pending_tasks = backup_context.get('pending_tasks', {})
            context.user_preferences = backup_context.get('user_preferences', {})
            context.skill_generation_history = backup_context.get('skill_generation_history', [])
            context.personality_context = backup_context.get('personality_context', {})
            context.tags = backup_context.get('tags', [])
            context.custom_properties = backup_context.get('custom_properties', {})

            # Update metadata
            context.persistence_metadata.recovery_attempts += 1
            context.persistence_metadata.last_modified = datetime.utcnow()

            # Clear compressed state
            context.compressed_state = None

            logger.info(f"Restored context from backup for {context.conversation_id}")

        except Exception as e:
            logger.error(f"Error restoring from backup: {e}")
            raise

    async def cleanup_old_backups(self, days_old: int = 30) -> int:
        """
        Clean up old backup files.

        Args:
            days_old: Remove backups older than this many days

        Returns:
            Number of backups removed
        """
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=days_old)
            removed_count = 0

            for backup_file in self.backup_directory.glob("*.json.gz"):
                try:
                    # Check file modification time
                    if datetime.fromtimestamp(backup_file.stat().st_mtime) < cutoff_date:
                        backup_file.unlink()
                        removed_count += 1
                except Exception as e:
                    logger.error(f"Error removing old backup {backup_file}: {e}")

            if removed_count > 0:
                logger.info(f"Cleaned up {removed_count} old backups")

            return removed_count

        except Exception as e:
            logger.error(f"Error cleaning up old backups: {e}")
            return 0

    def get_recovery_metrics(self) -> Dict[str, Any]:
        """
        Get recovery metrics and statistics.

        Returns:
            Dictionary containing recovery metrics
        """
        try:
            success_rate = (
                self.recovery_metrics['successful_recoveries'] /
                max(self.recovery_metrics['total_recovery_attempts'], 1)
            ) * 100

            return {
                **self.recovery_metrics,
                'success_rate_percent': round(success_rate, 2),
                'corruption_rate_percent': (
                    self.recovery_metrics['corruption_detected'] /
                    max(self.recovery_metrics['total_recovery_attempts'], 1)
                ) * 100,
                'backup_recovery_rate_percent': (
                    self.recovery_metrics['backup_recoveries'] /
                    max(self.recovery_metrics['successful_recoveries'], 1)
                ) * 100
            }

        except Exception as e:
            logger.error(f"Error calculating recovery metrics: {e}")
            return {'error': str(e)}

    async def perform_health_check(self) -> Dict[str, Any]:
        """
        Perform a health check on the recovery system.

        Returns:
            Health check results
        """
        try:
            health_status = {
                'recovery_system': 'healthy',
                'backup_directory_exists': self.backup_directory.exists(),
                'backup_directory_writable': False,
                'total_backups': 0,
                'oldest_backup_days': None,
                'newest_backup_days': None,
                'issues': []
            }

            # Check backup directory
            if not health_status['backup_directory_exists']:
                health_status['issues'].append("Backup directory does not exist")
                health_status['recovery_system'] = 'degraded'

            # Check write permissions
            try:
                test_file = self.backup_directory / ".write_test"
                test_file.write_text("test")
                test_file.unlink()
                health_status['backup_directory_writable'] = True
            except Exception:
                health_status['issues'].append("Backup directory not writable")
                health_status['recovery_system'] = 'degraded'

            # Count backups
            backup_files = list(self.backup_directory.glob("*.json.gz"))
            health_status['total_backups'] = len(backup_files)

            # Check backup ages
            if backup_files:
                backup_times = [f.stat().st_mtime for f in backup_files]
                oldest_time = min(backup_times)
                newest_time = max(backup_times)
                now = datetime.utcnow().timestamp()

                health_status['oldest_backup_days'] = round((now - oldest_time) / (24 * 3600), 1)
                health_status['newest_backup_days'] = round((now - newest_time) / (24 * 3600), 1)

                # Check for very old backups
                if health_status['oldest_backup_days'] > 90:
                    health_status['issues'].append("Some backups are very old (>90 days)")

            # Overall health assessment
            if len(health_status['issues']) > 2:
                health_status['recovery_system'] = 'unhealthy'

            return health_status

        except Exception as e:
            logger.error(f"Error performing recovery health check: {e}")
            return {
                'recovery_system': 'error',
                'error': str(e)
            }