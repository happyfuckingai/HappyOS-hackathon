"""
Unified service facades.

Stub implementation for testing purposes.
"""

from typing import Dict, Any


class UnifiedServiceFacades:
    """Unified service facades for AWS and local services."""
    
    def __init__(self, config):
        self.config = config
    
    async def get_service(self, service_name: str) -> Any:
        """Get service instance."""
        return MockService(service_name)


class MockService:
    """Mock service for testing."""
    
    def __init__(self, name: str):
        self.name = name
    
    async def call(self, method: str, **kwargs) -> Dict[str, Any]:
        """Mock service call."""
        return {"status": "success", "service": self.name, "method": method}