"""
A2A Agent - Core Agent Implementation for A2A Protocol

Provides the base agent class and specialized agent implementations
for the Agent-to-Agent communication protocol in HappyOS.
"""

import asyncio
import logging
from typing import Dict, Any, Optional, List, Callable
from datetime import datetime
from abc import ABC, abstractmethod

from .constants import (
    AgentCapability,
    MessageType,
    MessagePriority,
    AgentState,
    DEFAULT_CONFIG,
    AgentType,
    CrossAgentWorkflowType,
    WorkflowState
)
from .client import A2AClient
from .identity import IdentityManager

logger = logging.getLogger(__name__)


class A2AAgent(A2AClient):
    """
    Base class for A2A Protocol agents.

    Provides common functionality for all agents in the HappyOS A2A ecosystem.
    """

    def __init__(self,
                 agent_id: str,
                 capabilities: List[AgentCapability],
                 agent_type: str = "base",
                 description: str = "Base A2A Agent"):
        """
        Initialize A2A Agent.

        Args:
            agent_id: Unique identifier for this agent
            capabilities: List of capabilities this agent provides
            agent_type: Type/category of agent
            description: Human-readable description
        """
        super().__init__(agent_id, capabilities)

        self.agent_type = agent_type
        self.description = description
        self.state = AgentState.REGISTERING

        # Agent-specific attributes
        self.skills: List[str] = []
        self.services: List[str] = []
        self.metadata: Dict[str, Any] = {}

        # Performance tracking
        self.performance_stats = {
            "messages_processed": 0,
            "successful_operations": 0,
            "failed_operations": 0,
            "average_response_time": 0.0,
            "uptime_start": datetime.utcnow()
        }

        logger.info(f"A2A Agent initialized: {agent_id} ({agent_type})")

    async def initialize(self) -> bool:
        """Initialize the agent."""
        try:
            # Call parent initialization
            success = await super().initialize()

            if success:
                self.state = AgentState.ACTIVE
                logger.info(f"Agent {self.agent_id} initialized successfully")
            else:
                self.state = AgentState.ERROR
                logger.error(f"Agent {self.agent_id} initialization failed")

            return success

        except Exception as e:
            logger.error(f"Agent initialization error: {e}")
            self.state = AgentState.ERROR
            return False

    @abstractmethod
    async def process_message(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process an incoming message.

        Args:
            message: Message to process

        Returns:
            Processing result
        """
        pass

    async def handle_health_check(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Handle health check requests."""
        return {
            "status": self.state.value,
            "agent_id": self.agent_id,
            "agent_type": self.agent_type,
            "description": self.description,
            "capabilities": [cap.value for cap in self.capabilities],
            "uptime_seconds": (datetime.utcnow() - self.performance_stats["uptime_start"]).total_seconds(),
            "messages_processed": self.performance_stats["messages_processed"],
            "success_rate": (self.performance_stats["successful_operations"] /
                           max(1, self.performance_stats["successful_operations"] +
                               self.performance_stats["failed_operations"])) * 100
        }

    async def handle_capability_info(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Handle capability information requests."""
        requested_capability = parameters.get("capability")

        if requested_capability:
            has_capability = requested_capability in [cap.value for cap in self.capabilities]
            return {
                "capability": requested_capability,
                "supported": has_capability,
                "agent_id": self.agent_id,
                "agent_type": self.agent_type
            }
        else:
            return {
                "capabilities": [cap.value for cap in self.capabilities],
                "skills": self.skills,
                "services": self.services,
                "agent_id": self.agent_id,
                "agent_type": self.agent_type
            }

    def update_performance_stats(self, operation_success: bool, response_time: float = 0.0):
        """Update performance statistics."""
        self.performance_stats["messages_processed"] += 1

        if operation_success:
            self.performance_stats["successful_operations"] += 1
        else:
            self.performance_stats["failed_operations"] += 1

        # Update average response time
        total_operations = (self.performance_stats["successful_operations"] +
                          self.performance_stats["failed_operations"])
        if total_operations > 1:
            current_avg = self.performance_stats["average_response_time"]
            self.performance_stats["average_response_time"] = (
                (current_avg * (total_operations - 1) + response_time) / total_operations
            )

    def get_agent_info(self) -> Dict[str, Any]:
        """Get comprehensive agent information."""
        return {
            "agent_id": self.agent_id,
            "agent_type": self.agent_type,
            "description": self.description,
            "state": self.state.value,
            "capabilities": [cap.value for cap in self.capabilities],
            "skills": self.skills,
            "services": self.services,
            "metadata": self.metadata,
            "performance_stats": self.performance_stats,
            "client_status": self.get_client_status()
        }


class SpecializedA2AAgent(A2AAgent):
    """
    Base class for specialized A2A agents with domain-specific functionality.

    Provides common patterns for agents that need to handle specific
    types of requests or provide specialized services.
    """

    def __init__(self,
                 agent_id: str,
                 capabilities: List[AgentCapability],
                 specialization: str,
                 domain: str = "general"):
        """
        Initialize specialized agent.

        Args:
            agent_id: Unique identifier
            capabilities: Agent capabilities
            specialization: Specialization area
            domain: Domain of expertise
        """
        super().__init__(
            agent_id,
            capabilities,
            agent_type=f"specialized_{specialization}",
            description=f"Specialized {specialization} agent for {domain} domain"
        )

        self.specialization = specialization
        self.domain = domain

        # Specialization-specific attributes
        self.domain_knowledge: Dict[str, Any] = {}
        self.specialized_handlers: Dict[str, Callable] = {}

    async def register_specialized_handler(self, action: str, handler: Callable):
        """Register a specialized message handler."""
        self.specialized_handlers[action] = handler
        await self.register_message_handler(action, handler)
        logger.debug(f"Registered specialized handler for action: {action}")

    async def process_message(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """Process message with specialization support."""
        try:
            # Try specialized handler first
            payload = message.get("payload", {})
            action = payload.get("action")

            if action and action in self.specialized_handlers:
                start_time = datetime.utcnow()
                result = await self.specialized_handlers[action](payload)
                response_time = (datetime.utcnow() - start_time).total_seconds()

                self.update_performance_stats(True, response_time)
                return result

            # Fall back to general processing
            return await self._process_general_message(message)

        except Exception as e:
            logger.error(f"Specialized message processing failed: {e}")
            response_time = (datetime.utcnow() - datetime.utcnow()).total_seconds()  # Would need proper timing
            self.update_performance_stats(False, response_time)
            return {
                "success": False,
                "error": str(e)
            }

    @abstractmethod
    async def _process_general_message(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """Process general messages not handled by specialized handlers."""
        pass


class OrchestratorAgent(A2AAgent):
    """
    Agent specialized in orchestrating other agents and workflows.

    Manages complex multi-agent workflows and coordinates task execution
    across multiple specialized agents.
    """

    def __init__(self, agent_id: str = "a2a_orchestrator"):
        super().__init__(
            agent_id,
            [AgentCapability.ORCHESTRATION, AgentCapability.GENERAL],
            agent_type="orchestrator",
            description="A2A Protocol Orchestrator Agent"
        )

        self.active_workflows: Dict[str, Dict[str, Any]] = {}
        self.managed_agents: Dict[str, Dict[str, Any]] = {}

    async def initialize(self) -> bool:
        """Initialize orchestrator agent."""
        success = await super().initialize()

        if success:
            # Setup orchestrator-specific handlers
            await self.register_message_handler("create_workflow", self.handle_create_workflow)
            await self.register_message_handler("execute_workflow", self.handle_execute_workflow)
            await self.register_message_handler("list_workflows", self.handle_list_workflows)
            await self.register_message_handler("cross_agent_workflow", self.handle_cross_agent_workflow)

        return success

    async def process_message(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """Process orchestrator-specific messages."""
        # Delegate to parent implementation
        return await super().process_message(message)

    async def handle_create_workflow(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Handle workflow creation requests."""
        workflow_id = f"workflow_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"

        workflow = {
            "workflow_id": workflow_id,
            "name": parameters.get("name", "Unnamed Workflow"),
            "description": parameters.get("description", ""),
            "steps": parameters.get("steps", []),
            "created_at": datetime.utcnow().isoformat(),
            "status": "created"
        }

        self.active_workflows[workflow_id] = workflow

        return {
            "workflow_id": workflow_id,
            "status": "created",
            "message": f"Workflow '{workflow['name']}' created successfully"
        }

    async def handle_execute_workflow(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Handle workflow execution requests."""
        workflow_id = parameters.get("workflow_id")

        if workflow_id not in self.active_workflows:
            return {
                "success": False,
                "error": f"Workflow {workflow_id} not found"
            }

        workflow = self.active_workflows[workflow_id]
        workflow["status"] = "executing"
        workflow["started_at"] = datetime.utcnow().isoformat()

        # Execute workflow steps (simplified implementation)
        try:
            # In production, this would orchestrate actual workflow execution
            await asyncio.sleep(0.1)  # Simulate work

            workflow["status"] = "completed"
            workflow["completed_at"] = datetime.utcnow().isoformat()

            return {
                "workflow_id": workflow_id,
                "status": "completed",
                "result": "Workflow executed successfully"
            }

        except Exception as e:
            workflow["status"] = "failed"
            workflow["error"] = str(e)

            return {
                "success": False,
                "error": f"Workflow execution failed: {str(e)}"
            }

    async def handle_list_workflows(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Handle workflow listing requests."""
        return {
            "workflows": list(self.active_workflows.values()),
            "total_count": len(self.active_workflows)
        }

    # Cross-agent workflow orchestration methods

    async def handle_cross_agent_workflow(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Handle cross-agent workflow orchestration."""
        workflow_type = parameters.get("workflow_type")
        workflow_data = parameters.get("workflow_data", {})
        participating_agents = parameters.get("participating_agents", [])
        tenant_id = parameters.get("tenant_id")
        
        if not all([workflow_type, participating_agents, tenant_id]):
            return {
                "success": False,
                "error": "Missing required parameters: workflow_type, participating_agents, tenant_id"
            }
        
        try:
            workflow_type_enum = CrossAgentWorkflowType(workflow_type)
        except ValueError:
            return {
                "success": False,
                "error": f"Invalid workflow type: {workflow_type}"
            }
        
        # Create workflow instance
        workflow_id = f"cross_agent_{workflow_type}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
        
        workflow = {
            "workflow_id": workflow_id,
            "workflow_type": workflow_type_enum.value,
            "participating_agents": participating_agents,
            "workflow_data": workflow_data,
            "tenant_id": tenant_id,
            "status": WorkflowState.CREATED.value,
            "created_at": datetime.utcnow().isoformat(),
            "steps": self._generate_workflow_steps(workflow_type_enum, workflow_data),
            "current_step": 0,
            "results": {}
        }
        
        self.active_workflows[workflow_id] = workflow
        
        # Start workflow execution
        execution_result = await self._execute_cross_agent_workflow(workflow)
        
        return {
            "workflow_id": workflow_id,
            "status": workflow["status"],
            "execution_result": execution_result
        }

    def _generate_workflow_steps(self, workflow_type: CrossAgentWorkflowType, 
                                workflow_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Generate workflow steps based on workflow type."""
        if workflow_type == CrossAgentWorkflowType.FINANCIAL_COMPLIANCE:
            return [
                {
                    "step": 1,
                    "agent": AgentType.MEETMIND.value,
                    "action": "extract_financial_topics",
                    "description": "Extract financial topics from meeting transcript"
                },
                {
                    "step": 2,
                    "agent": AgentType.FELICIAS_FINANCE.value,
                    "action": "analyze_financial_implications",
                    "description": "Analyze financial implications of discussed topics"
                },
                {
                    "step": 3,
                    "agent": AgentType.AGENT_SVEA.value,
                    "action": "validate_swedish_compliance",
                    "description": "Validate compliance with Swedish regulations"
                }
            ]
        elif workflow_type == CrossAgentWorkflowType.COMPREHENSIVE_REPORTING:
            return [
                {
                    "step": 1,
                    "agent": AgentType.AGENT_SVEA.value,
                    "action": "collect_erp_data",
                    "description": "Collect ERP data from Swedish systems"
                },
                {
                    "step": 2,
                    "agent": AgentType.FELICIAS_FINANCE.value,
                    "action": "collect_trading_data",
                    "description": "Collect trading and crypto data"
                },
                {
                    "step": 3,
                    "agent": AgentType.MEETMIND.value,
                    "action": "generate_executive_summary",
                    "description": "Generate executive summary from collected data"
                }
            ]
        elif workflow_type == CrossAgentWorkflowType.MEETING_FINANCIAL_ANALYSIS:
            return [
                {
                    "step": 1,
                    "agent": AgentType.MEETMIND.value,
                    "action": "process_meeting_transcript",
                    "description": "Process and analyze meeting transcript"
                },
                {
                    "step": 2,
                    "agent": AgentType.FELICIAS_FINANCE.value,
                    "action": "analyze_financial_context",
                    "description": "Analyze financial context of meeting discussions"
                },
                {
                    "step": 3,
                    "agent": AgentType.AGENT_SVEA.value,
                    "action": "check_compliance_implications",
                    "description": "Check compliance implications of financial decisions"
                }
            ]
        else:
            return [
                {
                    "step": 1,
                    "agent": "generic",
                    "action": "process_request",
                    "description": "Process generic cross-agent request"
                }
            ]

    async def _execute_cross_agent_workflow(self, workflow: Dict[str, Any]) -> Dict[str, Any]:
        """Execute cross-agent workflow steps."""
        workflow_id = workflow["workflow_id"]
        steps = workflow["steps"]
        
        try:
            workflow["status"] = WorkflowState.RUNNING.value
            workflow["started_at"] = datetime.utcnow().isoformat()
            
            for step in steps:
                step_number = step["step"]
                agent_type = step["agent"]
                action = step["action"]
                
                self.logger.info(f"Executing workflow {workflow_id} step {step_number}: {action}")
                
                # In a real implementation, this would send messages to actual agents
                # For now, we'll simulate the execution
                step_result = await self._execute_workflow_step(
                    workflow_id, step_number, agent_type, action, workflow["workflow_data"]
                )
                
                workflow["results"][f"step_{step_number}"] = step_result
                workflow["current_step"] = step_number
                
                if not step_result.get("success", False):
                    workflow["status"] = WorkflowState.FAILED.value
                    workflow["error"] = step_result.get("error", "Step execution failed")
                    break
            
            if workflow["status"] == WorkflowState.RUNNING.value:
                workflow["status"] = WorkflowState.COMPLETED.value
                workflow["completed_at"] = datetime.utcnow().isoformat()
            
            return {
                "success": workflow["status"] == WorkflowState.COMPLETED.value,
                "workflow_id": workflow_id,
                "status": workflow["status"],
                "results": workflow["results"]
            }
            
        except Exception as e:
            workflow["status"] = WorkflowState.FAILED.value
            workflow["error"] = str(e)
            
            return {
                "success": False,
                "workflow_id": workflow_id,
                "error": str(e)
            }

    async def _execute_workflow_step(self, workflow_id: str, step_number: int, 
                                   agent_type: str, action: str, 
                                   workflow_data: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a single workflow step."""
        try:
            # Simulate step execution - in real implementation, this would
            # send messages to actual agent instances
            await asyncio.sleep(0.1)  # Simulate processing time
            
            # Mock successful execution
            return {
                "success": True,
                "step": step_number,
                "agent": agent_type,
                "action": action,
                "result": f"Step {step_number} completed successfully",
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            return {
                "success": False,
                "step": step_number,
                "agent": agent_type,
                "action": action,
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }

    async def register_agent_capability(self, agent_id: str, agent_type: AgentType, 
                                       capabilities: List[AgentCapability],
                                       endpoint: str, metadata: Dict[str, Any] = None) -> Dict[str, Any]:
        """Register agent capabilities for workflow orchestration."""
        agent_info = {
            "agent_id": agent_id,
            "agent_type": agent_type.value,
            "capabilities": [cap.value for cap in capabilities],
            "endpoint": endpoint,
            "metadata": metadata or {},
            "registered_at": datetime.utcnow().isoformat(),
            "status": "active"
        }
        
        self.managed_agents[agent_id] = agent_info
        
        return {
            "success": True,
            "message": f"Agent {agent_id} registered successfully",
            "agent_info": agent_info
        }

    async def discover_agents_by_capability(self, required_capabilities: List[AgentCapability]) -> List[Dict[str, Any]]:
        """Discover agents that have required capabilities."""
        matching_agents = []
        required_cap_values = [cap.value for cap in required_capabilities]
        
        for agent_id, agent_info in self.managed_agents.items():
            agent_capabilities = agent_info.get("capabilities", [])
            
            # Check if agent has all required capabilities
            if all(cap in agent_capabilities for cap in required_cap_values):
                matching_agents.append(agent_info)
        
        return matching_agents


class SelfBuildingAgent(A2AAgent):
    """
    Agent specialized in self-building and agent creation.

    Can analyze requirements and generate new agents dynamically
    using the ADK (Agent Development Kit) patterns.
    """

    def __init__(self, agent_id: str = "self_builder"):
        super().__init__(
            agent_id,
            [AgentCapability.SELF_BUILDING, AgentCapability.CODING, AgentCapability.ANALYSIS],
            agent_type="self_builder",
            description="A2A Self-Building Agent for dynamic agent creation"
        )

        self.generated_agents: List[Dict[str, Any]] = []
        self.build_templates: Dict[str, Dict[str, Any]] = {}

    async def initialize(self) -> bool:
        """Initialize self-building agent."""
        success = await super().initialize()

        if success:
            # Setup self-building handlers
            await self.register_message_handler("generate_agent", self.handle_generate_agent)
            await self.register_message_handler("list_generated_agents", self.handle_list_generated_agents)

        return success

    async def process_message(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """Process self-building messages."""
        return await super().process_message(message)

    async def handle_generate_agent(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Handle agent generation requests."""
        try:
            agent_type = parameters.get("agent_type", "general")
            capabilities = parameters.get("capabilities", ["general"])
            description = parameters.get("description", f"Generated {agent_type} agent")

            # Generate new agent (simplified implementation)
            new_agent_id = f"generated_{agent_type}_{len(self.generated_agents) + 1}"

            generated_agent = {
                "agent_id": new_agent_id,
                "agent_type": agent_type,
                "capabilities": capabilities,
                "description": description,
                "generated_at": datetime.utcnow().isoformat(),
                "generated_by": self.agent_id,
                "status": "created"
            }

            self.generated_agents.append(generated_agent)

            return {
                "success": True,
                "agent_id": new_agent_id,
                "agent_type": agent_type,
                "message": f"Successfully generated {agent_type} agent: {new_agent_id}"
            }

        except Exception as e:
            return {
                "success": False,
                "error": f"Agent generation failed: {str(e)}"
            }

    async def handle_list_generated_agents(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Handle requests to list generated agents."""
        return {
            "generated_agents": self.generated_agents,
            "total_count": len(self.generated_agents)
        }


class MonitoringAgent(A2AAgent):
    """
    Agent specialized in monitoring and health management.

    Monitors the health and performance of other agents in the A2A network.
    """

    def __init__(self, agent_id: str = "monitor_agent"):
        super().__init__(
            agent_id,
            [AgentCapability.MONITORING, AgentCapability.ANALYSIS],
            agent_type="monitor",
            description="A2A Monitoring Agent for health and performance tracking"
        )

        self.monitored_agents: Dict[str, Dict[str, Any]] = {}
        self.alert_thresholds: Dict[str, float] = {
            "response_time": 5.0,  # seconds
            "error_rate": 0.1,     # 10%
            "failure_rate": 0.05   # 5%
        }

    async def initialize(self) -> bool:
        """Initialize monitoring agent."""
        success = await super().initialize()

        if success:
            # Setup monitoring handlers
            await self.register_message_handler("register_monitoring", self.handle_register_monitoring)
            await self.register_message_handler("get_health_report", self.handle_get_health_report)

        return success

    async def process_message(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """Process monitoring messages."""
        return await super().process_message(message)

    async def handle_register_monitoring(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Handle monitoring registration requests."""
        agent_id = parameters.get("agent_id")
        monitoring_config = parameters.get("config", {})

        if not agent_id:
            return {
                "success": False,
                "error": "agent_id is required"
            }

        self.monitored_agents[agent_id] = {
            "agent_id": agent_id,
            "config": monitoring_config,
            "registered_at": datetime.utcnow().isoformat(),
            "last_check": None,
            "health_history": []
        }

        return {
            "success": True,
            "message": f"Monitoring registered for agent: {agent_id}"
        }

    async def handle_get_health_report(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Handle health report requests."""
        agent_id = parameters.get("agent_id")

        if agent_id:
            # Get health for specific agent
            if agent_id in self.monitored_agents:
                return {
                    "agent_id": agent_id,
                    "health_status": "healthy",  # Would be calculated from actual metrics
                    "last_check": self.monitored_agents[agent_id]["last_check"],
                    "monitoring_config": self.monitored_agents[agent_id]["config"]
                }
            else:
                return {
                    "success": False,
                    "error": f"Agent {agent_id} not found in monitoring"
                }
        else:
            # Get health for all monitored agents
            all_reports = {}
            for aid, info in self.monitored_agents.items():
                all_reports[aid] = {
                    "health_status": "healthy",
                    "last_check": info["last_check"],
                    "monitoring_config": info["config"]
                }

            return {
                "all_agents": all_reports,
                "total_monitored": len(all_reports),
                "summary": {
                    "healthy": len([r for r in all_reports.values() if r["health_status"] == "healthy"]),
                    "degraded": len([r for r in all_reports.values() if r["health_status"] == "degraded"]),
                    "unhealthy": len([r for r in all_reports.values() if r["health_status"] == "unhealthy"])
                }
            }


# Factory function for creating agents
async def create_a2a_agent(agent_type: str,
                          agent_id: str,
                          capabilities: List[AgentCapability],
                          **kwargs) -> A2AAgent:
    """
    Factory function to create A2A agents of different types.

    Args:
        agent_type: Type of agent to create
        agent_id: Agent identifier
        capabilities: Agent capabilities
        **kwargs: Additional agent-specific parameters

    Returns:
        Configured A2A agent instance
    """
    try:
        if agent_type == "orchestrator":
            agent = OrchestratorAgent(agent_id)
        elif agent_type == "self_builder":
            agent = SelfBuildingAgent(agent_id)
        elif agent_type == "monitor":
            agent = MonitoringAgent(agent_id)
        elif agent_type.startswith("specialized_"):
            specialization = agent_type.replace("specialized_", "")
            agent = SpecializedA2AAgent(agent_id, capabilities, specialization, **kwargs)
        else:
            agent = A2AAgent(agent_id, capabilities, agent_type, **kwargs)

        return agent

    except Exception as e:
        logger.error(f"Failed to create {agent_type} agent: {e}")
        raise


# Example usage
async def example_agent_creation():
    """Example of creating and using different types of A2A agents."""

    # Create orchestrator agent
    orchestrator = await create_a2a_agent(
        "orchestrator",
        "main_orchestrator",
        [AgentCapability.ORCHESTRATION, AgentCapability.GENERAL]
    )

    # Create self-building agent
    builder = await create_a2a_agent(
        "self_builder",
        "agent_builder",
        [AgentCapability.SELF_BUILDING, AgentCapability.CODING]
    )

    # Create monitoring agent
    monitor = await create_a2a_agent(
        "monitor",
        "health_monitor",
        [AgentCapability.MONITORING, AgentCapability.ANALYSIS]
    )

    return {
        "orchestrator": orchestrator,
        "builder": builder,
        "monitor": monitor
    }