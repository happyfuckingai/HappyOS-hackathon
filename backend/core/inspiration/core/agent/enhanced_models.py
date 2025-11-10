"""
🎯 ENHANCED CONVERSATION STATE MODELS

Extended models for conversation state management with persistence features.
Includes compression, integrity checks, and advanced metadata tracking.
"""

import json
import hashlib
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Any, List, Optional
from enum import Enum

from .models import ConversationContext, ConversationState


class CompressionAlgorithm(Enum):
    """Compression algorithms for conversation states."""
    NONE = "none"
    GZIP = "gzip"
    LZMA = "lzma"
    ZSTD = "zstd"


@dataclass
class StatePersistenceMetadata:
    """Metadata for conversation state persistence."""
    created_at: datetime = field(default_factory=datetime.utcnow)
    last_modified: datetime = field(default_factory=datetime.utcnow)
    last_accessed: datetime = field(default_factory=datetime.utcnow)
    access_count: int = 0
    size_bytes: int = 0
    compressed_size_bytes: int = 0
    compression_algorithm: CompressionAlgorithm = CompressionAlgorithm.NONE
    compression_ratio: float = 1.0
    checksum: Optional[str] = None
    schema_version: int = 1
    backup_versions: List[str] = field(default_factory=list)
    integrity_verified: bool = False
    corruption_detected: bool = False
    recovery_attempts: int = 0


@dataclass
class StateAccessMetrics:
    """Access patterns and performance metrics for conversation states."""
    total_accesses: int = 0
    average_access_time: float = 0.0
    last_access_time: Optional[datetime] = None
    access_frequency_score: float = 0.0  # 0.0 to 1.0
    relevance_score: float = 1.0  # 0.0 to 1.0, updated by usage patterns
    memory_residency_score: float = 0.5  # How often state is in memory


@dataclass
class StateCompressionMetadata:
    """Metadata for compressed conversation states."""
    original_size: int = 0
    compressed_size: int = 0
    compression_time_ms: float = 0.0
    decompression_time_ms: float = 0.0
    compression_level: int = 6  # gzip/lzma compression level
    chunks_compressed: int = 0
    compression_efficiency: float = 1.0  # ratio of saved space


