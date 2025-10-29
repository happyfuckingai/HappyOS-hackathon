"""
MCP Tenant Isolation Extension

Extends existing tenant isolation for MCP server-to-server communication.
Reuses TenantIsolationService, CrossTenantAccessError, and audit logging
for MCP protocol with header-based validation.

Requirements: 7.2, 7.3
"""

import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional, Set
from uuid import uuid4

from pydantic import BaseModel, Field

try:
    from .tenant_isolation import (
        TenantIsolationService, 
        CrossTenantAccessError, 
        TenantIsolationError,
        AuditLogger,
        tenant_isolation_service,
        audit_logger
    )
    from .jwt_service import JWTClaims, JWTService
except ImportError:
    # Fallback for testing without full backend dependencies
    class TenantIsolationService:
        pass
    class CrossTenantAccessError(Exception):
        def __init__(self, user_tenant, requested_tenant, user_id):
            super().__init__(f"Cross-tenant access: {user_tenant} -> {requested_tenant}")
            self.user_tenant = user_tenant
    class TenantIsolationError(Exception):
        pass
    class AuditLogger:
        def log_tenant_operation(self, **kwargs):
            pass
    class JWTClaims:
        pass
    class JWTService:
        pass
    tenant_isolation_service = TenantIsolationService()
    audit_logger = AuditLogger()

logger = logging.getLogger(__name__)


class MCPHeaders(BaseModel):
    """MCP protocol headers with tenant isolation"""
    tenant_id: str = Field(..., description="Tenant identifier")
    trace_id: str = Field(..., description="Trace identifier for request tracking")
    conversation_id: str = Field(..., description="Conversation identifier")
    reply_to: Optional[str] = Field(None, description="Reply-to endpoint for async callbacks")
    auth_sig: Optional[str] = Field(None, description="Authentication signature")
    caller: str = Field(..., description="Calling agent identifier")
    timestamp: Optional[str] = Field(None, description="Request timestamp")
    
    def to_dict(self) -> Dict[str, str]:
        """Convert headers to dictionary for HTTP transmission"""
        headers = {
            "X-MCP-Tenant-ID": self.tenant_id,
            "X-MCP-Trace-ID": self.trace_id,
            "X-MCP-Conversation-ID": self.conversation_id,
            "X-MCP-Caller": self.caller
        }
        
        if self.reply_to:
            headers["X-MCP-Reply-To"] = self.reply_to
        if self.auth_sig:
            headers["X-MCP-Auth-Sig"] = self.auth_sig
        if self.timestamp:
            headers["X-MCP-Timestamp"] = self.timestamp
            
        return headers
    
    @classmethod
    def from_dict(cls, headers: Dict[str, str]) -> "MCPHeaders":
        """Create MCPHeaders from HTTP headers dictionary"""
        return cls(
            tenant_id=headers.get("X-MCP-Tenant-ID", ""),
            trace_id=headers.get("X-MCP-Trace-ID", ""),
            conversation_id=headers.get("X-MCP-Conversation-ID", ""),
            reply_to=headers.get("X-MCP-Reply-To"),
            auth_sig=headers.get("X-MCP-Auth-Sig"),
            caller=headers.get("X-MCP-Caller", ""),
            timestamp=headers.get("X-MCP-Timestamp")
        )


class MCPAccessAttempt(BaseModel):
    """Record of MCP access attempt"""
    attempt_id: str = Field(default_factory=lambda: str(uuid4()))
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    caller_agent: str
    target_agent: str
    tenant_id: str
    operation: str
    tool_name: Optional[str] = None
    allowed: bool
    reason: str
    trace_id: Optional[str] = None
    conversation_id: Optional[str] = None
    auth_signature_valid: Optional[bool] = None


