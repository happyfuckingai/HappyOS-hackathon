"""
Authentication Dependencies for FastAPI

Provides dependency functions for JWT authentication and tenant validation.
Used by API endpoints to enforce authentication and authorization.

Requirements: 6.1, 6.4
"""

import logging
from typing import Optional

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from .jwt_service import JWTClaims, JWTService

logger = logging.getLogger(__name__)

# HTTP Bearer security scheme
security = HTTPBearer(auto_error=False)


class AuthenticationError(HTTPException):
    """Custom authentication error"""
    def __init__(self, detail: str = "Authentication failed"):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=detail,
            headers={"WWW-Authenticate": "Bearer"}
        )


class AuthorizationError(HTTPException):
    """Custom authorization error"""
    def __init__(self, detail: str = "Insufficient permissions"):
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=detail
        )


def get_jwt_claims(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
) -> JWTClaims:
    """
    Extract and validate JWT claims from Authorization header
    
    Args:
        credentials: HTTP Bearer credentials
        
    Returns:
        JWTClaims object
        
    Raises:
        AuthenticationError: If token is missing or invalid
    """
    if not credentials:
        raise AuthenticationError("Missing authorization token")
    
    token = credentials.credentials
    claims = JWTService.verify_token(token)
    
    if not claims:
        raise AuthenticationError("Invalid or expired token")
    
    return claims


def get_optional_jwt_claims(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
) -> Optional[JWTClaims]:
    """
    Extract JWT claims if present, return None if not authenticated
    
    Args:
        credentials: HTTP Bearer credentials
        
    Returns:
        JWTClaims object or None
    """
    if not credentials:
        return None
    
    token = credentials.credentials
    return JWTService.verify_token(token)


def require_scope(required_scope: str):
    """
    Dependency factory for requiring specific scopes
    
    Args:
        required_scope: Required scope string
        
    Returns:
        Dependency function
    """
    def scope_dependency(claims: JWTClaims = Depends(get_jwt_claims)) -> JWTClaims:
        if not claims.has_scope(required_scope):
            raise AuthorizationError(f"Missing required scope: {required_scope}")
        return claims
    
    return scope_dependency


def require_tenant_access(tenant_id: str, operation: str = "read"):
    """
    Dependency factory for requiring tenant access
    
    Args:
        tenant_id: Tenant ID to check
        operation: Operation type (read/write)
        
    Returns:
        Dependency function
    """
    def tenant_dependency(claims: JWTClaims = Depends(get_jwt_claims)) -> JWTClaims:
        if not JWTService.validate_tenant_access(claims, tenant_id, operation):
            raise AuthorizationError(f"No {operation} access to tenant: {tenant_id}")
        return claims
    
    return tenant_dependency


def validate_tenant_from_path(
    tenant_id: str,
    claims: JWTClaims = Depends(get_jwt_claims)
) -> JWTClaims:
    """
    Validate that JWT token has access to tenant from path parameter
    
    Args:
        tenant_id: Tenant ID from path parameter
        claims: JWT claims
        
    Returns:
        JWTClaims object
        
    Raises:
        AuthorizationError: If no access to tenant
    """
    if not JWTService.validate_tenant_access(claims, tenant_id, "read"):
        raise AuthorizationError(f"No access to tenant: {tenant_id}")
    
    return claims


def validate_ui_write_access(
    tenant_id: str,
    session_id: str,
    claims: JWTClaims = Depends(get_jwt_claims)
) -> JWTClaims:
    """
    Validate UI write access for specific tenant and session
    
    Args:
        tenant_id: Tenant ID
        session_id: Session ID
        claims: JWT claims
        
    Returns:
        JWTClaims object
        
    Raises:
        AuthorizationError: If no write access
    """
    required_scope = f"ui:write:{tenant_id}:{session_id}"
    if not claims.has_scope(required_scope):
        # Check wildcard scope
        wildcard_scope = f"ui:write:{tenant_id}:*"
        if not claims.has_scope(wildcard_scope):
            raise AuthorizationError(f"No write access to {tenant_id}/{session_id}")
    
    return claims


def validate_ui_read_access(
    tenant_id: str,
    session_id: str,
    claims: JWTClaims = Depends(get_jwt_claims)
) -> JWTClaims:
    """
    Validate UI read access for specific tenant and session
    
    Args:
        tenant_id: Tenant ID
        session_id: Session ID
        claims: JWT claims
        
    Returns:
        JWTClaims object
        
    Raises:
        AuthorizationError: If no read access
    """
    required_scope = f"ui:read:{tenant_id}:{session_id}"
    if not claims.has_scope(required_scope):
        # Check wildcard scope
        wildcard_scope = f"ui:read:{tenant_id}:*"
        if not claims.has_scope(wildcard_scope):
            raise AuthorizationError(f"No read access to {tenant_id}/{session_id}")
    
    return claims


def get_agent_info(claims: JWTClaims = Depends(get_jwt_claims)) -> dict:
    """
    Extract agent information from JWT claims
    
    Args:
        claims: JWT claims
        
    Returns:
        Dictionary with agent information
    """
    return {
        "agent_id": claims.agentId,
        "tenant_id": claims.tenantId,
        "session_id": claims.sessionId,
        "subject": claims.sub,
        "scopes": claims.scopes
    }


def require_agent_token(claims: JWTClaims = Depends(get_jwt_claims)) -> JWTClaims:
    """
    Require that the token is an agent token
    
    Args:
        claims: JWT claims
        
    Returns:
        JWTClaims object
        
    Raises:
        AuthorizationError: If not an agent token
    """
    if not claims.sub.startswith("agent-"):
        raise AuthorizationError("Agent token required")
    
    if not claims.agentId:
        raise AuthorizationError("Missing agent ID in token")
    
    return claims


class TenantValidator:
    """Helper class for tenant validation"""
    
    @staticmethod
    def validate_resource_access(
        claims: JWTClaims,
        resource_tenant_id: str,
        resource_session_id: str,
        operation: str = "read"
    ) -> bool:
        """
        Validate access to a specific resource
        
        Args:
            claims: JWT claims
            resource_tenant_id: Resource tenant ID
            resource_session_id: Resource session ID
            operation: Operation type (read/write)
            
        Returns:
            True if access is granted
        """
        required_scope = f"ui:{operation}:{resource_tenant_id}:{resource_session_id}"
        
        # Check exact scope
        if claims.has_scope(required_scope):
            return True
        
        # Check wildcard scopes
        wildcard_scopes = [
            f"ui:{operation}:{resource_tenant_id}:*",
            f"ui:{operation}:*:*"
        ]
        
        for scope in wildcard_scopes:
            if claims.has_scope(scope):
                return True
        
        return False
    
    @staticmethod
    def get_accessible_tenants(claims: JWTClaims) -> list:
        """
        Get list of tenants accessible by the token
        
        Args:
            claims: JWT claims
            
        Returns:
            List of tenant IDs
        """
        tenants = set()
        
        for scope in claims.scopes:
            parts = scope.split(":")
            if len(parts) >= 3 and parts[0] == "ui":
                tenant_id = parts[2]
                if tenant_id != "*":
                    tenants.add(tenant_id)
        
        return list(tenants)


# Global validator instance
tenant_validator = TenantValidator()