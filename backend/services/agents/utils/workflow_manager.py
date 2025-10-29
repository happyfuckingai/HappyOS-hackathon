"""
Workflow Manager

Handles workflow execution and management via MCP integration.
Extracted from orchestration_service.py to improve modularity.
"""

import logging
from datetime import datetime
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)


class WorkflowManager:
    """Manages workflow execution and tracking via MCP integration"""
    
    def __init__(self, orchestration_service):
        self.orchestration_service = orchestration_service
        self.summarizer_client = orchestration_service.summarizer_client
        self.active_workflows = orchestration_service.active_workflows
    
    async def execute_mission(self, mission: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a mission using MCP-coordinated agent system"""
        if not self.orchestration_service.is_initialized:
            return {
                "status": "error",
                "message": "Orchestration service not initialized"
            }
        
        try:
            # Execute mission through MCP coordination
            mission_result = await self.summarizer_client.coordinate_agents_async({
                "task_type": "execute_mission",
                "mission": mission,
                "priority": mission.get("priority", "normal")
            })
            
            if mission_result.get("status") == "coordinating":
                # Track workflow in local state
                workflow_id = mission_result.get("task_id")
                if workflow_id:
                    self.active_workflows[workflow_id] = {
                        "mission": mission,
                        "status": "executing",
                        "started_at": datetime.now(),
                        "task_id": workflow_id
                    }
                
                return {
                    "status": "mission_registered",
                    "workflow_id": workflow_id,
                    "message": "Mission registered successfully via MCP coordination."
                }
            else:
                return mission_result
                
        except Exception as e:
            logger.error(f"Mission execution failed: {e}")
            return {
                "status": "error",
                "message": str(e)
            }
    
    async def get_workflow_status(self, workflow_id: str) -> Optional[Dict[str, Any]]:
        """Get status of a specific workflow via MCP"""
        if workflow_id in self.active_workflows:
            workflow = self.active_workflows[workflow_id]
            
            try:
                # Get updated status via MCP coordination
                status_result = await self.summarizer_client.coordinate_agents_async({
                    "task_type": "get_workflow_status",
                    "workflow_id": workflow_id,
                    "priority": "low"
                })
                
                # Merge local and MCP status
                return {
                    **workflow,
                    "mcp_status": status_result,
                    "last_updated": datetime.now().isoformat()
                }
                
            except Exception as e:
                logger.warning(f"Failed to get MCP status for workflow {workflow_id}: {e}")
                return workflow
        
        return None
    
    async def list_active_workflows(self) -> List[Dict[str, Any]]:
        """List all active workflows"""
        workflows = []
        for workflow_id in self.active_workflows.keys():
            workflow_status = await self.get_workflow_status(workflow_id)
            if workflow_status:
                workflows.append(workflow_status)
        return workflows
    
    async def stop_workflow(self, workflow_id: str) -> bool:
        """Stop a specific workflow via MCP coordination"""
        try:
            result = await self.summarizer_client.coordinate_agents_async({
                "task_type": "stop_workflow",
                "workflow_id": workflow_id,
                "priority": "high"
            })
            
            if result.get("status") == "coordinating":
                # Update local state
                if workflow_id in self.active_workflows:
                    self.active_workflows[workflow_id]["status"] = "stopped"
                    self.active_workflows[workflow_id]["stopped_at"] = datetime.now()
                
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Failed to stop workflow {workflow_id}: {e}")
            return False