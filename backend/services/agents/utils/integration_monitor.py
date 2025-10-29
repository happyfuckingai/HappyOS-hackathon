"""
Integration Monitor

Monitors integration between coordinator and worker manager.
Extracted from orchestration_service.py to improve modularity.
"""

import asyncio
import logging
from datetime import datetime
from typing import Dict, Any

logger = logging.getLogger(__name__)


class IntegrationMonitor:
    """Monitors integration between systems via MCP"""
    
    def __init__(self, orchestration_service):
        self.orchestration_service = orchestration_service
        self.summarizer_client = orchestration_service.summarizer_client
        self.worker_manager = orchestration_service.worker_manager
        self.agent_processes = orchestration_service.agent_processes
        self._shutdown_event = orchestration_service._shutdown_event
    
    async def start_monitoring(self) -> None:
        """Start integration monitoring loop"""
        while not self._shutdown_event.is_set():
            try:
                # Sync heartbeats between systems
                await self._sync_heartbeats()
                
                # Check for failed agents and restart if needed
                await self._check_and_restart_failed_agents()
                
                # Update worker manager with agent status
                await self._update_worker_status()
                
                await asyncio.sleep(30)  # Check every 30 seconds
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in integration monitor: {e}")
                await asyncio.sleep(10)
    
    async def _sync_heartbeats(self) -> None:
        """Sync heartbeats via MCP integration"""
        if not self.worker_manager:
            return
        
        for agent_id, process in self.agent_processes.items():
            if process.get("state") == "running":
                try:
                    # Get agent status via MCP
                    status = await self.summarizer_client.get_a2a_agent_status_async(agent_id)
                    
                    if status.get("status") == "active":
                        # Report heartbeat to worker manager
                        metrics = {
                            "state": process.get("state", "unknown"),
                            "restart_count": process.get("restart_count", 0),
                            "uptime_seconds": int((datetime.now() - process.get("registered_at", datetime.now())).total_seconds())
                        }
                        
                        await self.worker_manager.report_agent_heartbeat(agent_id, metrics)
                        
                except Exception as e:
                    logger.warning(f"Failed to sync heartbeat for agent {agent_id}: {e}")
    
    async def _check_and_restart_failed_agents(self) -> None:
        """Check for failed agents and attempt restart via MCP"""
        for agent_id, process in self.agent_processes.items():
            if process.get("state") == "failed" and process.get("restart_count", 0) < 3:
                logger.info(f"Attempting to restart failed agent: {agent_id}")
                
                try:
                    # Attempt restart via MCP coordination
                    restart_result = await self.summarizer_client.coordinate_agents_async({
                        "task_type": "restart_agent",
                        "agent_id": agent_id,
                        "priority": "high"
                    })
                    
                    if restart_result.get("status") == "coordinating":
                        # Re-register as A2A agent
                        register_result = await self.summarizer_client.register_a2a_agent_async(
                            agent_id=agent_id,
                            capabilities=process.get("capabilities", []),
                            status="active"
                        )
                        
                        if register_result.get("status") == "registered":
                            # Update local state
                            process["state"] = "running"
                            process["restart_count"] = process.get("restart_count", 0) + 1
                            process["restarted_at"] = datetime.now()
                            
                            logger.info(f"Successfully restarted agent {agent_id} via MCP")
                        else:
                            logger.error(f"Failed to re-register restarted agent {agent_id}")
                    else:
                        logger.error(f"Failed to restart agent {agent_id}: {restart_result}")
                        
                except Exception as e:
                    logger.error(f"Error restarting agent {agent_id}: {e}")
                    process["state"] = "failed"
                    process["error_message"] = str(e)
    
    async def _update_worker_status(self) -> None:
        """Update worker manager with current agent status via MCP"""
        if not self.worker_manager:
            return
        
        for agent_id, process in self.agent_processes.items():
            if agent_id in self.worker_manager.workers:
                worker = self.worker_manager.workers[agent_id]
                
                try:
                    # Get current status via MCP
                    status = await self.summarizer_client.get_a2a_agent_status_async(agent_id)
                    
                    # Update worker status based on MCP response
                    if status.get("status") == "active":
                        worker.status = worker.status.RUNNING
                        process["state"] = "running"
                    else:
                        worker.status = worker.status.STOPPED
                        process["state"] = "stopped"
                        
                except Exception as e:
                    logger.warning(f"Failed to update status for agent {agent_id}: {e}")
                    worker.status = worker.status.FAILED
                    worker.error_message = str(e)
                    process["state"] = "failed"
                    process["error_message"] = str(e)