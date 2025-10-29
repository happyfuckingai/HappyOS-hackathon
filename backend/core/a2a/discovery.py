"""
Discovery Service - Agent Discovery and Service Registry for A2A Protocol

Provides agent discovery, service registration, capability matching, and
health monitoring for the Agent-to-Agent communication protocol in HappyOS.
"""

import asyncio
import json
import logging
import os
from typing import Dict, Any, Optional, List, Set
from datetime import datetime, timedelta
import aiohttp
import hashlib

from .constants import (
    AgentCapability,
    AgentState,
    DEFAULT_CONFIG,
    AgentRecord,
    ServiceRecord,
    MessageHeader,
    MessageType,
    MessagePriority,
    ErrorCode,
    ENV_CONFIG
)

logger = logging.getLogger(__name__)


class ServiceRegistry:
    """In-memory service registry for agent capabilities."""

    def __init__(self):
        self.registered_agents: Dict[str, AgentRecord] = {}
        self.capability_index: Dict[AgentCapability, Set[str]] = {}
        self.service_index: Dict[str, Set[str]] = {}  # service_name -> agent_ids
        self._lock = asyncio.Lock()

    async def register_agent(self,
                           agent_record: AgentRecord,
                           services: Optional[List[str]] = None) -> bool:
        """
        Register an agent in the service registry.

        Args:
            agent_record: Agent information record
            services: List of services provided by the agent

        Returns:
            True if registration successful, False otherwise
        """
        async with self._lock:
            try:
                agent_id = agent_record["agent_id"]

                # Add/update agent record
                agent_record["registered_at"] = datetime.utcnow().isoformat()
                agent_record["last_seen"] = datetime.utcnow().isoformat()
                agent_record["status"] = AgentState.ACTIVE.value

                self.registered_agents[agent_id] = agent_record

                # Update capability index
                capabilities = agent_record.get("capabilities", [])
                for capability in capabilities:
                    if capability not in self.capability_index:
                        self.capability_index[capability] = set()
                    self.capability_index[capability].add(agent_id)

                # Update service index
                if services:
                    for service in services:
                        if service not in self.service_index:
                            self.service_index[service] = set()
                        self.service_index[service].add(agent_id)

                logger.info(f"Registered agent: {agent_id} with capabilities: {capabilities}")
                return True

            except Exception as e:
                logger.error(f"Agent registration failed: {e}")
                return False

    async def unregister_agent(self, agent_id: str) -> bool:
        """
        Unregister an agent from the service registry.

        Args:
            agent_id: Agent to unregister

        Returns:
            True if unregistration successful, False otherwise
        """
        async with self._lock:
            try:
                if agent_id not in self.registered_agents:
                    logger.warning(f"Agent {agent_id} not found in registry")
                    return False

                agent_record = self.registered_agents[agent_id]

                # Remove from capability index
                capabilities = agent_record.get("capabilities", [])
                for capability in capabilities:
                    if capability in self.capability_index:
                        self.capability_index[capability].discard(agent_id)
                        if not self.capability_index[capability]:
                            del self.capability_index[capability]

                # Remove from service index
                for service in self.service_index:
                    self.service_index[service].discard(agent_id)
                    if not self.service_index[service]:
                        del self.service_index[service]

                # Remove agent record
                del self.registered_agents[agent_id]

                logger.info(f"Unregistered agent: {agent_id}")
                return True

            except Exception as e:
                logger.error(f"Agent unregistration failed: {e}")
                return False

    async def find_agents_by_capability(self, capability: AgentCapability) -> List[str]:
        """
        Find agents with a specific capability.

        Args:
            capability: Capability to search for

        Returns:
            List of agent IDs with the capability
        """
        async with self._lock:
            return list(self.capability_index.get(capability, set()))

    async def find_agents_by_service(self, service_name: str) -> List[str]:
        """
        Find agents providing a specific service.

        Args:
            service_name: Service to search for

        Returns:
            List of agent IDs providing the service
        """
        async with self._lock:
            return list(self.service_index.get(service_name, set()))

    async def get_agent_record(self, agent_id: str) -> Optional[AgentRecord]:
        """
        Get agent record by ID.

        Args:
            agent_id: Agent identifier

        Returns:
            Agent record if found, None otherwise
        """
        async with self._lock:
            return self.registered_agents.get(agent_id)

    async def list_agents(self) -> Dict[str, AgentRecord]:
        """
        List all registered agents.

        Returns:
            Dictionary of all agent records
        """
        async with self._lock:
            return self.registered_agents.copy()

    async def update_agent_status(self, agent_id: str, status: AgentState) -> bool:
        """
        Update an agent's status.

        Args:
            agent_id: Agent identifier
            status: New agent status

        Returns:
            True if update successful, False otherwise
        """
        async with self._lock:
            if agent_id not in self.registered_agents:
                return False

            self.registered_agents[agent_id]["status"] = status.value
            self.registered_agents[agent_id]["last_seen"] = datetime.utcnow().isoformat()

            return True

    async def cleanup_expired_agents(self, max_age_seconds: int = 3600) -> int:
        """
        Remove agents that haven't been seen for too long.

        Args:
            max_age_seconds: Maximum age in seconds before considering agent expired

        Returns:
            Number of agents removed
        """
        async with self._lock:
            current_time = datetime.utcnow()
            expired_agents = []

            for agent_id, record in self.registered_agents.items():
                last_seen_str = record.get("last_seen")
                if last_seen_str:
                    last_seen = datetime.fromisoformat(last_seen_str)
                    age = (current_time - last_seen).total_seconds()

                    if age > max_age_seconds:
                        expired_agents.append(agent_id)

            # Remove expired agents
            for agent_id in expired_agents:
                await self.unregister_agent(agent_id)

            if expired_agents:
                logger.info(f"Cleaned up {len(expired_agents)} expired agents")

            return len(expired_agents)