class MCPTenantIsolationService:
    """Extended tenant isolation service for MCP protocol"""
    
    def __init__(self, base_service: TenantIsolationService = None):
        """Initialize with existing tenant isolation service"""
        self.base_service = base_service or tenant_isolation_service
        self._mcp_access_attempts: List[MCPAccessAttempt] = []
        
        # MCP agent configurations
        self._mcp_agent_configs = {
            "agent_svea": {
                "name": "Agent Svea ERPNext",
                "allowed_tenants": ["agentsvea", "shared"],
                "allowed_tools": ["check_compliance", "validate_bas_account", "submit_skatteverket", "sync_erp_document"],
                "isolation_level": "strict"
            },
            "felicias_finance": {
                "name": "Felicia's Finance",
                "allowed_tenants": ["feliciasfi", "shared"],
                "allowed_tools": ["analyze_crypto_trade", "get_portfolio_analysis", "process_banking_transaction", "calculate_financial_risk"],
                "isolation_level": "strict"
            },
            "meetmind": {
                "name": "MeetMind",
                "allowed_tenants": ["meetmind", "shared"],
                "allowed_tools": ["ingest_result", "generate_meeting_summary", "extract_financial_topics", "create_action_items"],
                "isolation_level": "strict"
            },
            "communications_agent": {
                "name": "Communications Agent",
                "allowed_tenants": ["*"],  # Can orchestrate across tenants
                "allowed_tools": ["orchestrate_workflow", "route_message"],
                "isolation_level": "permissive"
            }
        }
    
    def validate_mcp_access(
        self,
        headers: MCPHeaders,
        target_agent: str,
        tool_name: str,
        operation: str = "call"
    ) -> bool:
        """
        Validate MCP access with tenant isolation
        
        Args:
            headers: MCP protocol headers
            target_agent: Target agent identifier
            tool_name: MCP tool being called
            operation: Operation type
            
        Returns:
            True if access is allowed
            
        Raises:
            CrossTenantAccessError: If cross-tenant access is attempted
            TenantIsolationError: If access is denied for other reasons
        """
        try:
            # Validate agent exists
            if target_agent not in self._mcp_agent_configs:
                self._log_mcp_access_attempt(
                    headers, target_agent, tool_name, operation, False, 
                    f"Unknown target agent: {target_agent}"
                )
                raise TenantIsolationError(f"Unknown agent: {target_agent}", headers.tenant_id, headers.caller)
            
            agent_config = self._mcp_agent_configs[target_agent]
            
            # Check tenant access for target agent
            allowed_tenants = agent_config["allowed_tenants"]
            if "*" not in allowed_tenants and headers.tenant_id not in allowed_tenants:
                self._log_mcp_access_attempt(
                    headers, target_agent, tool_name, operation, False,
                    f"Agent {target_agent} not allowed for tenant {headers.tenant_id}"
                )
                raise CrossTenantAccessError(headers.caller, headers.tenant_id, headers.caller)
            
            # Check tool access
            allowed_tools = agent_config["allowed_tools"]
            if tool_name not in allowed_tools:
                self._log_mcp_access_attempt(
                    headers, target_agent, tool_name, operation, False,
                    f"Tool {tool_name} not allowed for agent {target_agent}"
                )
                raise TenantIsolationError(f"Tool {tool_name} not allowed", headers.tenant_id, headers.caller)
            
            # Validate caller agent configuration
            if headers.caller not in self._mcp_agent_configs:
                self._log_mcp_access_attempt(
                    headers, target_agent, tool_name, operation, False,
                    f"Unknown caller agent: {headers.caller}"
                )
                raise TenantIsolationError(f"Unknown caller: {headers.caller}", headers.tenant_id, headers.caller)
            
            caller_config = self._mcp_agent_configs[headers.caller]
            caller_allowed_tenants = caller_config["allowed_tenants"]
            
            # Check if caller can access this tenant
            if "*" not in caller_allowed_tenants and headers.tenant_id not in caller_allowed_tenants:
                self._log_mcp_access_attempt(
                    headers, target_agent, tool_name, operation, False,
                    f"Caller {headers.caller} not allowed for tenant {headers.tenant_id}"
                )
                raise CrossTenantAccessError(headers.caller, headers.tenant_id, headers.caller)
            
            # Log successful access
            self._log_mcp_access_attempt(
                headers, target_agent, tool_name, operation, True, "Access granted"
            )
            
            return True
            
        except (CrossTenantAccessError, TenantIsolationError):
            # Re-raise isolation errors
            raise
        except Exception as e:
            logger.error(f"MCP access validation error: {e}")
            self._log_mcp_access_attempt(
                headers, target_agent, tool_name, operation, False, f"Validation error: {str(e)}"
            )
            raise TenantIsolationError(f"Access validation failed: {str(e)}", headers.tenant_id, headers.caller)
    
    def validate_mcp_callback(
        self,
        headers: MCPHeaders,
        original_trace_id: str,
        callback_data: Dict
    ) -> bool:
        """
        Validate MCP callback with tenant isolation
        
        Args:
            headers: MCP callback headers
            original_trace_id: Original request trace ID
            callback_data: Callback payload data
            
        Returns:
            True if callback is allowed
        """
        try:
            # Verify trace ID matches
            if headers.trace_id != original_trace_id:
                self._log_mcp_access_attempt(
                    headers, "callback", "ingest_result", "callback", False,
                    f"Trace ID mismatch: {headers.trace_id} != {original_trace_id}"
                )
                return False
            
            # Validate callback target (usually MeetMind)
            if headers.reply_to and "meetmind" not in headers.reply_to.lower():
                self._log_mcp_access_attempt(
                    headers, "callback", "ingest_result", "callback", False,
                    f"Invalid callback target: {headers.reply_to}"
                )
                return False
            
            # Log successful callback validation
            self._log_mcp_access_attempt(
                headers, "callback", "ingest_result", "callback", True, "Callback validated"
            )
            
            return True
            
        except Exception as e:
            logger.error(f"MCP callback validation error: {e}")
            return False
    
    def get_agent_tenant_permissions(self, agent_id: str) -> Dict[str, List[str]]:
        """
        Get tenant permissions for an agent
        
        Args:
            agent_id: Agent identifier
            
        Returns:
            Dictionary mapping tenants to allowed tools
        """
        if agent_id not in self._mcp_agent_configs:
            return {}
        
        config = self._mcp_agent_configs[agent_id]
        allowed_tenants = config["allowed_tenants"]
        allowed_tools = config["allowed_tools"]
        
        if "*" in allowed_tenants:
            # Agent can access all tenants
            return {"*": allowed_tools}
        
        # Return specific tenant permissions
        return {tenant: allowed_tools for tenant in allowed_tenants}
    
    def check_cross_agent_workflow_access(
        self,
        workflow_tenants: List[str],
        participating_agents: List[str]
    ) -> bool:
        """
        Check if cross-agent workflow is allowed across tenants
        
        Args:
            workflow_tenants: List of tenants involved in workflow
            participating_agents: List of agents in workflow
            
        Returns:
            True if workflow is allowed
        """
        try:
            for agent_id in participating_agents:
                if agent_id not in self._mcp_agent_configs:
                    logger.warning(f"Unknown agent in workflow: {agent_id}")
                    return False
                
                agent_config = self._mcp_agent_configs[agent_id]
                allowed_tenants = agent_config["allowed_tenants"]
                
                # Check if agent can access all workflow tenants
                if "*" not in allowed_tenants:
                    for tenant in workflow_tenants:
                        if tenant not in allowed_tenants:
                            logger.warning(f"Agent {agent_id} cannot access tenant {tenant}")
                            return False
            
            return True
            
        except Exception as e:
            logger.error(f"Cross-agent workflow validation error: {e}")
            return False
    
    def get_mcp_access_attempts(
        self,
        tenant_id: Optional[str] = None,
        agent_id: Optional[str] = None,
        failed_only: bool = False,
        limit: int = 100
    ) -> List[MCPAccessAttempt]:
        """
        Get MCP access attempts with filtering
        
        Args:
            tenant_id: Filter by tenant
            agent_id: Filter by agent
            failed_only: Only return failed attempts
            limit: Maximum number of results
            
        Returns:
            List of MCP access attempts
        """
        attempts = self._mcp_access_attempts
        
        # Apply filters
        if tenant_id:
            attempts = [a for a in attempts if a.tenant_id == tenant_id]
        
        if agent_id:
            attempts = [a for a in attempts if a.caller_agent == agent_id or a.target_agent == agent_id]
        
        if failed_only:
            attempts = [a for a in attempts if not a.allowed]
        
        # Sort by timestamp (newest first) and limit
        attempts.sort(key=lambda a: a.timestamp, reverse=True)
        return attempts[:limit]
    
    def get_mcp_tenant_stats(self, tenant_id: str) -> Dict:
        """
        Get MCP statistics for a tenant
        
        Args:
            tenant_id: Tenant identifier
            
        Returns:
            Dictionary with tenant MCP statistics
        """
        tenant_attempts = [a for a in self._mcp_access_attempts if a.tenant_id == tenant_id]
        
        return {
            "tenant_id": tenant_id,
            "total_mcp_calls": len(tenant_attempts),
            "successful_calls": len([a for a in tenant_attempts if a.allowed]),
            "failed_calls": len([a for a in tenant_attempts if not a.allowed]),
            "unique_agents": len(set(a.caller_agent for a in tenant_attempts)),
            "cross_tenant_attempts": len([
                a for a in tenant_attempts
                if not a.allowed and "cross-tenant" in a.reason.lower()
            ]),
            "most_called_tools": self._get_most_called_tools(tenant_attempts)
        }
    
    def _get_most_called_tools(self, attempts: List[MCPAccessAttempt]) -> List[Dict[str, int]]:
        """Get most frequently called tools from attempts"""
        tool_counts = {}
        for attempt in attempts:
            if attempt.tool_name and attempt.allowed:
                tool_counts[attempt.tool_name] = tool_counts.get(attempt.tool_name, 0) + 1
        
        # Sort by count and return top 5
        sorted_tools = sorted(tool_counts.items(), key=lambda x: x[1], reverse=True)
        return [{"tool": tool, "count": count} for tool, count in sorted_tools[:5]]
    
    def _log_mcp_access_attempt(
        self,
        headers: MCPHeaders,
        target_agent: str,
        tool_name: str,
        operation: str,
        allowed: bool,
        reason: str
    ):
        """Log MCP access attempt for audit trail"""
        attempt = MCPAccessAttempt(
            caller_agent=headers.caller,
            target_agent=target_agent,
            tenant_id=headers.tenant_id,
            operation=operation,
            tool_name=tool_name,
            allowed=allowed,
            reason=reason,
            trace_id=headers.trace_id,
            conversation_id=headers.conversation_id,
            auth_signature_valid=headers.auth_sig is not None
        )
        
        self._mcp_access_attempts.append(attempt)
        
        # Keep only recent attempts (last 5000)
        if len(self._mcp_access_attempts) > 5000:
            self._mcp_access_attempts = self._mcp_access_attempts[-5000:]
        
        # Log to system logger
        if not allowed:
            logger.warning(
                f"MCP access denied: {headers.caller} -> {target_agent}.{tool_name} "
                f"tenant={headers.tenant_id}, reason={reason}, trace={headers.trace_id}"
            )
        else:
            logger.debug(
                f"MCP access granted: {headers.caller} -> {target_agent}.{tool_name} "
                f"tenant={headers.tenant_id}, trace={headers.trace_id}"
            )
        
        # Also log to existing audit logger
        audit_logger.log_tenant_operation(
            operation=f"mcp_{operation}",
            tenant_id=headers.tenant_id,
            user_id=headers.caller,
            resource_id=f"{target_agent}.{tool_name}",
            details={
                "target_agent": target_agent,
                "tool_name": tool_name,
                "trace_id": headers.trace_id,
                "conversation_id": headers.conversation_id,
                "reason": reason
            },
            success=allowed
        )


