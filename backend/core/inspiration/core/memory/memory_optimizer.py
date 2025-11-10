"""
Memory Optimization System for HappyOS.

Provides intelligent memory cleanup, optimization, and fragmentation handling
using LRU policies and summarizer-based relevance scoring.
"""

import asyncio
import logging
import time
import psutil
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timedelta
from collections import OrderedDict, defaultdict
from dataclasses import dataclass, field
import threading

from app.core.ai.summarizer import Summarizer
from app.core.memory.intelligent_memory import IntelligentMemoryManager
from app.core.memory.context_memory import PersistentContextMemory
from app.core.fallbacks import with_fallback, register_fallback

logger = logging.getLogger(__name__)


@dataclass
class OptimizationMetrics:
    """Metrics for memory optimization operations."""
    total_cleaned_entries: int = 0
    total_compressed_entries: int = 0
    total_defragmented_mb: float = 0.0
    average_relevance_score: float = 0.0
    optimization_cycles: int = 0
    last_optimization: Optional[datetime] = None
    performance_impact_ms: float = 0.0


@dataclass
class MemoryFragment:
    """Represents a memory fragment for defragmentation."""
    conversation_id: str
    entries: List[Dict[str, Any]] = field(default_factory=list)
    total_size_bytes: int = 0
    average_relevance: float = 0.0
    last_accessed: Optional[datetime] = None
    fragmentation_ratio: float = 0.0


