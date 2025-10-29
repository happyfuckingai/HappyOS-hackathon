"""
MCP Security Middleware

Adapts existing A2A authentication patterns to MCP header-based security.
Reuses JWTAuthenticator, AuthToken, and AuthenticationManager classes
for MCP protocol with tenant-id, auth-sig, and caller headers.

Requirements: 7.1, 7.2
"""

import logging
import time
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple, Any
from uuid import uuid4

from pydantic import BaseModel, Field

from .mcp_tenant_isolation import MCPHeaders, MCPTenantIsolationService, mcp_tenant_isolation_service
from .mcp_security import MCPSigningService, MCPAuthenticationManager, mcp_signing_service, mcp_authentication_manager
from .mcp_audit_logging import MCPAuditLogger, MCPEventType, MCPAuditSeverity, mcp_audit_logger
from .jwt_service import JWTService, JWTClaims

logger = logging.getLogger(__name__)


class MCPAuthToken(BaseModel):
    """MCP authentication token adapted from A2A AuthToken"""
    token: str
    token_type: str = "MCP-JWT"
    expires_at: str
    agent_id: str
    tenant_id: str
    permissions: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    
    def is_expired(self) -> bool:
        """Check if token is expired"""
        expires_at = datetime.fromisoformat(self.expires_at.replace('Z', '+00:00'))
        return datetime.now(timezone.utc) > expires_at
    
    def has_permission(self, permission: str) -> bool:
        """Check if token has specific permission"""
        return permission in self.permissions


class MCPJWTAuthenticator:
    """MCP JWT authenticator adapted from A2A JWTAuthenticator"""
    
    def __init__(self, jwt_service: JWTService = None):
        self.jwt_service = jwt_service or JWTService()
        self._active_tokens: Dict[str, MCPAuthToken] = {}
    
    def create_mcp_token(
        self,
        agent_id: str,
        tenant_id: str,
        permissions: List[str],
        expires_in_hours: int = 24,
        metadata: Dict[str, Any] = None
    ) -> MCPAuthToken:
        """
        Create MCP JWT token for agent
        
        Args:
            agent_id: Agent identifier
            tenant_id: Tenant identifier
            permissions: List of permissions
            expires_in_hours: Token expiration in hours
            metadata: Additional metadata
            
        Returns:
            MCP authentication token
        """
        # Generate MCP-specific scopes
        scopes = []
        for permission in permissions:
            scopes.append(f"mcp:{permission}:{tenant_id}:*")
        
        # Add agent-specific scopes
        scopes.extend([
            f"agent:{agent_id}:call",
            f"agent:{agent_id}:callback"
        ])
        
        # Create JWT token
        jwt_token = self.jwt_service.create_access_token(
            subject=f"agent-{agent_id}",
            scopes=scopes,
            tenant_id=tenant_id,
            agent_id=agent_id,
            expires_delta=None  # Will use default from service
        )
        
        # Calculate expiration
        expires_at = datetime.now(timezone.utc).replace(microsecond=0)
        expires_at = expires_at.replace(hour=expires_at.hour + expires_in_hours)
        
        # Create MCP auth token
        mcp_token = MCPAuthToken(
            token=jwt_token,
            expires_at=expires_at.isoformat(),
            agent_id=agent_id,
            tenant_id=tenant_id,
            permissions=permissions,
            metadata=metadata or {}
        )
        
        # Cache token
        self._active_tokens[jwt_token] = mcp_token
        
        logger.debug(f"Created MCP token for agent {agent_id} tenant {tenant_id}")
        return mcp_token
    
    def validate_mcp_token(self, token: str) -> Optional[MCPAuthToken]:
        """
        Validate MCP JWT token
        
        Args:
            token: JWT token to validate
            
        Returns:
            MCP auth token if valid
        """
        # Check cache first
        if token in self._active_tokens:
            cached_token = self._active_tokens[token]
            if not cached_token.is_expired():
                return cached_token
            else:
                # Remove expired token
                del self._active_tokens[token]
        
        # Validate with JWT service
        claims = self.jwt_service.verify_token(token)
        if not claims:
            return None
        
        # Verify it's an agent token
        if not claims.sub.startswith("agent-"):
            return None
        
        # Extract agent ID
        agent_id = claims.agentId or claims.sub.replace("agent-", "")
        
        # Extract permissions from scopes
        permissions = []
        for scope in claims.scopes:
            if scope.startswith("mcp:"):
                parts = scope.split(":")
                if len(parts) >= 2:
                    permissions.append(parts[1])
        
        # Create MCP auth token
        mcp_token = MCPAuthToken(
            token=token,
            expires_at=datetime.fromtimestamp(claims.exp).isoformat(),
            agent_id=agent_id,
            tenant_id=claims.tenantId or "unknown",
            permissions=list(set(permissions)),  # Remove duplicates
            metadata={}
        )
        
        # Cache token
        self._active_tokens[token] = mcp_token
        
        return mcp_token
    
    def refresh_mcp_token(self, token: MCPAuthToken, expires_in_hours: int = 24) -> MCPAuthToken:
        """
        Refresh MCP token
        
        Args:
            token: Current MCP token
            expires_in_hours: New expiration in hours
            
        Returns:
            New MCP token
        """
        if token.is_expired():
            raise ValueError("Cannot refresh expired token")
        
        return self.create_mcp_token(
            agent_id=token.agent_id,
            tenant_id=token.tenant_id,
            permissions=token.permissions,
            expires_in_hours=expires_in_hours,
            metadata=token.metadata
        )


