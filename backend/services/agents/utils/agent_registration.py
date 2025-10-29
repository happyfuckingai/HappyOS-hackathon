"""
Agent Registration Manager

Handles agent registration and management via MCP integration.
Extracted from orchestration_service.py to improve modularity.
"""

import logging
import uuid
from datetime import datetime
from typing import Dict, List, Any

logger = logging.getLogger(__name__)


class AgentRegistrationManager:
    """Manages agent registration and lifecycle via MCP integration"""
    
    def __init__(self, orchestration_service):
        self.orchestration_service = orchestration_service
        self.mcp_service = orchestration_service.mcp_service
        self.summarizer_client = orchestration_service.summarizer_client
        self.worker_manager = orchestration_service.worker_manager
        self.agent_processes = orchestration_service.agent_processes
    
    async def register_agents_as_workers(self) -> None:
        """Register agents as workers via MCP integration"""
        if not self.worker_manager:
            return
        
        # Define capabilities for each agent type
        agent_capabilities = {
            "strategist": ["mission_analysis", "strategy_definition", "objective_setting"],
            "architect": ["conversation_design", "blueprint_creation", "tool_briefing"],
            "implementation": ["mcp_execution", "pipeline_processing", "tool_integration"],
            "qa": ["output_validation", "quality_assurance", "compliance_checking"]
        }
        
        # Register standard agent types via MCP
        for agent_type, capabilities in agent_capabilities.items():
            agent_id = f"{agent_type}_agent_{uuid.uuid4().hex[:8]}"
            
            try:
                # Register via MCP A2A protocol
                result = await self.summarizer_client.register_a2a_agent_async(
                    agent_id=agent_id,
                    capabilities=capabilities,
                    status="active"
                )
                
                if result.get("status") == "registered":
                    # Also register with worker manager
                    success = await self.worker_manager.register_agent_worker(
                        agent_id=agent_id,
                        agent_type=agent_type,
                        capabilities=capabilities
                    )
                    
                    if success:
                        # Track in local state
                        self.agent_processes[agent_id] = {
                            "agent_type": agent_type,
                            "state": "running",
                            "capabilities": capabilities,
                            "registered_at": datetime.now()
                        }
                        logger.info(f"Registered agent {agent_id} as worker via MCP")
                    else:
                        logger.error(f"Failed to register agent {agent_id} with worker manager")
                else:
                    logger.error(f"Failed to register agent {agent_id} via MCP: {result}")
                    
            except Exception as e:
                logger.error(f"Error registering agent {agent_type}: {e}")
    
    async def register_ingest_worker(self, worker_id: str, meeting_id: str, worker_instance) -> bool:
        """Register an ingest worker with the orchestration system"""
        try:
            # Register with worker manager
            if self.worker_manager:
                success = await self.worker_manager.register_agent_worker(
                    agent_id=worker_id,
                    agent_type="summarizer_ingest_worker",
                    capabilities=["transcript_processing", "real_time_analysis", "context_generation"]
                )
                
                if not success:
                    logger.error(f"Failed to register ingest worker {worker_id} with worker manager")
                    return False
            
            # Register with MCP coordination
            register_result = await self.summarizer_client.register_a2a_agent_async(
                agent_id=worker_id,
                capabilities=["transcript_processing", "real_time_analysis", "context_generation"],
                status="active"
            )
            
            if register_result.get("status") == "registered":
                # Track in local state
                self.agent_processes[worker_id] = {
                    "agent_type": "summarizer_ingest_worker",
                    "state": "running",
                    "meeting_id": meeting_id,
                    "worker_instance": worker_instance,
                    "registered_at": datetime.now(),
                    "capabilities": ["transcript_processing", "real_time_analysis", "context_generation"]
                }
                logger.info(f"Registered ingest worker {worker_id} via MCP coordination")
            else:
                logger.error(f"Failed to register ingest worker {worker_id} via MCP: {register_result}")
            
            logger.info(f"Successfully registered ingest worker: {worker_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to register ingest worker {worker_id}: {e}")
            return False
    
    async def unregister_ingest_worker(self, worker_id: str) -> bool:
        """Unregister an ingest worker from the orchestration system"""
        try:
            # Unregister from worker manager
            if self.worker_manager:
                await self.worker_manager.unregister_agent_worker(worker_id)
            
            # Unregister from MCP coordination
            unregister_result = await self.summarizer_client.unregister_a2a_agent_async(worker_id)
            
            if unregister_result.get("status") == "unregistered":
                # Remove from local state
                if worker_id in self.agent_processes:
                    del self.agent_processes[worker_id]
                
                logger.info(f"Successfully unregistered ingest worker: {worker_id}")
                return True
            else:
                logger.error(f"Failed to unregister ingest worker {worker_id} via MCP: {unregister_result}")
                return False
            
        except Exception as e:
            logger.error(f"Failed to unregister ingest worker {worker_id}: {e}")
            return False
    
    async def get_agent_status(self, agent_id: str) -> Dict[str, Any]:
        """Get detailed status of a specific agent via MCP"""
        try:
            # Get status via MCP
            mcp_status = await self.summarizer_client.get_a2a_agent_status_async(agent_id)
            
            # Merge with local state if available
            local_state = self.agent_processes.get(agent_id, {})
            
            return {
                **local_state,
                "mcp_status": mcp_status,
                "last_checked": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Failed to get agent status for {agent_id}: {e}")
            return None
    
    async def list_agents(self) -> List[Dict[str, Any]]:
        """List all managed agents"""
        agents = []
        
        for agent_id, process in self.agent_processes.items():
            try:
                # Get current MCP status
                mcp_status = await self.summarizer_client.get_a2a_agent_status_async(agent_id)
                
                agents.append({
                    "agent_id": agent_id,
                    **process,
                    "mcp_status": mcp_status,
                    "last_checked": datetime.now().isoformat()
                })
                
            except Exception as e:
                agents.append({
                    "agent_id": agent_id,
                    **process,
                    "mcp_status": {"status": "error", "error": str(e)},
                    "last_checked": datetime.now().isoformat()
                })
        
        return agents