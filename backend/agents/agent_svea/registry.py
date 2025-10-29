"""
Agent Svea Registry

Registers all Agent Svea ADK agents with the global registry.
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
from .services import ERPService, ComplianceService, SwedishIntegrationService


def _create_services():
    """Create and initialize Agent Svea services."""
    return {
        "erp_service": ERPService(),
        "compliance_service": ComplianceService(),
        "swedish_integration_service": SwedishIntegrationService()
    }


@register("svea.coordinator")
def build_svea_coordinator():
    """Factory function for Agent Svea Coordinator."""
    services = _create_services()
    return CoordinatorAgent(services=services)


@register("svea.architect")
def build_svea_architect():
    """Factory function for Agent Svea Architect."""
    services = _create_services()
    return ArchitectAgent(services=services)


@register("svea.implementation")
def build_svea_implementation():
    """Factory function for Agent Svea Implementation."""
    services = _create_services()
    return ImplementationAgent(services=services)


@register("svea.product_manager")
def build_svea_product_manager():
    """Factory function for Agent Svea Product Manager."""
    services = _create_services()
    return ProductManagerAgent(services=services)


@register("svea.quality_assurance")
def build_svea_quality_assurance():
    """Factory function for Agent Svea Quality Assurance."""
    services = _create_services()
    return QualityAssuranceAgent(services=services)