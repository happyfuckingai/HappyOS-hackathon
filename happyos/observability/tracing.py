"""
Distributed tracing for HappyOS SDK.

Stub implementation for testing purposes.
"""

from typing import Dict, Any, Optional


class TracingManager:
    """Tracing manager."""
    
    def __init__(self, service_name: str):
        self.service_name = service_name
    
    def start_span(self, operation_name: str, parent_span: Optional[Any] = None) -> 'Span':
        """Start a new span."""
        return Span(operation_name)
    
    def inject_headers(self, span: 'Span') -> Dict[str, str]:
        """Inject tracing headers."""
        return {"trace-id": "test-trace-id"}


class Span:
    """Tracing span."""
    
    def __init__(self, operation_name: str):
        self.operation_name = operation_name
        self.tags = {}
    
    def set_tag(self, key: str, value: Any) -> None:
        """Set span tag."""
        self.tags[key] = value
    
    def finish(self) -> None:
        """Finish the span."""
        pass