class MemoryOptimizer:
    """
    Intelligent memory optimizer that uses LRU cleanup, summarizer-based relevance scoring,
    and fragmentation handling for optimal memory management.
    """

    def __init__(self, memory_manager: IntelligentMemoryManager,
                 context_memory: PersistentContextMemory,
                 optimization_interval_seconds: int = 300,
                 max_memory_usage_percent: float = 80.0,
                 min_relevance_threshold: float = 0.3):
        """
        Initialize the memory optimizer.

        Args:
            memory_manager: Intelligent memory manager instance
            context_memory: Persistent context memory instance
            optimization_interval_seconds: Seconds between optimization cycles
            max_memory_usage_percent: Max memory usage before aggressive cleanup
            min_relevance_threshold: Minimum relevance score for retention
        """
        self.memory_manager = memory_manager
        self.context_memory = context_memory
        self.summarizer = Summarizer()

        self.optimization_interval = optimization_interval_seconds
        self.max_memory_usage_percent = max_memory_usage_percent
        self.min_relevance_threshold = min_relevance_threshold

        # LRU tracking
        self.lru_cache: OrderedDict[str, datetime] = OrderedDict()
        self.access_counts: Dict[str, int] = defaultdict(int)

        # Optimization state
        self.metrics = OptimizationMetrics()
        self.is_optimizing = False
        self.last_memory_check = datetime.utcnow()

        # Background tasks
        self._optimization_task: Optional[asyncio.Task] = None
        self._monitoring_task: Optional[asyncio.Task] = None

        # Performance tracking
        self.operation_times: List[float] = []
        self.memory_usage_history: List[Tuple[datetime, float]] = []

        logger.info("MemoryOptimizer initialized")

    async def start_optimization(self):
        """Start background optimization processes."""
        self._optimization_task = asyncio.create_task(self._optimization_worker())
        self._monitoring_task = asyncio.create_task(self._monitoring_worker())

        logger.info("MemoryOptimizer background processes started")

    async def stop_optimization(self):
        """Stop background optimization processes."""
        if self._optimization_task:
            self._optimization_task.cancel()
            try:
                await self._optimization_task
            except asyncio.CancelledError:
                pass

        if self._monitoring_task:
            self._monitoring_task.cancel()
            try:
                await self._monitoring_task
            except asyncio.CancelledError:
                pass

        logger.info("MemoryOptimizer stopped")

    async def optimize_now(self) -> Dict[str, Any]:
        """
        Perform immediate memory optimization.

        Returns:
            Optimization results and metrics
        """
        if self.is_optimizing:
            logger.warning("Optimization already in progress")
            return {"status": "in_progress"}

        start_time = time.time()
        self.is_optimizing = True

        try:
            results = {
                "lru_cleanup": await self._perform_lru_cleanup(),
                "relevance_based_cleanup": await self._perform_relevance_cleanup(),
                "fragmentation_handling": await self._handle_fragmentation(),
                "compression_optimization": await self._optimize_compression(),
                "memory_rebalancing": await self._rebalance_memory()
            }

            # Update metrics
            execution_time = time.time() - start_time
            self.metrics.optimization_cycles += 1
            self.metrics.last_optimization = datetime.utcnow()
            self.metrics.performance_impact_ms = execution_time * 1000

            self.operation_times.append(execution_time)
            if len(self.operation_times) > 100:
                self.operation_times.pop(0)

            results.update({
                "execution_time_seconds": execution_time,
                "status": "completed",
                "metrics": self._get_current_metrics()
            })

            logger.info(f"Memory optimization completed in {execution_time:.2f}s")
            return results

        except Exception as e:
            logger.error(f"Error during memory optimization: {e}")
            return {"status": "error", "error": str(e)}

        finally:
            self.is_optimizing = False

    async def _perform_lru_cleanup(self) -> Dict[str, Any]:
        """Perform LRU (Least Recently Used) cleanup."""
        try:
            # Get memory stats
            memory_stats = self.memory_manager.get_memory_stats()
            current_entries = memory_stats['total_entries']

            # Calculate target cleanup (remove oldest 20% if over threshold)
            max_entries = 1000  # Configurable
            if current_entries <= max_entries:
                return {"cleaned": 0, "reason": "below_threshold"}

            target_cleanup = int(current_entries * 0.2)
            cleaned_count = 0

            # Sort entries by last access time (oldest first)
            entries_to_check = []
            for entry_id, entry in self.memory_manager._memory.items():
                entries_to_check.append((entry_id, entry.last_accessed))

            entries_to_check.sort(key=lambda x: x[1])  # Sort by access time

            for entry_id, _ in entries_to_check[:target_cleanup]:
                try:
                    # Check if safe to remove (low relevance or old)
                    entry = self.memory_manager._memory[entry_id]
                    is_old = datetime.utcnow() - entry.timestamp > timedelta(days=7)
                    is_low_relevance = entry.relevance_score < self.min_relevance_threshold

                    if is_old or is_low_relevance:
                        self.memory_manager._remove_entry(entry_id)
                        cleaned_count += 1
                    else:
                        # Try to compress instead
                        await self.memory_manager.compress_memory(entry.conversation_id)
                        logger.debug(f"Compressed instead of removed: {entry_id}")

                except Exception as e:
                    logger.error(f"Error cleaning LRU entry {entry_id}: {e}")

            self.metrics.total_cleaned_entries += cleaned_count
            return {"cleaned": cleaned_count, "target": target_cleanup}

        except Exception as e:
            logger.error(f"Error in LRU cleanup: {e}")
            return {"error": str(e)}

    async def _perform_relevance_cleanup(self) -> Dict[str, Any]:
        """Perform cleanup based on summarizer relevance scoring."""
        try:
            cleaned_count = 0
            compressed_count = 0

            # Analyze each conversation for relevance
            for conversation_id in list(self.memory_manager._conversation_index.keys()):
                try:
                    # Get conversation context for relevance analysis
                    context = {"messages": []}

                    # Reconstruct messages from memory entries
                    entry_ids = self.memory_manager._conversation_index[conversation_id]
                    for entry_id in entry_ids:
                        if entry_id in self.memory_manager._memory:
                            entry = self.memory_manager._memory[entry_id]
                            context["messages"].append({
                                "role": "user",
                                "content": entry.content.get("user_input", "")
                            })

                    if not context["messages"]:
                        continue

                    # Generate mindmap to assess conversation importance
                    mindmap = await self.summarizer.generate_mindmap(context)

                    if mindmap:
                        # Calculate conversation relevance score
                        importance_score = len(mindmap.get("main_branches", [])) / 10.0  # Normalize
                        action_items = len(mindmap.get("action_items", []))
                        key_insights = len(mindmap.get("key_insights", []))

                        conversation_relevance = min(1.0, (importance_score + action_items * 0.2 + key_insights * 0.1))

                        # Update relevance scores for all entries in conversation
                        for entry_id in entry_ids:
                            if entry_id in self.memory_manager._memory:
                                entry = self.memory_manager._memory[entry_id]
                                entry.relevance_score = (entry.relevance_score + conversation_relevance) / 2

                                # Clean up low relevance entries
                                if conversation_relevance < self.min_relevance_threshold:
                                    self.memory_manager._remove_entry(entry_id)
                                    cleaned_count += 1
                                elif conversation_relevance < 0.5:
                                    # Compress low-moderate relevance conversations
                                    await self.memory_manager.compress_memory(conversation_id)
                                    compressed_count += 1

                except Exception as e:
                    logger.error(f"Error analyzing conversation {conversation_id}: {e}")

            return {"cleaned": cleaned_count, "compressed": compressed_count}

        except Exception as e:
            logger.error(f"Error in relevance cleanup: {e}")
            return {"error": str(e)}

    async def _handle_fragmentation(self) -> Dict[str, Any]:
        """Handle memory fragmentation by reorganizing and compacting data."""
        try:
            defragmented_mb = 0.0

            # Analyze memory fragmentation
            fragments = await self._analyze_fragmentation()

            for fragment in fragments:
                if fragment.fragmentation_ratio > 0.3:  # High fragmentation
                    try:
                        # Compact fragmented conversation
                        compacted_size = await self._compact_fragment(fragment)
                        defragmented_mb += (fragment.total_size_bytes - compacted_size) / (1024 * 1024)

                        logger.debug(f"Defragmented conversation {fragment.conversation_id}: "
                                   f"saved {(fragment.total_size_bytes - compacted_size) / 1024:.1f}KB")

                    except Exception as e:
                        logger.error(f"Error defragmenting {fragment.conversation_id}: {e}")

            self.metrics.total_defragmented_mb += defragmented_mb
            return {"defragmented_mb": defragmented_mb, "fragments_analyzed": len(fragments)}

        except Exception as e:
            logger.error(f"Error handling fragmentation: {e}")
            return {"error": str(e)}

    async def _optimize_compression(self) -> Dict[str, Any]:
        """Optimize compression settings and compress eligible data."""
        try:
            compressed_count = 0

            # Get current memory stats
            memory_stats = self.memory_manager.get_memory_stats()
            compressed_ratio = memory_stats['compressed_entries'] / max(memory_stats['total_entries'], 1)

            # If compression ratio is low, compress more aggressively
            if compressed_ratio < 0.3:
                target_compression = int(memory_stats['total_entries'] * 0.2)  # Compress 20%

                # Sort by size and age for compression candidates
                candidates = []
                for entry_id, entry in self.memory_manager._memory.items():
                    if not entry.compressed:
                        priority = (
                            entry.content.get('size_bytes', 0) * 0.5 +
                            (datetime.utcnow() - entry.timestamp).total_seconds() / 86400 * 0.3 +  # Age in days
                            (1.0 - entry.relevance_score) * 0.2  # Lower relevance = higher priority
                        )
                        candidates.append((entry_id, priority))

                candidates.sort(key=lambda x: x[1], reverse=True)  # Highest priority first

                for entry_id, _ in candidates[:target_compression]:
                    try:
                        conversation_id = self.memory_manager._memory[entry_id].conversation_id
                        await self.memory_manager.compress_memory(conversation_id)
                        compressed_count += 1
                    except Exception as e:
                        logger.error(f"Error compressing entry {entry_id}: {e}")

            self.metrics.total_compressed_entries += compressed_count
            return {"compressed": compressed_count, "compression_ratio": compressed_ratio}

        except Exception as e:
            logger.error(f"Error optimizing compression: {e}")
            return {"error": str(e)}

    async def _rebalance_memory(self) -> Dict[str, Any]:
        """Rebalance memory usage across different storage layers."""
        try:
            # Check system memory usage
            memory_percent = psutil.virtual_memory().percent

            actions_taken = []

            if memory_percent > self.max_memory_usage_percent:
                # High memory usage - aggressive cleanup
                logger.warning(f"High memory usage: {memory_percent}%, performing aggressive cleanup")

                # Clear old cache entries
                cache_cleared = await self._clear_old_cache()
                actions_taken.append(f"cleared {cache_cleared} cache entries")

                # Compress more aggressively
                compression_result = await self._optimize_compression()
                if compression_result.get('compressed', 0) > 0:
                    actions_taken.append(f"compressed {compression_result['compressed']} entries")

                # Force LRU cleanup
                lru_result = await self._perform_lru_cleanup()
                if lru_result.get('cleaned', 0) > 0:
                    actions_taken.append(f"LRU cleaned {lru_result['cleaned']} entries")

            # Rebalance between memory layers
            rebalanced = await self._rebalance_storage_layers()
            if rebalanced > 0:
                actions_taken.append(f"rebalanced {rebalanced} conversations")

            return {"actions_taken": actions_taken, "memory_percent": memory_percent}

        except Exception as e:
            logger.error(f"Error rebalancing memory: {e}")
            return {"error": str(e)}

    async def _analyze_fragmentation(self) -> List[MemoryFragment]:
        """Analyze memory for fragmentation patterns."""
        fragments = []

        try:
            for conversation_id, entry_ids in self.memory_manager._conversation_index.items():
                entries = []
                total_size = 0
                total_relevance = 0.0
                last_access = None

                for entry_id in entry_ids:
                    if entry_id in self.memory_manager._memory:
                        entry = self.memory_manager._memory[entry_id]
                        entries.append(entry.content)
                        total_size += len(str(entry.content).encode('utf-8'))
                        total_relevance += entry.relevance_score

                        if not last_access or entry.last_accessed > last_access:
                            last_access = entry.last_accessed

                if entries:
                    avg_relevance = total_relevance / len(entries)

                    # Calculate fragmentation ratio (spread in access times)
                    if len(entries) > 1:
                        access_times = [e.get('timestamp') for e in entries if e.get('timestamp')]
                        if access_times:
                            time_spread = max(access_times) - min(access_times)
                            fragmentation_ratio = min(1.0, time_spread.total_seconds() / (30 * 24 * 3600))  # Max 30 days
                        else:
                            fragmentation_ratio = 0.0
                    else:
                        fragmentation_ratio = 0.0

                    fragments.append(MemoryFragment(
                        conversation_id=conversation_id,
                        entries=entries,
                        total_size_bytes=total_size,
                        average_relevance=avg_relevance,
                        last_accessed=last_access,
                        fragmentation_ratio=fragmentation_ratio
                    ))

        except Exception as e:
            logger.error(f"Error analyzing fragmentation: {e}")

        return fragments

    async def _compact_fragment(self, fragment: MemoryFragment) -> int:
        """Compact a fragmented memory conversation."""
        try:
            # Create a compact representation
            compact_context = {
                "conversation_id": fragment.conversation_id,
                "total_entries": len(fragment.entries),
                "date_range": {
                    "oldest": min(e.get('timestamp') for e in fragment.entries if e.get('timestamp')),
                    "newest": max(e.get('timestamp') for e in fragment.entries if e.get('timestamp'))
                },
                "summary": await self.summarizer.summarize(
                    " ".join(str(e) for e in fragment.entries),
                    {"messages": [{"role": "user", "content": str(e)} for e in fragment.entries]}
                ),
                "compacted_at": datetime.utcnow().isoformat()
            }

            # Store compact version
            await self.context_memory.save_context(
                fragment.conversation_id,
                "COMPACTED_MEMORY",
                compact_context
            )

            # Calculate new size
            new_size = len(str(compact_context).encode('utf-8'))

            return new_size

        except Exception as e:
            logger.error(f"Error compacting fragment {fragment.conversation_id}: {e}")
            return fragment.total_size_bytes

    async def _clear_old_cache(self) -> int:
        """Clear old entries from cache."""
        try:
            cleared = 0
            cutoff_time = datetime.utcnow() - timedelta(hours=24)

            # Clear old entries from context memory cache
            to_remove = []
            for conv_id, context in self.context_memory._cache.items():
                # Check if cache entry is old
                if isinstance(context, dict) and 'history' in context:
                    last_entry = context['history'][-1] if context['history'] else None
                    if last_entry and last_entry.get('timestamp'):
                        entry_time = datetime.fromisoformat(last_entry['timestamp'])
                        if entry_time < cutoff_time:
                            to_remove.append(conv_id)

            for conv_id in to_remove:
                del self.context_memory._cache[conv_id]
                cleared += 1

            return cleared

        except Exception as e:
            logger.error(f"Error clearing old cache: {e}")
            return 0

    async def _rebalance_storage_layers(self) -> int:
        """Rebalance data between memory layers for optimal performance."""
        try:
            rebalanced = 0

            # Move frequently accessed conversations to faster storage
            # Move rarely accessed conversations to slower storage

            for conversation_id in list(self.memory_manager._conversation_index.keys()):
                try:
                    # Check access pattern
                    entry_ids = self.memory_manager._conversation_index[conversation_id]
                    recent_accesses = sum(
                        1 for entry_id in entry_ids
                        if entry_id in self.memory_manager._memory and
                        datetime.utcnow() - self.memory_manager._memory[entry_id].last_accessed < timedelta(hours=1)
                    )

                    if recent_accesses > 5:
                        # Frequently accessed - ensure in fast memory
                        await self.context_memory.get_context(conversation_id)  # Load to memory
                        rebalanced += 1
                    elif recent_accesses == 0:
                        # Not accessed recently - can be compressed
                        await self.memory_manager.compress_memory(conversation_id)
                        rebalanced += 1

                except Exception as e:
                    logger.error(f"Error rebalancing {conversation_id}: {e}")

            return rebalanced

        except Exception as e:
            logger.error(f"Error rebalancing storage layers: {e}")
            return 0

    def _get_current_metrics(self) -> Dict[str, Any]:
        """Get current optimization metrics."""
        memory_stats = self.memory_manager.get_memory_stats()

        return {
            "total_cleaned_entries": self.metrics.total_cleaned_entries,
            "total_compressed_entries": self.metrics.total_compressed_entries,
            "total_defragmented_mb": self.metrics.total_defragmented_mb,
            "average_relevance_score": memory_stats.get('average_relevance', 0.0),
            "optimization_cycles": self.metrics.optimization_cycles,
            "last_optimization": self.metrics.last_optimization.isoformat() if self.metrics.last_optimization else None,
            "performance_impact_ms": self.metrics.performance_impact_ms,
            "memory_entries": memory_stats.get('total_entries', 0),
            "compressed_ratio": memory_stats.get('compressed_entries', 0) / max(memory_stats.get('total_entries', 1), 1)
        }

    async def _optimization_worker(self):
        """Background optimization worker."""
        while True:
            try:
                await asyncio.sleep(self.optimization_interval)

                if not self.is_optimizing:
                    await self.optimize_now()

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Optimization worker error: {e}")
                await asyncio.sleep(60)  # Wait before retry

    async def _monitoring_worker(self):
        """Background monitoring worker."""
        while True:
            try:
                await asyncio.sleep(60)  # Check every minute

                # Record memory usage
                memory_percent = psutil.virtual_memory().percent
                self.memory_usage_history.append((datetime.utcnow(), memory_percent))

                # Keep only last 100 readings
                if len(self.memory_usage_history) > 100:
                    self.memory_usage_history.pop(0)

                # Trigger optimization if memory usage is critical
                if memory_percent > 90.0 and not self.is_optimizing:
                    logger.warning(f"Critical memory usage: {memory_percent}%, triggering emergency optimization")
                    asyncio.create_task(self.optimize_now())

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Monitoring worker error: {e}")
                await asyncio.sleep(120)  # Wait before retry

    def get_optimization_report(self) -> Dict[str, Any]:
        """Get comprehensive optimization report."""
        memory_stats = self.memory_manager.get_memory_stats()

        # Calculate trends
        recent_memory_usage = [usage for _, usage in self.memory_usage_history[-10:]]
        avg_memory_trend = sum(recent_memory_usage) / max(len(recent_memory_usage), 1)

        return {
            "current_metrics": self._get_current_metrics(),
            "memory_stats": memory_stats,
            "performance_trends": {
                "average_optimization_time": sum(self.operation_times) / max(len(self.operation_times), 1),
                "average_memory_usage_percent": avg_memory_trend,
                "optimization_frequency_per_hour": (self.metrics.optimization_cycles * 3600) / max(
                    (datetime.utcnow() - (self.metrics.last_optimization or datetime.utcnow())).total_seconds(), 3600)
            },
            "system_health": {
                "is_optimizing": self.is_optimizing,
                "last_memory_check": self.last_memory_check.isoformat(),
                "background_workers_active": (
                    self._optimization_task is not None and not self._optimization_task.done() and
                    self._monitoring_task is not None and not self._monitoring_task.done()
                )
            },
            "recommendations": self._generate_recommendations()
        }

    def _generate_recommendations(self) -> List[str]:
        """Generate optimization recommendations based on current state."""
        recommendations = []
        memory_stats = self.memory_manager.get_memory_stats()

        # Memory usage recommendations
        if memory_stats['total_entries'] > 800:
            recommendations.append("High memory entry count - consider increasing cleanup frequency")

        if memory_stats['compressed_entries'] / max(memory_stats['total_entries'], 1) < 0.2:
            recommendations.append("Low compression ratio - enable more aggressive compression")

        if self.metrics.average_relevance_score < 0.4:
            recommendations.append("Low average relevance - review summarizer configuration")

        # Performance recommendations
        if self.metrics.performance_impact_ms > 5000:  # > 5 seconds
            recommendations.append("High optimization impact - consider reducing optimization frequency")

        # System health recommendations
        if not self._optimization_task or self._optimization_task.done():
            recommendations.append("Optimization worker not running - restart required")

        return recommendations
