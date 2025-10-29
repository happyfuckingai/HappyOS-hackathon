"""
Agent Registry Service

Manages agent discovery, health monitoring, and capability advertisement
for the unified agent systems platform.
"""

import asyncio
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass

from backend.infrastructure.database.unified_database_service import unified_db_service
from backend.core.a2a.constants import AgentType, AgentCapability, AgentState
from backend.core.a2a.messaging import message_manager

logger = logging.getLogger(__name__)


@dataclass
class AgentHealthMetrics:
    """Agent health metrics."""
    agent_id: str
    response_time: float
    success_rate: float
    last_heartbeat: datetime
    failure_count: int
    status: str


@dataclass
class AgentCapabilityInfo:
    """Agent capability information."""
    capability: str
    description: str
    parameters: Dict[str, Any]
    performance_metrics: Dict[str, Any]


class AgentRegistry:
    """
    Agent Registry Service for managing agent discovery and health monitoring.
    
    Provides centralized agent registration, capability discovery, health tracking,
    and failure detection for the unified agent platform.
    """
    
    def __init__(self):
        self.logger = logging.getLogger(f"{__name__}.AgentRegistry")
        self.db_service = unified_db_service
        
        # In-memory cache for fast lookups
        self._agent_cache: Dict[str, Dict[str, Any]] = {}
        self._capability_index: Dict[str, List[str]] = {}  # capability -> [agent_ids]
        
        # Health monitoring configuration
        self.heartbeat_timeout = timedelta(minutes=5)
        self.health_check_interval = 30  # seconds
        self.max_failure_count = 3
        
        # Background tasks
        self._health_monitor_task: Optional[asyncio.Task] = None
        self._cleanup_task: Optional[asyncio.Task] = None
        
        self.logger.info("Agent Registry Service initialized")
    
    async def initialize(self):
        """Initialize the agent registry service."""
        try:
            # Load existing agents from database
            await self._load_agents_from_database()
            
            # Start background monitoring tasks
            self._health_monitor_task = asyncio.create_task(self._health_monitor_loop())
            self._cleanup_task = asyncio.create_task(self._cleanup_loop())
            
            self.logger.info("Agent Registry Service started")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize Agent Registry: {e}")
            raise
    
    async def shutdown(self):
        """Shutdown the agent registry service."""
        try:
            # Cancel background tasks
            if self._health_monitor_task:
                self._health_monitor_task.cancel()
            if self._cleanup_task:
                self._cleanup_task.cancel()
            
            # Wait for tasks to complete
            await asyncio.gather(
                self._health_monitor_task,
                self._cleanup_task,
                return_exceptions=True
            )
            
            self.logger.info("Agent Registry Service shutdown")
            
        except Exception as e:
            self.logger.error(f"Error during Agent Registry shutdown: {e}")
    
    async def register_agent(self, 
                           agent_id: str,
                           agent_type: AgentType,
                           capabilities: List[AgentCapability],
                           endpoint: str,
                           metadata: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Register an agent with the registry.
        
        Args:
            agent_id: Unique agent identifier
            agent_type: Type of agent
            capabilities: List of agent capabilities
            endpoint: Agent endpoint URL
            metadata: Additional agent metadata
            
        Returns:
            Registration result
        """
        try:
            # Prepare agent data
            agent_data = {
                "agent_id": agent_id,
                "agent_type": agent_type.value,
                "capabilities": [cap.value for cap in capabilities],
                "endpoint": endpoint,
                "metadata": metadata or {}
            }
            
            # Store in database
            await self.db_service.register_agent(agent_data)
            
            # Update in-memory cache
            self._agent_cache[agent_id] = {
                **agent_data,
                "status": AgentState.ACTIVE.value,
                "health_status": "healthy",
                "registered_at": datetime.utcnow(),
                "last_heartbeat": datetime.utcnow(),
                "failure_count": 0
            }
            
            # Update capability index
            for capability in capabilities:
                cap_value = capability.value
                if cap_value not in self._capability_index:
                    self._capability_index[cap_value] = []
                if agent_id not in self._capability_index[cap_value]:
                    self._capability_index[cap_value].append(agent_id)
            
            self.logger.info(f"Agent registered: {agent_id} ({agent_type.value})")
            
            return {
                "success": True,
                "agent_id": agent_id,
                "message": f"Agent {agent_id} registered successfully",
                "registration_time": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"Failed to register agent {agent_id}: {e}")
            return {
                "success": False,
                "agent_id": agent_id,
                "error": str(e)
            }
    
    async def deregister_agent(self, agent_id: str) -> Dict[str, Any]:
        """
        Deregister an agent from the registry.
        
        Args:
            agent_id: Agent identifier to deregister
            
        Returns:
            Deregistration result
        """
        try:
            # Remove from cache
            agent_info = self._agent_cache.pop(agent_id, None)
            
            if not agent_info:
                return {
                    "success": False,
                    "agent_id": agent_id,
                    "error": "Agent not found"
                }
            
            # Remove from capability index
            capabilities = agent_info.get("capabilities", [])
            for capability in capabilities:
                if capability in self._capability_index:
                    if agent_id in self._capability_index[capability]:
                        self._capability_index[capability].remove(agent_id)
                    if not self._capability_index[capability]:
                        del self._capability_index[capability]
            
            # Update database status
            # Note: We keep the record for historical purposes but mark as inactive
            # In a real implementation, you might want to update the database record
            
            self.logger.info(f"Agent deregistered: {agent_id}")
            
            return {
                "success": True,
                "agent_id": agent_id,
                "message": f"Agent {agent_id} deregistered successfully"
            }
            
        except Exception as e:
            self.logger.error(f"Failed to deregister agent {agent_id}: {e}")
            return {
                "success": False,
                "agent_id": agent_id,
                "error": str(e)
            }
    
    async def heartbeat(self, agent_id: str, health_metrics: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Process agent heartbeat.
        
        Args:
            agent_id: Agent identifier
            health_metrics: Optional health metrics from agent
            
        Returns:
            Heartbeat acknowledgment
        """
        try:
            # Update database
            success = await self.db_service.update_agent_heartbeat(agent_id)
            
            if not success:
                return {
                    "success": False,
                    "agent_id": agent_id,
                    "error": "Agent not found in registry"
                }
            
            # Update cache
            if agent_id in self._agent_cache:
                self._agent_cache[agent_id]["last_heartbeat"] = datetime.utcnow()
                self._agent_cache[agent_id]["failure_count"] = 0
                
                # Update health status if provided
                if health_metrics:
                    self._agent_cache[agent_id]["health_metrics"] = health_metrics
                    
                    # Determine health status based on metrics
                    health_status = self._calculate_health_status(health_metrics)
                    self._agent_cache[agent_id]["health_status"] = health_status
            
            return {
                "success": True,
                "agent_id": agent_id,
                "timestamp": datetime.utcnow().isoformat(),
                "next_heartbeat_expected": (datetime.utcnow() + self.heartbeat_timeout).isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"Failed to process heartbeat for agent {agent_id}: {e}")
            return {
                "success": False,
                "agent_id": agent_id,
                "error": str(e)
            }
    
    async def discover_agents(self, 
                            required_capabilities: List[AgentCapability] = None,
                            agent_type: AgentType = None,
                            health_status: str = None) -> List[Dict[str, Any]]:
        """
        Discover agents based on criteria.
        
        Args:
            required_capabilities: Required agent capabilities
            agent_type: Specific agent type to filter by
            health_status: Required health status
            
        Returns:
            List of matching agents
        """
        try:
            matching_agents = []
            
            # If specific capabilities are required, use capability index
            if required_capabilities:
                capability_values = [cap.value for cap in required_capabilities]
                candidate_agents = await self.db_service.get_agents_by_capability(capability_values)
                
                # Filter by additional criteria
                for agent_data in candidate_agents:
                    agent_id = agent_data["agent_id"]
                    
                    # Check if agent is in cache (active)
                    if agent_id not in self._agent_cache:
                        continue
                    
                    cached_agent = self._agent_cache[agent_id]
                    
                    # Apply filters
                    if agent_type and cached_agent.get("agent_type") != agent_type.value:
                        continue
                    
                    if health_status and cached_agent.get("health_status") != health_status:
                        continue
                    
                    matching_agents.append({
                        **agent_data,
                        "status": cached_agent.get("status"),
                        "health_status": cached_agent.get("health_status"),
                        "last_heartbeat": cached_agent.get("last_heartbeat").isoformat() if cached_agent.get("last_heartbeat") else None
                    })
            else:
                # Return all agents matching other criteria
                for agent_id, agent_info in self._agent_cache.items():
                    # Apply filters
                    if agent_type and agent_info.get("agent_type") != agent_type.value:
                        continue
                    
                    if health_status and agent_info.get("health_status") != health_status:
                        continue
                    
                    matching_agents.append({
                        "agent_id": agent_id,
                        "agent_type": agent_info.get("agent_type"),
                        "capabilities": agent_info.get("capabilities", []),
                        "endpoint": agent_info.get("endpoint"),
                        "metadata": agent_info.get("metadata", {}),
                        "status": agent_info.get("status"),
                        "health_status": agent_info.get("health_status"),
                        "last_heartbeat": agent_info.get("last_heartbeat").isoformat() if agent_info.get("last_heartbeat") else None
                    })
            
            self.logger.debug(f"Discovered {len(matching_agents)} agents")
            return matching_agents
            
        except Exception as e:
            self.logger.error(f"Failed to discover agents: {e}")
            return []
    
    async def get_agent_status(self, agent_id: str) -> Optional[Dict[str, Any]]:
        """
        Get detailed status for a specific agent.
        
        Args:
            agent_id: Agent identifier
            
        Returns:
            Agent status information or None if not found
        """
        try:
            if agent_id not in self._agent_cache:
                return None
            
            agent_info = self._agent_cache[agent_id]
            
            return {
                "agent_id": agent_id,
                "agent_type": agent_info.get("agent_type"),
                "capabilities": agent_info.get("capabilities", []),
                "endpoint": agent_info.get("endpoint"),
                "status": agent_info.get("status"),
                "health_status": agent_info.get("health_status"),
                "last_heartbeat": agent_info.get("last_heartbeat").isoformat() if agent_info.get("last_heartbeat") else None,
                "failure_count": agent_info.get("failure_count", 0),
                "registered_at": agent_info.get("registered_at").isoformat() if agent_info.get("registered_at") else None,
                "metadata": agent_info.get("metadata", {}),
                "health_metrics": agent_info.get("health_metrics", {})
            }
            
        except Exception as e:
            self.logger.error(f"Failed to get agent status for {agent_id}: {e}")
            return None
    
    async def get_registry_status(self) -> Dict[str, Any]:
        """
        Get overall registry status and statistics.
        
        Returns:
            Registry status information
        """
        try:
            total_agents = len(self._agent_cache)
            
            # Count agents by status
            status_counts = {}
            health_counts = {}
            type_counts = {}
            
            for agent_info in self._agent_cache.values():
                status = agent_info.get("status", "unknown")
                health = agent_info.get("health_status", "unknown")
                agent_type = agent_info.get("agent_type", "unknown")
                
                status_counts[status] = status_counts.get(status, 0) + 1
                health_counts[health] = health_counts.get(health, 0) + 1
                type_counts[agent_type] = type_counts.get(agent_type, 0) + 1
            
            # Count capabilities
            capability_counts = {cap: len(agents) for cap, agents in self._capability_index.items()}
            
            return {
                "total_agents": total_agents,
                "status_distribution": status_counts,
                "health_distribution": health_counts,
                "type_distribution": type_counts,
                "capability_distribution": capability_counts,
                "registry_uptime": datetime.utcnow().isoformat(),
                "monitoring_active": self._health_monitor_task is not None and not self._health_monitor_task.done()
            }
            
        except Exception as e:
            self.logger.error(f"Failed to get registry status: {e}")
            return {
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
    
    # Private methods
    
    async def _load_agents_from_database(self):
        """Load existing agents from database into cache."""
        try:
            # This would load agents from the database
            # For now, we'll start with an empty cache
            self.logger.info("Loaded agents from database")
            
        except Exception as e:
            self.logger.error(f"Failed to load agents from database: {e}")
            raise
    
    async def _health_monitor_loop(self):
        """Background task for monitoring agent health."""
        try:
            while True:
                await asyncio.sleep(self.health_check_interval)
                await self._check_agent_health()
                
        except asyncio.CancelledError:
            self.logger.info("Health monitor loop cancelled")
        except Exception as e:
            self.logger.error(f"Health monitor loop error: {e}")
    
    async def _check_agent_health(self):
        """Check health of all registered agents."""
        try:
            current_time = datetime.utcnow()
            unhealthy_agents = []
            
            for agent_id, agent_info in self._agent_cache.items():
                last_heartbeat = agent_info.get("last_heartbeat")
                
                if not last_heartbeat:
                    continue
                
                # Check if heartbeat is overdue
                time_since_heartbeat = current_time - last_heartbeat
                
                if time_since_heartbeat > self.heartbeat_timeout:
                    failure_count = agent_info.get("failure_count", 0) + 1
                    agent_info["failure_count"] = failure_count
                    
                    if failure_count >= self.max_failure_count:
                        agent_info["health_status"] = "unhealthy"
                        agent_info["status"] = AgentState.OFFLINE.value
                        unhealthy_agents.append(agent_id)
                    else:
                        agent_info["health_status"] = "degraded"
            
            if unhealthy_agents:
                self.logger.warning(f"Detected unhealthy agents: {unhealthy_agents}")
            
        except Exception as e:
            self.logger.error(f"Error checking agent health: {e}")
    
    async def _cleanup_loop(self):
        """Background task for cleaning up stale data."""
        try:
            while True:
                await asyncio.sleep(300)  # Run every 5 minutes
                await self._cleanup_stale_data()
                
        except asyncio.CancelledError:
            self.logger.info("Cleanup loop cancelled")
        except Exception as e:
            self.logger.error(f"Cleanup loop error: {e}")
    
    async def _cleanup_stale_data(self):
        """Clean up stale agent data."""
        try:
            current_time = datetime.utcnow()
            stale_threshold = timedelta(hours=24)  # Remove agents offline for 24 hours
            
            stale_agents = []
            for agent_id, agent_info in self._agent_cache.items():
                last_heartbeat = agent_info.get("last_heartbeat")
                
                if (last_heartbeat and 
                    current_time - last_heartbeat > stale_threshold and
                    agent_info.get("status") == AgentState.OFFLINE.value):
                    stale_agents.append(agent_id)
            
            # Remove stale agents
            for agent_id in stale_agents:
                await self.deregister_agent(agent_id)
                self.logger.info(f"Cleaned up stale agent: {agent_id}")
            
        except Exception as e:
            self.logger.error(f"Error cleaning up stale data: {e}")
    
    def _calculate_health_status(self, health_metrics: Dict[str, Any]) -> str:
        """Calculate health status based on metrics."""
        try:
            response_time = health_metrics.get("response_time", 0)
            success_rate = health_metrics.get("success_rate", 100)
            error_rate = health_metrics.get("error_rate", 0)
            
            # Define thresholds
            if response_time > 5.0 or success_rate < 80 or error_rate > 20:
                return "unhealthy"
            elif response_time > 2.0 or success_rate < 95 or error_rate > 5:
                return "degraded"
            else:
                return "healthy"
                
        except Exception as e:
            self.logger.error(f"Error calculating health status: {e}")
            return "unknown"


# Global agent registry instance
agent_registry = AgentRegistry()