class DiscoveryService:
    """
    Provides agent discovery and service registry capabilities for A2A Protocol.

    Handles agent registration, capability-based discovery, health monitoring,
    and service registry management.
    """

    def __init__(self,
                 registry_url: Optional[str] = None,
                 enable_health_monitoring: bool = DEFAULT_CONFIG["enable_health_monitoring"]):
        """
        Initialize DiscoveryService.

        Args:
            registry_url: URL of external service registry (optional)
            enable_health_monitoring: Whether to enable health monitoring
        """
        self.registry_url = registry_url or os.getenv(ENV_CONFIG["A2A_DISCOVERY_URL"])
        self.enable_health_monitoring = enable_health_monitoring

        # Local service registry
        self.local_registry = ServiceRegistry()

        # External registry client
        self._registry_session = None

        # Health monitoring
        self._health_monitor_task = None
        self._monitoring_interval = DEFAULT_CONFIG["health_check_interval"]

        # Cache for external registry queries
        self._external_cache: Dict[str, Dict[str, Any]] = {}
        self._cache_ttl = DEFAULT_CONFIG["discovery_cache_ttl"]

        logger.info(f"DiscoveryService initialized with registry URL: {self.registry_url}")

    async def initialize(self) -> bool:
        """
        Initialize the discovery service.

        Returns:
            True if initialization successful, False otherwise
        """
        try:
            # Initialize HTTP session for external registry
            if self.registry_url:
                timeout = aiohttp.ClientTimeout(total=10)
                self._registry_session = aiohttp.ClientSession(timeout=timeout)

            # Start health monitoring if enabled
            if self.enable_health_monitoring:
                self._health_monitor_task = asyncio.create_task(self._health_monitoring_loop())

            logger.info("DiscoveryService initialized successfully")
            return True

        except Exception as e:
            logger.error(f"DiscoveryService initialization failed: {e}")
            return False

    async def shutdown(self):
        """Shutdown the discovery service gracefully."""
        try:
            # Stop health monitoring
            if self._health_monitor_task:
                self._health_monitor_task.cancel()
                try:
                    await self._health_monitor_task
                except asyncio.CancelledError:
                    pass

            # Close HTTP session
            if self._registry_session:
                await self._registry_session.close()
                self._registry_session = None

            logger.info("DiscoveryService shutdown completed")

        except Exception as e:
            logger.error(f"Error during discovery service shutdown: {e}")

    async def register_agent(self,
                           agent_id: str,
                           capabilities: List[AgentCapability],
                           metadata: Optional[Dict[str, Any]] = None) -> bool:
        """
        Register an agent with its capabilities.

        Args:
            agent_id: Unique agent identifier
            capabilities: List of agent capabilities
            metadata: Additional agent metadata

        Returns:
            True if registration successful, False otherwise
        """
        try:
            # Create agent record
            agent_record = {
                "agent_id": agent_id,
                "capabilities": [cap.value for cap in capabilities],
                "metadata": metadata or {},
                "registration_time": datetime.utcnow().isoformat(),
                "protocol_version": DEFAULT_CONFIG["protocol_version"]
            }

            # Register locally
            local_success = await self.local_registry.register_agent(agent_record)

            # Register with external registry if configured
            external_success = True
            if self.registry_url:
                external_success = await self._register_external(agent_id, agent_record)

            success = local_success and external_success

            if success:
                logger.info(f"Successfully registered agent: {agent_id}")
            else:
                logger.error(f"Failed to register agent: {agent_id}")

            return success

        except Exception as e:
            logger.error(f"Agent registration failed: {e}")
            return False

    async def unregister_agent(self, agent_id: str) -> bool:
        """
        Unregister an agent.

        Args:
            agent_id: Agent to unregister

        Returns:
            True if unregistration successful, False otherwise
        """
        try:
            # Unregister locally
            local_success = await self.local_registry.unregister_agent(agent_id)

            # Unregister from external registry if configured
            external_success = True
            if self.registry_url:
                external_success = await self._unregister_external(agent_id)

            success = local_success and external_success

            if success:
                logger.info(f"Successfully unregistered agent: {agent_id}")
            else:
                logger.error(f"Failed to unregister agent: {agent_id}")

            return success

        except Exception as e:
            logger.error(f"Agent unregistration failed: {e}")
            return False

    async def discover_agents(self,
                            capability: Optional[AgentCapability] = None,
                            service_name: Optional[str] = None,
                            min_agents: int = 1) -> List[AgentRecord]:
        """
        Discover agents based on capabilities or services.

        Args:
            capability: Required capability
            service_name: Required service name
            min_agents: Minimum number of agents to return

        Returns:
            List of matching agent records
        """
        try:
            agents = []

            # Search local registry
            if capability:
                local_agents = await self.local_registry.find_agents_by_capability(capability)
                for agent_id in local_agents:
                    record = await self.local_registry.get_agent_record(agent_id)
                    if record:
                        agents.append(record)

            if service_name:
                local_agents = await self.local_registry.find_agents_by_service(service_name)
                for agent_id in local_agents:
                    record = await self.local_registry.get_agent_record(agent_id)
                    if record:
                        agents.append(record)

            # Remove duplicates
            seen_agent_ids = set()
            unique_agents = []
            for agent in agents:
                agent_id = agent["agent_id"]
                if agent_id not in seen_agent_ids:
                    seen_agent_ids.add(agent_id)
                    unique_agents.append(agent)

            # If we don't have enough agents locally, try external registry
            if len(unique_agents) < min_agents and self.registry_url:
                external_agents = await self._discover_external(capability, service_name)
                unique_agents.extend(external_agents)

                # Remove duplicates again
                seen_agent_ids = set()
                final_agents = []
                for agent in unique_agents:
                    agent_id = agent["agent_id"]
                    if agent_id not in seen_agent_ids:
                        seen_agent_ids.add(agent_id)
                        final_agents.append(agent)

                unique_agents = final_agents

            logger.debug(f"Discovered {len(unique_agents)} agents")
            return unique_agents

        except Exception as e:
            logger.error(f"Agent discovery failed: {e}")
            return []

    async def find_best_agent(self,
                            capability: AgentCapability,
                            criteria: Optional[Dict[str, Any]] = None) -> Optional[AgentRecord]:
        """
        Find the best agent for a specific capability.

        Args:
            capability: Required capability
            criteria: Selection criteria (response_time, load, etc.)

        Returns:
            Best matching agent record or None
        """
        try:
            agents = await self.discover_agents(capability=capability, min_agents=1)

            if not agents:
                return None

            # Simple selection: return first healthy agent
            # In production, implement sophisticated selection based on:
            # - Response time
            # - Current load
            # - Success rate
            # - Geographic proximity

            for agent in agents:
                status = agent.get("status", "unknown")
                if status == AgentState.ACTIVE.value:
                    return agent

            # If no active agents, return first available
            return agents[0] if agents else None

        except Exception as e:
            logger.error(f"Best agent search failed: {e}")
            return None

    async def update_agent_health(self, agent_id: str, health_status: str) -> bool:
        """
        Update an agent's health status.

        Args:
            agent_id: Agent identifier
            health_status: Health status (healthy, degraded, unhealthy)

        Returns:
            True if update successful, False otherwise
        """
        try:
            # Update local registry
            status_enum = AgentState(health_status.lower())
            success = await self.local_registry.update_agent_status(agent_id, status_enum)

            if success:
                logger.debug(f"Updated health status for agent {agent_id}: {health_status}")

            return success

        except Exception as e:
            logger.error(f"Failed to update agent health: {e}")
            return False

    async def get_service_registry_stats(self) -> Dict[str, Any]:
        """Get service registry statistics."""
        try:
            agents = await self.local_registry.list_agents()

            # Count agents by status
            status_counts = {}
            capability_counts = {}

            for agent in agents.values():
                status = agent.get("status", "unknown")
                status_counts[status] = status_counts.get(status, 0) + 1

                capabilities = agent.get("capabilities", [])
                for capability in capabilities:
                    capability_counts[capability] = capability_counts.get(capability, 0) + 1

            return {
                "total_agents": len(agents),
                "status_distribution": status_counts,
                "capability_distribution": capability_counts,
                "service_count": len(set().union(*[set(agent.get("services", [])) for agent in agents.values()])),
                "registry_url": self.registry_url,
                "health_monitoring_enabled": self.enable_health_monitoring,
                "cache_entries": len(self._external_cache)
            }

        except Exception as e:
            logger.error(f"Failed to get registry stats: {e}")
            return {"error": str(e)}

    async def _register_external(self, agent_id: str, agent_record: AgentRecord) -> bool:
        """Register agent with external registry."""
        if not self.registry_url or not self._registry_session:
            return True  # Not configured, consider success

        try:
            async with self._registry_session.post(
                f"{self.registry_url}/agents",
                json=agent_record
            ) as response:
                if response.status == 201:
                    logger.debug(f"Registered agent {agent_id} with external registry")
                    return True
                else:
                    logger.error(f"External registration failed for agent {agent_id}: HTTP {response.status}")
                    return False

        except Exception as e:
            logger.error(f"External registration error for agent {agent_id}: {e}")
            return False

    async def _unregister_external(self, agent_id: str) -> bool:
        """Unregister agent from external registry."""
        if not self.registry_url or not self._registry_session:
            return True  # Not configured, consider success

        try:
            async with self._registry_session.delete(
                f"{self.registry_url}/agents/{agent_id}"
            ) as response:
                if response.status in [200, 204]:
                    logger.debug(f"Unregistered agent {agent_id} from external registry")
                    return True
                else:
                    logger.error(f"External unregistration failed for agent {agent_id}: HTTP {response.status}")
                    return False

        except Exception as e:
            logger.error(f"External unregistration error for agent {agent_id}: {e}")
            return False

    async def _discover_external(self,
                               capability: Optional[AgentCapability] = None,
                               service_name: Optional[str] = None) -> List[AgentRecord]:
        """Discover agents from external registry."""
        if not self.registry_url or not self._registry_session:
            return []

        try:
            # Check cache first
            cache_key = f"{capability.value if capability else 'all'}_{service_name or 'all'}"
            cached_result = self._external_cache.get(cache_key)

            if cached_result:
                cache_time = datetime.fromisoformat(cached_result["cached_at"])
                if (datetime.utcnow() - cache_time).seconds < self._cache_ttl:
                    logger.debug("Using cached external discovery result")
                    return cached_result["agents"]

            # Query external registry
            params = {}
            if capability:
                params["capability"] = capability.value
            if service_name:
                params["service"] = service_name

            async with self._registry_session.get(
                f"{self.registry_url}/agents",
                params=params
            ) as response:
                if response.status == 200:
                    agents = await response.json()

                    # Cache result
                    self._external_cache[cache_key] = {
                        "agents": agents,
                        "cached_at": datetime.utcnow().isoformat()
                    }

                    logger.debug(f"Discovered {len(agents)} agents from external registry")
                    return agents
                else:
                    logger.error(f"External discovery failed: HTTP {response.status}")
                    return []

        except Exception as e:
            logger.error(f"External discovery error: {e}")
            return []

    async def _health_monitoring_loop(self):
        """Background task for health monitoring."""
        while True:
            try:
                # Check for expired agents
                await self.local_registry.cleanup_expired_agents()

                # Health check interval
                await asyncio.sleep(self._monitoring_interval)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Health monitoring error: {e}")
                await asyncio.sleep(self._monitoring_interval)

    async def ping_agent(self, agent_id: str) -> Dict[str, Any]:
        """
        Ping an agent to check its health.

        Args:
            agent_id: Agent to ping

        Returns:
            Ping result with response time and status
        """
        try:
            start_time = datetime.utcnow()

            # Get agent record
            agent_record = await self.local_registry.get_agent_record(agent_id)
            if not agent_record:
                return {
                    "success": False,
                    "error": "Agent not found in registry",
                    "response_time": 0.0
                }

            # In a real implementation, this would send an actual ping message
            # For now, we'll simulate based on last seen time
            last_seen_str = agent_record.get("last_seen")
            if last_seen_str:
                last_seen = datetime.fromisoformat(last_seen_str)
                time_since_seen = (datetime.utcnow() - last_seen).total_seconds()

                # Consider agent healthy if seen within last 60 seconds
                is_healthy = time_since_seen < 60

                response_time = (datetime.utcnow() - start_time).total_seconds()

                return {
                    "success": True,
                    "healthy": is_healthy,
                    "response_time": response_time,
                    "last_seen_seconds_ago": time_since_seen,
                    "agent_status": agent_record.get("status")
                }
            else:
                return {
                    "success": False,
                    "error": "No last seen information",
                    "response_time": (datetime.utcnow() - start_time).total_seconds()
                }

        except Exception as e:
            logger.error(f"Agent ping failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "response_time": (datetime.utcnow() - start_time).total_seconds()
            }


# Global discovery service instance
discovery_service = DiscoveryService()


# Utility function to get config values
def get_config_value(key: str, default: Any = None) -> Any:
    """Get configuration value from environment variables."""
    import os
    return os.getenv(key, default)