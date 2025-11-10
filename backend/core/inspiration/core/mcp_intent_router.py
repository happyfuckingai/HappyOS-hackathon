"""
MCP Intent Routing module.
This module handles the dispatch of MCP requests to appropriate servers/handlers.
"""
import logging
import httpx
import os
import json
from typing import Dict, Any, Optional, List

logger = logging.getLogger(__name__)

# MCP server registry
_mcp_servers: Dict[str, Dict[str, Any]] = {}
_mcp_discovery_endpoints: List[str] = []


async def initialize_mcp_routing():
    """Initialize MCP routing by discovering available servers."""
    global _mcp_servers, _mcp_discovery_endpoints
    
    # Get discovery endpoints from environment
    discovery_env = os.getenv("MCP_DISCOVERY_ENDPOINTS", "")
    if discovery_env:
        _mcp_discovery_endpoints = [endpoint.strip() for endpoint in discovery_env.split(",")]
    
    # Add default discovery endpoint if configured
    default_endpoint = os.getenv("MCP_DEFAULT_ENDPOINT")
    if default_endpoint:
        _mcp_discovery_endpoints.append(default_endpoint)
    
    # Discover servers
    await discover_mcp_servers()


async def discover_mcp_servers():
    """Discover available MCP servers from configured endpoints."""
    global _mcp_servers
    
    if not _mcp_discovery_endpoints:
        logger.warning("No MCP discovery endpoints configured")
        # Fall back to static configuration
        _configure_static_servers()
        return
    
    discovered_servers = {}
    
    # Try each discovery endpoint
    for endpoint in _mcp_discovery_endpoints:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(f"{endpoint}/discover")
                
                if response.status_code == 200:
                    servers = response.json().get("servers", {})
                    discovered_servers.update(servers)
                    logger.info(f"Discovered {len(servers)} MCP servers from {endpoint}")
                else:
                    logger.warning(f"Failed to discover MCP servers from {endpoint}: {response.status_code}")
        
        except Exception as e:
            logger.error(f"Error discovering MCP servers from {endpoint}: {str(e)}")
    
    if discovered_servers:
        _mcp_servers = discovered_servers
        logger.info(f"Total MCP servers discovered: {len(_mcp_servers)}")
    else:
        logger.warning("No MCP servers discovered, falling back to static configuration")
        _configure_static_servers()


def _configure_static_servers():
    """Configure static MCP servers as fallback."""
    global _mcp_servers
    
    _mcp_servers = {
        "web_search": {
            "type": "web",
            "capabilities": ["search", "browse", "scrape"],
            "endpoint": os.getenv("MCP_WEB_SEARCH_ENDPOINT", "https://mcp-web-search.happyos.ai"),
            "status": "active"
        },
        "api_gateway": {
            "type": "api",
            "capabilities": ["rest", "graphql", "webhook"],
            "endpoint": os.getenv("MCP_API_GATEWAY_ENDPOINT", "https://mcp-api-gateway.happyos.ai"),
            "status": "active"
        },
        "data_service": {
            "type": "data",
            "capabilities": ["query", "transform", "analyze"],
            "endpoint": os.getenv("MCP_DATA_SERVICE_ENDPOINT", "https://mcp-data-service.happyos.ai"),
            "status": "active"
        }
    }
    
    logger.info(f"Configured {len(_mcp_servers)} static MCP servers")


async def route_to_mcp(
    service: str,
    operation: Optional[str],
    data: Dict[str, Any],
    context: Dict[str, Any],
    server: str,  # Server identifier selected by MCPRouter
    original_request: str
) -> Dict[str, Any]:
    """
    Route a request to the specified MCP server.
    
    Args:
        service: The target service name
        operation: The operation to perform on the service
        data: Data payload for the service operation
        context: Additional context
        server: Server identifier selected by MCPRouter
        original_request: The original user request string
        
    Returns:
        Dict with response data and metadata
    """
    # Check if server exists in registry
    if server not in _mcp_servers:
        logger.error(f"MCP server '{server}' not found in registry")
        return {
            "success": False,
            "error": f"MCP server '{server}' not found"
        }
    
    server_info = _mcp_servers[server]
    endpoint = server_info.get("endpoint")
    
    if not endpoint:
        logger.error(f"No endpoint defined for MCP server '{server}'")
        return {
            "success": False,
            "error": f"No endpoint defined for MCP server '{server}'"
        }
    
    # Prepare request payload
    payload = {
        "service": service,
        "operation": operation,
        "data": data,
        "context": _filter_context(context),
        "original_request": original_request
    }
    
    try:
        # Check if we're in test/mock mode
        if os.getenv("MCP_MOCK_MODE", "false").lower() == "true":
            logger.info(f"MCP mock mode: simulating request to {server} for {service}.{operation}")
            return _mock_mcp_response(server, service, operation, data)
        
        # Make actual request to MCP server
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{endpoint}/execute",
                json=payload,
                headers={"Content-Type": "application/json"}
            )
            
            if response.status_code == 200:
                result = response.json()
                return {
                    "success": True,
                    "data": result.get("data", {}),
                    "metadata": {
                        "server": server,
                        "service": service,
                        "operation": operation,
                        "response_time": result.get("response_time"),
                        "handler_module": __name__
                    }
                }
            else:
                error_msg = f"MCP request failed with status {response.status_code}"
                try:
                    error_data = response.json()
                    if "error" in error_data:
                        error_msg = error_data["error"]
                except:
                    pass
                
                logger.error(f"MCP request failed: {error_msg}")
                return {
                    "success": False,
                    "error": error_msg
                }
    
    except Exception as e:
        logger.error(f"Error routing to MCP server '{server}': {str(e)}")
        return {
            "success": False,
            "error": f"Error routing to MCP: {str(e)}"
        }


def _filter_context(context: Dict[str, Any]) -> Dict[str, Any]:
    """Filter context to remove sensitive information."""
    if not context:
        return {}
    
    # Create a copy to avoid modifying the original
    filtered = context.copy()
    
    # Remove sensitive keys
    sensitive_keys = ["api_keys", "credentials", "tokens", "password", "secret"]
    for key in list(filtered.keys()):
        if any(sensitive in key.lower() for sensitive in sensitive_keys):
            del filtered[key]
    
    return filtered


def _mock_mcp_response(server: str, service: str, operation: Optional[str], data: Dict[str, Any]) -> Dict[str, Any]:
    """Generate a mock response for testing."""
    return {
        "success": True,
        "data": {
            "message": f"Mock MCP response from '{server}' for service '{service}' (operation: {operation})",
            "received_data": data
        },
        "metadata": {
            "mock": True,
            "handler_module": __name__
        }
    }


def get_available_mcp_servers() -> Dict[str, Dict[str, Any]]:
    """Get the list of available MCP servers."""
    return _mcp_servers


async def refresh_mcp_servers():
    """Refresh the MCP server registry."""
    await discover_mcp_servers()


# Initialize on module import
# This will be properly initialized when the application starts
_configure_static_servers()

__all__ = [
    "route_to_mcp", 
    "initialize_mcp_routing", 
    "get_available_mcp_servers", 
    "refresh_mcp_servers"
]