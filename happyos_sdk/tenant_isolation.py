"""
HappyOS SDK - Unified Tenant Isolation

Standardized tenant isolation for all HappyOS agents using MCP protocol.
Ensures consistent tenant access control across Agent Svea, Felicia's Finance, and MeetMind.

Requirements: 5.2, 5.3, 8.1, 8.2
"""

import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional, Set, Any
from uuid import uuid4
from dataclasses import dataclass
from enum import Enum

from .mcp_security import MCPHeaders
from .exceptions import A2AError, AuthorizationError

logger = logging.getLogger(__name__)


class TenantIsolationLevel(Enum):
    """Tenant isolation levels"""
    STRICT = "strict"      # No cross-tenant access allowed
    PERMISSIVE = "permissive"  # Limited cross-tenant access for orchestration
    SHARED = "shared"      # Shared resources across tenants


@dataclass
class TenantConfig:
    """Tenant configuration"""
    tenant_id: str
    name: str
    domain: str
    allowed_agents: List[str]
    isolation_level: TenantIsolationLevel
    shared_resources: List[str] = None
    
    def __post_init__(self):
        if self.shared_resources is None:
            self.shared_resources = []


@dataclass
class AgentConfig:
    """Agent configuration for tenant access"""
    agent_id: str
    name: str
    allowed_tenants: List[str]
    allowed_tools: List[str]
    isolation_level: TenantIsolationLevel
    cross_tenant_permissions: List[str] = None
    
    def __post_init__(self):
        if self.cross_tenant_permissions is None:
            self.cross_tenant_permissions = []


@dataclass
class TenantAccessAttempt:
    """Record of tenant access attempt"""
    attempt_id: str
    timestamp: str
    caller_agent: str
    target_agent: str
    tenant_id: str
    operation: str
    tool_name: Optional[str] = None
    allowed: bool = False
    reason: str = ""
    trace_id: Optional[str] = None
    conversation_id: Optional[str] = None


class TenantIsolationError(A2AError):
    """Tenant isolation violation error"""
    def __init__(self, message: str, tenant_id: str, agent_id: str):
        super().__init__(message)
        self.tenant_id = tenant_id
        self.agent_id = agent_id


class CrossTenantAccessError(TenantIsolationError):
    """Cross-tenant access violation error"""
    def __init__(self, caller_tenant: str, requested_tenant: str, agent_id: str):
        message = f"Cross-tenant access denied: {caller_tenant} -> {requested_tenant}"
        super().__init__(message, requested_tenant, agent_id)
        self.caller_tenant = caller_tenant


