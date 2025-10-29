"""
Transport Layer - Secure Communication Transport for A2A Protocol

Handles HTTP/2 and WebSocket transport protocols with TLS encryption,
connection management, and reliable message delivery for the Agent-to-Agent
communication protocol in HappyOS.
"""

import asyncio
import ssl
import json
import logging
from typing import Dict, Any, Optional, List, Callable
from datetime import datetime, timedelta
import aiohttp
import websockets
from aiohttp import web, WSMsgType
import certifi

from .constants import (
    TransportProtocol,
    DEFAULT_CONFIG,
    MessageHeader,
    ResponseCode,
    AgentState,
    ENV_CONFIG
)

logger = logging.getLogger(__name__)


class TransportConfig:
    """Configuration for transport layer."""

    def __init__(self,
                 protocol: TransportProtocol = TransportProtocol.HTTP2,
                 host: str = "localhost",
                 port: int = DEFAULT_CONFIG["port"],
                 enable_tls: bool = DEFAULT_CONFIG["enable_tls"],
                 cert_file: Optional[str] = None,
                 key_file: Optional[str] = None,
                 ca_cert_file: Optional[str] = None,
                 max_connections: int = DEFAULT_CONFIG["max_connections"],
                 connection_timeout: int = DEFAULT_CONFIG["connection_timeout"],
                 message_timeout: int = DEFAULT_CONFIG["message_timeout"],
                 max_message_size: int = DEFAULT_CONFIG["max_message_size"],
                 enable_http2: bool = DEFAULT_CONFIG["enable_http2"],
                 enable_websocket_fallback: bool = DEFAULT_CONFIG["enable_websocket_fallback"]):
        self.protocol = protocol
        self.host = host
        self.port = port
        self.enable_tls = enable_tls
        self.cert_file = cert_file
        self.key_file = key_file
        self.ca_cert_file = ca_cert_file or certifi.where()
        self.max_connections = max_connections
        self.connection_timeout = connection_timeout
        self.message_timeout = message_timeout
        self.max_message_size = max_message_size
        self.enable_http2 = enable_http2
        self.enable_websocket_fallback = enable_websocket_fallback


class ConnectionManager:
    """Manages connections to other agents."""

    def __init__(self):
        self.active_connections: Dict[str, Any] = {}
        self.connection_health: Dict[str, Dict[str, Any]] = {}
        self._lock = asyncio.Lock()

    async def add_connection(self, agent_id: str, connection: Any, connection_type: str):
        """Add a new active connection."""
        async with self._lock:
            self.active_connections[agent_id] = {
                "connection": connection,
                "connection_type": connection_type,
                "connected_at": datetime.utcnow(),
                "last_activity": datetime.utcnow(),
                "message_count": 0,
                "error_count": 0
            }

            self.connection_health[agent_id] = {
                "status": "healthy",
                "last_health_check": datetime.utcnow(),
                "consecutive_failures": 0,
                "average_response_time": 0.0
            }

        logger.debug(f"Added connection for agent: {agent_id}")

    async def remove_connection(self, agent_id: str):
        """Remove a connection."""
        async with self._lock:
            if agent_id in self.active_connections:
                connection_info = self.active_connections[agent_id]
                connection = connection_info["connection"]

                # Close connection gracefully
                try:
                    if hasattr(connection, 'close'):
                        await connection.close()
                except Exception as e:
                    logger.warning(f"Error closing connection for agent {agent_id}: {e}")

                del self.active_connections[agent_id]

            if agent_id in self.connection_health:
                del self.connection_health[agent_id]

        logger.debug(f"Removed connection for agent: {agent_id}")

    async def get_connection(self, agent_id: str) -> Optional[Any]:
        """Get connection for an agent."""
        async with self._lock:
            connection_info = self.active_connections.get(agent_id)
            if connection_info:
                connection_info["last_activity"] = datetime.utcnow()
                return connection_info["connection"]
            return None

    async def update_connection_health(self, agent_id: str, success: bool, response_time: float = 0.0):
        """Update connection health statistics."""
        async with self._lock:
            if agent_id in self.connection_health:
                health = self.connection_health[agent_id]
                health["last_health_check"] = datetime.utcnow()

                if success:
                    health["consecutive_failures"] = 0
                    health["status"] = "healthy"

                    # Update average response time
                    current_avg = health["average_response_time"]
                    message_count = self.active_connections[agent_id]["message_count"]
                    if message_count > 0:
                        health["average_response_time"] = (current_avg * (message_count - 1) + response_time) / message_count
                else:
                    health["consecutive_failures"] += 1
                    health["status"] = "unhealthy" if health["consecutive_failures"] >= 3 else "degraded"

    def get_connection_stats(self) -> Dict[str, Any]:
        """Get connection statistics."""
        return {
            "total_connections": len(self.active_connections),
            "healthy_connections": len([h for h in self.connection_health.values() if h["status"] == "healthy"]),
            "unhealthy_connections": len([h for h in self.connection_health.values() if h["status"] == "unhealthy"]),
            "degraded_connections": len([h for h in self.connection_health.values() if h["status"] == "degraded"]),
            "connection_details": {
                agent_id: {
                    "status": health["status"],
                    "consecutive_failures": health["consecutive_failures"],
                    "average_response_time": health["average_response_time"],
                    "connected_at": conn_info["connected_at"].isoformat(),
                    "last_activity": conn_info["last_activity"].isoformat()
                }
                for agent_id, (conn_info, health) in {
                    aid: (self.active_connections[aid], self.connection_health.get(aid, {}))
                    for aid in self.active_connections
                }.items()
            }
        }


