"""
Agent Orchestration Service

Provides production-ready agent orchestration via MCP integration with
real process management, heartbeat monitoring, graceful shutdown, and
A2A communication. Uses MCP protocol to communicate with Summarizer
agents instead of direct imports, enforcing architectural boundaries.

Requirements: 4.1, 4.2, 4.3, 4.4, 4.5
"""

import asyncio
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any

try:
    from backend.services.workers.management import WorkerManager, get_worker_manager
    from backend.services.integration.mcp_integration import get_mcp_service
    from backend.services.integration.summarizer_client import SummarizerClient
except ImportError:
    from backend.services.workers.management import WorkerManager, get_worker_manager
    from backend.services.integration.mcp_integration import get_mcp_service
    from backend.services.integration.summarizer_client import SummarizerClient

# Import utilities from extracted modules
from .utils import (
    AgentRegistrationManager,
    WorkflowManager,
    IntegrationMonitor
)

logger = logging.getLogger(__name__)


class AgentOrchestrationService:
    """
    Production-ready agent orchestration service that provides:
    - MCP-based agent coordination (no direct summarizer imports)
    - WorkerManager for background job processing
    - A2A protocol communication via MCP integration
    - Real-time monitoring and health checks
    - Architectural boundary enforcement
    """
    
    def __init__(self, config_path: Optional[str] = None):
        # MCP-based service composition (no direct imports from summarizer)
        self.mcp_service = get_mcp_service()
        self.summarizer_client = SummarizerClient(self.mcp_service)
        self.worker_manager: Optional[WorkerManager] = None
        self.is_initialized = False
        self.logger = logging.getLogger(__name__)
        
        # Service state
        self._shutdown_event = asyncio.Event()
        self._integration_task: Optional[asyncio.Task] = None
        
        # Agent coordination state (managed via MCP)
        self.active_workflows: Dict[str, Dict[str, Any]] = {}
        self.agent_processes: Dict[str, Dict[str, Any]] = {}
        
        # Initialize utility managers
        self.agent_registration = AgentRegistrationManager(self)
        self.workflow_manager = WorkflowManager(self)
        self.integration_monitor = IntegrationMonitor(self)
        
        self.logger.info("Agent orchestration service created with MCP integration")
    
    async def initialize(self) -> bool:
        """Initialize the orchestration service"""
        try:
            # Initialize MCP service
            await self.mcp_service.initialize()
            
            # Initialize worker manager (without direct coordinator dependency)
            self.worker_manager = await get_worker_manager()
            
            # Register existing agents as workers
            await self.agent_registration.register_agents_as_workers()
            
            # Start integration monitoring
            self._integration_task = asyncio.create_task(self.integration_monitor.start_monitoring())
            
            self.is_initialized = True
            self.logger.info("Agent orchestration service initialized successfully with MCP")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to initialize orchestration service: {e}")
            return False
    
    async def shutdown(self) -> None:
        """Gracefully shutdown the orchestration service"""
        self.logger.info("Shutting down agent orchestration service...")
        
        # Signal shutdown
        self._shutdown_event.set()
        
        # Stop integration monitoring
        if self._integration_task and not self._integration_task.done():
            self._integration_task.cancel()
            try:
                await self._integration_task
            except asyncio.CancelledError:
                pass
        
        # Shutdown via MCP coordination
        try:
            await self.summarizer_client.coordinate_agents_async({
                "task_type": "shutdown_coordination",
                "priority": "high"
            })
        except Exception as e:
            self.logger.warning(f"MCP coordination shutdown failed: {e}")
        
        # Shutdown worker manager
        if self.worker_manager:
            await self.worker_manager.shutdown()
        
        # Cleanup MCP service
        await self.mcp_service.cleanup()
        
        self.is_initialized = False
        self.logger.info("Agent orchestration service shutdown complete")
    
    # Public API methods - delegate to utility managers
    
    async def execute_mission(self, mission: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a mission using MCP-coordinated agent system"""
        return await self.workflow_manager.execute_mission(mission)
    
    async def get_system_status(self) -> Dict[str, Any]:
        """Get comprehensive system status via MCP integration"""
        # Get MCP health status
        mcp_health = self.summarizer_client.get_mcp_health_status()
        
        worker_status = {}
        available_agents = []
        
        if self.worker_manager:
            worker_status = {
                "total_workers": len(self.worker_manager.workers),
                "active_jobs": 0,  # Would need to query Redis for active jobs
                "redis_connected": self.worker_manager.redis_client is not None
            }
            
            available_agents = await self.worker_manager.get_available_agents()
        
        # Get agent status via MCP
        agent_statuses = {}
        for agent_id in self.agent_processes.keys():
            try:
                status = await self.summarizer_client.get_a2a_agent_status_async(agent_id)
                agent_statuses[agent_id] = status
            except Exception as e:
                agent_statuses[agent_id] = {"status": "error", "error": str(e)}
        
        return {
            "orchestration_service": {
                "initialized": self.is_initialized,
                "monitoring_active": not self._shutdown_event.is_set(),
                "mcp_integration": mcp_health.get("is_initialized", False)
            },
            "mcp_health": mcp_health,
            "worker_manager": worker_status,
            "available_agents": available_agents,
            "agent_statuses": agent_statuses,
            "active_workflows": len(self.active_workflows),
            "timestamp": datetime.now().isoformat()
        }
    
    async def get_workflow_status(self, workflow_id: str) -> Optional[Dict[str, Any]]:
        """Get status of a specific workflow via MCP"""
        return await self.workflow_manager.get_workflow_status(workflow_id)
    
    async def list_active_workflows(self) -> List[Dict[str, Any]]:
        """List all active workflows"""
        return await self.workflow_manager.list_active_workflows()
    
    async def stop_workflow(self, workflow_id: str) -> bool:
        """Stop a specific workflow via MCP coordination"""
        return await self.workflow_manager.stop_workflow(workflow_id)
    
    async def enqueue_agent_job(self, job_type: str, agent_type: str, payload: Dict[str, Any], priority: int = 5) -> Optional[str]:
        """Enqueue a job for agent processing"""
        if not self.worker_manager:
            return None
        
        return await self.worker_manager.enqueue_agent_job(job_type, agent_type, payload, priority)
    
    async def register_ingest_worker(self, worker_id: str, meeting_id: str, worker_instance) -> bool:
        """Register an ingest worker with the orchestration system"""
        return await self.agent_registration.register_ingest_worker(worker_id, meeting_id, worker_instance)
    
    async def unregister_ingest_worker(self, worker_id: str) -> bool:
        """Unregister an ingest worker from the orchestration system"""
        return await self.agent_registration.unregister_ingest_worker(worker_id)
    
    async def get_agent_status(self, agent_id: str) -> Optional[Dict[str, Any]]:
        """Get detailed status of a specific agent via MCP"""
        return await self.agent_registration.get_agent_status(agent_id)
    
    async def list_agents(self) -> List[Dict[str, Any]]:
        """List all managed agents"""
        return await self.agent_registration.list_agents()


# Global orchestration service instance
_orchestration_service: Optional[AgentOrchestrationService] = None


async def get_orchestration_service(config_path: Optional[str] = None) -> AgentOrchestrationService:
    """Get or create global orchestration service instance"""
    global _orchestration_service
    
    if _orchestration_service is None:
        _orchestration_service = AgentOrchestrationService(config_path)
        await _orchestration_service.initialize()
    
    return _orchestration_service


async def shutdown_orchestration_service():
    """Shutdown the global orchestration service"""
    global _orchestration_service
    
    if _orchestration_service:
        await _orchestration_service.shutdown()
        _orchestration_service = None