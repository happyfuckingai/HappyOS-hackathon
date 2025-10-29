"""
MCP Router - Inter-System Communication

Routes MCP messages between isolated MCP servers and to MCP UI Hub.
Handles communication between Felicia's Finance, Agent Svea, MeetMind, and UI Hub.
"""

import asyncio
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime

from .protocol import MCPMessage, MCPResponse, MCPMessageType
from .ui_hub import MCPUIHub

logger = logging.getLogger(__name__)


class MCPRouter:
    """
    Router for MCP communication between systems and UI Hub.
    
    Routes messages between:
    - felicias_finance MCP server
    - agent_svea MCP server  
    - meetmind MCP server
    - MCP UI Hub (for frontend visualization)
    """
    
    def __init__(self):
        self.registered_servers = {}
        self.ui_hub = MCPUIHub()
        self.message_history = []
        self.active_workflows = {}
        
    def register_server(self, server_name: str, server_instance):
        """Register an MCP server."""
        self.registered_servers[server_name] = server_instance
        logger.info(f"Registered MCP server: {server_name}")
        
        # Notify UI Hub of new server
        self.ui_hub.notify_server_registered(server_name)
    
    async def route_mcp_message(self, message: MCPMessage) -> MCPResponse:
        """
        Route MCP message to target server or UI Hub.
        
        Args:
            message: MCP message to route
            
        Returns:
            Response from target server
        """
        try:
            target_server = message.target_server
            
            # Special handling for UI Hub messages
            if target_server == "ui_hub":
                return await self._route_to_ui_hub(message)
            
            # Check if target server is registered
            if target_server not in self.registered_servers:
                available = list(self.registered_servers.keys())
                return MCPResponse(
                    success=False,
                    error=f"MCP server '{target_server}' not found. Available: {available}",
                    message_id=message.message_id
                )
            
            # Route to target MCP server
            server = self.registered_servers[target_server]
            
            logger.info(f"Routing MCP message from {message.source_server} to {target_server}")
            self._log_mcp_message(message)
            
            # Send to target server
            if hasattr(server, 'handle_mcp_message'):
                response_data = await server.handle_mcp_message(message)
            elif hasattr(server, 'call_tool'):
                response_data = await server.call_tool(message.tool, message.payload)
            else:
                return MCPResponse(
                    success=False,
                    error=f"Server '{target_server}' does not support MCP messaging",
                    message_id=message.message_id
                )
            
            # Create response
            response = MCPResponse(
                success=True,
                data=response_data,
                message_id=message.message_id,
                source_server=target_server,
                target_server=message.source_server
            )
            
            # Also send result to UI Hub for visualization
            await self._notify_ui_hub_of_result(message, response)
            
            self._log_mcp_response(response)
            return response
            
        except Exception as e:
            logger.error(f"MCP routing failed: {e}")
            
            error_response = MCPResponse(
                success=False,
                error=str(e),
                message_id=message.message_id
            )
            
            # Notify UI Hub of error
            await self._notify_ui_hub_of_error(message, error_response)
            
            return error_response
    
    async def start_cross_system_workflow(self, workflow_config: Dict[str, Any]) -> str:
        """
        Start a workflow that spans multiple MCP servers.
        
        Args:
            workflow_config: Configuration for the workflow
            
        Returns:
            Workflow ID
        """
        workflow_id = f"workflow_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        workflow = {
            "id": workflow_id,
            "config": workflow_config,
            "status": "started",
            "steps": [],
            "created_at": datetime.now().isoformat()
        }
        
        self.active_workflows[workflow_id] = workflow
        
        # Notify UI Hub of new workflow
        await self.ui_hub.notify_workflow_started(workflow)
        
        logger.info(f"Started cross-system workflow: {workflow_id}")
        return workflow_id
    
    async def execute_workflow_step(self, workflow_id: str, step_config: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a single step in a cross-system workflow."""
        if workflow_id not in self.active_workflows:
            raise ValueError(f"Workflow {workflow_id} not found")
        
        workflow = self.active_workflows[workflow_id]
        
        # Create MCP message for this step
        message = MCPMessage(
            message_id=f"{workflow_id}_step_{len(workflow['steps'])}",
            source_server="mcp_router",
            target_server=step_config["target_server"],
            message_type=MCPMessageType.TOOL_CALL,
            tool=step_config["tool"],
            payload=step_config["payload"],
            workflow_id=workflow_id
        )
        
        # Execute step
        response = await self.route_mcp_message(message)
        
        # Record step result
        step_result = {
            "step_number": len(workflow['steps']) + 1,
            "target_server": step_config["target_server"],
            "tool": step_config["tool"],
            "success": response.success,
            "result": response.data if response.success else response.error,
            "timestamp": datetime.now().isoformat()
        }
        
        workflow['steps'].append(step_result)
        
        # Update UI Hub
        await self.ui_hub.notify_workflow_step_completed(workflow_id, step_result)
        
        return step_result
    
    async def broadcast_to_all_servers(self, message: MCPMessage, exclude_servers: List[str] = None) -> Dict[str, MCPResponse]:
        """Broadcast message to all registered MCP servers."""
        exclude_servers = exclude_servers or []
        responses = {}
        
        for server_name in self.registered_servers.keys():
            if server_name not in exclude_servers:
                # Create message copy for this server
                server_message = MCPMessage(
                    message_id=f"{message.message_id}_{server_name}",
                    source_server=message.source_server,
                    target_server=server_name,
                    message_type=message.message_type,
                    tool=message.tool,
                    payload=message.payload,
                    workflow_id=message.workflow_id
                )
                
                response = await self.route_mcp_message(server_message)
                responses[server_name] = response
        
        return responses
    
    async def _route_to_ui_hub(self, message: MCPMessage) -> MCPResponse:
        """Route message specifically to UI Hub."""
        try:
            result = await self.ui_hub.handle_message(message)
            
            return MCPResponse(
                success=True,
                data=result,
                message_id=message.message_id,
                source_server="ui_hub",
                target_server=message.source_server
            )
            
        except Exception as e:
            return MCPResponse(
                success=False,
                error=str(e),
                message_id=message.message_id
            )
    
    async def _notify_ui_hub_of_result(self, message: MCPMessage, response: MCPResponse):
        """Notify UI Hub of MCP message result for visualization."""
        try:
            await self.ui_hub.notify_mcp_result(message, response)
        except Exception as e:
            logger.error(f"Failed to notify UI Hub of result: {e}")
    
    async def _notify_ui_hub_of_error(self, message: MCPMessage, response: MCPResponse):
        """Notify UI Hub of MCP error for visualization."""
        try:
            await self.ui_hub.notify_mcp_error(message, response)
        except Exception as e:
            logger.error(f"Failed to notify UI Hub of error: {e}")
    
    def get_server_status(self) -> Dict[str, Any]:
        """Get status of all registered MCP servers."""
        server_status = {}
        
        for server_name, server in self.registered_servers.items():
            try:
                if hasattr(server, 'get_status'):
                    server_status[server_name] = server.get_status()
                else:
                    server_status[server_name] = {"status": "unknown"}
            except Exception as e:
                server_status[server_name] = {"status": "error", "error": str(e)}
        
        return {
            "total_servers": len(self.registered_servers),
            "servers": server_status,
            "active_workflows": len(self.active_workflows),
            "total_messages": len(self.message_history)
        }
    
    def _log_mcp_message(self, message: MCPMessage):
        """Log MCP message."""
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "type": "mcp_message",
            "message_id": message.message_id,
            "source_server": message.source_server,
            "target_server": message.target_server,
            "tool": message.tool,
            "workflow_id": message.workflow_id
        }
        self.message_history.append(log_entry)
    
    def _log_mcp_response(self, response: MCPResponse):
        """Log MCP response."""
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "type": "mcp_response",
            "message_id": response.message_id,
            "source_server": response.source_server,
            "target_server": response.target_server,
            "success": response.success
        }
        self.message_history.append(log_entry)


# Global MCP router instance
_mcp_router = MCPRouter()

def get_mcp_router() -> MCPRouter:
    """Get the global MCP router instance."""
    return _mcp_router

async def route_mcp_message(message: MCPMessage) -> MCPResponse:
    """Convenience function for routing MCP messages."""
    return await _mcp_router.route_mcp_message(message)