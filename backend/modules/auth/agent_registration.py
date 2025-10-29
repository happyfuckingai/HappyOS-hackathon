"""
Agent Registration and Authentication Service

Handles registration and authentication of MCP agents with tenant-specific tokens.
Provides secure agent onboarding and token management.

Requirements: 6.1, 6.4
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional
from uuid import uuid4

from pydantic import BaseModel, Field

from .jwt_service import JWTService, ScopeBuilder
from ..config.settings import settings

logger = logging.getLogger(__name__)


class AgentRegistration(BaseModel):
    """Agent registration data"""
    agent_id: str = Field(..., pattern="^[a-z0-9-]+$", min_length=1, max_length=50)
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    tenant_id: str = Field(..., pattern="^[a-z0-9-]+$")
    permissions: List[str] = Field(default_factory=lambda: ["read", "write"])
    session_patterns: List[str] = Field(default_factory=lambda: ["*"])
    expires_in_hours: Optional[int] = Field(default=24, ge=1, le=8760)  # Max 1 year
    
    @property
    def full_agent_id(self) -> str:
        """Get full agent identifier"""
        return f"agent-{self.agent_id}"


class AgentCredentials(BaseModel):
    """Agent credentials response"""
    agent_id: str
    tenant_id: str
    access_token: str
    expires_at: str
    scopes: List[str]
    refresh_token: Optional[str] = None


class RegisteredAgent(BaseModel):
    """Registered agent information"""
    agent_id: str
    name: str
    description: Optional[str]
    tenant_id: str
    permissions: List[str]
    session_patterns: List[str]
    created_at: str
    last_token_issued: Optional[str] = None
    active: bool = True


class AgentRegistrationService:
    """Service for managing agent registration and authentication"""
    
    def __init__(self):
        # In-memory storage for demo - in production use database
        self._registered_agents: Dict[str, RegisteredAgent] = {}
        self._agent_tokens: Dict[str, Dict] = {}
    
    def register_agent(self, registration: AgentRegistration) -> RegisteredAgent:
        """
        Register a new MCP agent
        
        Args:
            registration: Agent registration data
            
        Returns:
            RegisteredAgent object
            
        Raises:
            ValueError: If agent already exists or invalid data
        """
        agent_key = f"{registration.tenant_id}:{registration.agent_id}"
        
        if agent_key in self._registered_agents:
            raise ValueError(f"Agent {registration.agent_id} already registered for tenant {registration.tenant_id}")
        
        # Validate permissions
        valid_permissions = ["read", "write", "admin"]
        for perm in registration.permissions:
            if perm not in valid_permissions:
                raise ValueError(f"Invalid permission: {perm}")
        
        # Create registered agent
        registered_agent = RegisteredAgent(
            agent_id=registration.agent_id,
            name=registration.name,
            description=registration.description,
            tenant_id=registration.tenant_id,
            permissions=registration.permissions,
            session_patterns=registration.session_patterns,
            created_at=datetime.now(timezone.utc).isoformat()
        )
        
        self._registered_agents[agent_key] = registered_agent
        
        logger.info(f"Registered agent {registration.agent_id} for tenant {registration.tenant_id}")
        return registered_agent
    
    def authenticate_agent(
        self,
        agent_id: str,
        tenant_id: str,
        session_id: str = "*",
        expires_in_hours: int = 24
    ) -> AgentCredentials:
        """
        Authenticate agent and issue JWT token
        
        Args:
            agent_id: Agent identifier
            tenant_id: Tenant identifier
            session_id: Session identifier (default: *)
            expires_in_hours: Token expiration in hours
            
        Returns:
            AgentCredentials with JWT token
            
        Raises:
            ValueError: If agent not found or inactive
        """
        agent_key = f"{tenant_id}:{agent_id}"
        
        if agent_key not in self._registered_agents:
            raise ValueError(f"Agent {agent_id} not registered for tenant {tenant_id}")
        
        registered_agent = self._registered_agents[agent_key]
        if not registered_agent.active:
            raise ValueError(f"Agent {agent_id} is inactive")
        
        # Check if session matches allowed patterns
        if session_id != "*" and not self._matches_session_patterns(session_id, registered_agent.session_patterns):
            raise ValueError(f"Session {session_id} not allowed for agent {agent_id}")
        
        # Generate scopes based on permissions and session patterns
        scopes = self._generate_agent_scopes(registered_agent, session_id)
        
        # Create JWT token
        expires_delta = timedelta(hours=expires_in_hours)
        access_token = JWTService.create_access_token(
            subject=f"agent-{agent_id}",
            scopes=scopes,
            tenant_id=tenant_id,
            agent_id=agent_id,
            session_id=session_id if session_id != "*" else None,
            expires_delta=expires_delta
        )
        
        # Update last token issued
        registered_agent.last_token_issued = datetime.now(timezone.utc).isoformat()
        
        # Store token info for tracking
        token_id = str(uuid4())
        self._agent_tokens[token_id] = {
            "agent_id": agent_id,
            "tenant_id": tenant_id,
            "session_id": session_id,
            "issued_at": datetime.now(timezone.utc),
            "expires_at": datetime.now(timezone.utc) + expires_delta,
            "revoked": False
        }
        
        expires_at = (datetime.now(timezone.utc) + expires_delta).isoformat()
        
        logger.info(f"Issued token for agent {agent_id} in tenant {tenant_id}")
        
        return AgentCredentials(
            agent_id=agent_id,
            tenant_id=tenant_id,
            access_token=access_token,
            expires_at=expires_at,
            scopes=scopes
        )
    
    def revoke_agent_tokens(self, agent_id: str, tenant_id: str) -> int:
        """
        Revoke all tokens for an agent
        
        Args:
            agent_id: Agent identifier
            tenant_id: Tenant identifier
            
        Returns:
            Number of tokens revoked
        """
        revoked_count = 0
        
        for token_id, token_info in self._agent_tokens.items():
            if (token_info["agent_id"] == agent_id and 
                token_info["tenant_id"] == tenant_id and 
                not token_info["revoked"]):
                token_info["revoked"] = True
                revoked_count += 1
        
        logger.info(f"Revoked {revoked_count} tokens for agent {agent_id}")
        return revoked_count
    
    def deactivate_agent(self, agent_id: str, tenant_id: str) -> bool:
        """
        Deactivate an agent and revoke all tokens
        
        Args:
            agent_id: Agent identifier
            tenant_id: Tenant identifier
            
        Returns:
            True if agent was deactivated
        """
        agent_key = f"{tenant_id}:{agent_id}"
        
        if agent_key not in self._registered_agents:
            return False
        
        # Deactivate agent
        self._registered_agents[agent_key].active = False
        
        # Revoke all tokens
        self.revoke_agent_tokens(agent_id, tenant_id)
        
        logger.info(f"Deactivated agent {agent_id} for tenant {tenant_id}")
        return True
    
    def get_registered_agent(self, agent_id: str, tenant_id: str) -> Optional[RegisteredAgent]:
        """
        Get registered agent information
        
        Args:
            agent_id: Agent identifier
            tenant_id: Tenant identifier
            
        Returns:
            RegisteredAgent if found, None otherwise
        """
        agent_key = f"{tenant_id}:{agent_id}"
        return self._registered_agents.get(agent_key)
    
    def list_tenant_agents(self, tenant_id: str) -> List[RegisteredAgent]:
        """
        List all agents for a tenant
        
        Args:
            tenant_id: Tenant identifier
            
        Returns:
            List of RegisteredAgent objects
        """
        return [
            agent for key, agent in self._registered_agents.items()
            if key.startswith(f"{tenant_id}:")
        ]
    
    def _matches_session_patterns(self, session_id: str, patterns: List[str]) -> bool:
        """Check if session ID matches allowed patterns"""
        for pattern in patterns:
            if pattern == "*":
                return True
            if pattern == session_id:
                return True
            # Simple wildcard matching
            if pattern.endswith("*") and session_id.startswith(pattern[:-1]):
                return True
        return False
    
    def _generate_agent_scopes(self, agent: RegisteredAgent, session_id: str) -> List[str]:
        """Generate scopes for agent based on permissions and session patterns"""
        scopes = []
        
        for permission in agent.permissions:
            if permission in ["read", "write"]:
                for pattern in agent.session_patterns:
                    if pattern == "*" or pattern == session_id:
                        scope_session = session_id if session_id != "*" else "*"
                        scopes.append(f"ui:{permission}:{agent.tenant_id}:{scope_session}")
                        break
            elif permission == "admin":
                # Admin permission grants broader access
                scopes.extend([
                    f"ui:read:{agent.tenant_id}:*",
                    f"ui:write:{agent.tenant_id}:*",
                    f"admin:manage:{agent.tenant_id}:*"
                ])
        
        return list(set(scopes))  # Remove duplicates


class PredefinedAgents:
    """Predefined agent configurations for hackathon demo"""
    
    MEETMIND_SUMMARIZER = AgentRegistration(
        agent_id="meetmind-summarizer",
        name="MeetMind Summarizer",
        description="AI-powered meeting summarization agent",
        tenant_id="meetmind",
        permissions=["read", "write"],
        session_patterns=["*"],
        expires_in_hours=24
    )
    
    AGENT_SVEA = AgentRegistration(
        agent_id="agent-svea",
        name="Agent Svea",
        description="Bokföring and cost analysis agent",
        tenant_id="agentsvea",
        permissions=["read", "write"],
        session_patterns=["*"],
        expires_in_hours=24
    )
    
    FELICIA_CORE = AgentRegistration(
        agent_id="felicia-core",
        name="Felicia's Finance Core",
        description="Financial market data and trading agent",
        tenant_id="feliciasfi",
        permissions=["read", "write"],
        session_patterns=["*"],
        expires_in_hours=24
    )
    
    @classmethod
    def get_all(cls) -> List[AgentRegistration]:
        """Get all predefined agents"""
        return [
            cls.MEETMIND_SUMMARIZER,
            cls.AGENT_SVEA,
            cls.FELICIA_CORE
        ]


def setup_demo_agents(service: AgentRegistrationService) -> Dict[str, AgentCredentials]:
    """
    Set up demo agents for hackathon
    
    Args:
        service: Agent registration service
        
    Returns:
        Dictionary of agent credentials
    """
    credentials = {}
    
    for agent_config in PredefinedAgents.get_all():
        try:
            # Register agent
            registered_agent = service.register_agent(agent_config)
            
            # Authenticate and get credentials
            creds = service.authenticate_agent(
                agent_id=agent_config.agent_id,
                tenant_id=agent_config.tenant_id,
                expires_in_hours=agent_config.expires_in_hours or 24
            )
            
            credentials[f"{agent_config.tenant_id}:{agent_config.agent_id}"] = creds
            
            logger.info(f"Set up demo agent: {agent_config.name}")
            
        except Exception as e:
            logger.error(f"Failed to set up agent {agent_config.agent_id}: {e}")
    
    return credentials


# Global service instance
agent_registration_service = AgentRegistrationService()