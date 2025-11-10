"""
🤖 HAPPYOS MCP SERVER

MCP (Model Control Protocol) server som fungerar som brygga mellan
Windows AI Studio och HappyOS agent-system.

Denna server:
- Implementerar MCP-protokollet för kommunikation
- Exponerar HappyOS-agenter som MCP-verktyg
- Hanterar realtids-kommunikation och sessioner
- Tillhandahåller felhantering och loggning

Författare: HappyOS AI Team
Version: 1.0.0
"""

import asyncio
import json
import logging
import uuid
from typing import Dict, List, Any, Optional, Callable, AsyncGenerator
from datetime import datetime
from contextlib import asynccontextmanager

from app.core.mcp.happyos_mcp_adapter import (
    HappyOSMCPAdapter,
    MCPToolResult,
    initialize_mcp_adapter,
    execute_mcp_tool
)
from app.core.logging.logger import get_logger
from app.core.error_handler import error_handler, HappyOSError

logger = get_logger(__name__)


class HappyOSMCPServer:
    """
    MCP Server för HappyOS - hanterar kommunikation med Windows AI Studio.

    Servern implementerar MCP-protokollet och fungerar som interface
    mellan AI Studio's verktyg och HappyOS agent-system.
    """

    def __init__(self, adapter: Optional[HappyOSMCPAdapter] = None):
        self.adapter = adapter or HappyOSMCPAdapter()
        self.active_sessions: Dict[str, Dict[str, Any]] = {}
        self.request_handlers: Dict[str, Callable] = {}
        self._initialized = False

        # Registrera MCP request handlers
        self._register_handlers()

    async def initialize(self):
        """Initiera MCP servern."""
        if self._initialized:
            return

        logger.info("Initializing HappyOS MCP Server...")

        try:
            # Initiera MCP adaptern
            await self.adapter.initialize()

            self._initialized = True
            logger.info("HappyOS MCP Server initialized successfully")

        except Exception as e:
            logger.error(f"Failed to initialize MCP Server: {str(e)}")
            raise HappyOSError(f"MCP Server initialization failed: {str(e)}")

    def _register_handlers(self):
        """Registrera alla MCP request handlers."""
        self.request_handlers = {
            "initialize": self._handle_initialize,
            "tools/list": self._handle_tools_list,
            "tools/call": self._handle_tools_call,
            "resources/list": self._handle_resources_list,
            "resources/read": self._handle_resources_read,
            "resources/subscribe": self._handle_resources_subscribe,
            "prompts/list": self._handle_prompts_list,
            "prompts/get": self._handle_prompts_get,
            "logging/setLevel": self._handle_logging_set_level,
            "session/create": self._handle_session_create,
            "session/destroy": self._handle_session_destroy,
            "ping": self._handle_ping
        }

    async def handle_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """
        Hantera inkommande MCP-request.

        Args:
            request: MCP request objekt

        Returns:
            MCP response objekt
        """
        try:
            method = request.get("method", "")
            params = request.get("params", {})
            request_id = request.get("id")

            logger.debug(f"Handling MCP request: {method} (ID: {request_id})")

            # Hitta och kör handler
            if method in self.request_handlers:
                handler = self.request_handlers[method]
                response_data = await handler(params)

                return {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "result": response_data
                }
            else:
                return {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "error": {
                        "code": -32601,
                        "message": f"Method not found: {method}"
                    }
                }

        except Exception as e:
            logger.error(f"Error handling MCP request: {str(e)}")
            return {
                "jsonrpc": "2.0",
                "id": request.get("id"),
                "error": {
                    "code": -32603,
                    "message": f"Internal error: {str(e)}"
                }
            }

    async def _handle_initialize(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Hantera initialize request."""
        await self.initialize()

        # Returnera server capabilities
        return {
            "protocolVersion": "1.0",
            "capabilities": {
                "tools": {
                    "listChanged": True
                },
                "resources": {
                    "subscribe": True,
                    "listChanged": True
                },
                "prompts": {
                    "listChanged": True
                },
                "logging": {},
                "session": {
                    "create": True,
                    "destroy": True
                }
            },
            "serverInfo": {
                "name": "HappyOS MCP Server",
                "version": "1.0.0",
                "description": "MCP server for HappyOS AI agent system integration with Windows AI Studio"
            }
        }

    async def _handle_tools_list(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Returnera lista över tillgängliga verktyg."""
        tools = []

        for tool_name, tool_info in self.adapter.get_available_tools().items():
            tools.append({
                "name": tool_name,
                "description": tool_info["description"],
                "inputSchema": tool_info["input_schema"]
            })

        return {"tools": tools}

    async def _handle_tools_call(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Hantera verktygsanrop."""
        try:
            tool_name = params.get("name", "")
            tool_params = params.get("arguments", {})

            if not tool_name:
                raise ValueError("Tool name is required")

            # Exekvera verktyget genom adaptern
            result = await self.adapter.execute_tool(tool_name, tool_params)

            # Konvertera till MCP-format
            content = []
            for item in result.content:
                if item["type"] == "text":
                    content.append({
                        "type": "text",
                        "text": item["text"]
                    })
                elif item["type"] == "json":
                    content.append({
                        "type": "text",
                        "text": json.dumps(item["data"], indent=2, ensure_ascii=False)
                    })

            response = {"content": content}

            # Lägg till felinformation om det finns
            if not result.success:
                response["isError"] = True
                if result.error:
                    content.insert(0, {
                        "type": "text",
                        "text": f"Error: {result.error}"
                    })

            return response

        except Exception as e:
            logger.error(f"Tool call failed: {str(e)}")
            return {
                "content": [{"type": "text", "text": f"Tool execution failed: {str(e)}"}],
                "isError": True
            }

    async def _handle_resources_list(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Returnera lista över tillgängliga resurser."""
        resources = [
            {
                "uri": "happyos://agents",
                "name": "HappyOS Agents",
                "description": "List of all available HappyOS agents",
                "mimeType": "application/json"
            },
            {
                "uri": "happyos://templates",
                "name": "Agent Templates",
                "description": "Visual templates for HappyOS agents",
                "mimeType": "application/json"
            },
            {
                "uri": "happyos://system/status",
                "name": "System Status",
                "description": "Current status of HappyOS system",
                "mimeType": "application/json"
            },
            {
                "uri": "happyos://performance/metrics",
                "name": "Performance Metrics",
                "description": "Real-time performance metrics",
                "mimeType": "application/json"
            }
        ]

        return {"resources": resources}

    async def _handle_resources_read(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Läs en resurs."""
        try:
            uri = params.get("uri", "")

            if uri == "happyos://agents":
                # Returnera agent-information
                agents_data = await self._get_agents_resource()
                return {
                    "contents": [{
                        "uri": uri,
                        "mimeType": "application/json",
                        "text": json.dumps(agents_data, indent=2, ensure_ascii=False)
                    }]
                }

            elif uri == "happyos://templates":
                # Returnera templates
                templates_data = self.adapter.get_agent_templates()
                return {
                    "contents": [{
                        "uri": uri,
                        "mimeType": "application/json",
                        "text": json.dumps(templates_data, indent=2, ensure_ascii=False)
                    }]
                }

            elif uri == "happyos://system/status":
                # Returnera systemstatus
                status_data = await self._get_system_status()
                return {
                    "contents": [{
                        "uri": uri,
                        "mimeType": "application/json",
                        "text": json.dumps(status_data, indent=2, ensure_ascii=False)
                    }]
                }

            elif uri == "happyos://performance/metrics":
                # Returnera prestandametrics
                metrics_data = await self._get_performance_metrics()
                return {
                    "contents": [{
                        "uri": uri,
                        "mimeType": "application/json",
                        "text": json.dumps(metrics_data, indent=2, ensure_ascii=False)
                    }]
                }

            else:
                return {
                    "contents": [{
                        "uri": uri,
                        "mimeType": "text/plain",
                        "text": f"Resource not found: {uri}"
                    }]
                }

        except Exception as e:
            logger.error(f"Resource read failed: {str(e)}")
            return {
                "contents": [{
                    "uri": params.get("uri", ""),
                    "mimeType": "text/plain",
                    "text": f"Error reading resource: {str(e)}"
                }]
            }

    async def _handle_resources_subscribe(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Hantera prenumeration på resurser."""
        # För enkelhetens skull, stöd endast system status
        uri = params.get("uri", "")

        if uri == "happyos://system/status":
            return {"success": True}
        else:
            return {"success": False, "error": "Subscription not supported for this resource"}

    async def _handle_prompts_list(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Returnera lista över tillgängliga prompts."""
        prompts = [
            {
                "name": "agent_task",
                "description": "Execute a task with a specific HappyOS agent",
                "arguments": [
                    {
                        "name": "agent_name",
                        "description": "Name of the agent to use",
                        "required": True
                    },
                    {
                        "name": "task_description",
                        "description": "Description of the task to execute",
                        "required": True
                    }
                ]
            },
            {
                "name": "bulk_test",
                "description": "Run tests across multiple agents",
                "arguments": [
                    {
                        "name": "test_cases",
                        "description": "Array of test cases to execute",
                        "required": True
                    }
                ]
            }
        ]

        return {"prompts": prompts}

    async def _handle_prompts_get(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Hämta en specifik prompt."""
        prompt_name = params.get("name", "")

        prompt_templates = {
            "agent_task": {
                "description": "Execute a task with a specific HappyOS agent",
                "messages": [
                    {
                        "role": "user",
                        "content": {
                            "type": "text",
                            "text": "Please execute the following task using the {agent_name} agent: {task_description}"
                        }
                    }
                ]
            },
            "bulk_test": {
                "description": "Run tests across multiple agents",
                "messages": [
                    {
                        "role": "user",
                        "content": {
                            "type": "text",
                            "text": "Please run the following test cases across multiple agents: {test_cases}"
                        }
                    }
                ]
            }
        }

        if prompt_name in prompt_templates:
            return {
                "name": prompt_name,
                "description": prompt_templates[prompt_name]["description"],
                "messages": prompt_templates[prompt_name]["messages"]
            }
        else:
            raise ValueError(f"Prompt not found: {prompt_name}")

    async def _handle_logging_set_level(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Ställ in loggningsnivå."""
        level = params.get("level", "INFO")

        # Map MCP log levels to Python logging levels
        level_mapping = {
            "DEBUG": logging.DEBUG,
            "INFO": logging.INFO,
            "WARN": logging.WARNING,
            "ERROR": logging.ERROR
        }

        if level in level_mapping:
            logger.setLevel(level_mapping[level])
            return {"success": True}
        else:
            return {"success": False, "error": f"Invalid log level: {level}"}

    async def _handle_session_create(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Skapa en ny session."""
        session_id = str(uuid.uuid4())
        self.active_sessions[session_id] = {
            "created": datetime.now(),
            "metadata": params.get("metadata", {}),
            "tool_calls": 0
        }

        logger.info(f"Created MCP session: {session_id}")
        return {"sessionId": session_id}

    async def _handle_session_destroy(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Förstör en session."""
        session_id = params.get("sessionId", "")

        if session_id in self.active_sessions:
            del self.active_sessions[session_id]
            logger.info(f"Destroyed MCP session: {session_id}")
            return {"success": True}
        else:
            return {"success": False, "error": f"Session not found: {session_id}"}

    async def _handle_ping(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Hantera ping-request för hälsa-koll."""
        return {"pong": True, "timestamp": datetime.now().isoformat()}

    async def _get_agents_resource(self) -> Dict[str, Any]:
        """Hämta agent-resurs data."""
        result = await self.adapter.execute_tool("happyos_system_get_agents", {})
        if result.success and result.content:
            # Extrahera JSON-data från första content-item
            for item in result.content:
                if item.get("type") == "json":
                    return item.get("data", {})

        return {"error": "Failed to retrieve agent data"}

    async def _get_system_status(self) -> Dict[str, Any]:
        """Hämta systemstatus."""
        return {
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "active_sessions": len(self.active_sessions),
            "initialized": self._initialized,
            "server_info": {
                "name": "HappyOS MCP Server",
                "version": "1.0.0",
                "uptime": "N/A"  # Kan implementeras senare
            }
        }

    async def _get_performance_metrics(self) -> Dict[str, Any]:
        """Hämta prestandametrics."""
        return {
            "timestamp": datetime.now().isoformat(),
            "active_sessions": len(self.active_sessions),
            "total_requests": sum(session.get("tool_calls", 0) for session in self.active_sessions.values()),
            "server_status": "operational",
            "memory_usage": "N/A",  # Kan implementeras senare
            "cpu_usage": "N/A"      # Kan implementeras senare
        }


class MCPTransport:
    """Abstrakt basklass för MCP-transport."""

    async def send(self, message: Dict[str, Any]):
        """Skicka ett meddelande."""
        raise NotImplementedError

    async def receive(self) -> Dict[str, Any]:
        """Ta emot ett meddelande."""
        raise NotImplementedError

    async def close(self):
        """Stäng transporten."""
        pass


class StdioMCPTransport(MCPTransport):
    """MCP-transport över stdio (för lokal användning)."""

    def __init__(self):
        self._running = True

    async def send(self, message: Dict[str, Any]):
        """Skicka meddelande via stdout."""
        json_str = json.dumps(message, ensure_ascii=False)
        print(json_str, flush=True)

    async def receive(self) -> Dict[str, Any]:
        """Ta emot meddelande via stdin."""
        import sys
        line = sys.stdin.readline()
        if not line:
            self._running = False
            return None
        return json.loads(line.strip())

    async def close(self):
        """Stäng transporten."""
        self._running = False


@asynccontextmanager
async def create_mcp_server(transport_type: str = "stdio"):
    """
    Context manager för att skapa och hantera MCP-server.

    Args:
        transport_type: Typ av transport ("stdio" eller "http")
    """
    server = HappyOSMCPServer()
    transport = None

    try:
        # Initiera server
        await server.initialize()

        # Skapa transport
        if transport_type == "stdio":
            transport = StdioMCPTransport()
        else:
            raise ValueError(f"Unsupported transport type: {transport_type}")

        logger.info(f"HappyOS MCP Server started with {transport_type} transport")
        yield server, transport

    except Exception as e:
        logger.error(f"Failed to create MCP server: {str(e)}")
        raise

    finally:
        if transport:
            await transport.close()
        logger.info("HappyOS MCP Server stopped")


async def run_stdio_server():
    """Kör MCP-server över stdio (för Windows AI Studio integration)."""
    async with create_mcp_server("stdio") as (server, transport):
        logger.info("HappyOS MCP Server running on stdio transport")

        while transport._running:
            try:
                # Ta emot request
                request = await transport.receive()
                if request is None:
                    break

                # Hantera request
                response = await server.handle_request(request)

                # Skicka response
                await transport.send(response)

            except Exception as e:
                logger.error(f"Error in stdio server loop: {str(e)}")
                # Skicka fel-response
                await transport.send({
                    "jsonrpc": "2.0",
                    "id": request.get("id") if 'request' in locals() else None,
                    "error": {
                        "code": -32603,
                        "message": f"Internal server error: {str(e)}"
                    }
                })


# Exportera viktiga komponenter
__all__ = [
    'HappyOSMCPServer',
    'MCPTransport',
    'StdioMCPTransport',
    'create_mcp_server',
    'run_stdio_server'
]


if __name__ == "__main__":
    # Kör servern när modulen körs direkt
    import asyncio
    asyncio.run(run_stdio_server())