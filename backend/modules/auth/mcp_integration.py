"""
MCP Security Integration

Comprehensive integration module that ties together all MCP security components:
- Tenant isolation for MCP communication
- MCP header signing and verification
- Audit logging for MCP workflows
- Security middleware for MCP protocol

This module provides a unified interface for MCP security operations.

Requirements: 7.1, 7.2, 7.3, 7.4
"""

import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple, Any
from uuid import uuid4

from fastapi import Request, HTTPException, status
from fastapi.responses import JSONResponse

from .mcp_tenant_isolation import (
    MCPHeaders, 
    MCPTenantIsolationService, 
    MCPTenantMiddleware,
    mcp_tenant_isolation_service,
    mcp_tenant_middleware
)
from .mcp_security import (
    MCPSigningService,
    MCPAuthenticationManager,
    mcp_signing_service,
    mcp_authentication_manager
)
from .mcp_audit_logging import (
    MCPAuditLogger,
    MCPEventType,
    MCPAuditSeverity,
    mcp_audit_logger
)
from .mcp_security_middleware import (
    MCPAuthenticationMiddleware,
    MCPJWTAuthenticator,
    MCPAuthToken,
    mcp_authentication_middleware
)

logger = logging.getLogger(__name__)


class MCPSecurityManager:
    """Unified MCP security manager"""
    
    def __init__(
        self,
        tenant_service: MCPTenantIsolationService = None,
        signing_service: MCPSigningService = None,
        auth_manager: MCPAuthenticationManager = None,
        audit_logger: MCPAuditLogger = None,
        auth_middleware: MCPAuthenticationMiddleware = None
    ):
        self.tenant_service = tenant_service or mcp_tenant_isolation_service
        self.signing_service = signing_service or mcp_signing_service
        self.auth_manager = auth_manager or mcp_authentication_manager
        self.audit_logger = audit_logger or mcp_audit_logger
        self.auth_middleware = auth_middleware or mcp_authentication_middleware
    
    async def validate_mcp_request(
        self,
        request: Request,
        target_agent: str,
        tool_name: str,
        arguments: Dict[str, Any]
    ) -> Tuple[bool, Optional[str], Optional[MCPHeaders], Optional[MCPAuthToken]]:
        """
        Comprehensive MCP request validation
        
        Args:
            request: FastAPI request object
            target_agent: Target agent identifier
            tool_name: Tool being called
            arguments: Tool arguments
            
        Returns:
            Tuple of (is_valid, error_message, headers, auth_token)
        """
        start_time = datetime.now(timezone.utc)
        
        try:
            # 1. Extract and validate MCP headers
            raw_headers = dict(request.headers)
            
            try:
                mcp_headers = MCPHeaders.from_dict(raw_headers)
            except Exception as e:
                error_msg = f"Invalid MCP headers: {str(e)}"
                logger.warning(error_msg)
                return False, error_msg, None, None
            
            # 2. Validate required headers
            if not mcp_headers.tenant_id:
                return False, "Missing tenant ID in MCP headers", None, None
            
            if not mcp_headers.caller:
                return False, "Missing caller in MCP headers", None, None
            
            if not mcp_headers.trace_id:
                return False, "Missing trace ID in MCP headers", None, None
            
            # 3. Extract JWT token if present
            jwt_token = None
            auth_header = request.headers.get("authorization")
            if auth_header and auth_header.startswith("Bearer "):
                jwt_token = auth_header.split(" ")[1]
            
            # 4. Authenticate request
            is_authenticated, auth_error, auth_token = self.auth_middleware.authenticate_mcp_request(
                headers=mcp_headers,
                jwt_token=jwt_token,
                target_agent=target_agent,
                tool_name=tool_name
            )
            
            if not is_authenticated:
                # Log authentication failure
                self.audit_logger.log_mcp_tool_call(
                    headers=mcp_headers,
                    target_agent=target_agent,
                    tool_name=tool_name,
                    arguments=arguments,
                    success=False,
                    error_message=auth_error,
                    signature_valid=mcp_headers.auth_sig is not None
                )
                return False, auth_error, mcp_headers, None
            
            # 5. Log successful validation
            processing_time = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
            
            self.audit_logger.log_mcp_tool_call(
                headers=mcp_headers,
                target_agent=target_agent,
                tool_name=tool_name,
                arguments=arguments,
                success=True,
                response_time_ms=processing_time,
                signature_valid=True
            )
            
            logger.debug(
                f"MCP request validated: {mcp_headers.caller} -> {target_agent}.{tool_name} "
                f"tenant={mcp_headers.tenant_id} trace={mcp_headers.trace_id}"
            )
            
            return True, None, mcp_headers, auth_token
            
        except Exception as e:
            error_msg = f"MCP request validation failed: {str(e)}"
            logger.error(error_msg)
            
            # Log validation error
            if 'mcp_headers' in locals():
                self.audit_logger.log_security_violation(
                    tenant_id=mcp_headers.tenant_id,
                    agent_id=mcp_headers.caller,
                    violation_type="validation_error",
                    description=error_msg,
                    evidence={
                        "target_agent": target_agent,
                        "tool_name": tool_name,
                        "error": str(e)
                    },
                    severity=MCPAuditSeverity.HIGH,
                    trace_id=mcp_headers.trace_id
                )
            
            return False, error_msg, None, None
    
    async def validate_mcp_callback(
        self,
        request: Request,
        original_trace_id: str,
        callback_data: Dict[str, Any]
    ) -> Tuple[bool, Optional[str], Optional[MCPHeaders]]:
        """
        Validate MCP callback request
        
        Args:
            request: FastAPI request object
            original_trace_id: Original request trace ID
            callback_data: Callback payload
            
        Returns:
            Tuple of (is_valid, error_message, headers)
        """
        start_time = datetime.now(timezone.utc)
        
        try:
            # Extract MCP headers
            raw_headers = dict(request.headers)
            mcp_headers = MCPHeaders.from_dict(raw_headers)
            
            # Validate callback
            is_valid = self.tenant_service.validate_mcp_callback(
                mcp_headers, original_trace_id, callback_data
            )
            
            if not is_valid:
                error_msg = "Invalid MCP callback"
                self.audit_logger.log_mcp_callback(
                    headers=mcp_headers,
                    original_trace_id=original_trace_id,
                    callback_data=callback_data,
                    success=False,
                    error_message=error_msg
                )
                return False, error_msg, mcp_headers
            
            # Log successful callback
            processing_time = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
            
            self.audit_logger.log_mcp_callback(
                headers=mcp_headers,
                original_trace_id=original_trace_id,
                callback_data=callback_data,
                success=True,
                processing_time_ms=processing_time
            )
            
            return True, None, mcp_headers
            
        except Exception as e:
            error_msg = f"MCP callback validation failed: {str(e)}"
            logger.error(error_msg)
            return False, error_msg, None
    
    def create_agent_token(
        self,
        agent_id: str,
        tenant_id: str,
        permissions: List[str] = None,
        expires_in_hours: int = 24
    ) -> MCPAuthToken:
        """
        Create authentication token for MCP agent
        
        Args:
            agent_id: Agent identifier
            tenant_id: Tenant identifier
            permissions: List of permissions
            expires_in_hours: Token expiration in hours
            
        Returns:
            MCP authentication token
        """
        if permissions is None:
            permissions = ["read", "write"]
        
        return self.auth_middleware.jwt_authenticator.create_mcp_token(
            agent_id=agent_id,
            tenant_id=tenant_id,
            permissions=permissions,
            expires_in_hours=expires_in_hours
        )
    
    def create_signed_headers(
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
        return self.auth_middleware.create_signed_mcp_headers(
            tenant_id=tenant_id,
            caller=caller,
            trace_id=trace_id,
            conversation_id=conversation_id,
            reply_to=reply_to
        )
    
    def start_workflow_audit(
        self,
        workflow_id: str,
        workflow_type: str,
        tenant_id: str,
        initiator_agent: str,
        participating_agents: List[str]
    ):
        """Start audit trail for cross-agent workflow"""
        self.audit_logger.start_workflow_audit_trail(
            workflow_id=workflow_id,
            workflow_type=workflow_type,
            tenant_id=tenant_id,
            initiator_agent=initiator_agent,
            participating_agents=participating_agents
        )
    
    def complete_workflow_audit(
        self,
        workflow_id: str,
        success: bool,
        error_message: Optional[str] = None,
        performance_summary: Optional[Dict[str, Any]] = None
    ):
        """Complete audit trail for cross-agent workflow"""
        self.audit_logger.complete_workflow_audit_trail(
            workflow_id=workflow_id,
            success=success,
            error_message=error_message,
            performance_summary=performance_summary
        )
    
    def get_security_stats(self) -> Dict[str, Any]:
        """Get comprehensive security statistics"""
        auth_stats = self.auth_middleware.get_authentication_stats()
        key_stats = self.signing_service.get_key_stats()
        
        return {
            "authentication": auth_stats,
            "signing_keys": key_stats,
            "tenant_isolation": {
                "total_agents": len(self.tenant_service._mcp_agent_configs),
                "isolation_level": "strict"
            },
            "audit_logging": {
                "total_events": len(self.audit_logger._mcp_events),
                "active_workflows": len(self.audit_logger._workflow_trails),
                "security_alerts": len(self.audit_logger._security_alerts)
            }
        }
    
    def rotate_agent_keys(self, agent_id: str) -> Dict[str, str]:
        """Rotate signing keys for an agent"""
        return self.signing_service.rotate_agent_keys(agent_id)
    
    def get_audit_summary(self, tenant_id: str) -> Dict[str, Any]:
        """Get audit summary for a tenant"""
        return self.audit_logger.get_mcp_audit_summary(tenant_id)


class MCPSecurityMiddleware:
    """FastAPI middleware for MCP security"""
    
    def __init__(self, security_manager: MCPSecurityManager = None):
        self.security_manager = security_manager or MCPSecurityManager()
    
    async def __call__(self, request: Request, call_next):
        """Middleware call handler"""
        # Check if this is an MCP request
        if not self._is_mcp_request(request):
            return await call_next(request)
        
        # Extract target agent and tool from path
        target_agent, tool_name = self._extract_mcp_info(request)
        if not target_agent or not tool_name:
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={"error": "Invalid MCP request path"}
            )
        
        # Validate MCP request
        try:
            # Get request body for arguments
            body = await request.body()
            arguments = {}
            if body:
                import json
                try:
                    arguments = json.loads(body)
                except json.JSONDecodeError:
                    arguments = {}
            
            is_valid, error_msg, headers, auth_token = await self.security_manager.validate_mcp_request(
                request=request,
                target_agent=target_agent,
                tool_name=tool_name,
                arguments=arguments
            )
            
            if not is_valid:
                return JSONResponse(
                    status_code=status.HTTP_403_FORBIDDEN,
                    content={
                        "error": "MCP security validation failed",
                        "message": error_msg
                    }
                )
            
            # Add validated info to request state
            request.state.mcp_headers = headers
            request.state.mcp_auth_token = auth_token
            request.state.target_agent = target_agent
            request.state.tool_name = tool_name
            
            # Process request
            response = await call_next(request)
            
            # Add MCP security headers to response
            if headers:
                response.headers["X-MCP-Trace-ID"] = headers.trace_id
                response.headers["X-MCP-Tenant-ID"] = headers.tenant_id
                response.headers["X-MCP-Security"] = "validated"
            
            return response
            
        except Exception as e:
            logger.error(f"MCP security middleware error: {e}")
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={
                    "error": "MCP security middleware error",
                    "message": str(e)
                }
            )
    
    def _is_mcp_request(self, request: Request) -> bool:
        """Check if request is an MCP request"""
        path = request.url.path
        return (
            path.startswith("/mcp/") or
            "X-MCP-Tenant-ID" in request.headers or
            "X-MCP-Caller" in request.headers
        )
    
    def _extract_mcp_info(self, request: Request) -> Tuple[Optional[str], Optional[str]]:
        """Extract target agent and tool from request path"""
        path = request.url.path
        
        # Expected format: /mcp/{agent}/{tool}
        if path.startswith("/mcp/"):
            parts = path.split("/")
            if len(parts) >= 4:
                return parts[2], parts[3]
        
        return None, None


# Global security manager
mcp_security_manager = MCPSecurityManager()
mcp_security_middleware = MCPSecurityMiddleware(mcp_security_manager)