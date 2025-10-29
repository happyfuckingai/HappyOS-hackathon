"""
Observability middleware for integrating CloudWatch, X-Ray, and audit logging.
"""

import time
import asyncio
from typing import Callable, Optional
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from .cloudwatch import get_cloudwatch_monitor, MetricUnit
from .xray_tracing import get_xray_tracer, XRaySegmentContext
from .audit_logger import get_audit_logger, AuditEventType, AuditSeverity
from backend.services.observability.logger import get_logger


class ObservabilityMiddleware(BaseHTTPMiddleware):
    """Middleware to integrate all observability components."""
    
    def __init__(self, app):
        super().__init__(app)
        self.logger = get_logger(__name__)
        self.cloudwatch = get_cloudwatch_monitor()
        self.xray_tracer = get_xray_tracer()
        self.audit_logger = get_audit_logger()
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request with full observability integration."""
        start_time = time.time()
        
        # Extract context information
        method = request.method
        path = request.url.path
        client_ip = self._get_client_ip(request)
        user_agent = request.headers.get("user-agent", "")
        
        # Extract tenant context from path or headers
        tenant_id = self._extract_tenant_id(request)
        session_id = self._extract_session_id(request)
        agent_id = self._extract_agent_id(request)
        
        # Start X-Ray segment
        segment_name = f"{method} {path}"
        with XRaySegmentContext(
            segment_name,
            self.xray_tracer,
            tenant_id=tenant_id,
            session_id=session_id,
            agent_id=agent_id,
            http_method=method,
            http_path=path,
            client_ip=client_ip
        ) as trace_context:
            
            try:
                # Process request
                response = await call_next(request)
                
                # Calculate duration
                duration_ms = (time.time() - start_time) * 1000
                
                # Record successful metrics
                await self._record_success_metrics(
                    method, path, response.status_code, duration_ms,
                    tenant_id, session_id, agent_id
                )
                
                # Log audit event for sensitive operations
                if self._is_sensitive_operation(method, path):
                    await self._log_audit_event(
                        request, response, duration_ms,
                        tenant_id, session_id, agent_id,
                        trace_context.correlation_id, client_ip, user_agent
                    )
                
                return response
                
            except Exception as e:
                # Calculate duration for error case
                duration_ms = (time.time() - start_time) * 1000
                
                # Record error metrics
                await self._record_error_metrics(
                    method, path, str(e), duration_ms,
                    tenant_id, session_id, agent_id
                )
                
                # Log error audit event
                await self._log_error_audit_event(
                    request, e, duration_ms,
                    tenant_id, session_id, agent_id,
                    trace_context.correlation_id, client_ip, user_agent
                )
                
                # Re-raise exception
                raise
    
    def _get_client_ip(self, request: Request) -> str:
        """Extract client IP address from request."""
        # Check for forwarded headers first
        forwarded_for = request.headers.get("x-forwarded-for")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()
        
        real_ip = request.headers.get("x-real-ip")
        if real_ip:
            return real_ip
        
        # Fallback to direct client
        if hasattr(request, "client") and request.client:
            return request.client.host
        
        return "unknown"
    
    def _extract_tenant_id(self, request: Request) -> Optional[str]:
        """Extract tenant ID from request path or headers."""
        # Check path for tenant-specific routes
        path_parts = request.url.path.strip("/").split("/")
        
        # Look for tenant in MCP UI routes
        if "mcp-ui" in path_parts:
            # Check query parameters
            tenant_id = request.query_params.get("tenantId")
            if tenant_id:
                return tenant_id
        
        # Check headers
        tenant_header = request.headers.get("x-tenant-id")
        if tenant_header:
            return tenant_header
        
        # Try to extract from JWT token (would need JWT parsing)
        # For now, return None
        return None
    
    def _extract_session_id(self, request: Request) -> Optional[str]:
        """Extract session ID from request."""
        # Check query parameters
        session_id = request.query_params.get("sessionId")
        if session_id:
            return session_id
        
        # Check headers
        session_header = request.headers.get("x-session-id")
        if session_header:
            return session_header
        
        return None
    
    def _extract_agent_id(self, request: Request) -> Optional[str]:
        """Extract agent ID from request."""
        # Check query parameters
        agent_id = request.query_params.get("agentId")
        if agent_id:
            return agent_id
        
        # Check headers
        agent_header = request.headers.get("x-agent-id")
        if agent_header:
            return agent_header
        
        return None
    
    async def _record_success_metrics(
        self,
        method: str,
        path: str,
        status_code: int,
        duration_ms: float,
        tenant_id: str = None,
        session_id: str = None,
        agent_id: str = None
    ):
        """Record successful request metrics."""
        try:
            # CloudWatch metrics
            dimensions = {
                "Method": method,
                "Path": self._normalize_path(path),
                "StatusCode": str(status_code)
            }
            
            await self.cloudwatch.put_metric(
                "HTTPRequests",
                1,
                MetricUnit.COUNT,
                dimensions,
                tenant_id
            )
            
            await self.cloudwatch.put_metric(
                "HTTPRequestDuration",
                duration_ms,
                MetricUnit.MILLISECONDS,
                dimensions,
                tenant_id
            )
            
            # Record specific operation metrics for MCP UI routes
            if "/mcp-ui/" in path and tenant_id:
                operation = self._extract_operation_from_path(method, path)
                if operation:
                    await self.cloudwatch.record_resource_operation(
                        operation, tenant_id, session_id or "unknown",
                        agent_id or "unknown", duration_ms, True
                    )
            
        except Exception as e:
            self.logger.error(f"Failed to record success metrics: {e}")
    
    async def _record_error_metrics(
        self,
        method: str,
        path: str,
        error: str,
        duration_ms: float,
        tenant_id: str = None,
        session_id: str = None,
        agent_id: str = None
    ):
        """Record error request metrics."""
        try:
            # CloudWatch error metrics
            await self.cloudwatch.record_error_metrics(
                error_type=type(error).__name__ if isinstance(error, Exception) else "HTTPError",
                component="api",
                tenant_id=tenant_id,
                severity="error"
            )
            
            # HTTP error metrics
            dimensions = {
                "Method": method,
                "Path": self._normalize_path(path),
                "ErrorType": type(error).__name__ if isinstance(error, Exception) else "HTTPError"
            }
            
            await self.cloudwatch.put_metric(
                "HTTPErrors",
                1,
                MetricUnit.COUNT,
                dimensions,
                tenant_id
            )
            
        except Exception as e:
            self.logger.error(f"Failed to record error metrics: {e}")
    
    def _normalize_path(self, path: str) -> str:
        """Normalize path for metrics (remove IDs and parameters)."""
        # Replace UUIDs and IDs with placeholders
        import re
        
        # Replace UUID patterns
        path = re.sub(r'/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}', '/{id}', path)
        
        # Replace numeric IDs
        path = re.sub(r'/\d+', '/{id}', path)
        
        # Replace resource IDs (mm://...)
        path = re.sub(r'/mm%3A%2F%2F[^/]+', '/{resource_id}', path)
        
        return path
    
    def _extract_operation_from_path(self, method: str, path: str) -> Optional[str]:
        """Extract operation type from HTTP method and path."""
        if "/mcp-ui/resources" in path:
            if method == "POST":
                return "create"
            elif method == "PATCH":
                return "update"
            elif method == "DELETE":
                return "delete"
            elif method == "GET":
                return "read"
        
        return None
    
    def _is_sensitive_operation(self, method: str, path: str) -> bool:
        """Determine if operation should be audited."""
        sensitive_paths = [
            "/mcp-ui/resources",
            "/auth/",
            "/admin/",
            "/observability/"
        ]
        
        return any(sensitive_path in path for sensitive_path in sensitive_paths)
    
    async def _log_audit_event(
        self,
        request: Request,
        response: Response,
        duration_ms: float,
        tenant_id: str = None,
        session_id: str = None,
        agent_id: str = None,
        correlation_id: str = None,
        client_ip: str = None,
        user_agent: str = None
    ):
        """Log successful operation audit event."""
        try:
            operation = self._extract_operation_from_path(request.method, request.url.path)
            
            if operation and "/mcp-ui/resources" in request.url.path:
                # Extract resource ID from path or response
                resource_id = self._extract_resource_id_from_request(request)
                
                await self.audit_logger.log_resource_operation(
                    operation=operation,
                    resource_id=resource_id or "unknown",
                    tenant_id=tenant_id or "unknown",
                    session_id=session_id,
                    agent_id=agent_id,
                    success=True,
                    duration_ms=duration_ms,
                    correlation_id=correlation_id,
                    details={
                        "method": request.method,
                        "path": request.url.path,
                        "status_code": response.status_code,
                        "client_ip": client_ip,
                        "user_agent": user_agent
                    }
                )
            
        except Exception as e:
            self.logger.error(f"Failed to log audit event: {e}")
    
    async def _log_error_audit_event(
        self,
        request: Request,
        error: Exception,
        duration_ms: float,
        tenant_id: str = None,
        session_id: str = None,
        agent_id: str = None,
        correlation_id: str = None,
        client_ip: str = None,
        user_agent: str = None
    ):
        """Log error operation audit event."""
        try:
            await self.audit_logger.log_security_event(
                event_type=AuditEventType.SYSTEM_ERROR,
                message=f"HTTP request failed: {request.method} {request.url.path}",
                severity=AuditSeverity.MEDIUM,
                tenant_id=tenant_id,
                client_ip=client_ip,
                correlation_id=correlation_id,
                details={
                    "method": request.method,
                    "path": request.url.path,
                    "error_type": type(error).__name__,
                    "error_message": str(error),
                    "duration_ms": duration_ms,
                    "user_agent": user_agent
                }
            )
            
        except Exception as e:
            self.logger.error(f"Failed to log error audit event: {e}")
    
    def _extract_resource_id_from_request(self, request: Request) -> Optional[str]:
        """Extract resource ID from request path or body."""
        # Try to extract from path
        path_parts = request.url.path.split("/")
        for part in path_parts:
            if part.startswith("mm%3A%2F%2F") or part.startswith("mm://"):
                return part
        
        # Could also extract from request body for POST requests
        # But that would require reading the body, which might interfere with the actual handler
        
        return None