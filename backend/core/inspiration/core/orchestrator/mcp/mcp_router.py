"""
MCP routing logic separated from orchestrator.
Handles Model Context Protocol routing and integration.
"""

import logging
import time
from datetime import datetime
from typing import Dict, Any, Optional, List
from dataclasses import dataclass

from app.core.mcp_intent_router import route_to_mcp
from app.core.error_handler import safe_execute

logger = logging.getLogger(__name__)


@dataclass
class MCPRoutingResult:
    """Result of MCP routing."""
    success: bool
    data: Any = None
    error: Optional[str] = None
    mcp_server: Optional[str] = None
    execution_time: float = 0.0
    metadata: Dict[str, Any] = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


class MCPRouter:
    """Handles MCP routing and protocol integration."""
    
    def __init__(self):
        self.mcp_servers = {}
        self.routing_cache = {}
        self.routing_history = []
    
    async def initialize(self):
        """Initialize MCP router."""
        try:
            # Initialize the MCP intent router first
            from app.core.mcp_intent_router import initialize_mcp_routing
            await initialize_mcp_routing()
        except Exception as e:
            logger.error(f"Error initializing MCP intent router: {e}")
        
        # Discover available MCP servers
        await self._discover_mcp_servers()
    
    async def route_request(
        self,
        service: str,
        operation: Optional[str],
        data: Dict[str, Any],
        original_request: str,
        context: Dict[str, Any] = None,
        preferred_server: Optional[str] = None
    ) -> MCPRoutingResult:
        """
        Route request through MCP protocol.

        Args:
            service: The target service name.
            operation: The operation to perform on the service.
            data: Data payload for the service operation.
            original_request: The original user request string.
            context: Additional context.
            preferred_server: Preferred MCP server to use.

        Returns:
            MCPRoutingResult with routing details
        """
        if context is None:
            context = {}

        start_time = time.time()

        try:
            # It's assumed that if route_request is called, it's definitely an MCP request.
            # Determine best MCP server
            mcp_server = preferred_server or await self._select_mcp_server(service, data, context)

            if not mcp_server:
                return MCPRoutingResult(
                    success=False,
                    error="No suitable MCP server found"
                )
            
            # Route through MCP
            result = await safe_execute(
                route_to_mcp,
                service=service,
                operation=operation,
                data=data,
                context=context,
                server=mcp_server,
                original_request=original_request
            )

            execution_time = time.time() - start_time

            if result and result.get("success"):
                routing_result = MCPRoutingResult(
                    success=True,
                    data=result.get("data"),
                    mcp_server=mcp_server,
                    execution_time=execution_time,
                    metadata=result.get("metadata", {})
                )
            else:
                routing_result = MCPRoutingResult(
                    success=False,
                    error=result.get("error", "Unknown MCP error"),
                    mcp_server=mcp_server,
                    execution_time=execution_time
                )

            # Track routing
            self._track_routing(routing_result, original_request)

            return routing_result

        except Exception as e:
            execution_time = time.time() - start_time
            logger.error(f"Error routing through MCP: {e}")
            
            return MCPRoutingResult(
                success=False,
                error=str(e),
                execution_time=execution_time
            )

    async def _select_mcp_server(self, service: str, data: Dict[str, Any], context: Dict[str, Any]) -> Optional[str]:
        """Select the best MCP server for the request."""

        if not self.mcp_servers:
            return None

        # Score each server for this request
        server_scores = {}

        for server_name, server_info in self.mcp_servers.items():
            score = await self._score_mcp_server(server_name, server_info, service, data, context)
            server_scores[server_name] = score

        # Return server with highest score
        if server_scores:
            best_server = max(server_scores, key=server_scores.get)
            if server_scores[best_server] > 0.3:  # Minimum threshold
                return best_server
        
        return None
    
    async def _score_mcp_server(
        self,
        server_name: str,
        server_info: Dict[str, Any],
        service: str,
        data: Dict[str, Any], # operation is often in data
        context: Dict[str, Any]
    ) -> float:
        """Score how well an MCP server can handle the request."""

        score = 0.0
        service_lower = service.lower()

        # Check server capabilities
        capabilities = server_info.get("capabilities", [])
        for capability in capabilities:
            if capability.lower() == service_lower: # Exact match for service
                score += 0.5
            # Consider if service is part of a broader capability, e.g. service "user_info" under "hr_api"
            elif service_lower in capability.lower():
                score += 0.3


        # Check server type/domain against service or data
        server_type = server_info.get("type", "").lower()
        if server_type:
            # Example: if server_type is 'web' and service is 'web_search'
            if server_type in service_lower:
                score += 0.2
            # Example: if data contains keys like 'query' and server_type is 'data'
            if "data" in server_type and any(key in data for key in ["query", "fetch", "get_data"]):
                score += 0.2
            if "api" in server_type and any(key in data for key in ["api_call", "endpoint"]):
                 score += 0.2

        # Factor in historical performance
        historical_score = self._get_mcp_server_performance(server_name)
        score = (score * 0.7) + (historical_score * 0.3)
        
        return min(score, 1.0)
    
    async def _discover_mcp_servers(self):
        """Discover available MCP servers."""
        
        try:
            # Get servers from the MCP intent router
            from app.core.mcp_intent_router import get_available_mcp_servers, refresh_mcp_servers
            
            # Refresh the server registry first
            await refresh_mcp_servers()
            
            # Get the available servers
            self.mcp_servers = get_available_mcp_servers()
            
            logger.info(f"Discovered {len(self.mcp_servers)} MCP servers")
            
        except Exception as e:
            logger.error(f"Error discovering MCP servers: {e}")
            self.mcp_servers = {}
    
    def _track_routing(self, result: MCPRoutingResult, original_request: str):
        """Track MCP routing for performance analysis."""

        self.routing_history.append({
            "timestamp": datetime.now(),
            "mcp_server": result.mcp_server,
            "success": result.success,
            "execution_time": result.execution_time,
            "request_length": len(original_request)
        })

        # Keep only recent history
        if len(self.routing_history) > 1000:
            self.routing_history = self.routing_history[-500:]
    
    def _get_mcp_server_performance(self, server_name: str) -> float:
        """Get historical performance score for MCP server."""
        
        server_history = [
            h for h in self.routing_history 
            if h["mcp_server"] == server_name
        ]
        
        if not server_history:
            return 0.5  # Neutral score for new servers
        
        # Calculate success rate
        success_rate = sum(1 for h in server_history if h["success"]) / len(server_history)
        
        # Factor in average execution time
        avg_time = sum(h["execution_time"] for h in server_history) / len(server_history)
        time_score = max(0, 1 - (avg_time / 5))  # Normalize to 0-1
        
        return (success_rate * 0.8) + (time_score * 0.2)
    
    def get_mcp_stats(self) -> Dict[str, Any]:
        """Get MCP routing statistics."""
        
        if not self.routing_history:
            return {"total_routings": 0}
        
        total = len(self.routing_history)
        successful = sum(1 for h in self.routing_history if h["success"])
        
        server_stats = {}
        for history in self.routing_history:
            server = history["mcp_server"]
            if server not in server_stats:
                server_stats[server] = {"total": 0, "successful": 0, "avg_time": 0}
            
            server_stats[server]["total"] += 1
            if history["success"]:
                server_stats[server]["successful"] += 1
            server_stats[server]["avg_time"] += history["execution_time"]
        
        # Calculate averages
        for server, stats in server_stats.items():
            stats["success_rate"] = stats["successful"] / stats["total"]
            stats["avg_time"] /= stats["total"]
        
        return {
            "total_routings": total,
            "success_rate": successful / total,
            "available_servers": list(self.mcp_servers.keys()),
            "server_stats": server_stats
        }
    
    def clear_cache(self):
        """Clear routing cache."""
        self.routing_cache.clear()


# Global MCP router instance
mcp_router = MCPRouter()