class TransportLayer:
    """
    Manages secure transport protocols for A2A communication.

    Supports HTTP/2 as primary protocol with WebSocket fallback,
    automatic connection management, and TLS encryption.
    """

    def __init__(self, config: TransportConfig):
        """Initialize transport layer with configuration."""
        self.config = config
        self.connection_manager = ConnectionManager()
        self._message_handlers: Dict[str, Callable] = {}
        self._server = None
        self._session = None

        # Performance tracking
        self.stats = {
            "messages_sent": 0,
            "messages_received": 0,
            "connections_established": 0,
            "connections_failed": 0,
            "bytes_sent": 0,
            "bytes_received": 0,
            "errors": 0
        }

        logger.info(f"TransportLayer initialized for {config.protocol.value}://{config.host}:{config.port}")

    async def initialize(self) -> bool:
        """
        Initialize the transport layer.

        Returns:
            True if initialization successful, False otherwise
        """
        try:
            # Create SSL context if TLS is enabled
            ssl_context = None
            if self.config.enable_tls:
                ssl_context = ssl.create_default_context(
                    purpose=ssl.Purpose.CLIENT_AUTH,
                    cafile=self.config.ca_cert_file
                )
                ssl_context.load_cert_chain(self.config.cert_file, self.config.key_file)
                ssl_context.check_hostname = False
                ssl_context.verify_mode = ssl.CERT_NONE

            # Initialize HTTP session for HTTP/2
            connector = aiohttp.TCPConnector(
                limit=self.config.max_connections,
                limit_per_host=10,
                enable_cleanup_closed=True,
                ssl=ssl_context if self.config.enable_tls else False
            )

            timeout = aiohttp.ClientTimeout(
                total=self.config.connection_timeout,
                connect=self.config.connection_timeout
            )

            self._session = aiohttp.ClientSession(
                connector=connector,
                timeout=timeout,
                trust_env=True
            )

            logger.info("TransportLayer initialized successfully")
            return True

        except Exception as e:
            logger.error(f"TransportLayer initialization failed: {e}")
            return False

    async def shutdown(self):
        """Shutdown the transport layer gracefully."""
        try:
            # Close HTTP session
            if self._session:
                await self._session.close()
                self._session = None

            # Close all active connections
            connection_ids = list(self.connection_manager.active_connections.keys())
            for agent_id in connection_ids:
                await self.connection_manager.remove_connection(agent_id)

            logger.info("TransportLayer shutdown completed")

        except Exception as e:
            logger.error(f"Error during transport layer shutdown: {e}")

    async def send_message_http(self,
                              target_url: str,
                              message: Dict[str, Any],
                              headers: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        """
        Send message via HTTP/2.

        Args:
            target_url: Target URL for the request
            message: Message to send
            headers: Additional headers to include

        Returns:
            Response data
        """
        try:
            request_headers = {
                "Content-Type": "application/json",
                "User-Agent": f"HappyOS-A2A/{DEFAULT_CONFIG['protocol_version']}",
                **(headers or {})
            }

            message_data = json.dumps(message)
            self.stats["bytes_sent"] += len(message_data.encode('utf-8'))

            async with self._session.post(
                target_url,
                data=message_data,
                headers=request_headers
            ) as response:
                response_data = await response.text()
                self.stats["bytes_received"] += len(response_data.encode('utf-8'))

                if response.status == ResponseCode.SUCCESS:
                    self.stats["messages_sent"] += 1

                    return {
                        "success": True,
                        "status_code": response.status,
                        "response": json.loads(response_data) if response_data else {},
                        "headers": dict(response.headers)
                    }
                else:
                    self.stats["errors"] += 1
                    return {
                        "success": False,
                        "status_code": response.status,
                        "error": f"HTTP {response.status}: {response_data}",
                        "headers": dict(response.headers)
                    }

        except asyncio.TimeoutError:
            self.stats["errors"] += 1
            return {
                "success": False,
                "error": f"Request timeout after {self.config.message_timeout}s",
                "timeout": True
            }

        except Exception as e:
            self.stats["errors"] += 1
            logger.error(f"HTTP message send failed: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    async def start_server(self, message_handler: Callable) -> bool:
        """
        Start the A2A server to receive messages.

        Args:
            message_handler: Function to handle incoming messages

        Returns:
            True if server started successfully, False otherwise
        """
        try:
            # Store message handler
            self._message_handlers["http"] = message_handler

            # Create SSL context for server
            ssl_context = None
            if self.config.enable_tls:
                ssl_context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
                ssl_context.load_cert_chain(self.config.cert_file, self.config.key_file)
                ssl_context.check_hostname = False
                ssl_context.verify_mode = ssl.CERT_NONE

            # Create web application
            app = web.Application()

            async def handle_message(request):
                try:
                    message_data = await request.json()
                    self.stats["messages_received"] += 1

                    # Call message handler
                    response = await message_handler(message_data)

                    return web.json_response(response)

                except json.JSONDecodeError:
                    return web.json_response(
                        {"error": "Invalid JSON"},
                        status=ResponseCode.BAD_REQUEST
                    )
                except Exception as e:
                    logger.error(f"Error handling message: {e}")
                    return web.json_response(
                        {"error": "Internal server error"},
                        status=ResponseCode.INTERNAL_SERVER_ERROR
                    )

            # Add routes
            app.router.add_post("/a2a/message", handle_message)
            app.router.add_get("/a2a/health", self._handle_health_check)

            # Start server
            runner = web.AppRunner(app)
            await runner.setup()

            site = web.TCPSite(
                runner,
                self.config.host,
                self.config.port,
                ssl_context=ssl_context
            )

            await site.start()
            self._server = {"runner": runner, "site": site}

            logger.info(f"A2A server started on {self.config.protocol.value}://{self.config.host}:{self.config.port}")
            return True

        except Exception as e:
            logger.error(f"Failed to start A2A server: {e}")
            return False

    async def _handle_health_check(self, request) -> web.Response:
        """Handle health check requests."""
        try:
            health_info = {
                "status": "healthy",
                "timestamp": datetime.utcnow().isoformat(),
                "protocol": self.config.protocol.value,
                "port": self.config.port,
                "connections": self.connection_manager.get_connection_stats(),
                "stats": self.stats,
                "version": DEFAULT_CONFIG["protocol_version"]
            }

            return web.json_response(health_info)

        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return web.json_response(
                {"status": "unhealthy", "error": str(e)},
                status=ResponseCode.INTERNAL_SERVER_ERROR
            )

    async def send_message_websocket(self,
                                   target_url: str,
                                   message: Dict[str, Any]) -> Dict[str, Any]:
        """
        Send message via WebSocket.

        Args:
            target_url: WebSocket URL to connect to
            message: Message to send

        Returns:
            Response data
        """
        try:
            # Create SSL context for WebSocket
            ssl_context = None
            if self.config.enable_tls:
                ssl_context = ssl.create_default_context()
                ssl_context.check_hostname = False
                ssl_context.verify_mode = ssl.CERT_NONE

            message_data = json.dumps(message)
            self.stats["bytes_sent"] += len(message_data.encode('utf-8'))

            async with websockets.connect(
                target_url,
                ssl=ssl_context,
                ping_interval=30,
                ping_timeout=10,
                close_timeout=5
            ) as websocket:
                # Send message
                await websocket.send(message_data)

                # Wait for response
                response_data = await asyncio.wait_for(
                    websocket.recv(),
                    timeout=self.config.message_timeout
                )

                self.stats["bytes_received"] += len(response_data.encode('utf-8'))
                self.stats["messages_sent"] += 1

                response = json.loads(response_data)

                return {
                    "success": True,
                    "response": response,
                    "websocket_url": target_url
                }

        except asyncio.TimeoutError:
            self.stats["errors"] += 1
            return {
                "success": False,
                "error": f"WebSocket timeout after {self.config.message_timeout}s",
                "timeout": True
            }

        except Exception as e:
            self.stats["errors"] += 1
            logger.error(f"WebSocket message send failed: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    async def send_message(self,
                          target_agent_id: str,
                          message: Dict[str, Any],
                          preferred_protocol: Optional[TransportProtocol] = None) -> Dict[str, Any]:
        """
        Send message to target agent using appropriate transport protocol.

        Args:
            target_agent_id: ID of target agent
            message: Message to send
            preferred_protocol: Preferred transport protocol

        Returns:
            Send result with success status and response data
        """
        try:
            # Determine transport protocol
            if preferred_protocol:
                protocol = preferred_protocol
            elif self.config.enable_http2:
                protocol = TransportProtocol.HTTP2
            else:
                protocol = TransportProtocol.WEBSOCKET

            # Construct target URL
            scheme = "https" if self.config.enable_tls else "http"
            if protocol == TransportProtocol.HTTP2:
                target_url = f"{scheme}://{target_agent_id}:{self.config.port}/a2a/message"
            else:
                ws_scheme = "wss" if self.config.enable_tls else "ws"
                target_url = f"{ws_scheme}://{target_agent_id}:{self.config.port}/a2a/websocket"

            # Send message based on protocol
            if protocol == TransportProtocol.HTTP2:
                result = await self.send_message_http(target_url, message)
            else:
                result = await self.send_message_websocket(target_url, message)

            # Update connection health
            await self.connection_manager.update_connection_health(
                target_agent_id,
                result["success"]
            )

            return result

        except Exception as e:
            logger.error(f"Failed to send message to agent {target_agent_id}: {e}")
            await self.connection_manager.update_connection_health(target_agent_id, False)
            return {
                "success": False,
                "error": str(e)
            }

    def get_transport_statistics(self) -> Dict[str, Any]:
        """Get transport layer statistics."""
        connection_stats = self.connection_manager.get_connection_stats()

        return {
            "transport_stats": self.stats,
            "connection_stats": connection_stats,
            "config": {
                "protocol": self.config.protocol.value,
                "host": self.config.host,
                "port": self.config.port,
                "enable_tls": self.config.enable_tls,
                "max_connections": self.config.max_connections
            },
            "session_active": self._session is not None,
            "server_running": self._server is not None
        }


class WebSocketHandler:
    """Handles WebSocket connections for A2A protocol."""

    def __init__(self, transport_layer: TransportLayer):
        self.transport = transport_layer
        self.active_connections: Dict[str, websockets.WebSocketServerProtocol] = {}

    async def handle_websocket_connection(self, websocket, path):
        """Handle new WebSocket connection."""
        try:
            # Extract agent ID from connection (in real implementation, this would be authenticated)
            agent_id = "unknown"  # This should be determined through authentication

            self.active_connections[agent_id] = websocket
            logger.info(f"WebSocket connection established for agent: {agent_id}")

            try:
                async for message_raw in websocket:
                    if message_raw.type == WSMsgType.TEXT:
                        try:
                            message = json.loads(message_raw.data)
                            self.transport.stats["messages_received"] += 1

                            # Process message
                            if "http" in self.transport._message_handlers:
                                response = await self.transport._message_handlers["http"](message)
                                await websocket.send(json.dumps(response))

                        except json.JSONDecodeError:
                            error_response = {"error": "Invalid JSON message"}
                            await websocket.send(json.dumps(error_response))

                    elif message_raw.type == WSMsgType.ERROR:
                        logger.error(f"WebSocket error for agent {agent_id}: {message_raw.exception()}")

            except websockets.exceptions.ConnectionClosed:
                logger.info(f"WebSocket connection closed for agent: {agent_id}")

            finally:
                # Remove connection
                self.active_connections.pop(agent_id, None)

        except Exception as e:
            logger.error(f"WebSocket handler error: {e}")