class UnifiedTenantIsolationService:
    """Unified tenant isolation service for all HappyOS agents"""
    
    def __init__(self):
        # Tenant configurations
        self._tenant_configs: Dict[str, TenantConfig] = {}
        
        # Agent configurations
        self._agent_configs: Dict[str, AgentConfig] = {}
        
        # Access attempt tracking
        self._access_attempts: List[TenantAccessAttempt] = []
        
        # Blocked agents
        self._blocked_agents: Set[str] = set()
        
        # Initialize default configurations
        self._initialize_default_configs()
    
    def _initialize_default_configs(self):
        """Initialize default tenant and agent configurations"""
        # Default tenant configurations
        tenants = [
            TenantConfig(
                tenant_id="agentsvea",
                name="Agent Svea ERPNext",
                domain="agentsvea.se",
                allowed_agents=["agent_svea", "communications_agent", "meetmind"],
                isolation_level=TenantIsolationLevel.STRICT
            ),
            TenantConfig(
                tenant_id="feliciasfi",
                name="Felicia's Finance",
                domain="feliciasfi.com",
                allowed_agents=["felicias_finance", "communications_agent", "meetmind"],
                isolation_level=TenantIsolationLevel.STRICT
            ),
            TenantConfig(
                tenant_id="meetmind",
                name="MeetMind",
                domain="meetmind.se",
                allowed_agents=["meetmind", "communications_agent", "agent_svea", "felicias_finance"],
                isolation_level=TenantIsolationLevel.STRICT
            ),
            TenantConfig(
                tenant_id="shared",
                name="Shared Resources",
                domain="happyos.com",
                allowed_agents=["*"],
                isolation_level=TenantIsolationLevel.SHARED,
                shared_resources=["logging", "monitoring", "health_checks"]
            )
        ]
        
        for tenant in tenants:
            self._tenant_configs[tenant.tenant_id] = tenant
        
        # Default agent configurations
        agents = [
            AgentConfig(
                agent_id="agent_svea",
                name="Agent Svea ERPNext",
                allowed_tenants=["agentsvea", "shared"],
                allowed_tools=[
                    "check_swedish_compliance",
                    "validate_bas_account", 
                    "sync_erp_document",
                    "submit_skatteverket"
                ],
                isolation_level=TenantIsolationLevel.STRICT
            ),
            AgentConfig(
                agent_id="felicias_finance",
                name="Felicia's Finance",
                allowed_tenants=["feliciasfi", "shared"],
                allowed_tools=[
                    "analyze_financial_risk",
                    "execute_crypto_trade",
                    "process_banking_transaction",
                    "optimize_portfolio",
                    "get_market_analysis"
                ],
                isolation_level=TenantIsolationLevel.STRICT
            ),
            AgentConfig(
                agent_id="meetmind",
                name="MeetMind",
                allowed_tenants=["*"],  # MeetMind can receive callbacks from all tenants
                allowed_tools=[
                    "ingest_result",
                    "generate_meeting_summary",
                    "extract_financial_topics",
                    "create_action_items"
                ],
                isolation_level=TenantIsolationLevel.PERMISSIVE
            ),
            AgentConfig(
                agent_id="communications_agent",
                name="Communications Agent",
                allowed_tenants=["*"],  # Can orchestrate across tenants
                allowed_tools=[
                    "orchestrate_workflow",
                    "route_message",
                    "coordinate_agents"
                ],
                isolation_level=TenantIsolationLevel.PERMISSIVE,
                cross_tenant_permissions=["orchestrate", "coordinate"]
            )
        ]
        
        for agent in agents:
            self._agent_configs[agent.agent_id] = agent
        
        logger.info("Initialized default tenant isolation configurations")
    
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
            # Check if caller is blocked
            if headers.caller in self._blocked_agents:
                self._log_access_attempt(
                    headers, target_agent, tool_name, operation, False,
                    f"Caller {headers.caller} is blocked"
                )
                raise TenantIsolationError(
                    f"Agent {headers.caller} is blocked", 
                    headers.tenant_id, 
                    headers.caller
                )
            
            # Validate tenant exists
            if headers.tenant_id not in self._tenant_configs:
                self._log_access_attempt(
                    headers, target_agent, tool_name, operation, False,
                    f"Unknown tenant: {headers.tenant_id}"
                )
                raise TenantIsolationError(
                    f"Unknown tenant: {headers.tenant_id}",
                    headers.tenant_id,
                    headers.caller
                )
            
            # Validate caller agent exists
            if headers.caller not in self._agent_configs:
                self._log_access_attempt(
                    headers, target_agent, tool_name, operation, False,
                    f"Unknown caller agent: {headers.caller}"
                )
                raise TenantIsolationError(
                    f"Unknown caller: {headers.caller}",
                    headers.tenant_id,
                    headers.caller
                )
            
            # Validate target agent exists
            if target_agent not in self._agent_configs:
                self._log_access_attempt(
                    headers, target_agent, tool_name, operation, False,
                    f"Unknown target agent: {target_agent}"
                )
                raise TenantIsolationError(
                    f"Unknown target agent: {target_agent}",
                    headers.tenant_id,
                    headers.caller
                )
            
            # Get configurations
            tenant_config = self._tenant_configs[headers.tenant_id]
            caller_config = self._agent_configs[headers.caller]
            target_config = self._agent_configs[target_agent]
            
            # Check if caller can access this tenant
            if not self._can_agent_access_tenant(caller_config, headers.tenant_id):
                self._log_access_attempt(
                    headers, target_agent, tool_name, operation, False,
                    f"Caller {headers.caller} not allowed for tenant {headers.tenant_id}"
                )
                raise CrossTenantAccessError(
                    caller_config.allowed_tenants[0] if caller_config.allowed_tenants else "unknown",
                    headers.tenant_id,
                    headers.caller
                )
            
            # Check if target agent is allowed for this tenant
            if not self._can_agent_access_tenant(target_config, headers.tenant_id):
                self._log_access_attempt(
                    headers, target_agent, tool_name, operation, False,
                    f"Target agent {target_agent} not allowed for tenant {headers.tenant_id}"
                )
                raise TenantIsolationError(
                    f"Agent {target_agent} not allowed for tenant {headers.tenant_id}",
                    headers.tenant_id,
                    headers.caller
                )
            
            # Check if target agent allows this tool
            if tool_name not in target_config.allowed_tools:
                self._log_access_attempt(
                    headers, target_agent, tool_name, operation, False,
                    f"Tool {tool_name} not allowed for agent {target_agent}"
                )
                raise TenantIsolationError(
                    f"Tool {tool_name} not allowed for agent {target_agent}",
                    headers.tenant_id,
                    headers.caller
                )
            
            # Check tenant isolation level
            if tenant_config.isolation_level == TenantIsolationLevel.STRICT:
                # Strict isolation - only allow same-tenant access
                if headers.caller != target_agent and headers.tenant_id != "shared":
                    # Allow communications agent to orchestrate
                    # Allow MeetMind to receive callbacks from any agent (fan-in logic)
                    if headers.caller not in ["communications_agent"] and target_agent != "meetmind":
                        self._log_access_attempt(
                            headers, target_agent, tool_name, operation, False,
                            f"Strict isolation violation: {headers.caller} -> {target_agent}"
                        )
                        raise TenantIsolationError(
                            f"Strict tenant isolation prevents cross-agent access",
                            headers.tenant_id,
                            headers.caller
                        )
            
            # Log successful access
            self._log_access_attempt(
                headers, target_agent, tool_name, operation, True, "Access granted"
            )
            
            return True
            
        except (CrossTenantAccessError, TenantIsolationError):
            # Re-raise isolation errors
            raise
        except Exception as e:
            logger.error(f"MCP access validation error: {e}")
            self._log_access_attempt(
                headers, target_agent, tool_name, operation, False, 
                f"Validation error: {str(e)}"
            )
            raise TenantIsolationError(
                f"Access validation failed: {str(e)}",
                headers.tenant_id,
                headers.caller
            )
    
    def validate_callback_access(
        self,
        headers: MCPHeaders,
        original_trace_id: str,
        callback_data: Dict[str, Any]
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
                self._log_access_attempt(
                    headers, "callback", "ingest_result", "callback", False,
                    f"Trace ID mismatch: {headers.trace_id} != {original_trace_id}"
                )
                return False
            
            # Validate callback target (usually MeetMind)
            if headers.reply_to and "meetmind" not in headers.reply_to.lower():
                # Allow other valid callback targets
                valid_targets = ["meetmind", "communications_agent"]
                if not any(target in headers.reply_to.lower() for target in valid_targets):
                    self._log_access_attempt(
                        headers, "callback", "ingest_result", "callback", False,
                        f"Invalid callback target: {headers.reply_to}"
                    )
                    return False
            
            # Log successful callback validation
            self._log_access_attempt(
                headers, "callback", "ingest_result", "callback", True, "Callback validated"
            )
            
            return True
            
        except Exception as e:
            logger.error(f"MCP callback validation error: {e}")
            return False
    
    def _can_agent_access_tenant(self, agent_config: AgentConfig, tenant_id: str) -> bool:
        """Check if agent can access tenant"""
        if "*" in agent_config.allowed_tenants:
            return True
        
        return tenant_id in agent_config.allowed_tenants
    
    def get_agent_tenant_permissions(self, agent_id: str) -> Dict[str, List[str]]:
        """
        Get tenant permissions for an agent
        
        Args:
            agent_id: Agent identifier
            
        Returns:
            Dictionary mapping tenants to allowed tools
        """
        if agent_id not in self._agent_configs:
            return {}
        
        config = self._agent_configs[agent_id]
        
        if "*" in config.allowed_tenants:
            # Agent can access all tenants
            return {"*": config.allowed_tools}
        
        # Return specific tenant permissions
        return {tenant: config.allowed_tools for tenant in config.allowed_tenants}
    
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
                if agent_id not in self._agent_configs:
                    logger.warning(f"Unknown agent in workflow: {agent_id}")
                    return False
                
                agent_config = self._agent_configs[agent_id]
                
                # Check if agent can access all workflow tenants
                if "*" not in agent_config.allowed_tenants:
                    for tenant in workflow_tenants:
                        if tenant not in agent_config.allowed_tenants:
                            logger.warning(f"Agent {agent_id} cannot access tenant {tenant}")
                            return False
            
            return True
            
        except Exception as e:
            logger.error(f"Cross-agent workflow validation error: {e}")
            return False
    
    def block_agent(self, agent_id: str, reason: str) -> bool:
        """
        Block agent from accessing any tenant
        
        Args:
            agent_id: Agent identifier
            reason: Reason for blocking
            
        Returns:
            True if agent was blocked
        """
        self._blocked_agents.add(agent_id)
        logger.warning(f"Blocked agent {agent_id}: {reason}")
        return True
    
    def unblock_agent(self, agent_id: str) -> bool:
        """
        Unblock agent
        
        Args:
            agent_id: Agent identifier
            
        Returns:
            True if agent was unblocked
        """
        if agent_id in self._blocked_agents:
            self._blocked_agents.remove(agent_id)
            logger.info(f"Unblocked agent {agent_id}")
            return True
        return False
    
    def get_access_attempts(
        self,
        tenant_id: Optional[str] = None,
        agent_id: Optional[str] = None,
        failed_only: bool = False,
        limit: int = 100
    ) -> List[TenantAccessAttempt]:
        """
        Get access attempts with filtering
        
        Args:
            tenant_id: Filter by tenant
            agent_id: Filter by agent
            failed_only: Only return failed attempts
            limit: Maximum number of results
            
        Returns:
            List of access attempts
        """
        attempts = self._access_attempts
        
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
    
    def get_tenant_stats(self, tenant_id: str) -> Dict[str, Any]:
        """
        Get statistics for a tenant
        
        Args:
            tenant_id: Tenant identifier
            
        Returns:
            Dictionary with tenant statistics
        """
        tenant_attempts = [a for a in self._access_attempts if a.tenant_id == tenant_id]
        
        return {
            "tenant_id": tenant_id,
            "total_attempts": len(tenant_attempts),
            "successful_attempts": len([a for a in tenant_attempts if a.allowed]),
            "failed_attempts": len([a for a in tenant_attempts if not a.allowed]),
            "unique_agents": len(set(a.caller_agent for a in tenant_attempts)),
            "cross_tenant_attempts": len([
                a for a in tenant_attempts
                if not a.allowed and "cross-tenant" in a.reason.lower()
            ]),
            "most_called_tools": self._get_most_called_tools(tenant_attempts)
        }
    
    def _get_most_called_tools(self, attempts: List[TenantAccessAttempt]) -> List[Dict[str, int]]:
        """Get most frequently called tools from attempts"""
        tool_counts = {}
        for attempt in attempts:
            if attempt.tool_name and attempt.allowed:
                tool_counts[attempt.tool_name] = tool_counts.get(attempt.tool_name, 0) + 1
        
        # Sort by count and return top 5
        sorted_tools = sorted(tool_counts.items(), key=lambda x: x[1], reverse=True)
        return [{"tool": tool, "count": count} for tool, count in sorted_tools[:5]]
    
    def _log_access_attempt(
        self,
        headers: MCPHeaders,
        target_agent: str,
        tool_name: str,
        operation: str,
        allowed: bool,
        reason: str
    ):
        """Log access attempt for audit trail"""
        attempt = TenantAccessAttempt(
            attempt_id=str(uuid4()),
            timestamp=datetime.now(timezone.utc).isoformat(),
            caller_agent=headers.caller,
            target_agent=target_agent,
            tenant_id=headers.tenant_id,
            operation=operation,
            tool_name=tool_name,
            allowed=allowed,
            reason=reason,
            trace_id=headers.trace_id,
            conversation_id=headers.conversation_id
        )
        
        self._access_attempts.append(attempt)
        
        # Keep only recent attempts (last 5000)
        if len(self._access_attempts) > 5000:
            self._access_attempts = self._access_attempts[-5000:]
        
        # Log to system logger
        if not allowed:
            logger.warning(
                f"Tenant access denied: {headers.caller} -> {target_agent}.{tool_name} "
                f"tenant={headers.tenant_id}, reason={reason}, trace={headers.trace_id}"
            )
        else:
            logger.debug(
                f"Tenant access granted: {headers.caller} -> {target_agent}.{tool_name} "
                f"tenant={headers.tenant_id}, trace={headers.trace_id}"
            )


# Global service for HappyOS SDK
unified_tenant_isolation_service = UnifiedTenantIsolationService()


def validate_mcp_tenant_access(
    headers: MCPHeaders,
    target_agent: str,
    tool_name: str,
    operation: str = "call"
) -> bool:
    """
    Convenience function to validate MCP tenant access
    
    Args:
        headers: MCP headers
        target_agent: Target agent identifier
        tool_name: Tool being called
        operation: Operation type
        
    Returns:
        True if access is allowed
        
    Raises:
        TenantIsolationError: If access is denied
    """
    return unified_tenant_isolation_service.validate_mcp_access(
        headers, target_agent, tool_name, operation
    )


def get_agent_tenant_permissions(agent_id: str) -> Dict[str, List[str]]:
    """
    Convenience function to get agent tenant permissions
    
    Args:
        agent_id: Agent identifier
        
    Returns:
        Dictionary mapping tenants to allowed tools
    """
    return unified_tenant_isolation_service.get_agent_tenant_permissions(agent_id)