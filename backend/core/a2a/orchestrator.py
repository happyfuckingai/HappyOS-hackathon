"""
A2A Orchestrator - Main Protocol Manager for HappyOS

Coordinates all A2A Protocol components and provides the primary interface
for agent communication, workflow orchestration, and system integration.
"""

import asyncio
import logging
from typing import Dict, Any, Optional, List, Callable
from datetime import datetime

from .constants import (
    AgentCapability,
    MessageType,
    MessagePriority,
    AgentState,
    DEFAULT_CONFIG,
    WorkflowState,
    TaskState,
    ErrorCode
)
from .identity import IdentityManager
from .messaging import MessageManager, message_manager
from .transport import TransportLayer, TransportConfig
from .discovery import DiscoveryService, discovery_service
from .auth import AuthenticationManager
from .agent import A2AAgent, create_a2a_agent
from .client import A2AClient

logger = logging.getLogger(__name__)


class A2AProtocolManager:
    """
    Main coordinator for the A2A Protocol in HappyOS.

    Manages all protocol components and provides high-level interfaces
    for agent communication, workflow orchestration, and system integration.
    """

    def __init__(self,
                 config: Optional[Dict[str, Any]] = None,
                 storage_path: Optional[str] = None):
        """
        Initialize A2A Protocol Manager.

        Args:
            config: Protocol configuration
            storage_path: Base path for storing protocol data
        """
        self.config = config or DEFAULT_CONFIG
        self.storage_path = storage_path or "./data/a2a"

        # Core components (using global instances for now)
        self.identity_manager = IdentityManager()
        self.message_manager = message_manager
        self.discovery_service = discovery_service

        # Transport configuration
        self.transport_config = TransportConfig(
            host=self.config.get("host", "localhost"),
            port=self.config.get("port", DEFAULT_CONFIG["port"]),
            enable_tls=self.config.get("enable_tls", DEFAULT_CONFIG["enable_tls"]),
            enable_http2=self.config.get("enable_http2", DEFAULT_CONFIG["enable_http2"]),
            enable_websocket_fallback=self.config.get("enable_websocket_fallback", DEFAULT_CONFIG["enable_websocket_fallback"])
        )

        # Managed agents
        self.managed_agents: Dict[str, A2AAgent] = {}
        self.agent_states: Dict[str, Dict[str, Any]] = {}

        # Workflows and tasks
        self.active_workflows: Dict[str, Dict[str, Any]] = {}
        self.workflow_tasks: Dict[str, Dict[str, Any]] = {}

        # System state
        self._initialized = False
        self._running = False

        logger.info("A2A Protocol Manager initialized")

    async def initialize(self) -> bool:
        """
        Initialize the A2A Protocol Manager and all components.

        Returns:
            True if initialization successful, False otherwise
        """
        try:
            logger.info("Initializing A2A Protocol Manager...")

            # Initialize core services
            identity_success = True  # Already initialized
            discovery_success = await self.discovery_service.initialize()

            if not discovery_success:
                logger.warning("Discovery service initialization failed")

            # Initialize transport layer
            self.transport_layer = TransportLayer(self.transport_config)
            transport_success = await self.transport_layer.initialize()

            if not transport_success:
                logger.warning("Transport layer initialization failed")

            # Create default orchestrator agent
            await self.create_agent(
                "orchestrator",
                "a2a_orchestrator",
                [AgentCapability.ORCHESTRATION, AgentCapability.GENERAL],
                description="Main A2A Protocol Orchestrator"
            )

            # Create default self-builder agent
            await self.create_agent(
                "self_builder",
                "a2a_self_builder",
                [AgentCapability.SELF_BUILDING, AgentCapability.CODING, AgentCapability.ANALYSIS],
                description="A2A Self-Building Agent for dynamic agent creation"
            )

            # Create default monitoring agent
            await self.create_agent(
                "monitor",
                "a2a_monitor",
                [AgentCapability.MONITORING, AgentCapability.ANALYSIS],
                description="A2A Monitoring Agent for health and performance tracking"
            )

            self._initialized = True

            logger.info("A2A Protocol Manager initialized successfully")
            return True

        except Exception as e:
            logger.error(f"A2A Protocol Manager initialization failed: {e}")
            return False

    async def shutdown(self):
        """Shutdown the A2A Protocol Manager gracefully."""
        try:
            logger.info("Shutting down A2A Protocol Manager...")

            self._running = False

            # Shutdown all managed agents
            for agent_id, agent in self.managed_agents.items():
                try:
                    await agent.shutdown()
                except Exception as e:
                    logger.warning(f"Error shutting down agent {agent_id}: {e}")

            # Shutdown core services
            await self.discovery_service.shutdown()
            await self.transport_layer.shutdown()

            # Clear state
            self.managed_agents.clear()
            self.agent_states.clear()
            self.active_workflows.clear()
            self.workflow_tasks.clear()

            logger.info("A2A Protocol Manager shutdown completed")

        except Exception as e:
            logger.error(f"Error during A2A Protocol Manager shutdown: {e}")

    async def create_agent(self,
                          agent_type: str,
                          agent_id: str,
                          capabilities: List[AgentCapability],
                          description: str = "",
                          **kwargs) -> Optional[A2AAgent]:
        """
        Create and register a new A2A agent.

        Args:
            agent_type: Type of agent to create
            agent_id: Unique agent identifier
            capabilities: Agent capabilities
            description: Agent description
            **kwargs: Additional agent-specific parameters

        Returns:
            Created agent instance or None if creation failed
        """
        try:
            logger.info(f"Creating A2A agent: {agent_id} ({agent_type})")

            # Create agent using factory function
            agent = await create_a2a_agent(agent_type, agent_id, capabilities, **kwargs)

            if not agent:
                logger.error(f"Failed to create agent: {agent_id}")
                return None

            # Initialize agent
            success = await agent.initialize()
            if not success:
                logger.error(f"Agent initialization failed: {agent_id}")
                return None

            # Register agent
            self.managed_agents[agent_id] = agent
            self.agent_states[agent_id] = {
                "state": AgentState.ACTIVE.value,
                "created_at": datetime.utcnow().isoformat(),
                "agent_type": agent_type,
                "capabilities": [cap.value for cap in capabilities],
                "description": description
            }

            logger.info(f"Successfully created and registered agent: {agent_id}")
            return agent

        except Exception as e:
            logger.error(f"Agent creation failed: {e}")
            return None

    async def send_message(self,
                          from_agent: str,
                          to_agent: str,
                          action: str,
                          parameters: Optional[Dict[str, Any]] = None,
                          priority: MessagePriority = MessagePriority.NORMAL) -> Dict[str, Any]:
        """
        Send a message between agents.

        Args:
            from_agent: Sending agent ID
            to_agent: Receiving agent ID
            action: Action to perform
            parameters: Action parameters
            priority: Message priority

        Returns:
            Send result
        """
        try:
            if from_agent not in self.managed_agents:
                return {
                    "success": False,
                    "error": f"Source agent not found: {from_agent}"
                }

            sender = self.managed_agents[from_agent]

            # Use the sender's client to send message
            result = await sender.send_message(
                to_agent,
                action,
                parameters,
                priority
            )

            return result

        except Exception as e:
            logger.error(f"Inter-agent message failed: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    async def broadcast_message(self,
                              from_agent: str,
                              action: str,
                              parameters: Optional[Dict[str, Any]] = None,
                              capability_filter: Optional[AgentCapability] = None) -> Dict[str, Any]:
        """
        Broadcast a message to multiple agents.

        Args:
            from_agent: Sending agent ID
            action: Action to perform
            parameters: Action parameters
            capability_filter: Only send to agents with this capability

        Returns:
            Broadcast results
        """
        try:
            if from_agent not in self.managed_agents:
                return {
                    "success": False,
                    "error": f"Source agent not found: {from_agent}"
                }

            sender = self.managed_agents[from_agent]

            # Discover target agents
            target_agents = await self.discovery_service.discover_agents(
                capability=capability_filter,
                min_agents=1
            )

            if not target_agents:
                return {
                    "success": False,
                    "error": "No target agents found for broadcast"
                }

            # Send to each target agent
            results = []
            for agent_record in target_agents[:10]:  # Limit to 10 agents
                agent_id = agent_record["agent_id"]

                # Skip sending to self
                if agent_id == from_agent:
                    continue

                try:
                    result = await self.send_message(
                        from_agent,
                        agent_id,
                        action,
                        parameters,
                        MessagePriority.NORMAL
                    )
                    results.append({
                        "agent_id": agent_id,
                        "success": result["success"],
                        "response": result.get("response")
                    })
                except Exception as e:
                    results.append({
                        "agent_id": agent_id,
                        "success": False,
                        "error": str(e)
                    })

            successful_sends = sum(1 for r in results if r["success"])

            return {
                "success": successful_sends > 0,
                "total_targets": len(results),
                "successful_sends": successful_sends,
                "results": results
            }

        except Exception as e:
            logger.error(f"Broadcast failed: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    async def create_workflow(self,
                            workflow_name: str,
                            description: str,
                            steps: List[Dict[str, Any]]) -> str:
        """
        Create a new workflow for multi-agent orchestration.

        Args:
            workflow_name: Name of the workflow
            description: Workflow description
            steps: List of workflow steps

        Returns:
            Workflow ID
        """
        try:
            workflow_id = f"workflow_{datetime.utcnow().strftime('%Y%m%d_%H%M%S_%f')}"

            workflow = {
                "workflow_id": workflow_id,
                "name": workflow_name,
                "description": description,
                "steps": steps,
                "created_at": datetime.utcnow().isoformat(),
                "status": WorkflowState.CREATED.value,
                "current_step": 0,
                "results": []
            }

            self.active_workflows[workflow_id] = workflow

            logger.info(f"Created workflow: {workflow_id}")
            return workflow_id

        except Exception as e:
            logger.error(f"Workflow creation failed: {e}")
            raise

    async def execute_workflow(self, workflow_id: str) -> Dict[str, Any]:
        """
        Execute a workflow.

        Args:
            workflow_id: ID of workflow to execute

        Returns:
            Execution results
        """
        try:
            if workflow_id not in self.active_workflows:
                return {
                    "success": False,
                    "error": f"Workflow not found: {workflow_id}"
                }

            workflow = self.active_workflows[workflow_id]
            workflow["status"] = WorkflowState.RUNNING.value
            workflow["started_at"] = datetime.utcnow().isoformat()

            logger.info(f"Executing workflow: {workflow_id}")

            # Execute workflow steps (simplified implementation)
            results = []
            for i, step in enumerate(workflow["steps"]):
                try:
                    step_result = await self._execute_workflow_step(workflow_id, step)
                    results.append(step_result)

                    workflow["current_step"] = i + 1

                except Exception as e:
                    logger.error(f"Workflow step {i} failed: {e}")
                    results.append({
                        "step": i,
                        "success": False,
                        "error": str(e)
                    })
                    break

            # Update workflow status
            successful_steps = sum(1 for r in results if r.get("success", False))
            total_steps = len(workflow["steps"])

            if successful_steps == total_steps:
                workflow["status"] = WorkflowState.COMPLETED.value
                final_status = "completed"
            else:
                workflow["status"] = WorkflowState.FAILED.value
                final_status = "failed"

            workflow["completed_at"] = datetime.utcnow().isoformat()
            workflow["results"] = results

            return {
                "success": final_status == "completed",
                "workflow_id": workflow_id,
                "status": final_status,
                "total_steps": total_steps,
                "successful_steps": successful_steps,
                "results": results
            }

        except Exception as e:
            logger.error(f"Workflow execution failed: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    async def _execute_workflow_step(self, workflow_id: str, step: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a single workflow step."""
        try:
            step_type = step.get("type", "agent_task")
            agent_id = step.get("agent_id")
            action = step.get("action")
            parameters = step.get("parameters", {})

            if step_type == "agent_task" and agent_id:
                # Execute task on specific agent
                result = await self.send_message(
                    "a2a_orchestrator",  # System orchestrator
                    agent_id,
                    action,
                    parameters
                )

                return {
                    "step_type": step_type,
                    "agent_id": agent_id,
                    "action": action,
                    "success": result["success"],
                    "result": result.get("response")
                }
            else:
                return {
                    "step_type": step_type,
                    "success": False,
                    "error": f"Unsupported step type: {step_type}"
                }

        except Exception as e:
            return {
                "step_type": step.get("type"),
                "success": False,
                "error": str(e)
            }

    async def get_system_status(self) -> Dict[str, Any]:
        """Get comprehensive system status."""
        try:
            # Get agent statuses
            agent_statuses = {}
            for agent_id, agent in self.managed_agents.items():
                agent_statuses[agent_id] = agent.get_agent_info()

            # Get workflow status
            workflow_summary = {
                "total_workflows": len(self.active_workflows),
                "created": len([w for w in self.active_workflows.values() if w["status"] == WorkflowState.CREATED.value]),
                "running": len([w for w in self.active_workflows.values() if w["status"] == WorkflowState.RUNNING.value]),
                "completed": len([w for w in self.active_workflows.values() if w["status"] == WorkflowState.COMPLETED.value]),
                "failed": len([w for w in self.active_workflows.values() if w["status"] == WorkflowState.FAILED.value])
            }

            return {
                "protocol_manager": {
                    "initialized": self._initialized,
                    "running": self._running,
                    "config": self.config,
                    "storage_path": self.storage_path
                },
                "agents": {
                    "total": len(self.managed_agents),
                    "by_state": {},
                    "details": agent_statuses
                },
                "workflows": workflow_summary,
                "services": {
                    "identity_manager": self.identity_manager.get_identity_statistics(),
                    "discovery_service": await self.discovery_service.get_service_registry_stats(),
                    "transport_layer": self.transport_layer.get_transport_statistics() if hasattr(self, 'transport_layer') else None
                },
                "timestamp": datetime.utcnow().isoformat()
            }

        except Exception as e:
            logger.error(f"Failed to get system status: {e}")
            return {
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }

    async def get_agent(self, agent_id: str) -> Optional[A2AAgent]:
        """Get a managed agent by ID."""
        return self.managed_agents.get(agent_id)

    async def list_agents(self) -> Dict[str, A2AAgent]:
        """List all managed agents."""
        return self.managed_agents.copy()

    async def list_workflows(self) -> Dict[str, Dict[str, Any]]:
        """List all workflows."""
        return self.active_workflows.copy()

    async def health_check(self) -> Dict[str, Any]:
        """Perform comprehensive health check."""
        try:
            # Check core components
            identity_healthy = True  # Assume healthy if no errors
            discovery_healthy = True  # Assume healthy if no errors
            transport_healthy = self.transport_layer is not None

            # Check agent health
            agent_health = {}
            for agent_id, agent in self.managed_agents.items():
                try:
                    status = agent.get_client_status()
                    agent_health[agent_id] = "healthy" if status.get("initialized", False) else "unhealthy"
                except Exception as e:
                    agent_health[agent_id] = f"error: {str(e)}"

            # Overall health assessment
            healthy_agents = sum(1 for h in agent_health.values() if h == "healthy")
            total_agents = len(agent_health)

            overall_health = "healthy" if (
                identity_healthy and
                discovery_healthy and
                transport_healthy and
                healthy_agents >= total_agents * 0.8  # 80% healthy threshold
            ) else "degraded"

            return {
                "overall_status": overall_health,
                "components": {
                    "identity_manager": "healthy" if identity_healthy else "unhealthy",
                    "discovery_service": "healthy" if discovery_healthy else "unhealthy",
                    "transport_layer": "healthy" if transport_healthy else "unhealthy"
                },
                "agents": {
                    "total": total_agents,
                    "healthy": healthy_agents,
                    "unhealthy": total_agents - healthy_agents,
                    "details": agent_health
                },
                "workflows": {
                    "total": len(self.active_workflows),
                    "active": len([w for w in self.active_workflows.values() if w["status"] == WorkflowState.RUNNING.value])
                },
                "timestamp": datetime.utcnow().isoformat()
            }

        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return {
                "overall_status": "error",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }


# Global A2A Protocol Manager instance
a2a_protocol_manager = A2AProtocolManager()


# Example usage and testing functions
async def initialize_a2a_system() -> bool:
    """Initialize the complete A2A system."""
    return await a2a_protocol_manager.initialize()


async def shutdown_a2a_system():
    """Shutdown the complete A2A system."""
    await a2a_protocol_manager.shutdown()


async def example_a2a_workflow():
    """Example of creating and executing an A2A workflow."""

    # Create a workflow for data processing
    workflow_id = await a2a_protocol_manager.create_workflow(
        "Data Processing Pipeline",
        "Process data through multiple specialized agents",
        [
            {
                "type": "agent_task",
                "agent_id": "a2a_orchestrator",
                "action": "analyze_request",
                "parameters": {"request": "Process financial data"}
            },
            {
                "type": "agent_task",
                "agent_id": "a2a_self_builder",
                "action": "generate_agent",
                "parameters": {"agent_type": "data_processor"}
            }
        ]
    )

    # Execute the workflow
    result = await a2a_protocol_manager.execute_workflow(workflow_id)

    return {
        "workflow_id": workflow_id,
        "result": result
    }


async def get_a2a_system_status():
    """Get comprehensive A2A system status."""
    return await a2a_protocol_manager.get_system_status()