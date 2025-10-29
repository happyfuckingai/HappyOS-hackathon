"""
Tenant Isolation Middleware

Enforces tenant isolation at the middleware level for all API requests.
Integrates with existing security middleware and provides comprehensive
tenant access control.

Requirements: 6.1, 6.2, 6.3, 6.5
"""

import logging
import time
from typing import Callable, Optional

from fastapi import Request, Response, HTTPException, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from ..modules.auth import get_jwt_claims, JWTClaims
from ..modules.auth.tenant_isolation import (
    tenant_isolation_service, audit_logger, TenantIsolationError, CrossTenantAccessError
)
from ..modules.auth.security_monitoring import (
    security_monitoring_service, ThreatType, AlertSeverity
)

logger = logging.getLogger(__name__)


class TenantIsolationMiddleware(BaseHTTPMiddleware):
    """
    Middleware for enforcing tenant isolation across all API endpoints
    
    Features:
    - Automatic tenant validation for all requests
    - Cross-tenant access prevention
    - Audit logging for all tenant operations
    - Integration with JWT authentication
    - Row-level security enforcement
    """
    
    def __init__(self, app):
        super().__init__(app)
        
        # Endpoints that require tenant isolation
        self.tenant_protected_paths = [
            "/mcp-ui/resources",
            "/mcp-ui/hydrate",
            "/mcp-ui/websocket"
        ]
        
        # Endpoints that bypass tenant isolation
        self.bypass_paths = [
            "/health",
            "/docs",
            "/openapi.json",
            "/mcp-ui/health",
            "/mcp-ui/tenants",
            "/mcp-ui/agents/register",
            "/mcp-ui/agents",
            "/auth/"
        ]
    
    def _should_enforce_tenant_isolation(self, path: str) -> bool:
        """Check if path requires tenant isolation"""
        # Skip bypass paths
        for bypass_path in self.bypass_paths:
            if path.startswith(bypass_path):
                return False
        
        # Check if path is tenant-protected
        for protected_path in self.tenant_protected_paths:
            if path.startswith(protected_path):
                return True
        
        return False
    
    def _extract_tenant_from_path(self, path: str) -> Optional[str]:
        """Extract tenant ID from URL path"""
        # Handle hydration endpoint: /mcp-ui/hydrate/{tenant_id}/{session_id}
        if "/hydrate/" in path:
            parts = path.split("/")
            if len(parts) >= 4 and parts[2] == "hydrate":
                return parts[3]
        
        return None
    
    def _extract_tenant_from_body(self, request: Request) -> Optional[str]:
        """Extract tenant ID from request body (for POST/PATCH requests)"""
        # This would need to be implemented based on request body parsing
        # For now, we'll rely on JWT claims and path parameters
        return None
    
    def _get_client_info(self, request: Request) -> tuple:
        """Extract client IP and user agent"""
        # Get client IP
        forwarded_for = request.headers.get("x-forwarded-for")
        if forwarded_for:
            client_ip = forwarded_for.split(",")[0].strip()
        else:
            client_ip = request.headers.get("x-real-ip") or str(request.client.host)
        
        # Get user agent
        user_agent = request.headers.get("user-agent")
        
        return client_ip, user_agent
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Main middleware dispatch method"""
        start_time = time.time()
        path = request.url.path
        
        # Skip if tenant isolation not required
        if not self._should_enforce_tenant_isolation(path):
            return await call_next(request)
        
        try:
            # Extract JWT claims
            auth_header = request.headers.get("authorization")
            if not auth_header or not auth_header.startswith("Bearer "):
                # Let the endpoint handle authentication
                return await call_next(request)
            
            token = auth_header.split(" ")[1]
            
            # Get JWT claims using existing auth system
            try:
                from ..modules.auth.jwt_service import JWTService
                claims = JWTService.verify_token(token)
                if not claims:
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail="Invalid or expired token"
                    )
            except Exception as e:
                logger.warning(f"JWT verification failed in tenant middleware: {e}")
                # Let the endpoint handle authentication
                return await call_next(request)
            
            # Extract tenant information
            tenant_from_path = self._extract_tenant_from_path(path)
            tenant_from_body = self._extract_tenant_from_body(request)
            tenant_from_jwt = claims.tenantId
            
            # Determine the tenant being accessed
            requested_tenant = tenant_from_path or tenant_from_body or tenant_from_jwt
            
            if not requested_tenant:
                # No tenant context, let endpoint handle
                return await call_next(request)
            
            # Get client information for audit logging
            client_ip, user_agent = self._get_client_info(request)
            
            # Check rate limits
            rate_limit_allowed, rate_limit_reason = security_monitoring_service.check_rate_limit(
                claims, path, client_ip
            )
            
            if not rate_limit_allowed:
                return JSONResponse(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    content={
                        "error": "rate_limit_exceeded",
                        "message": rate_limit_reason,
                        "retry_after": 60
                    },
                    headers={"Retry-After": "60"}
                )
            
            # Check if user is blocked
            if security_monitoring_service.is_user_blocked(claims.sub):
                security_monitoring_service.record_security_event(
                    threat_type=ThreatType.BRUTE_FORCE,
                    severity=AlertSeverity.HIGH,
                    user_id=claims.sub,
                    tenant_id=requested_tenant,
                    ip_address=client_ip,
                    user_agent=user_agent,
                    details={"action": "blocked_user_access_attempt", "path": path}
                )
                
                return JSONResponse(
                    status_code=status.HTTP_403_FORBIDDEN,
                    content={
                        "error": "user_blocked",
                        "message": "User is temporarily blocked due to security violations"
                    }
                )
            
            # Validate tenant access
            try:
                # Determine operation type
                operation = "write" if request.method in ["POST", "PUT", "PATCH", "DELETE"] else "read"
                
                # Use session from JWT or wildcard
                session_id = claims.sessionId or "*"
                
                # Validate access
                tenant_isolation_service.validate_tenant_access(
                    claims=claims,
                    requested_tenant=requested_tenant,
                    session_id=session_id,
                    operation=operation,
                    ip_address=client_ip,
                    user_agent=user_agent
                )
                
                # Store tenant info in request state for use by endpoints
                request.state.tenant_id = requested_tenant
                request.state.jwt_claims = claims
                request.state.client_ip = client_ip
                
            except CrossTenantAccessError as e:
                # Record security event
                security_monitoring_service.record_security_event(
                    threat_type=ThreatType.CROSS_TENANT_ACCESS,
                    severity=AlertSeverity.HIGH,
                    user_id=claims.sub,
                    tenant_id=requested_tenant,
                    ip_address=client_ip,
                    user_agent=user_agent,
                    details={
                        "user_tenant": e.user_tenant,
                        "requested_tenant": e.tenant_id,
                        "path": path,
                        "method": request.method
                    }
                )
                
                # Log security incident
                audit_logger.log_tenant_operation(
                    operation="cross_tenant_access_attempt",
                    tenant_id=requested_tenant,
                    user_id=claims.sub,
                    details={
                        "user_tenant": e.user_tenant,
                        "requested_tenant": e.tenant_id,
                        "path": path,
                        "method": request.method,
                        "ip_address": client_ip,
                        "user_agent": user_agent
                    },
                    success=False
                )
                
                return JSONResponse(
                    status_code=status.HTTP_403_FORBIDDEN,
                    content={
                        "error": "cross_tenant_access_denied",
                        "message": "Cross-tenant access is not allowed",
                        "user_tenant": e.user_tenant,
                        "requested_tenant": e.tenant_id
                    }
                )
            
            except TenantIsolationError as e:
                # Record security event
                security_monitoring_service.record_security_event(
                    threat_type=ThreatType.PRIVILEGE_ESCALATION,
                    severity=AlertSeverity.MEDIUM,
                    user_id=claims.sub,
                    tenant_id=requested_tenant,
                    ip_address=client_ip,
                    user_agent=user_agent,
                    details={
                        "reason": str(e),
                        "path": path,
                        "method": request.method
                    }
                )
                
                # Log access denial
                audit_logger.log_tenant_operation(
                    operation="tenant_access_denied",
                    tenant_id=requested_tenant,
                    user_id=claims.sub,
                    details={
                        "reason": str(e),
                        "path": path,
                        "method": request.method,
                        "ip_address": client_ip,
                        "user_agent": user_agent
                    },
                    success=False
                )
                
                return JSONResponse(
                    status_code=status.HTTP_403_FORBIDDEN,
                    content={
                        "error": "tenant_access_denied",
                        "message": str(e),
                        "tenant_id": e.tenant_id
                    }
                )
            
            # Process the request
            response = await call_next(request)
            
            # Log successful tenant operation
            response_time = time.time() - start_time
            
            audit_logger.log_tenant_operation(
                operation=f"{request.method.lower()}_{path.split('/')[-1] if '/' in path else path}",
                tenant_id=requested_tenant,
                user_id=claims.sub,
                details={
                    "path": path,
                    "method": request.method,
                    "response_status": response.status_code,
                    "response_time": response_time,
                    "ip_address": client_ip
                },
                success=response.status_code < 400
            )
            
            # Add tenant isolation headers
            response.headers["X-Tenant-ID"] = requested_tenant
            response.headers["X-Tenant-Isolation"] = "enforced"
            
            return response
            
        except HTTPException:
            # Re-raise HTTP exceptions
            raise
        except Exception as e:
            logger.error(f"Tenant isolation middleware error: {e}")
            
            # Log the error
            response_time = time.time() - start_time
            audit_logger.log_tenant_operation(
                operation="middleware_error",
                tenant_id="unknown",
                user_id="unknown",
                details={
                    "error": str(e),
                    "path": path,
                    "method": request.method,
                    "response_time": response_time
                },
                success=False
            )
            
            # Return generic error
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={
                    "error": "tenant_isolation_error",
                    "message": "Tenant isolation check failed"
                }
            )


class DynamoDBRowLevelSecurity:
    """Helper class for DynamoDB row-level security"""
    
    @staticmethod
    def validate_partition_key_access(
        partition_key: str,
        claims: JWTClaims,
        operation: str = "read"
    ) -> bool:
        """
        Validate that user can access the partition key
        
        Args:
            partition_key: DynamoDB partition key (format: tenantId#sessionId)
            claims: JWT claims
            operation: Operation type
            
        Returns:
            True if access is allowed
            
        Raises:
            TenantIsolationError: If access is denied
        """
        from ..modules.auth.tenant_isolation import DynamoDBTenantIsolation
        
        # Extract tenant from partition key
        tenant_id = DynamoDBTenantIsolation.extract_tenant_from_partition_key(partition_key)
        
        if not tenant_id:
            raise TenantIsolationError("Invalid partition key format", "unknown", claims.sub)
        
        # Validate tenant access
        return tenant_isolation_service.validate_tenant_access(
            claims=claims,
            requested_tenant=tenant_id,
            session_id="*",  # Session is embedded in partition key
            operation=operation
        )
    
    @staticmethod
    def build_tenant_filter_expression(claims: JWTClaims) -> dict:
        """
        Build DynamoDB filter expression for tenant isolation
        
        Args:
            claims: JWT claims
            
        Returns:
            Dictionary with filter expression components
        """
        accessible_tenants = tenant_isolation_service.get_accessible_tenants(claims)
        
        if not accessible_tenants:
            # No accessible tenants
            return {
                "FilterExpression": "attribute_not_exists(PK)",  # Never matches
                "ExpressionAttributeNames": {},
                "ExpressionAttributeValues": {}
            }
        
        if len(accessible_tenants) == 1:
            # Single tenant filter
            tenant_id = accessible_tenants[0]
            return {
                "FilterExpression": "begins_with(PK, :tenant_prefix)",
                "ExpressionAttributeNames": {},
                "ExpressionAttributeValues": {
                    ":tenant_prefix": f"{tenant_id}#"
                }
            }
        
        # Multiple tenants filter
        filter_conditions = []
        expression_values = {}
        
        for i, tenant_id in enumerate(accessible_tenants):
            filter_conditions.append(f"begins_with(PK, :tenant_prefix_{i})")
            expression_values[f":tenant_prefix_{i}"] = f"{tenant_id}#"
        
        return {
            "FilterExpression": " OR ".join(filter_conditions),
            "ExpressionAttributeNames": {},
            "ExpressionAttributeValues": expression_values
        }


def create_tenant_isolation_middleware(app):
    """Factory function to create tenant isolation middleware"""
    return TenantIsolationMiddleware(app)