# Domain-specific agent implementations

# Import all registries to ensure agents are registered
from .agent_svea import registry as agent_svea_registry
from .felicias_finance import registry as felicias_finance_registry  
from .meetmind import registry as meetmind_registry

__all__ = []