@dataclass
class EnhancedConversationContext(ConversationContext):
    """
    Enhanced conversation context with persistence and compression features.

    Extends the base ConversationContext with advanced persistence capabilities,
    integrity verification, compression support, and performance tracking.
    """

    # Persistence metadata
    persistence_metadata: StatePersistenceMetadata = field(default_factory=StatePersistenceMetadata)

    # Access and usage metrics
    access_metrics: StateAccessMetrics = field(default_factory=StateAccessMetrics)

    # Compression support
    compressed_state: Optional[bytes] = None
    compression_metadata: Optional[StateCompressionMetadata] = None

    # Integrity and recovery
    state_checksum: Optional[str] = None
    backup_checksums: Dict[str, str] = field(default_factory=dict)

    # Advanced features
    tags: List[str] = field(default_factory=list)
    custom_properties: Dict[str, Any] = field(default_factory=dict)
    related_conversations: List[str] = field(default_factory=list)

    # Performance optimization
    memory_cache_priority: int = 0  # 0=low, 1=normal, 2=high, 3=critical
    auto_cleanup_eligible: bool = True

    def __post_init__(self):
        """Initialize enhanced features after dataclass creation."""
        super().__post_init__()
        self._update_size_metrics()
        self._calculate_checksum()

    def _update_size_metrics(self):
        """Update size metrics based on current state."""
        state_data = self._serialize_for_size_calculation()
        self.persistence_metadata.size_bytes = len(state_data.encode('utf-8'))

        if self.compressed_state:
            self.persistence_metadata.compressed_size_bytes = len(self.compressed_state)
            self.persistence_metadata.compression_ratio = (
                self.persistence_metadata.size_bytes / self.persistence_metadata.compressed_size_bytes
                if self.persistence_metadata.compressed_size_bytes > 0 else 1.0
            )

    def _serialize_for_size_calculation(self) -> str:
        """Serialize state for size calculation."""
        return json.dumps({
            'conversation_id': self.conversation_id,
            'user_id': self.user_id,
            'state': self.state.value,
            'current_task': self.current_task,
            'history': self.history,
            'context_data': self.context_data,
            'created_at': self.created_at.isoformat(),
            'last_activity': self.last_activity.isoformat(),
            'pending_tasks': self.pending_tasks,
            'user_preferences': self.user_preferences,
            'skill_generation_history': self.skill_generation_history,
            'error_recovery_attempts': self.error_recovery_attempts,
            'personality_context': self.personality_context,
            'tags': self.tags,
            'custom_properties': self.custom_properties,
        }, sort_keys=True)

    def _calculate_checksum(self):
        """Calculate SHA256 checksum of the conversation state."""
        if not self.state_checksum:
            state_data = self._serialize_for_size_calculation()
            self.state_checksum = hashlib.sha256(state_data.encode('utf-8')).hexdigest()

    def update_access_metrics(self):
        """Update access metrics when state is accessed."""
        now = datetime.utcnow()

        self.access_metrics.total_accesses += 1
        self.access_metrics.last_access_time = now
        self.persistence_metadata.last_accessed = now
        self.persistence_metadata.access_count += 1

        # Update access frequency score (simple exponential moving average)
        if self.access_metrics.last_access_time:
            time_diff = (now - self.access_metrics.last_access_time).total_seconds()
            if time_diff > 0:
                # Higher score for more frequent access
                self.access_metrics.access_frequency_score = min(
                    1.0, self.access_metrics.access_frequency_score + (1.0 / max(time_diff / 3600, 1))
                )

    def mark_modified(self):
        """Mark the conversation state as modified."""
        self.persistence_metadata.last_modified = datetime.utcnow()
        self._calculate_checksum()
        self._update_size_metrics()

    def add_tag(self, tag: str):
        """Add a tag to the conversation state."""
        if tag not in self.tags:
            self.tags.append(tag)
            self.mark_modified()

    def remove_tag(self, tag: str):
        """Remove a tag from the conversation state."""
        if tag in self.tags:
            self.tags.remove(tag)
            self.mark_modified()

    def set_custom_property(self, key: str, value: Any):
        """Set a custom property."""
        self.custom_properties[key] = value
        self.mark_modified()

    def get_custom_property(self, key: str, default: Any = None) -> Any:
        """Get a custom property."""
        return self.custom_properties.get(key, default)

    def add_related_conversation(self, conversation_id: str):
        """Add a related conversation."""
        if conversation_id not in self.related_conversations:
            self.related_conversations.append(conversation_id)

    def is_compressed(self) -> bool:
        """Check if the state is currently compressed."""
        return self.compressed_state is not None

    def should_compress(self, threshold_bytes: int = 1024 * 1024) -> bool:
        """Determine if state should be compressed based on size."""
        return self.persistence_metadata.size_bytes > threshold_bytes

    def get_compression_info(self) -> Dict[str, Any]:
        """Get compression information."""
        return {
            'is_compressed': self.is_compressed(),
            'original_size': self.persistence_metadata.size_bytes,
            'compressed_size': self.persistence_metadata.compressed_size_bytes,
            'compression_ratio': self.persistence_metadata.compression_ratio,
            'algorithm': self.persistence_metadata.compression_algorithm.value,
        }

    def get_performance_info(self) -> Dict[str, Any]:
        """Get performance metrics."""
        return {
            'access_count': self.persistence_metadata.access_count,
            'access_frequency': self.access_metrics.access_frequency_score,
            'relevance_score': self.access_metrics.relevance_score,
            'memory_priority': self.memory_cache_priority,
            'last_access': self.persistence_metadata.last_accessed.isoformat() if self.persistence_metadata.last_accessed else None,
            'size_bytes': self.persistence_metadata.size_bytes,
        }


@dataclass
class ConversationStateBackup:
    """Backup information for conversation states."""
    conversation_id: str
    backup_id: str
    timestamp: datetime
    backup_data: bytes  # Compressed backup data
    checksum: str
    schema_version: int
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class StateMigrationRecord:
    """Record of a state migration operation."""
    conversation_id: str
    from_version: int
    to_version: int
    migration_timestamp: datetime
    success: bool
    error_message: Optional[str] = None
    checksum_before: Optional[str] = None
    checksum_after: Optional[str] = None
    migration_duration_ms: float = 0.0