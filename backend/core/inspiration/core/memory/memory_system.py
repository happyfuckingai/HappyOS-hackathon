"""
Integrated Memory System for HappyOS.

Combines IntelligentMemoryManager, PersistentContextMemory, MemoryOptimizer,
and SummarizedMemory for comprehensive memory management.
"""

import asyncio
import logging
from typing import Dict, Any, List, Optional, Union
from datetime import datetime
from dataclasses import dataclass, field

from app.core.memory.intelligent_memory import IntelligentMemoryManager
from app.core.memory.context_memory import PersistentContextMemory
from app.core.memory.memory_optimizer import MemoryOptimizer
from app.core.memory.summarized_memory import SummarizedMemory

logger = logging.getLogger(__name__)


@dataclass
class MemorySystemConfig:
    """Configuration for the integrated memory system."""
    enable_persistence: bool = True
    enable_optimization: bool = True
    enable_summarization: bool = True
    max_memory_entries: int = 1000
    optimization_interval_seconds: int = 300
    auto_summarize_threshold: int = 10
    max_memory_size_mb: float = 100.0
    backup_interval_hours: int = 24


@dataclass
class MemoryQueryResult:
    """Result of a memory query."""
    conversation_id: str
    results: List[Dict[str, Any]] = field(default_factory=list)
    summary_available: bool = False
    relevance_score: float = 0.0
    source: str = "unknown"  # "intelligent", "persistent", "summarized"
    execution_time_ms: float = 0.0