class MCPTenantMiddleware:
    """Middleware for MCP tenant isolation validation"""
    
    def __init__(self, mcp_service: MCPTenantIsolationService = None):
        self.mcp_service = mcp_service or MCPTenantIsolationService()
    
    async def validate_mcp_request(
        self,
        headers: Dict[str, str],
        target_agent: str,
        tool_name: str
    ) -> MCPHeaders:
        """
        Validate MCP request and return validated headers
        
        Args:
            headers: Raw HTTP headers
            target_agent: Target agent identifier
            tool_name: MCP tool being called
            
        Returns:
            Validated MCPHeaders
            
        Raises:
            TenantIsolationError: If validation fails
        """
        try:
            # Parse MCP headers
            mcp_headers = MCPHeaders.from_dict(headers)
            
            # Validate required headers
            if not mcp_headers.tenant_id:
                raise TenantIsolationError("Missing tenant ID in MCP headers", "unknown", "unknown")
            
            if not mcp_headers.caller:
                raise TenantIsolationError("Missing caller in MCP headers", mcp_headers.tenant_id, "unknown")
            
            if not mcp_headers.trace_id:
                raise TenantIsolationError("Missing trace ID in MCP headers", mcp_headers.tenant_id, mcp_headers.caller)
            
            # Validate access
            self.mcp_service.validate_mcp_access(mcp_headers, target_agent, tool_name)
            
            return mcp_headers
            
        except (CrossTenantAccessError, TenantIsolationError):
            # Re-raise isolation errors
            raise
        except Exception as e:
            logger.error(f"MCP request validation error: {e}")
            raise TenantIsolationError(f"Request validation failed: {str(e)}", "unknown", "unknown")
    
    async def validate_mcp_callback(
        self,
        headers: Dict[str, str],
        original_trace_id: str,
        callback_data: Dict
    ) -> bool:
        """
        Validate MCP callback
        
        Args:
            headers: Raw HTTP headers
            original_trace_id: Original request trace ID
            callback_data: Callback payload
            
        Returns:
            True if callback is valid
        """
        try:
            mcp_headers = MCPHeaders.from_dict(headers)
            return self.mcp_service.validate_mcp_callback(mcp_headers, original_trace_id, callback_data)
        except Exception as e:
            logger.error(f"MCP callback validation error: {e}")
            return False


# Global services
mcp_tenant_isolation_service = MCPTenantIsolationService()
mcp_tenant_middleware = MCPTenantMiddleware(mcp_tenant_isolation_service)