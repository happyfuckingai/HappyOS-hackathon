"""
Intelligent Memory Management System.

Integrates summarizer for automatic relevance assessment and smart memory management.
"""

import asyncio
import logging
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from collections import defaultdict, deque
import json

from app.core.ai.summarizer import Summarizer
from app.core.memory.context_memory import ContextMemory

logger = logging.getLogger(__name__)


@dataclass
class MemoryEntry:
    """Represents a memory entry with metadata."""
    conversation_id: str
    content: Dict[str, Any]
    timestamp: datetime = field(default_factory=datetime.utcnow)
    relevance_score: float = 0.0
    access_count: int = 0
    last_accessed: datetime = field(default_factory=datetime.utcnow)
    summary: Optional[str] = None
    mindmap: Optional[Dict[str, Any]] = None
    compressed: bool = False
    retention_policy: str = "default"  # "default", "important", "temporary"


@dataclass
class MemoryStats:
    """Memory usage statistics."""
    total_entries: int = 0
    compressed_entries: int = 0
    important_entries: int = 0
    average_relevance: float = 0.0
    memory_usage_mb: float = 0.0
    cleanup_operations: int = 0
    last_cleanup: Optional[datetime] = None


class IntelligentMemoryManager:
    """
    Intelligent memory manager that integrates summarizer for smart memory management.

    Features:
    - Automatic relevance assessment using summarizer
    - Smart cleanup based on conversation flow
    - Prioritization of important content
    - Adaptive memory retention policies
    - Memory compression for large conversations
    """

    def __init__(self, max_memory_entries: int = 1000, cleanup_threshold: float = 0.8):
        """
        Initialize the intelligent memory manager.

        Args:
            max_memory_entries: Maximum number of memory entries to keep
            cleanup_threshold: Threshold for triggering cleanup (0.0-1.0)
        """
        self.max_memory_entries = max_memory_entries
        self.cleanup_threshold = cleanup_threshold

        # Core components
        self.summarizer = Summarizer()
        self.context_memory = ContextMemory()

        # Memory storage
        self._memory: Dict[str, MemoryEntry] = {}
        self._conversation_index: Dict[str, List[str]] = defaultdict(list)  # conversation_id -> entry_ids
        self._recent_access: deque = deque(maxlen=100)  # LRU tracking

        # Statistics
        self.stats = MemoryStats()

        # Background tasks
        self._cleanup_task: Optional[asyncio.Task] = None
        self._maintenance_task: Optional[asyncio.Task] = None

        # Configuration
        self.relevance_thresholds = {
            'important': 0.8,
            'normal': 0.5,
            'temporary': 0.2
        }

        self.retention_policies = {
            'important': timedelta(days=30),
            'normal': timedelta(days=7),
            'temporary': timedelta(hours=1)
        }

        logger.info(f"IntelligentMemoryManager initialized with max_entries={max_memory_entries}")

    async def initialize(self):
        """Initialize the memory manager and start background tasks."""
        # Start background maintenance
        self._cleanup_task = asyncio.create_task(self._cleanup_worker())
        self._maintenance_task = asyncio.create_task(self._maintenance_worker())

        logger.info("IntelligentMemoryManager background tasks started")

    async def shutdown(self):
        """Shutdown the memory manager and cleanup resources."""
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass

        if self._maintenance_task:
            self._maintenance_task.cancel()
            try:
                await self._maintenance_task
            except asyncio.CancelledError:
                pass

        logger.info("IntelligentMemoryManager shutdown complete")

    async def store_memory(self, conversation_id: str, content: Dict[str, Any],
                          context: Optional[Dict[str, Any]] = None) -> str:
        """
        Store memory entry with intelligent processing.

        Args:
            conversation_id: Conversation identifier
            content: Memory content to store
            context: Optional conversation context for summarization

        Returns:
            Memory entry ID
        """
        try:
            # Generate unique entry ID
            entry_id = f"{conversation_id}_{int(datetime.utcnow().timestamp() * 1000)}"

            # Create memory entry
            entry = MemoryEntry(
                conversation_id=conversation_id,
                content=content.copy(),
                timestamp=datetime.utcnow()
            )

            # Assess relevance using summarizer if context provided
            if context:
                relevance_score = await self._assess_relevance(content, context)
                entry.relevance_score = relevance_score

                # Determine retention policy
                entry.retention_policy = self._determine_retention_policy(relevance_score)

                # Generate summary for important content
                if relevance_score >= self.relevance_thresholds['important']:
                    entry.summary = await self.summarizer.summarize(
                        json.dumps(content),
                        context
                    )

                    # Generate mindmap for highly relevant content
                    if relevance_score >= 0.9:
                        entry.mindmap = await self.summarizer.generate_mindmap(context)

            # Store entry
            self._memory[entry_id] = entry
            self._conversation_index[conversation_id].append(entry_id)
            self._recent_access.append(entry_id)

            # Update statistics
            self._update_stats()

            # Check if cleanup needed
            if self._should_cleanup():
                asyncio.create_task(self._perform_cleanup())

            # Also store in basic context memory for compatibility
            self.context_memory.save_context(conversation_id, json.dumps(content), content)

            logger.debug(f"Stored memory entry {entry_id} for conversation {conversation_id}")
            return entry_id

        except Exception as e:
            logger.error(f"Error storing memory: {e}")
            raise

    async def retrieve_memory(self, conversation_id: str, query: Optional[str] = None,
                            limit: int = 10) -> List[Dict[str, Any]]:
        """
        Retrieve memory entries with intelligent filtering.

        Args:
            conversation_id: Conversation identifier
            query: Optional search query
            limit: Maximum number of entries to return

        Returns:
            List of memory entries
        """
        try:
            entry_ids = self._conversation_index.get(conversation_id, [])

            if not entry_ids:
                return []

            # Get entries and sort by relevance and recency
            entries = []
            for entry_id in entry_ids:
                if entry_id in self._memory:
                    entry = self._memory[entry_id]
                    entries.append((entry_id, entry))

            # Sort by relevance score and last accessed time
            entries.sort(key=lambda x: (x[1].relevance_score, x[1].last_accessed), reverse=True)

            # Filter by query if provided
            if query:
                filtered_entries = []
                query_lower = query.lower()
                for entry_id, entry in entries:
                    content_str = json.dumps(entry.content).lower()
                    if query_lower in content_str or (entry.summary and query_lower in entry.summary.lower()):
                        filtered_entries.append((entry_id, entry))
                entries = filtered_entries

            # Update access times
            result = []
            for entry_id, entry in entries[:limit]:
                entry.access_count += 1
                entry.last_accessed = datetime.utcnow()
                self._recent_access.append(entry_id)

                # Return compressed or full content based on access pattern
                if entry.compressed and entry.access_count < 3:
                    result.append({
                        'id': entry_id,
                        'summary': entry.summary,
                        'compressed': True,
                        'timestamp': entry.timestamp.isoformat()
                    })
                else:
                    result.append({
                        'id': entry_id,
                        'content': entry.content,
                        'summary': entry.summary,
                        'mindmap': entry.mindmap,
                        'relevance_score': entry.relevance_score,
                        'compressed': entry.compressed,
                        'timestamp': entry.timestamp.isoformat()
                    })

            return result

        except Exception as e:
            logger.error(f"Error retrieving memory: {e}")
            return []

    async def update_memory_relevance(self, entry_id: str, new_context: Dict[str, Any]):
        """
        Update relevance score for a memory entry based on new context.

        Args:
            entry_id: Memory entry ID
            new_context: New conversation context
        """
        try:
            if entry_id not in self._memory:
                return

            entry = self._memory[entry_id]

            # Re-assess relevance with new context
            new_score = await self._assess_relevance(entry.content, new_context)
            entry.relevance_score = max(entry.relevance_score, new_score)  # Keep higher score

            # Update retention policy if needed
            new_policy = self._determine_retention_policy(entry.relevance_score)
            if new_policy != entry.retention_policy:
                entry.retention_policy = new_policy
                logger.debug(f"Updated retention policy for {entry_id} to {new_policy}")

            # Update summary if relevance increased significantly
            if new_score > entry.relevance_score + 0.2:
                entry.summary = await self.summarizer.summarize(
                    json.dumps(entry.content),
                    new_context
                )

        except Exception as e:
            logger.error(f"Error updating memory relevance: {e}")

    async def compress_memory(self, conversation_id: str):
        """
        Compress old or low-relevance memory entries for a conversation.

        Args:
            conversation_id: Conversation identifier
        """
        try:
            entry_ids = self._conversation_index.get(conversation_id, [])
            compressed_count = 0

            for entry_id in entry_ids:
                if entry_id in self._memory:
                    entry = self._memory[entry_id]

                    # Compress if old or low relevance and not already compressed
                    should_compress = (
                        not entry.compressed and
                        (entry.relevance_score < self.relevance_thresholds['normal'] or
                         entry.timestamp < datetime.utcnow() - timedelta(days=1))
                    )

                    if should_compress:
                        # Keep only summary, remove full content
                        if entry.summary:
                            entry.content = {'compressed_summary': entry.summary}
                            entry.compressed = True
                            compressed_count += 1

            if compressed_count > 0:
                logger.info(f"Compressed {compressed_count} memory entries for conversation {conversation_id}")

        except Exception as e:
            logger.error(f"Error compressing memory: {e}")

    def get_memory_stats(self) -> Dict[str, Any]:
        """Get comprehensive memory statistics."""
        return {
            'total_entries': len(self._memory),
            'conversations': len(self._conversation_index),
            'compressed_entries': sum(1 for e in self._memory.values() if e.compressed),
            'important_entries': sum(1 for e in self._memory.values()
                                   if e.relevance_score >= self.relevance_thresholds['important']),
            'average_relevance': sum(e.relevance_score for e in self._memory.values()) / max(len(self._memory), 1),
            'cleanup_operations': self.stats.cleanup_operations,
            'last_cleanup': self.stats.last_cleanup.isoformat() if self.stats.last_cleanup else None,
            'timestamp': datetime.utcnow().isoformat()
        }

    async def _assess_relevance(self, content: Dict[str, Any], context: Dict[str, Any]) -> float:
        """
        Assess relevance of content using summarizer insights.

        Args:
            content: Content to assess
            context: Conversation context

        Returns:
            Relevance score between 0.0 and 1.0
        """
        try:
            # Use summarizer to generate context analysis
            content_str = json.dumps(content)
            summary = await self.summarizer.summarize(content_str, context)

            if not summary:
                return 0.5  # Default medium relevance

            # Simple relevance scoring based on summary characteristics
            score = 0.5  # Base score

            # Increase score based on summary length (longer = more relevant)
            summary_length = len(summary)
            if summary_length > 200:
                score += 0.2
            elif summary_length < 50:
                score -= 0.1

            # Check for action items or important keywords
            important_keywords = ['important', 'critical', 'urgent', 'decision', 'action']
            if any(keyword in summary.lower() for keyword in important_keywords):
                score += 0.2

            # Check for user questions or requests
            if 'user' in content_str.lower() and ('?' in content_str or 'please' in content_str.lower()):
                score += 0.1

            return min(max(score, 0.0), 1.0)

        except Exception as e:
            logger.error(f"Error assessing relevance: {e}")
            return 0.5

    def _determine_retention_policy(self, relevance_score: float) -> str:
        """Determine retention policy based on relevance score."""
        if relevance_score >= self.relevance_thresholds['important']:
            return 'important'
        elif relevance_score >= self.relevance_thresholds['normal']:
            return 'normal'
        else:
            return 'temporary'

    def _should_cleanup(self) -> bool:
        """Check if cleanup should be performed."""
        current_ratio = len(self._memory) / max(self.max_memory_entries, 1)
        return current_ratio >= self.cleanup_threshold

    async def _perform_cleanup(self):
        """Perform intelligent cleanup of memory entries."""
        try:
            logger.info("Starting intelligent memory cleanup")

            # Sort entries by cleanup priority (lower relevance, older access = higher priority for cleanup)
            entries_to_evaluate = []
            for entry_id, entry in self._memory.items():
                # Calculate cleanup priority (higher = more likely to be cleaned)
                priority = (
                    (1.0 - entry.relevance_score) * 0.6 +  # Lower relevance = higher priority
                    (datetime.utcnow() - entry.last_accessed).total_seconds() / (24 * 3600) * 0.3 +  # Older access = higher priority
                    (1 if entry.compressed else 0) * 0.1  # Already compressed = slightly higher priority
                )
                entries_to_evaluate.append((entry_id, entry, priority))

            # Sort by priority (highest first)
            entries_to_evaluate.sort(key=lambda x: x[2], reverse=True)

            # Remove entries based on retention policies and priority
            removed_count = 0
            target_removal = max(1, int(len(self._memory) * 0.2))  # Remove 20% of entries

            for entry_id, entry, priority in entries_to_evaluate:
                # Check retention policy
                policy_expiry = self.retention_policies.get(entry.retention_policy, timedelta(days=1))
                if datetime.utcnow() - entry.timestamp > policy_expiry:
                    # Entry has expired according to policy
                    self._remove_entry(entry_id)
                    removed_count += 1
                elif priority > 0.7 and removed_count < target_removal:
                    # High cleanup priority and haven't reached target
                    self._remove_entry(entry_id)
                    removed_count += 1

                if removed_count >= target_removal:
                    break

            self.stats.cleanup_operations += 1
            self.stats.last_cleanup = datetime.utcnow()

            logger.info(f"Memory cleanup completed: removed {removed_count} entries")

        except Exception as e:
            logger.error(f"Error during memory cleanup: {e}")

    def _remove_entry(self, entry_id: str):
        """Remove a memory entry."""
        if entry_id in self._memory:
            entry = self._memory[entry_id]
            conversation_id = entry.conversation_id

            # Remove from memory
            del self._memory[entry_id]

            # Remove from conversation index
            if conversation_id in self._conversation_index:
                if entry_id in self._conversation_index[conversation_id]:
                    self._conversation_index[conversation_id].remove(entry_id)

                # Clean up empty conversation indices
                if not self._conversation_index[conversation_id]:
                    del self._conversation_index[conversation_id]

            # Remove from recent access if present
            try:
                self._recent_access.remove(entry_id)
            except ValueError:
                pass

    def _update_stats(self):
        """Update memory statistics."""
        self.stats.total_entries = len(self._memory)
        self.stats.compressed_entries = sum(1 for e in self._memory.values() if e.compressed)
        self.stats.important_entries = sum(1 for e in self._memory.values()
                                         if e.relevance_score >= self.relevance_thresholds['important'])
        if self._memory:
            self.stats.average_relevance = sum(e.relevance_score for e in self._memory.values()) / len(self._memory)

    async def _cleanup_worker(self):
        """Background cleanup worker."""
        while True:
            try:
                await asyncio.sleep(300)  # Run every 5 minutes

                if self._should_cleanup():
                    await self._perform_cleanup()

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Cleanup worker error: {e}")
                await asyncio.sleep(60)  # Wait a bit before retrying

    async def _maintenance_worker(self):
        """Background maintenance worker."""
        while True:
            try:
                await asyncio.sleep(600)  # Run every 10 minutes

                # Update statistics
                self._update_stats()

                # Compress old conversations
                for conversation_id in list(self._conversation_index.keys()):
                    await self.compress_memory(conversation_id)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Maintenance worker error: {e}")
                await asyncio.sleep(120)  # Wait before retrying