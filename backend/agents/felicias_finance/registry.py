"""
Felicia's Finance Registry

Registers all Felicia's Finance ADK agents with the global registry.
This file handles backend imports so ADK agents stay clean.
"""

try:
    from backend.core.registry.agents import register
except ImportError:
    from core.registry.agents import register


# Simple agent classes for registration
class SimpleAgent:
    """Simple agent implementation for registry purposes."""
    def __init__(self, role: str, domain: str = "felicia"):
        self.role = role
        self.domain = domain
        self.name = f"{domain}.{role}"
    
    def __repr__(self):
        return f"<{self.__class__.__name__}({self.name})>"


class CoordinatorAgent(SimpleAgent):
    def __init__(self):
        super().__init__("coordinator")


class ArchitectAgent(SimpleAgent):
    def __init__(self):
        super().__init__("architect")


class ImplementationAgent(SimpleAgent):
    def __init__(self):
        super().__init__("implementation")


class ProductManagerAgent(SimpleAgent):
    def __init__(self):
        super().__init__("product_manager")


class QualityAssuranceAgent(SimpleAgent):
    def __init__(self):
        super().__init__("quality_assurance")


@register("felicia.coordinator")
def build_felicia_coordinator():
    """Factory function for Felicia's Finance Coordinator."""
    return CoordinatorAgent()


@register("felicia.architect")
def build_felicia_architect():
    """Factory function for Felicia's Finance Architect."""
    return ArchitectAgent()


@register("felicia.implementation")
def build_felicia_implementation():
    """Factory function for Felicia's Finance Implementation."""
    return ImplementationAgent()


@register("felicia.product_manager")
def build_felicia_product_manager():
    """Factory function for Felicia's Finance Product Manager."""
    return ProductManagerAgent()


@register("felicia.quality_assurance")
def build_felicia_quality_assurance():
    """Factory function for Felicia's Finance Quality Assurance."""
    return QualityAssuranceAgent()