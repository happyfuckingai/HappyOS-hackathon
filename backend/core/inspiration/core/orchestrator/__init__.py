"""
Orchestrator Package - Self-building system implementations.

This package provides two main orchestrator implementations:
1. BasicSelfBuildingOrchestrator - Simple, lightweight orchestrator
2. UltimateSelfBuildingOrchestrator - Advanced orchestrator with full integration

Both orchestrators share a common BaseOrchestratorCore for reduced code duplication
and easier maintenance.
"""

from .orchestrator_core import BaseOrchestratorCore, RequestType, ProcessingStrategy, RequestAnalysis, ProcessingResult
from .basic_orchestrator import BasicSelfBuildingOrchestrator
from .ultimate_orchestrator import UltimateSelfBuildingOrchestrator, EnhancedRequestAnalysis, UltimateProcessingResult

# Alias for backward compatibility
BasicOrchestrator = BasicSelfBuildingOrchestrator

__all__ = [
    # Core components
    "BaseOrchestratorCore",
    "RequestType",
    "ProcessingStrategy",
    "RequestAnalysis",
    "ProcessingResult",
    
    # Orchestrator implementations
    "BasicSelfBuildingOrchestrator",
    "BasicOrchestrator",  # Alias for backward compatibility
    "UltimateSelfBuildingOrchestrator",
    
    # Advanced components
    "EnhancedRequestAnalysis",
    "UltimateProcessingResult",
]

# Convenience functions for creating orchestrators
async def create_basic_orchestrator() -> BasicSelfBuildingOrchestrator:
    """
    Create and initialize a basic self-building orchestrator.
    
    Returns:
        BasicSelfBuildingOrchestrator: Initialized basic orchestrator
    """
    orchestrator = BasicSelfBuildingOrchestrator()
    await orchestrator.initialize()
    return orchestrator

async def create_ultimate_orchestrator() -> UltimateSelfBuildingOrchestrator:
    """
    Create and initialize an ultimate self-building orchestrator.
    
    Returns:
        UltimateSelfBuildingOrchestrator: Initialized ultimate orchestrator
    """
    orchestrator = UltimateSelfBuildingOrchestrator()
    await orchestrator.initialize()
    return orchestrator

# Default orchestrator selection
async def create_default_orchestrator(advanced: bool = False):
    """
    Create the default orchestrator based on requirements.
    
    Args:
        advanced: If True, creates ultimate orchestrator; otherwise basic
        
    Returns:
        Orchestrator instance
    """
    if advanced:
        return await create_ultimate_orchestrator()
    else:
        return await create_basic_orchestrator()
