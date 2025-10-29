"""
MCP UI Hub - Frontend Visualization Hub

Central hub that receives results from all MCP servers and provides
data for frontend visualization of agent activities and workflows.
"""

import asyncio
import json
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
from collections import defaultdict, deque

from .protocol import MCPMessage, MCPResponse

logger = logging.getLogger(__name__)


class MCPUIHub:
    """
    Central hub for MCP UI visualization.
    
    Collects data from all MCP servers and provides real-time updates
    to the frontend for visualizing agent activities, workflows, and results.
    """
    
    def __init__(self):
        self.connected_servers = set()
        self.active_workflows = {}
        self.recent_activities = deque(maxlen=1000)  # Keep last 1000 activities
        self.server_metrics = defaultdict(dict)
        self.websocket_connections = set()  # For real-time frontend updates
        
        # Activity categories for frontend filtering
        self.activity_categories = {
            "agent_communication": [],
            "workflow_execution": [],
            "tool_calls": [],
            "errors": [],
            "system_events": []
        }
        
    async def handle_message(self, message: MCPMessage) -> Dict[str, Any]:
        """Handle direct messages to UI Hub."""
        try:
            if message.tool == "get_dashboard_data":
                return await self._get_dashboard_data()
            elif message.tool == "get_workflow_status":
                workflow_id = message.payload.get("workflow_id")
                return await self._get_workflow_status(workflow_id)
            elif message.tool == "get_server_metrics":
                return await self._get_server_metrics()
            elif message.tool == "get_recent_activities":
                limit = message.payload.get("limit", 50)
                return await self._get_recent_activities(limit)
            else:
                return {"error": f"Unknown UI Hub tool: {message.tool}"}
                
        except Exception as e:
            logger.error(f"UI Hub message handling failed: {e}")
            return {"error": str(e)}
    
    async def notify_server_registered(self, server_name: str):
        """Notify UI Hub that a new MCP server was registered."""
        self.connected_servers.add(server_name)
        
        activity = {
            "id": f"server_reg_{datetime.now().timestamp()}",
            "timestamp": datetime.now().isoformat(),
            "type": "server_registered",
            "server": server_name,
            "message": f"MCP server '{server_name}' connected",
            "category": "system_events"
        }
        
        await self._add_activity(activity)
        await self._broadcast_to_frontend("server_registered", activity)
    
    async def notify_workflow_started(self, workflow: Dict[str, Any]):
        """Notify UI Hub that a new workflow was started."""
        workflow_id = workflow["id"]
        self.active_workflows[workflow_id] = workflow
        
        activity = {
            "id": f"workflow_start_{workflow_id}",
            "timestamp": datetime.now().isoformat(),
            "type": "workflow_started",
            "workflow_id": workflow_id,
            "message": f"Workflow '{workflow_id}' started",
            "category": "workflow_execution",
            "details": workflow
        }
        
        await self._add_activity(activity)
        await self._broadcast_to_frontend("workflow_started", activity)
    
    async def notify_workflow_step_completed(self, workflow_id: str, step_result: Dict[str, Any]):
        """Notify UI Hub that a workflow step was completed."""
        if workflow_id in self.active_workflows:
            workflow = self.active_workflows[workflow_id]
            
            activity = {
                "id": f"workflow_step_{workflow_id}_{step_result['step_number']}",
                "timestamp": datetime.now().isoformat(),
                "type": "workflow_step_completed",
                "workflow_id": workflow_id,
                "step_number": step_result["step_number"],
                "server": step_result["target_server"],
                "tool": step_result["tool"],
                "success": step_result["success"],
                "message": f"Step {step_result['step_number']} completed on {step_result['target_server']}",
                "category": "workflow_execution",
                "details": step_result
            }
            
            await self._add_activity(activity)
            await self._broadcast_to_frontend("workflow_step_completed", activity)
    
    async def notify_mcp_result(self, message: MCPMessage, response: MCPResponse):
        """Notify UI Hub of MCP message result for visualization."""
        activity = {
            "id": f"mcp_result_{message.message_id}",
            "timestamp": datetime.now().isoformat(),
            "type": "mcp_result",
            "message_id": message.message_id,
            "source_server": message.source_server,
            "target_server": message.target_server,
            "tool": message.tool,
            "success": response.success,
            "message": f"MCP call from {message.source_server} to {message.target_server}",
            "category": "agent_communication" if response.success else "errors",
            "details": {
                "request": {
                    "tool": message.tool,
                    "payload_size": len(str(message.payload)) if message.payload else 0
                },
                "response": {
                    "success": response.success,
                    "data_size": len(str(response.data)) if response.data else 0,
                    "error": response.error if not response.success else None
                }
            }
        }
        
        await self._add_activity(activity)
        await self._broadcast_to_frontend("mcp_result", activity)
        
        # Update server metrics
        await self._update_server_metrics(message.target_server, response.success)
    
    async def notify_mcp_error(self, message: MCPMessage, response: MCPResponse):
        """Notify UI Hub of MCP error for visualization."""
        activity = {
            "id": f"mcp_error_{message.message_id}",
            "timestamp": datetime.now().isoformat(),
            "type": "mcp_error",
            "message_id": message.message_id,
            "source_server": message.source_server,
            "target_server": message.target_server,
            "tool": message.tool,
            "error": response.error,
            "message": f"MCP error: {message.source_server} → {message.target_server}",
            "category": "errors",
            "details": {
                "request": {
                    "tool": message.tool,
                    "payload": message.payload
                },
                "error": response.error
            }
        }
        
        await self._add_activity(activity)
        await self._broadcast_to_frontend("mcp_error", activity)
        
        # Update server metrics
        await self._update_server_metrics(message.target_server, False)
    
    async def register_websocket(self, websocket):
        """Register a WebSocket connection for real-time updates."""
        self.websocket_connections.add(websocket)
        logger.info("New WebSocket connection registered for UI Hub")
        
        # Send current dashboard data to new connection
        dashboard_data = await self._get_dashboard_data()
        await self._send_to_websocket(websocket, "dashboard_data", dashboard_data)
    
    async def unregister_websocket(self, websocket):
        """Unregister a WebSocket connection."""
        self.websocket_connections.discard(websocket)
        logger.info("WebSocket connection unregistered from UI Hub")
    
    async def _get_dashboard_data(self) -> Dict[str, Any]:
        """Get comprehensive dashboard data for frontend."""
        return {
            "connected_servers": list(self.connected_servers),
            "active_workflows": len(self.active_workflows),
            "recent_activities": list(self.recent_activities)[-20:],  # Last 20 activities
            "server_metrics": dict(self.server_metrics),
            "activity_summary": {
                category: len(activities) 
                for category, activities in self.activity_categories.items()
            },
            "timestamp": datetime.now().isoformat()
        }
    
    async def _get_workflow_status(self, workflow_id: str) -> Dict[str, Any]:
        """Get detailed status of a specific workflow."""
        if workflow_id not in self.active_workflows:
            return {"error": f"Workflow {workflow_id} not found"}
        
        workflow = self.active_workflows[workflow_id]
        
        # Get related activities
        related_activities = [
            activity for activity in self.recent_activities
            if activity.get("workflow_id") == workflow_id
        ]
        
        return {
            "workflow": workflow,
            "related_activities": related_activities,
            "status": workflow.get("status", "unknown"),
            "progress": {
                "total_steps": len(workflow.get("steps", [])),
                "completed_steps": len([
                    step for step in workflow.get("steps", [])
                    if step.get("success", False)
                ])
            }
        }
    
    async def _get_server_metrics(self) -> Dict[str, Any]:
        """Get metrics for all connected servers."""
        return {
            "servers": dict(self.server_metrics),
            "summary": {
                "total_servers": len(self.connected_servers),
                "healthy_servers": len([
                    server for server, metrics in self.server_metrics.items()
                    if metrics.get("success_rate", 0) > 0.8
                ]),
                "total_requests": sum(
                    metrics.get("total_requests", 0)
                    for metrics in self.server_metrics.values()
                )
            }
        }
    
    async def _get_recent_activities(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get recent activities with optional limit."""
        return list(self.recent_activities)[-limit:]
    
    async def _add_activity(self, activity: Dict[str, Any]):
        """Add activity to recent activities and categorize it."""
        self.recent_activities.append(activity)
        
        category = activity.get("category", "system_events")
        if category in self.activity_categories:
            self.activity_categories[category].append(activity["id"])
    
    async def _update_server_metrics(self, server_name: str, success: bool):
        """Update metrics for a server based on request result."""
        if server_name not in self.server_metrics:
            self.server_metrics[server_name] = {
                "total_requests": 0,
                "successful_requests": 0,
                "failed_requests": 0,
                "success_rate": 0.0,
                "last_activity": None
            }
        
        metrics = self.server_metrics[server_name]
        metrics["total_requests"] += 1
        metrics["last_activity"] = datetime.now().isoformat()
        
        if success:
            metrics["successful_requests"] += 1
        else:
            metrics["failed_requests"] += 1
        
        # Calculate success rate
        if metrics["total_requests"] > 0:
            metrics["success_rate"] = metrics["successful_requests"] / metrics["total_requests"]
    
    async def _broadcast_to_frontend(self, event_type: str, data: Dict[str, Any]):
        """Broadcast event to all connected WebSocket clients."""
        if not self.websocket_connections:
            return
        
        message = {
            "type": event_type,
            "data": data,
            "timestamp": datetime.now().isoformat()
        }
        
        # Send to all connected WebSockets
        disconnected = set()
        for websocket in self.websocket_connections:
            try:
                await self._send_to_websocket(websocket, event_type, data)
            except Exception as e:
                logger.error(f"Failed to send to WebSocket: {e}")
                disconnected.add(websocket)
        
        # Remove disconnected WebSockets
        for websocket in disconnected:
            self.websocket_connections.discard(websocket)
    
    async def _send_to_websocket(self, websocket, event_type: str, data: Dict[str, Any]):
        """Send message to a specific WebSocket."""
        message = {
            "type": event_type,
            "data": data,
            "timestamp": datetime.now().isoformat()
        }
        
        # This would be implemented based on your WebSocket library
        # For example, with FastAPI WebSockets:
        # await websocket.send_text(json.dumps(message))
        
        # Placeholder implementation
        logger.debug(f"Sending to WebSocket: {event_type}")
    
    def get_hub_status(self) -> Dict[str, Any]:
        """Get UI Hub status information."""
        return {
            "connected_servers": len(self.connected_servers),
            "active_workflows": len(self.active_workflows),
            "websocket_connections": len(self.websocket_connections),
            "total_activities": len(self.recent_activities),
            "activity_categories": {
                category: len(activities)
                for category, activities in self.activity_categories.items()
            },
            "uptime": "active",  # Could track actual uptime
            "last_activity": self.recent_activities[-1]["timestamp"] if self.recent_activities else None
        }