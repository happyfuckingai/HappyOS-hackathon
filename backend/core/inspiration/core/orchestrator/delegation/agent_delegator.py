"""
Agent delegation logic.
Handles routing requests to appropriate agents using CAMEL and OWL clients.
Creates dynamic agent teams for complex tasks.
"""

import logging
import time
import uuid
from datetime import datetime
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from enum import Enum

from app.core.error_handler import safe_execute
# Import system clients for proper agent management
from app.core.camel.camel_client import camel_client
from app.core.owl.owl_client import OwlClient

logger = logging.getLogger(__name__)


class AgentType(Enum):
    """Types of agents that can be created dynamically."""
    ACCOUNTING = "accounting"
    RESEARCH = "research"
    WRITING = "writing"
    CODING = "coding"
    ANALYSIS = "analysis"
    GENERAL = "general"
    TEAM_LEAD = "team_lead"


@dataclass
class DynamicAgent:
    """Represents a dynamically created agent."""
    agent_id: str
    agent_type: AgentType
    capabilities: List[str]
    camel_agent_id: Optional[str] = None  # Reference to actual CAMEL agent
    created_at: datetime = None
    last_used: datetime = None
    performance_score: float = 0.5

    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now()
        if self.last_used is None:
            self.last_used = datetime.now()


@dataclass
class DelegationResult:
    """Result of agent delegation."""
    success: bool
    agent_name: Optional[str] = None
    task_id: Optional[str] = None
    response: Any = None
    error: Optional[str] = None
    execution_time: float = 0.0
    agents_used: List[str] = None
    camel_conversation_id: Optional[str] = None

    def __post_init__(self):
        if self.agents_used is None:
            self.agents_used = []


