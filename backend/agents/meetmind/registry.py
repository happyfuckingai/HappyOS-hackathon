"""
MeetMind Registry

Registers all MeetMind ADK agents with the global registry.
This file handles backend imports so ADK agents stay clean.
"""

try:
    from backend.core.registry.agents import register
except ImportError:
    from core.registry.agents import register

from .adk_agents.coordinator_agent import CoordinatorAgent
from .adk_agents.architect_agent import ArchitectAgent
from .adk_agents.implementation_agent import ImplementationAgent
from .adk_agents.product_manager_agent import ProductManagerAgent
from .adk_agents.quality_assurance_agent import QualityAssuranceAgent
from .services import MeetingService, SummarizationService


def _create_services():
    """Create and initialize MeetMind services."""
    return {
        "meeting_service": MeetingService(),
        "summarization_service": SummarizationService()
    }


@register("meetmind.coordinator")
def build_meetmind_coordinator():
    """Factory function for MeetMind Coordinator."""
    services = _create_services()
    return CoordinatorAgent(services=services)


@register("meetmind.architect")
def build_meetmind_architect():
    """Factory function for MeetMind Architect."""
    services = _create_services()
    return ArchitectAgent(services=services)


@register("meetmind.implementation")
def build_meetmind_implementation():
    """Factory function for MeetMind Implementation."""
    services = _create_services()
    return ImplementationAgent(services=services)


@register("meetmind.product_manager")
def build_meetmind_product_manager():
    """Factory function for MeetMind Product Manager."""
    services = _create_services()
    return ProductManagerAgent(services=services)


@register("meetmind.quality_assurance")
def build_meetmind_quality_assurance():
    """Factory function for MeetMind Quality Assurance."""
    services = _create_services()
    return QualityAssuranceAgent(services=services)