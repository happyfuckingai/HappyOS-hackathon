"""
Agent Svea ADK Agents

Standardized 5-role agent structure for Swedish ERP and compliance system.
Reuses existing Agent Svea logic organized into standard ADK roles.
"""

from .coordinator_agent import CoordinatorAgent
from .architect_agent import ArchitectAgent  
from .implementation_agent import ImplementationAgent
from .product_manager_agent import ProductManagerAgent
from .quality_assurance_agent import QualityAssuranceAgent

__all__ = [
    'CoordinatorAgent',
    'ArchitectAgent', 
    'ImplementationAgent',
    'ProductManagerAgent',
    'QualityAssuranceAgent'
]