class MemorySystem:
    """
    Integrated memory system that combines all memory management components
    for optimal performance and intelligence.
    """

    def __init__(self, config: Optional[MemorySystemConfig] = None):
        """
        Initialize the integrated memory system.

        Args:
            config: System configuration
        """
        self.config = config or MemorySystemConfig()

        # Core components
        self.intelligent_memory = None
        self.persistent_memory = None
        self.memory_optimizer = None
        self.summarized_memory = None

        # System state
        self._initialized = False
        self._components_initialized = set()

        logger.info("MemorySystem initialized with config")

    async def initialize(self) -> Dict[str, Any]:
        """
        Initialize all memory system components.

        Returns:
            Initialization status
        """
        try:
            init_status = {
                "intelligent_memory": False,
                "persistent_memory": False,
                "memory_optimizer": False,
                "summarized_memory": False,
                "errors": []
            }

            # Initialize Intelligent Memory Manager
            if not self.intelligent_memory:
                self.intelligent_memory = IntelligentMemoryManager(
                    max_memory_entries=self.config.max_memory_entries
                )
                await self.intelligent_memory.initialize()
                self._components_initialized.add("intelligent_memory")
                init_status["intelligent_memory"] = True
                logger.info("IntelligentMemoryManager initialized")

            # Initialize Persistent Context Memory
            if self.config.enable_persistence and not self.persistent_memory:
                self.persistent_memory = PersistentContextMemory(
                    max_memory_size_mb=self.config.max_memory_size_mb,
                    backup_interval_hours=self.config.backup_interval_hours
                )
                await self.persistent_memory.initialize()
                self._components_initialized.add("persistent_memory")
                init_status["persistent_memory"] = True
                logger.info("PersistentContextMemory initialized")

            # Initialize Memory Optimizer
            if self.config.enable_optimization and not self.memory_optimizer:
                self.memory_optimizer = MemoryOptimizer(
                    memory_manager=self.intelligent_memory,
                    context_memory=self.persistent_memory or self.intelligent_memory.context_memory,
                    optimization_interval_seconds=self.config.optimization_interval_seconds
                )
                await self.memory_optimizer.start_optimization()
                self._components_initialized.add("memory_optimizer")
                init_status["memory_optimizer"] = True
                logger.info("MemoryOptimizer initialized")

            # Initialize Summarized Memory
            if self.config.enable_summarization and not self.summarized_memory:
                self.summarized_memory = SummarizedMemory(
                    intelligent_memory=self.intelligent_memory,
                    context_memory=self.persistent_memory or self.intelligent_memory.context_memory,
                    auto_summarize_threshold=self.config.auto_summarize_threshold
                )
                self._components_initialized.add("summarized_memory")
                init_status["summarized_memory"] = True
                logger.info("SummarizedMemory initialized")

            self._initialized = True

            init_status.update({
                "overall_status": "success",
                "components_active": len(self._components_initialized),
                "timestamp": datetime.utcnow().isoformat()
            })

            logger.info(f"MemorySystem fully initialized with {len(self._components_initialized)} components")
            return init_status

        except Exception as e:
            error_msg = f"Failed to initialize MemorySystem: {e}"
            logger.error(error_msg)
            return {
                "overall_status": "error",
                "error": error_msg,
                "components_active": len(self._components_initialized),
                "timestamp": datetime.utcnow().isoformat()
            }

    async def shutdown(self) -> Dict[str, Any]:
        """
        Shutdown all memory system components.

        Returns:
            Shutdown status
        """
        try:
            shutdown_status = {
                "components_shutdown": 0,
                "errors": []
            }

            # Shutdown in reverse order
            if self.memory_optimizer and "memory_optimizer" in self._components_initialized:
                await self.memory_optimizer.stop_optimization()
                shutdown_status["components_shutdown"] += 1

            if self.persistent_memory and "persistent_memory" in self._components_initialized:
                await self.persistent_memory.shutdown()
                shutdown_status["components_shutdown"] += 1

            if self.intelligent_memory and "intelligent_memory" in self._components_initialized:
                await self.intelligent_memory.shutdown()
                shutdown_status["components_shutdown"] += 1

            self._initialized = False
            self._components_initialized.clear()

            shutdown_status.update({
                "overall_status": "success",
                "timestamp": datetime.utcnow().isoformat()
            })

            logger.info("MemorySystem shutdown complete")
            return shutdown_status

        except Exception as e:
            error_msg = f"Error during MemorySystem shutdown: {e}"
            logger.error(error_msg)
            return {
                "overall_status": "error",
                "error": error_msg,
                "timestamp": datetime.utcnow().isoformat()
            }

    async def store_memory(self, conversation_id: str, user_input: str,
                          context_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Store memory using the integrated system.

        Args:
            conversation_id: Conversation identifier
            user_input: User input text
            context_data: Context data to store

        Returns:
            Storage result
        """
        if not self._initialized:
            return {"status": "error", "error": "MemorySystem not initialized"}

        start_time = datetime.utcnow()

        try:
            results = {}

            # Store in intelligent memory (primary)
            if self.intelligent_memory:
                entry_id = await self.intelligent_memory.store_memory(
                    conversation_id, context_data, {"messages": [context_data]}
                )
                results["intelligent_memory"] = {"entry_id": entry_id}

            # Store in persistent memory if enabled
            if self.persistent_memory and self.config.enable_persistence:
                await self.persistent_memory.save_context(conversation_id, user_input, context_data)
                results["persistent_memory"] = {"stored": True}

            # Process for summarization if enabled
            if self.summarized_memory and self.config.enable_summarization:
                # Get conversation history for summarization
                conversation_context = {"messages": []}

                if self.intelligent_memory:
                    memory_entries = await self.intelligent_memory.retrieve_memory(conversation_id)
                    for entry in memory_entries:
                        if "content" in entry:
                            conversation_context["messages"].append({
                                "role": "user",
                                "content": entry["content"].get("user_input", "")
                            })

                # Add current message
                conversation_context["messages"].append({
                    "role": "user",
                    "content": user_input
                })

                summary_id = await self.summarized_memory.process_conversation_chunk(
                    conversation_id, conversation_context["messages"]
                )

                if summary_id:
                    results["summarized_memory"] = {"summary_id": summary_id}

            execution_time = (datetime.utcnow() - start_time).total_seconds() * 1000

            return {
                "status": "success",
                "conversation_id": conversation_id,
                "components_used": list(results.keys()),
                "execution_time_ms": execution_time,
                "timestamp": datetime.utcnow().isoformat(),
                **results
            }

        except Exception as e:
            execution_time = (datetime.utcnow() - start_time).total_seconds() * 1000
            error_msg = f"Error storing memory: {e}"
            logger.error(error_msg)
            return {
                "status": "error",
                "error": error_msg,
                "execution_time_ms": execution_time,
                "timestamp": datetime.utcnow().isoformat()
            }

    async def retrieve_memory(self, conversation_id: str, query: Optional[str] = None,
                            context: Optional[Dict[str, Any]] = None) -> MemoryQueryResult:
        """
        Retrieve memory using intelligent querying across all components.

        Args:
            conversation_id: Conversation identifier
            query: Search query
            context: Additional context

        Returns:
            Query result with relevant memories
        """
        if not self._initialized:
            return MemoryQueryResult(conversation_id=conversation_id)

        start_time = datetime.utcnow()

        try:
            all_results = []
            sources_used = []

            # Query summarized memory first (most relevant)
            if self.summarized_memory and self.config.enable_summarization and query:
                summarized_results = await self.summarized_memory.retrieve_relevant_memory(
                    conversation_id, query, context, limit=5
                )
                if summarized_results:
                    all_results.extend(summarized_results)
                    sources_used.append("summarized")

            # Query intelligent memory
            if self.intelligent_memory:
                intelligent_results = await self.intelligent_memory.retrieve_memory(
                    conversation_id, query, limit=10
                )
                if intelligent_results:
                    # Convert to consistent format
                    for result in intelligent_results:
                        all_results.append({
                            "id": result.get("id"),
                            "content": result.get("content", result.get("summary", "")),
                            "summary": result.get("summary"),
                            "relevance_score": result.get("relevance_score", 0.5),
                            "source": "intelligent",
                            "timestamp": result.get("timestamp")
                        })
                    sources_used.append("intelligent")

            # Query persistent memory as fallback
            if self.persistent_memory and self.config.enable_persistence and not all_results:
                persistent_context = await self.persistent_memory.get_context(conversation_id)
                if persistent_context and "history" in persistent_context:
                    for item in persistent_context["history"][-5:]:  # Last 5 entries
                        all_results.append({
                            "content": item.get("context_data", {}),
                            "relevance_score": 0.5,
                            "source": "persistent",
                            "timestamp": item.get("timestamp")
                        })
                    sources_used.append("persistent")

            # Sort results by relevance and recency
            all_results.sort(key=lambda x: (
                x.get("relevance_score", 0),
                x.get("timestamp", ""),
                x.get("source") == "summarized"  # Prefer summarized results
            ), reverse=True)

            execution_time = (datetime.utcnow() - start_time).total_seconds() * 1000

            result = MemoryQueryResult(
                conversation_id=conversation_id,
                results=all_results[:10],  # Max 10 results
                summary_available=bool(self.summarized_memory and
                                     self.summarized_memory._conversation_summaries.get(conversation_id)),
                relevance_score=max((r.get("relevance_score", 0) for r in all_results), default=0.0),
                source=", ".join(sources_used) if sources_used else "none",
                execution_time_ms=execution_time
            )

            return result

        except Exception as e:
            execution_time = (datetime.utcnow() - start_time).total_seconds() * 1000
            logger.error(f"Error retrieving memory: {e}")
            return MemoryQueryResult(
                conversation_id=conversation_id,
                execution_time_ms=execution_time
            )

    async def optimize_memory(self) -> Dict[str, Any]:
        """
        Trigger memory optimization across all components.

        Returns:
            Optimization results
        """
        if not self._initialized:
            return {"status": "error", "error": "MemorySystem not initialized"}

        try:
            results = {}

            if self.memory_optimizer and self.config.enable_optimization:
                opt_result = await self.memory_optimizer.optimize_now()
                results["memory_optimizer"] = opt_result

            # Trigger cleanup in persistent memory
            if self.persistent_memory and self.config.enable_persistence:
                cleanup_result = await self.persistent_memory.cleanup_old_conversations(days_old=30)
                results["persistent_cleanup"] = {"conversations_removed": cleanup_result}

            # Clear old summaries
            if self.summarized_memory and self.config.enable_summarization:
                summary_cleanup = self.summarized_memory.clear_old_summaries(days_old=90)
                results["summary_cleanup"] = {"summaries_removed": summary_cleanup}

            results.update({
                "status": "success",
                "timestamp": datetime.utcnow().isoformat()
            })

            return results

        except Exception as e:
            logger.error(f"Error during memory optimization: {e}")
            return {
                "status": "error",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }

    def get_system_stats(self) -> Dict[str, Any]:
        """
        Get comprehensive statistics from all memory components.

        Returns:
            System statistics
        """
        try:
            stats = {
                "system_status": "initialized" if self._initialized else "not_initialized",
                "components_active": list(self._components_initialized),
                "config": {
                    "enable_persistence": self.config.enable_persistence,
                    "enable_optimization": self.config.enable_optimization,
                    "enable_summarization": self.config.enable_summarization,
                    "max_memory_entries": self.config.max_memory_entries,
                    "optimization_interval_seconds": self.config.optimization_interval_seconds,
                    "auto_summarize_threshold": self.config.auto_summarize_threshold,
                    "max_memory_size_mb": self.config.max_memory_size_mb,
                    "backup_interval_hours": self.config.backup_interval_hours
                },
                "timestamp": datetime.utcnow().isoformat()
            }

            # Collect stats from each component
            if self.intelligent_memory:
                stats["intelligent_memory"] = self.intelligent_memory.get_memory_stats()

            if self.persistent_memory and self.config.enable_persistence:
                stats["persistent_memory"] = self.persistent_memory.get_conversation_stats("system_overview")

            if self.memory_optimizer and self.config.enable_optimization:
                stats["memory_optimizer"] = self.memory_optimizer.get_optimization_report()

            if self.summarized_memory and self.config.enable_summarization:
                stats["summarized_memory"] = self.summarized_memory.get_memory_stats()

            return stats

        except Exception as e:
            logger.error(f"Error getting system stats: {e}")
            return {
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }

    async def get_conversation_overview(self, conversation_id: str) -> Dict[str, Any]:
        """
        Get comprehensive overview of a conversation.

        Args:
            conversation_id: Conversation identifier

        Returns:
            Conversation overview
        """
        if not self._initialized:
            return {"status": "error", "error": "MemorySystem not initialized"}

        try:
            overview = {
                "conversation_id": conversation_id,
                "sources": []
            }

            # Get overview from summarized memory
            if self.summarized_memory and self.config.enable_summarization:
                summary_overview = await self.summarized_memory.get_conversation_overview(conversation_id)
                if summary_overview.get("total_summaries", 0) > 0:
                    overview["summary_overview"] = summary_overview
                    overview["sources"].append("summarized")

            # Get stats from persistent memory
            if self.persistent_memory and self.config.enable_persistence:
                persistent_stats = await self.persistent_memory.get_conversation_stats(conversation_id)
                if persistent_stats.get("total_entries", 0) > 0:
                    overview["persistent_stats"] = persistent_stats
                    overview["sources"].append("persistent")

            # Get basic info from intelligent memory
            if self.intelligent_memory:
                memory_entries = await self.intelligent_memory.retrieve_memory(conversation_id, limit=1)
                if memory_entries:
                    overview["intelligent_memory_entries"] = len(memory_entries)
                    overview["sources"].append("intelligent")

            overview.update({
                "status": "success",
                "timestamp": datetime.utcnow().isoformat()
            })

            return overview

        except Exception as e:
            logger.error(f"Error getting conversation overview: {e}")
            return {
                "status": "error",
                "error": str(e),
                "conversation_id": conversation_id,
                "timestamp": datetime.utcnow().isoformat()
            }