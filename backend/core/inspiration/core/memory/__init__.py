# This file makes the 'memory' directory a Python package.

from .context_memory import ContextMemory, PersistentContextMemory
from .intelligent_memory import IntelligentMemoryManager
from .memory_optimizer import MemoryOptimizer
from .summarized_memory import SummarizedMemory
from .memory_system import MemorySystem, MemorySystemConfig

# Legacy support
_memory_instance = None

def get_memory_instance() -> ContextMemory:
    """Get the global memory instance (legacy)."""
    global _memory_instance
    if _memory_instance is None:
        _memory_instance = ContextMemory()
    return _memory_instance

# New integrated system
_memory_system_instance = None

def get_memory_system(config: MemorySystemConfig = None) -> MemorySystem:
    """Get the global integrated memory system instance."""
    global _memory_system_instance
    if _memory_system_instance is None:
        _memory_system_instance = MemorySystem(config)
    return _memory_system_instance
