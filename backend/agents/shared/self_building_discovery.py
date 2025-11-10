"""
Self-Building Agent Discovery Module

Provides utilities for agents to discover and communicate with the self-building agent.
"""

import logging
from typing import Dict, Any, Optional
import httpx

logger = logging.getLogger(__name__)


class SelfBuildingAgentDiscovery:
    """
    Helper class for discovering and interacting with the self-building agent.
    """
    
    def __init__(self, agent_id: str, agent_registry_url: str = "http://localhost:8000"):
        """
        Initialize self-building agent discovery.
        
        Args:
            agent_id: ID of the current agent
            agent_registry_url: URL of the agent registry service
        """
        self.agent_id = agent_id
        self.agent_registry_url = agent_registry_url
        self.self_building_endpoint: Optional[str] = None
        self.self_building_health_endpoint: Optional[str] = None
        self.self_building_agent_info: Optional[Dict[str, Any]] = None
        self._http_client: Optional[httpx.AsyncClient] = None
    
    async def discover_self_building_agent(self) -> bool:
        """
        Discover the self-building agent from the agent registry.
        
        Returns:
            True if discovery successful, False otherwise
        """
        try:
            if not self._http_client:
                self._http_client = httpx.AsyncClient(timeout=10.0)
            
            # Query agent registry for self-building agent
            response = await self._http_client.get(
                f"{self.agent_registry_url}/api/agents/self-building"
            )
            
            if response.status_code == 200:
                agent_info = response.json()
                self.self_building_agent_info = agent_info
                self.self_building_endpoint = agent_info.get("mcp_endpoint")
                self.self_building_health_endpoint = agent_info.get("health_endpoint")
                
                logger.info(
                    f"[{self.agent_id}] Discovered self-building agent at {self.self_building_endpoint}"
                )
                return True
            else:
                logger.warning(
                    f"[{self.agent_id}] Failed to discover self-building agent: "
                    f"status={response.status_code}"
                )
                return False
                
        except Exception as e:
            logger.error(
                f"[{self.agent_id}] Error discovering self-building agent: {e}"
            )
            return False
    
    async def check_self_building_health(self) -> Dict[str, Any]:
        """
        Check health status of the self-building agent.
        
        Returns:
            Health status dictionary
        """
        if not self.self_building_health_endpoint:
            return {"status": "unknown", "error": "Self-building agent not discovered"}
        
        try:
            if not self._http_client:
                self._http_client = httpx.AsyncClient(timeout=10.0)
            
            response = await self._http_client.get(self.self_building_health_endpoint)
            
            if response.status_code == 200:
                return response.json()
            else:
                return {
                    "status": "unhealthy",
                    "error": f"Health check failed with status {response.status_code}"
                }
                
        except Exception as e:
            logger.error(
                f"[{self.agent_id}] Error checking self-building health: {e}"
            )
            return {"status": "error", "error": str(e)}
    
    async def call_self_building_tool(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
        api_key: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Call a self-building MCP tool.
        
        Args:
            tool_name: Name of the tool to call
            arguments: Tool arguments
            api_key: Optional API key for authentication
            
        Returns:
            Tool response dictionary
        """
        if not self.self_building_endpoint:
            return {
                "success": False,
                "error": "Self-building agent not discovered"
            }
        
        try:
            if not self._http_client:
                self._http_client = httpx.AsyncClient(timeout=30.0)
            
            headers = {}
            if api_key:
                headers["Authorization"] = f"Bearer {api_key}"
            
            # Call MCP tool endpoint
            response = await self._http_client.post(
                f"{self.self_building_endpoint}/tools/{tool_name}",
                json=arguments,
                headers=headers
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                return {
                    "success": False,
                    "error": f"Tool call failed with status {response.status_code}",
                    "details": response.text
                }
                
        except Exception as e:
            logger.error(
                f"[{self.agent_id}] Error calling self-building tool {tool_name}: {e}"
            )
            return {"success": False, "error": str(e)}
    
    async def trigger_improvement_cycle(
        self,
        analysis_window_hours: int = 24,
        max_improvements: int = 3,
        tenant_id: Optional[str] = None,
        api_key: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Trigger an improvement cycle for this agent.
        
        Args:
            analysis_window_hours: Hours of telemetry to analyze
            max_improvements: Maximum concurrent improvements
            tenant_id: Optional tenant scope
            api_key: Optional API key for authentication
            
        Returns:
            Improvement cycle result
        """
        return await self.call_self_building_tool(
            tool_name="trigger_improvement_cycle",
            arguments={
                "analysis_window_hours": analysis_window_hours,
                "max_improvements": max_improvements,
                "tenant_id": tenant_id
            },
            api_key=api_key
        )
    
    async def query_telemetry_insights(
        self,
        metric_name: Optional[str] = None,
        time_range_hours: int = 1,
        tenant_id: Optional[str] = None,
        api_key: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Query telemetry insights from the self-building agent.
        
        Args:
            metric_name: Specific metric to query
            time_range_hours: Time range for analysis
            tenant_id: Optional tenant filter
            api_key: Optional API key for authentication
            
        Returns:
            Telemetry insights
        """
        return await self.call_self_building_tool(
            tool_name="query_telemetry_insights",
            arguments={
                "metric_name": metric_name,
                "time_range_hours": time_range_hours,
                "tenant_id": tenant_id
            },
            api_key=api_key
        )
    
    async def get_system_status(
        self,
        api_key: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get self-building system status.
        
        Args:
            api_key: Optional API key for authentication
            
        Returns:
            System status
        """
        return await self.call_self_building_tool(
            tool_name="get_system_status",
            arguments={},
            api_key=api_key
        )
    
    def is_discovered(self) -> bool:
        """Check if self-building agent has been discovered."""
        return self.self_building_endpoint is not None
    
    def get_endpoint(self) -> Optional[str]:
        """Get the self-building agent MCP endpoint."""
        return self.self_building_endpoint
    
    async def close(self):
        """Close HTTP client."""
        if self._http_client:
            await self._http_client.aclose()
            self._http_client = None