class AgentDelegator:
    """
    Advanced agent delegation system using CAMEL and OWL clients.

    This creates the "agent manager under ultimate_orchestrator" that dynamically
    creates and manages agent teams for complex tasks.
    """

    def __init__(self):
        # System clients for dynamic agent creation
        self.camel_client = camel_client
        self.owl_client = OwlClient()

        # Track dynamically created agents
        self.active_agents: Dict[str, DynamicAgent] = {}
        self.agent_templates = self._get_agent_templates()

        # Delegation history and performance tracking
        self.delegation_history = []

    async def initialize(self):
        """Initialize the delegator with system clients."""
        try:
            # Ensure clients are ready
            logger.info("Initializing AgentDelegator with CAMEL and OWL clients")

            # Test client availability
            if hasattr(self.camel_client, '_get_session'):
                await self.camel_client._get_session()

            logger.info("AgentDelegator initialized successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to initialize AgentDelegator: {e}")
            return False

    def _get_agent_templates(self) -> Dict[AgentType, Dict[str, Any]]:
        """Get templates for different agent types."""
        return {
            AgentType.ACCOUNTING: {
                "template": "accountant",
                "capabilities": ["accounting", "financial analysis", "budgeting", "tax calculation"],
                "system_message": "You are an expert accountant with deep knowledge of financial systems."
            },
            AgentType.RESEARCH: {
                "template": "researcher",
                "capabilities": ["research", "data analysis", "information gathering", "synthesis"],
                "system_message": "You are an expert researcher skilled at finding and analyzing information."
            },
            AgentType.WRITING: {
                "template": "writer",
                "capabilities": ["writing", "editing", "content creation", "communication"],
                "system_message": "You are an expert writer skilled at creating clear and engaging content."
            },
            AgentType.CODING: {
                "template": "programmer",
                "capabilities": ["programming", "code review", "debugging", "architecture"],
                "system_message": "You are an expert programmer skilled at writing and maintaining code."
            },
            AgentType.ANALYSIS: {
                "template": "analyst",
                "capabilities": ["analysis", "problem solving", "decision making", "evaluation"],
                "system_message": "You are an expert analyst skilled at breaking down complex problems."
            },
            AgentType.GENERAL: {
                "template": "assistant",
                "capabilities": ["general assistance", "coordination", "task management"],
                "system_message": "You are a helpful assistant skilled at coordinating and managing tasks."
            },
            AgentType.TEAM_LEAD: {
                "template": "team_lead",
                "capabilities": ["leadership", "coordination", "project management", "delegation"],
                "system_message": "You are an expert team leader skilled at coordinating multiple agents."
            }
        }
    
    async def delegate_to_agent(
        self,
        agent_type: AgentType,
        request: str,
        context: Dict[str, Any] = None,
        priority: TaskPriority = TaskPriority.NORMAL
    ) -> DelegationResult:
        """
        Delegate request to dynamically created agent using CAMEL client.

        Args:
            agent_type: Type of agent to create
            request: The request to process
            context: Additional context
            priority: Task priority

        Returns:
            DelegationResult with execution details
        """
        if context is None:
            context = {}

        start_time = time.time()
        task_id = f"task_{uuid.uuid4().hex[:8]}"

        try:
            # Create or reuse dynamic agent
            agent = await self._get_or_create_agent(agent_type)

            if not agent:
                return DelegationResult(
                    success=False,
                    agent_name=agent_type.value,
                    task_id=task_id,
                    error="Failed to create agent",
                    execution_time=time.time() - start_time
                )

            # Execute task using CAMEL client
            logger.info(f"Delegating task {task_id} to {agent_type.value} agent")

            # For single agent tasks, use direct CAMEL task execution
            if agent_type != AgentType.TEAM_LEAD:
                result = await self._execute_single_agent_task(agent, request, context)
                agents_used = [agent.agent_id]
                camel_conversation_id = None
            else:
                # For team lead, create a team
                result = await self._execute_team_task(request, context)
                agents_used = result.get("agents_used", [])
                camel_conversation_id = result.get("conversation_id")

            execution_time = time.time() - start_time

            if result and result.get("success", False):
                delegation_result = DelegationResult(
                    success=True,
                    agent_name=agent_type.value,
                    task_id=task_id,
                    response=result,
                    execution_time=execution_time,
                    agents_used=agents_used,
                    camel_conversation_id=camel_conversation_id
                )

                # Update agent performance
                agent.performance_score = min(1.0, agent.performance_score + 0.1)
                agent.last_used = datetime.now()

            else:
                delegation_result = DelegationResult(
                    success=False,
                    agent_name=agent_type.value,
                    task_id=task_id,
                    error=result.get("error", "Task execution failed") if result else "No result",
                    execution_time=execution_time,
                    agents_used=agents_used
                )

                # Penalize agent performance
                agent.performance_score = max(0.0, agent.performance_score - 0.1)

            # Track delegation
            self._track_delegation(delegation_result, request)

            return delegation_result

        except Exception as e:
            execution_time = time.time() - start_time
            logger.error(f"Error delegating to agent {agent_type.value}: {e}")

            return DelegationResult(
                success=False,
                agent_name=agent_type.value,
                task_id=task_id,
                error=str(e),
                execution_time=execution_time
            )

    async def _get_or_create_agent(self, agent_type: AgentType) -> Optional[DynamicAgent]:
        """Get existing agent or create new one."""
        try:
            # Look for existing agent of this type
            for agent in self.active_agents.values():
                if agent.agent_type == agent_type and agent.performance_score > 0.3:
                    agent.last_used = datetime.now()
                    return agent

            # Create new agent
            agent_id = f"{agent_type.value}_{uuid.uuid4().hex[:8]}"
            template = self.agent_templates.get(agent_type, {})

            # Create CAMEL agent
            camel_response = await self.camel_client.create_agent(
                role=template.get("template", "assistant"),
                name=f"{agent_type.value}_agent_{agent_id}",
                system_message=template.get("system_message", "You are a helpful assistant."),
                custom_parameters={"capabilities": template.get("capabilities", [])}
            )

            if not camel_response.success:
                logger.error(f"Failed to create CAMEL agent: {camel_response.message}")
                return None

            # Create dynamic agent wrapper
            dynamic_agent = DynamicAgent(
                agent_id=agent_id,
                agent_type=agent_type,
                capabilities=template.get("capabilities", []),
                camel_agent_id=camel_response.data.get("agent_id")
            )

            self.active_agents[agent_id] = dynamic_agent
            logger.info(f"Created new dynamic agent: {agent_id} ({agent_type.value})")

            return dynamic_agent

        except Exception as e:
            logger.error(f"Error creating agent {agent_type.value}: {e}")
            return None

    async def _execute_single_agent_task(self, agent: DynamicAgent, request: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute task with single CAMEL agent."""
        try:
            task_data = {
                "task": request,
                "context": context,
                "agent_id": agent.camel_agent_id
            }

            result = await self.camel_client.run_agent_task(
                agent_id=agent.camel_agent_id,
                task=request,
                context=context
            )

            return {
                "success": result.success,
                "result": result.data if result.success else None,
                "error": result.message if not result.success else None
            }

        except Exception as e:
            logger.error(f"Error executing single agent task: {e}")
            return {"success": False, "error": str(e)}

    async def _execute_team_task(self, request: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute complex task with agent team using CAMEL."""
        try:
            # Determine required agent types for this task
            required_types = self._analyze_task_requirements(request, context)

            # Create agents
            agents = []
            for agent_type in required_types:
                agent = await self._get_or_create_agent(agent_type)
                if agent:
                    agents.append(agent)

            if not agents:
                return {"success": False, "error": "Could not create required agents"}

            # Create multi-agent task
            camel_result = await self.camel_client.run_multi_agent_task(
                task=request,
                roles=[agent.agent_type.value for agent in agents],
                context=context,
                max_turns=5
            )

            success, data, conversation_id = camel_result

            return {
                "success": success,
                "result": data,
                "agents_used": [agent.agent_id for agent in agents],
                "conversation_id": conversation_id,
                "error": data.get("error") if not success else None
            }

        except Exception as e:
            logger.error(f"Error executing team task: {e}")
            return {"success": False, "error": str(e)}

    def _analyze_task_requirements(self, request: str, context: Dict[str, Any]) -> List[AgentType]:
        """Analyze what agent types are needed for a task."""
        requirements = []
        request_lower = request.lower()

        # Simple keyword-based analysis
        if any(word in request_lower for word in ["money", "finance", "accounting", "budget"]):
            requirements.append(AgentType.ACCOUNTING)

        if any(word in request_lower for word in ["research", "find", "analyze", "data"]):
            requirements.append(AgentType.RESEARCH)

        if any(word in request_lower for word in ["write", "create", "content", "text"]):
            requirements.append(AgentType.WRITING)

        if any(word in request_lower for word in ["code", "program", "develop", "implement"]):
            requirements.append(AgentType.CODING)

        # Always include a team lead for complex tasks
        if len(requirements) > 1:
            requirements.append(AgentType.TEAM_LEAD)

        # Default to general assistant if no specific requirements
        if not requirements:
            requirements.append(AgentType.GENERAL)

        return requirements
    
    async def find_best_agent_type(self, request: str, context: Dict[str, Any] = None) -> Optional[AgentType]:
        """
        Find the best agent type for handling a request.

        Args:
            request: The request to analyze
            context: Additional context

        Returns:
            Best AgentType or None if no suitable type found
        """
        if context is None:
            context = {}

        try:
            # Analyze task requirements
            required_types = self._analyze_task_requirements(request, context)

            if not required_types:
                return AgentType.GENERAL

            # For complex tasks requiring multiple agents, use team lead
            if len(required_types) > 1:
                return AgentType.TEAM_LEAD

            # Return the primary required type
            return required_types[0]

        except Exception as e:
            logger.error(f"Error finding best agent type: {e}")
            return AgentType.GENERAL
    
    # REMOVED: _score_agent_for_request - replaced by _analyze_task_requirements
    # REMOVED: _load_agent_capabilities - replaced by dynamic agent creation
    
    def _track_delegation(self, result: DelegationResult, request: str):
        """Track delegation for performance analysis."""
        
        self.delegation_history.append({
            "timestamp": datetime.now(),
            "agent_name": result.agent_name,
            "success": result.success,
            "execution_time": result.execution_time,
            "request_length": len(request)
        })
        
        # Keep only recent history
        if len(self.delegation_history) > 1000:
            self.delegation_history = self.delegation_history[-500:]
    
    def cleanup_inactive_agents(self, max_age_hours: int = 24):
        """Clean up agents that haven't been used recently."""
        cutoff_time = datetime.now().replace(hour=datetime.now().hour - max_age_hours)

        agents_to_remove = []
        for agent_id, agent in self.active_agents.items():
            if agent.last_used < cutoff_time:
                agents_to_remove.append(agent_id)

        for agent_id in agents_to_remove:
            del self.active_agents[agent_id]
            logger.info(f"Cleaned up inactive agent: {agent_id}")

        return len(agents_to_remove)
    
    def get_delegation_stats(self) -> Dict[str, Any]:
        """Get delegation statistics."""
        return {
            "total_delegations": len(self.delegation_history),
            "active_agents": len(self.active_agents),
            "successful_delegations": sum(1 for h in self.delegation_history if h["success"]),
            "agent_types_created": list(set(agent.agent_type.value for agent in self.active_agents.values())),
            "delegation_history_size": len(self.delegation_history)
        }

    def get_active_agents_info(self) -> Dict[str, Any]:
        """Get information about active dynamic agents."""
        return {
            agent_id: {
                "type": agent.agent_type.value,
                "capabilities": agent.capabilities,
                "performance_score": agent.performance_score,
                "created_at": agent.created_at.isoformat(),
                "last_used": agent.last_used.isoformat()
            }
            for agent_id, agent in self.active_agents.items()
        }


# Global delegator instance - the new agent manager under ultimate orchestrator
agent_delegator = AgentDelegator()