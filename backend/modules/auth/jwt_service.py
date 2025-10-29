"""
JWT Authentication Service with Tenant Scoping

Implements JWT token validation with tenant-specific scopes for MCP UI Hub.
Supports multi-tenant access control with scopes like:
- ui:read:{tenantId}:{sessionId}
- ui:write:{tenantId}:{sessionId}
- ui:read:{tenantId}:*
- ui:write:{tenantId}:*

Requirements: 6.1, 6.4
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Set
from uuid import uuid4

from jose import JWTError, jwt
from pydantic import BaseModel, Field

from ..config.settings import settings

logger = logging.getLogger(__name__)


class JWTClaims(BaseModel):
    """JWT token claims with tenant scoping"""
    sub: str = Field(..., description="Subject (user/agent ID)")
    iss: str = Field(default="meetmind-auth", description="Issuer")
    aud: str = Field(default="mcp-ui-hub", description="Audience")
    exp: int = Field(..., description="Expiration timestamp")
    iat: int = Field(..., description="Issued at timestamp")
    scopes: List[str] = Field(default_factory=list, description="Access scopes")
    tenantId: Optional[str] = Field(None, description="Primary tenant ID")
    agentId: Optional[str] = Field(None, description="Agent ID")
    sessionId: Optional[str] = Field(None, description="Session ID")
    
    def has_scope(self, required_scope: str) -> bool:
        """Check if token has required scope"""
        return JWTService.verify_scope(self.scopes, required_scope)
    
    def get_tenant_scopes(self, tenant_id: str) -> List[str]:
        """Get all scopes for a specific tenant"""
        return [scope for scope in self.scopes if f":{tenant_id}:" in scope or scope.endswith(f":{tenant_id}:*")]


class TokenType:
    """Token type constants"""
    ACCESS = "access"
    REFRESH = "refresh"
    AGENT = "agent"


class JWTService:
    """JWT service with tenant-aware scope validation"""
    
    @staticmethod
    def create_access_token(
        subject: str,
        scopes: List[str],
        tenant_id: Optional[str] = None,
        agent_id: Optional[str] = None,
        session_id: Optional[str] = None,
        expires_delta: Optional[timedelta] = None
    ) -> str:
        """
        Create JWT access token with tenant scoping
        
        Args:
            subject: User or agent identifier
            scopes: List of access scopes
            tenant_id: Primary tenant ID
            agent_id: Agent identifier
            session_id: Session identifier
            expires_delta: Custom expiration time
            
        Returns:
            Encoded JWT token
        """
        if expires_delta:
            expire = datetime.now(timezone.utc) + expires_delta
        else:
            expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        
        claims = {
            "sub": subject,
            "iss": "meetmind-auth",
            "aud": "mcp-ui-hub",
            "exp": int(expire.timestamp()),
            "iat": int(datetime.now(timezone.utc).timestamp()),
            "type": TokenType.ACCESS,
            "scopes": scopes
        }
        
        # Add optional claims
        if tenant_id:
            claims["tenantId"] = tenant_id
        if agent_id:
            claims["agentId"] = agent_id
        if session_id:
            claims["sessionId"] = session_id
        
        try:
            return jwt.encode(claims, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
        except Exception as e:
            logger.error(f"Failed to create access token: {e}")
            raise ValueError("Token creation failed")
    
    @staticmethod
    def create_agent_token(
        agent_id: str,
        tenant_id: str,
        session_id: str,
        permissions: List[str] = None,
        expires_delta: Optional[timedelta] = None
    ) -> str:
        """
        Create JWT token for MCP agents with tenant-specific scopes
        
        Args:
            agent_id: Agent identifier
            tenant_id: Tenant identifier
            session_id: Session identifier
            permissions: List of permissions (read, write)
            expires_delta: Custom expiration time
            
        Returns:
            Encoded JWT token
        """
        if permissions is None:
            permissions = ["read", "write"]
        
        # Generate tenant-specific scopes
        scopes = []
        for permission in permissions:
            scopes.append(f"ui:{permission}:{tenant_id}:{session_id}")
        
        if expires_delta:
            expire = datetime.now(timezone.utc) + expires_delta
        else:
            expire = datetime.now(timezone.utc) + timedelta(hours=24)  # Longer for agents
        
        claims = {
            "sub": f"agent-{agent_id}",
            "iss": "meetmind-auth",
            "aud": "mcp-ui-hub",
            "exp": int(expire.timestamp()),
            "iat": int(datetime.now(timezone.utc).timestamp()),
            "type": TokenType.AGENT,
            "scopes": scopes,
            "tenantId": tenant_id,
            "agentId": agent_id,
            "sessionId": session_id
        }
        
        try:
            return jwt.encode(claims, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
        except Exception as e:
            logger.error(f"Failed to create agent token: {e}")
            raise ValueError("Agent token creation failed")
    
    @staticmethod
    def verify_token(token: str) -> Optional[JWTClaims]:
        """
        Verify JWT token and return claims
        
        Args:
            token: JWT token to verify
            
        Returns:
            JWTClaims if valid, None if invalid
        """
        try:
            # Decode without audience verification for now (can be enabled in production)
            payload = jwt.decode(
                token, 
                settings.SECRET_KEY, 
                algorithms=[settings.ALGORITHM],
                options={"verify_aud": False}  # Disable audience verification for development
            )
            
            # Validate required fields
            if not payload.get("sub") or not payload.get("exp"):
                logger.warning("Token missing required fields")
                return None
            
            # Check expiration
            exp_timestamp = payload.get("exp")
            if datetime.now(timezone.utc).timestamp() > exp_timestamp:
                logger.warning("Token has expired")
                return None
            
            # Create claims object
            return JWTClaims(**payload)
            
        except JWTError as e:
            logger.warning(f"JWT verification failed: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error verifying token: {e}")
            return None
    
    @staticmethod
    def verify_scope(token_scopes: List[str], required_scope: str) -> bool:
        """
        Verify JWT token has required scope with wildcard support
        
        Args:
            token_scopes: List of scopes from token
            required_scope: Required scope to check
            
        Returns:
            True if scope is granted, False otherwise
        """
        # Check exact scope match
        if required_scope in token_scopes:
            return True
        
        # Check wildcard scopes
        scope_parts = required_scope.split(":")
        if len(scope_parts) == 4:
            operation, resource, tenant_id, session_id = scope_parts
            
            # Check tenant wildcard: ui:read:tenant:*
            tenant_wildcard = f"{operation}:{resource}:{tenant_id}:*"
            if tenant_wildcard in token_scopes:
                return True
            
            # Check global wildcard: ui:read:*:*
            global_wildcard = f"{operation}:{resource}:*:*"
            if global_wildcard in token_scopes:
                return True
        
        return False
    
    @staticmethod
    def extract_tenant_from_scope(scope: str) -> Optional[str]:
        """
        Extract tenant ID from scope string
        
        Args:
            scope: Scope string like "ui:read:tenant:session"
            
        Returns:
            Tenant ID if found, None otherwise
        """
        parts = scope.split(":")
        if len(parts) >= 3 and parts[0] == "ui":
            return parts[2] if parts[2] != "*" else None
        return None
    
    @staticmethod
    def get_tenant_scopes(token_scopes: List[str], tenant_id: str) -> List[str]:
        """
        Get all scopes for a specific tenant
        
        Args:
            token_scopes: List of all token scopes
            tenant_id: Tenant ID to filter by
            
        Returns:
            List of scopes for the tenant
        """
        tenant_scopes = []
        for scope in token_scopes:
            if f":{tenant_id}:" in scope or scope.endswith(f":{tenant_id}:*"):
                tenant_scopes.append(scope)
        return tenant_scopes
    
    @staticmethod
    def validate_tenant_access(claims: JWTClaims, tenant_id: str, operation: str = "read") -> bool:
        """
        Validate that token has access to specific tenant
        
        Args:
            claims: JWT claims
            tenant_id: Tenant ID to check
            operation: Operation type (read/write)
            
        Returns:
            True if access is granted, False otherwise
        """
        # Check if token has tenant-specific scopes
        tenant_scopes = claims.get_tenant_scopes(tenant_id)
        if not tenant_scopes:
            return False
        
        # Check for specific operation
        required_patterns = [
            f"ui:{operation}:{tenant_id}:",
            f"ui:{operation}:{tenant_id}:*",
            f"ui:{operation}:*:*"
        ]
        
        for scope in tenant_scopes:
            for pattern in required_patterns:
                if scope.startswith(pattern):
                    return True
        
        return False


class ScopeBuilder:
    """Helper class for building JWT scopes"""
    
    @staticmethod
    def ui_read_scope(tenant_id: str, session_id: str = "*") -> str:
        """Build UI read scope"""
        return f"ui:read:{tenant_id}:{session_id}"
    
    @staticmethod
    def ui_write_scope(tenant_id: str, session_id: str = "*") -> str:
        """Build UI write scope"""
        return f"ui:write:{tenant_id}:{session_id}"
    
    @staticmethod
    def agent_scopes(tenant_id: str, session_id: str = "*", permissions: List[str] = None) -> List[str]:
        """Build standard agent scopes"""
        if permissions is None:
            permissions = ["read", "write"]
        
        scopes = []
        for permission in permissions:
            scopes.append(f"ui:{permission}:{tenant_id}:{session_id}")
        
        return scopes
    
    @staticmethod
    def admin_scopes(tenant_id: str = "*") -> List[str]:
        """Build admin scopes for tenant management"""
        return [
            f"ui:read:{tenant_id}:*",
            f"ui:write:{tenant_id}:*",
            f"admin:manage:{tenant_id}:*"
        ]


class TokenRefreshService:
    """Service for token refresh and rotation"""
    
    def __init__(self):
        self._refresh_tokens: Dict[str, Dict] = {}  # In-memory store for demo
    
    def create_refresh_token(self, subject: str, tenant_id: str) -> str:
        """Create refresh token"""
        jti = str(uuid4())
        expire = datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
        
        refresh_data = {
            "subject": subject,
            "tenant_id": tenant_id,
            "expires_at": expire,
            "revoked": False
        }
        
        self._refresh_tokens[jti] = refresh_data
        
        claims = {
            "sub": subject,
            "jti": jti,
            "exp": int(expire.timestamp()),
            "iat": int(datetime.now(timezone.utc).timestamp()),
            "type": TokenType.REFRESH,
            "tenantId": tenant_id
        }
        
        return jwt.encode(claims, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    
    def refresh_access_token(self, refresh_token: str, new_scopes: List[str]) -> Optional[str]:
        """Refresh access token using refresh token"""
        try:
            payload = jwt.decode(refresh_token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
            
            if payload.get("type") != TokenType.REFRESH:
                return None
            
            jti = payload.get("jti")
            if not jti or jti not in self._refresh_tokens:
                return None
            
            refresh_data = self._refresh_tokens[jti]
            if refresh_data["revoked"] or refresh_data["expires_at"] < datetime.now(timezone.utc):
                return None
            
            # Create new access token
            return JWTService.create_access_token(
                subject=refresh_data["subject"],
                scopes=new_scopes,
                tenant_id=refresh_data["tenant_id"]
            )
            
        except Exception as e:
            logger.error(f"Token refresh failed: {e}")
            return None
    
    def revoke_refresh_token(self, refresh_token: str) -> bool:
        """Revoke refresh token"""
        try:
            payload = jwt.decode(refresh_token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
            jti = payload.get("jti")
            
            if jti and jti in self._refresh_tokens:
                self._refresh_tokens[jti]["revoked"] = True
                return True
            
            return False
            
        except Exception:
            return False


# Global services
jwt_service = JWTService()
token_refresh_service = TokenRefreshService()