class MCPAuthenticationMiddleware:
    """MCP authentication middleware adapted from A2A AuthenticationManager"""
    
    def __init__(
        self,
        jwt_authenticator: MCPJWTAuthenticator = None,
        signing_service: MCPSigningService = None,
        tenant_service: MCPTenantIsolationService = None,
        audit_logger: MCPAuditLogger = None
    ):
        self.jwt_authenticator = jwt_authenticator or MCPJWTAuthenticator()
        self.signing_service = signing_service or mcp_signing_service
        self.tenant_service = tenant_service or mcp_tenant_isolation_service
        self.audit_logger = audit_logger or mcp_audit_logger
        
        # Active sessions
        self._active_sessions: Dict[str, Dict[str, Any]] = {}
    
    def authenticate_mcp_request(
        self,
        headers: MCPHeaders,
        jwt_token: Optional[str] = None,
        target_agent: str = None,
        tool_name: str = None
    ) -> Tuple[bool, Optional[str], Optional[MCPAuthToken]]:
        """
        Authenticate MCP request with signature and optional JWT
        
        Args:
            headers: MCP headers
            jwt_token: Optional JWT token
            target_agent: Target agent identifier
            tool_name: Tool being called
            
        Returns:
            Tuple of (is_authenticated, error_message, auth_token)
        """
        start_time = time.time()
        auth_token = None
        
        try:
            # 1. Verify signature
            signature_valid = self.signing_service.verify_mcp_signature(headers)
            if not signature_valid:
                self.audit_logger.log_security_violation(
                    tenant_id=headers.tenant_id,
                    agent_id=headers.caller,
                    violation_type="invalid_signature",
                    description="MCP request signature verification failed",
                    evidence={
                        "headers": headers.dict(),
                        "target_agent": target_agent,
                        "tool_name": tool_name
                    },
                    severity=MCPAuditSeverity.HIGH,
                    trace_id=headers.trace_id
                )
                return False, "Invalid or missing signature", None
            
            # 2. Validate JWT token if provided
            if jwt_token:
                auth_token = self.jwt_authenticator.validate_mcp_token(jwt_token)
                if not auth_token:
                    self.audit_logger.log_security_violation(
                        tenant_id=headers.tenant_id,
                        agent_id=headers.caller,
                        violation_type="invalid_jwt",
                        description="MCP JWT token validation failed",
                        evidence={
                            "headers": headers.dict(),
                            "token_present": True
                        },
                        severity=MCPAuditSeverity.HIGH,
                        trace_id=headers.trace_id
                    )
                    return False, "Invalid JWT token", None
                
                # Verify agent ID matches caller
                if auth_token.agent_id != headers.caller:
                    self.audit_logger.log_security_violation(
                        tenant_id=headers.tenant_id,
                        agent_id=headers.caller,
                        violation_type="agent_id_mismatch",
                        description=f"Agent ID mismatch: {headers.caller} != {auth_token.agent_id}",
                        evidence={
                            "headers": headers.dict(),
                            "token_agent_id": auth_token.agent_id
                        },
                        severity=MCPAuditSeverity.HIGH,
                        trace_id=headers.trace_id
                    )
                    return False, f"Agent ID mismatch", None
                
                # Verify tenant access
                if auth_token.tenant_id != headers.tenant_id:
                    self.audit_logger.log_security_violation(
                        tenant_id=headers.tenant_id,
                        agent_id=headers.caller,
                        violation_type="tenant_mismatch",
                        description=f"Tenant mismatch: {headers.tenant_id} != {auth_token.tenant_id}",
                        evidence={
                            "headers": headers.dict(),
                            "token_tenant_id": auth_token.tenant_id
                        },
                        severity=MCPAuditSeverity.HIGH,
                        trace_id=headers.trace_id
                    )
                    return False, f"Tenant mismatch", None
            
            # 3. Validate tenant isolation
            if target_agent and tool_name:
                try:
                    self.tenant_service.validate_mcp_access(headers, target_agent, tool_name)
                except Exception as e:
                    self.audit_logger.log_security_violation(
                        tenant_id=headers.tenant_id,
                        agent_id=headers.caller,
                        violation_type="tenant_isolation_violation",
                        description=f"Tenant isolation check failed: {str(e)}",
                        evidence={
                            "headers": headers.dict(),
                            "target_agent": target_agent,
                            "tool_name": tool_name
                        },
                        severity=MCPAuditSeverity.HIGH,
                        trace_id=headers.trace_id
                    )
                    return False, f"Tenant isolation violation: {str(e)}", None
            
            # 4. Create session if not exists
            session_key = f"{headers.caller}:{headers.tenant_id}:{headers.conversation_id}"
            if session_key not in self._active_sessions:
                self._active_sessions[session_key] = {
                    "agent_id": headers.caller,
                    "tenant_id": headers.tenant_id,
                    "conversation_id": headers.conversation_id,
                    "created_at": datetime.now(timezone.utc).isoformat(),
                    "last_activity": datetime.now(timezone.utc).isoformat(),
                    "request_count": 0
                }
            
            # Update session activity
            session = self._active_sessions[session_key]
            session["last_activity"] = datetime.now(timezone.utc).isoformat()
            session["request_count"] += 1
            
            # Log successful authentication
            response_time_ms = (time.time() - start_time) * 1000
            
            logger.debug(
                f"MCP request authenticated: {headers.caller} -> {target_agent}.{tool_name} "
                f"tenant={headers.tenant_id} trace={headers.trace_id}"
            )
            
            return True, None, auth_token
            
        except Exception as e:
            logger.error(f"MCP authentication error: {e}")
            self.audit_logger.log_security_violation(
                tenant_id=headers.tenant_id,
                agent_id=headers.caller,
                violation_type="authentication_error",
                description=f"Authentication failed: {str(e)}",
                evidence={
                    "headers": headers.dict(),
                    "error": str(e)
                },
                severity=MCPAuditSeverity.CRITICAL,
                trace_id=headers.trace_id
            )
            return False, f"Authentication failed: {str(e)}", None
    
    def authorize_mcp_action(
        self,
        auth_token: MCPAuthToken,
        action: str,
        resource: Optional[str] = None
    ) -> bool:
        """
        Authorize MCP action based on token permissions
        
        Args:
            auth_token: MCP authentication token
            action: Action to authorize
            resource: Optional resource identifier
            
        Returns:
            True if authorized
        """
        try:
            # Check token expiration
            if auth_token.is_expired():
                return False
            
            # Map actions to permissions
            permission_map = {
                "call_tool": "write",
                "send_callback": "write",
                "read_data": "read",
                "list_tools": "read"
            }
            
            required_permission = permission_map.get(action, action)
            
            # Check if token has required permission
            if not auth_token.has_permission(required_permission):
                logger.warning(
                    f"Agent {auth_token.agent_id} lacks permission {required_permission} for action {action}"
                )
                return False
            
            logger.debug(f"Authorized agent {auth_token.agent_id} for action {action}")
            return True
            
        except Exception as e:
            logger.error(f"MCP authorization error: {e}")
            return False
    
    def create_signed_mcp_headers(
        self,
        tenant_id: str,
        caller: str,
        trace_id: Optional[str] = None,
        conversation_id: Optional[str] = None,
        reply_to: Optional[str] = None
    ) -> MCPHeaders:
        """
        Create signed MCP headers for outgoing requests
        
        Args:
            tenant_id: Tenant identifier
            caller: Calling agent identifier
            trace_id: Optional trace ID
            conversation_id: Optional conversation ID
            reply_to: Optional reply-to endpoint
            
        Returns:
            Signed MCP headers
        """
        return mcp_authentication_manager.create_signed_mcp_headers(
            tenant_id=tenant_id,
            caller=caller,
            trace_id=trace_id,
            conversation_id=conversation_id,
            reply_to=reply_to
        )
    
    def get_session_info(self, session_key: str) -> Optional[Dict[str, Any]]:
        """Get session information"""
        return self._active_sessions.get(session_key)
    
    def cleanup_expired_sessions(self) -> int:
        """Clean up expired sessions"""
        now = datetime.now(timezone.utc)
        expired_sessions = []
        
        for session_key, session in self._active_sessions.items():
            last_activity = datetime.fromisoformat(session["last_activity"].replace('Z', '+00:00'))
            # Sessions expire after 1 hour of inactivity
            if (now - last_activity).total_seconds() > 3600:
                expired_sessions.append(session_key)
        
        # Remove expired sessions
        for session_key in expired_sessions:
            del self._active_sessions[session_key]
        
        if expired_sessions:
            logger.info(f"Cleaned up {len(expired_sessions)} expired MCP sessions")
        
        return len(expired_sessions)
    
    def get_authentication_stats(self) -> Dict[str, Any]:
        """Get authentication statistics"""
        active_sessions = len(self._active_sessions)
        active_tokens = len(self.jwt_authenticator._active_tokens)
        
        # Calculate session activity
        now = datetime.now(timezone.utc)
        recent_sessions = 0
        
        for session in self._active_sessions.values():
            last_activity = datetime.fromisoformat(session["last_activity"].replace('Z', '+00:00'))
            if (now - last_activity).total_seconds() < 300:  # Active in last 5 minutes
                recent_sessions += 1
        
        return {
            "active_sessions": active_sessions,
            "active_tokens": active_tokens,
            "recent_sessions": recent_sessions,
            "total_agents": len(set(s["agent_id"] for s in self._active_sessions.values())),
            "total_tenants": len(set(s["tenant_id"] for s in self._active_sessions.values()))
        }


# Global middleware instance
mcp_authentication_middleware = MCPAuthenticationMiddleware()