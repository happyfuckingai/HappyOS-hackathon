"""
MCP UI Hub Platform Service

Core platform service that provides the integration backbone for all startup MCP servers.
Implements the central platform functionality for:
- Multi-tenant isolation and management
- Standardized MCP server registration and discovery
- Platform-as-a-service infrastructure
- Ecosystem control through centralized resource management

This is the heart of the central MCP UI Hub platform that enables rapid startup deployment.

Requirements: 1.4, 6.1, 6.5
"""

import asyncio
import json
import logging
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Set
from uuid import uuid4
import aioredis
import boto3
from botocore.exceptions import ClientError

from ..observability import get_logger

logger = get_logger(__name__)


class TenantConfig:
    """Configuration for a tenant in the multi-tenant platform"""
    
    def __init__(
        self,
        tenant_id: str,
        name: str,
        domain: str,
        allowed_agents: List[str],
        theme_config: Optional[Dict[str, Any]] = None,
        resource_limits: Optional[Dict[str, int]] = None
    ):
        self.tenant_id = tenant_id
        self.name = name
        self.domain = domain
        self.allowed_agents = allowed_agents
        self.theme_config = theme_config or {}
        self.resource_limits = resource_limits or {
            "max_resources": 1000,
            "max_sessions": 100,
            "max_agents": 10
        }
        self.created_at = datetime.now(timezone.utc)
        self.updated_at = datetime.now(timezone.utc)


class MCPUIHubService:
    """
    Central MCP UI Hub Platform Service
    
    This service provides the core platform functionality that all startup MCP servers
    connect to for UI resource management and real-time updates.
    """
    
    def __init__(self, use_redis: bool = False, use_dynamodb: bool = False):
        self.use_redis = use_redis
        self.use_dynamodb = use_dynamodb
        self.redis_client = None
        self.dynamodb_client = None
        self.dynamodb_table = None
        
        # In-memory storage (fallback when Redis/DynamoDB not available)
        self.ui_resources: Dict[str, Dict[str, Any]] = {}
        self.resource_revisions: Dict[str, int] = {}
        self.registered_agents: Dict[str, Dict[str, Any]] = {}
        self.active_websockets: Dict[str, Set] = {}
        
        # Platform configuration
        self.tenant_configs = {
            "meetmind": TenantConfig(
                tenant_id="meetmind",
                name="MeetMind",
                domain="meetmind.com",
                allowed_agents=["meetmind-summarizer"],
                theme_config={"primaryColor": "#2563eb", "logo": "/meetmind-logo.svg"}
            ),
            "happyos": TenantConfig(
                tenant_id="happyos",
                name="HappyOS",
                domain="happyos.com",
                allowed_agents=["felicia-core", "agent-svea", "meetmind-summarizer"],
                theme_config={"primaryColor": "#059669", "logo": "/happyos-logo.svg"}
            ),
            "feliciasfi": TenantConfig(
                tenant_id="feliciasfi",
                name="Felicia's Finance",
                domain="feliciasfi.com",
                allowed_agents=["felicia-core"],
                theme_config={"primaryColor": "#dc2626", "logo": "/felicia-logo.svg"}
            )
        }
    
    async def initialize(self):
        """Initialize the platform service with external dependencies"""
        try:
            if self.use_redis:
                await self._initialize_redis()
            
            if self.use_dynamodb:
                await self._initialize_dynamodb()
            
            logger.info("MCP UI Hub Platform Service initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize MCP UI Hub Platform Service: {e}")
            # Fall back to in-memory storage
            logger.warning("Falling back to in-memory storage")
    
    async def _initialize_redis(self):
        """Initialize Redis connection for caching and real-time features"""
        try:
            self.redis_client = await aioredis.from_url(
                "redis://localhost:6379",
                encoding="utf-8",
                decode_responses=True
            )
            await self.redis_client.ping()
            logger.info("Redis connection established")
        except Exception as e:
            logger.warning(f"Redis connection failed: {e}")
            self.use_redis = False
    
    async def _initialize_dynamodb(self):
        """Initialize DynamoDB for persistent storage"""
        try:
            self.dynamodb_client = boto3.resource('dynamodb', region_name='us-east-1')
            self.dynamodb_table = self.dynamodb_client.Table('ui_resources')
            
            # Test connection
            self.dynamodb_table.load()
            logger.info("DynamoDB connection established")
        except Exception as e:
            logger.warning(f"DynamoDB connection failed: {e}")
            self.use_dynamodb = False
    
    # === Tenant Management ===
    
    def get_tenant_config(self, tenant_id: str) -> Optional[TenantConfig]:
        """Get tenant configuration for platform-as-a-service infrastructure"""
        return self.tenant_configs.get(tenant_id)
    
    def list_tenants(self) -> List[TenantConfig]:
        """List all supported tenants for ecosystem control"""
        return list(self.tenant_configs.values())
    
    def validate_tenant_agent(self, tenant_id: str, agent_id: str) -> bool:
        """Validate that an agent is allowed for a tenant"""
        tenant_config = self.get_tenant_config(tenant_id)
        if not tenant_config:
            return False
        return agent_id in tenant_config.allowed_agents
    
    async def add_tenant(self, tenant_config: TenantConfig) -> bool:
        """Add new tenant for rapid startup deployment"""
        try:
            self.tenant_configs[tenant_config.tenant_id] = tenant_config
            
            # Persist to Redis if available
            if self.redis_client:
                await self.redis_client.hset(
                    "tenants",
                    tenant_config.tenant_id,
                    json.dumps({
                        "name": tenant_config.name,
                        "domain": tenant_config.domain,
                        "allowed_agents": tenant_config.allowed_agents,
                        "theme_config": tenant_config.theme_config,
                        "resource_limits": tenant_config.resource_limits,
                        "created_at": tenant_config.created_at.isoformat(),
                        "updated_at": tenant_config.updated_at.isoformat()
                    })
                )
            
            logger.info(f"Added tenant {tenant_config.tenant_id} to platform")
            return True
            
        except Exception as e:
            logger.error(f"Failed to add tenant {tenant_config.tenant_id}: {e}")
            return False
    
    # === Agent Registration and Discovery ===
    
    async def register_agent(
        self,
        agent_id: str,
        tenant_id: str,
        agent_info: Dict[str, Any]
    ) -> bool:
        """Register MCP agent for standardized server discovery"""
        try:
            # Validate tenant and agent
            if not self.validate_tenant_agent(tenant_id, agent_id):
                logger.warning(f"Agent {agent_id} not allowed for tenant {tenant_id}")
                return False
            
            agent_key = f"{tenant_id}:{agent_id}"
            agent_data = {
                **agent_info,
                "agentId": agent_id,
                "tenantId": tenant_id,
                "registeredAt": datetime.now(timezone.utc).isoformat(),
                "lastHeartbeat": datetime.now(timezone.utc).isoformat()
            }
            
            # Store in memory
            self.registered_agents[agent_key] = agent_data
            
            # Store in Redis if available
            if self.redis_client:
                await self.redis_client.hset(
                    "registered_agents",
                    agent_key,
                    json.dumps(agent_data)
                )
            
            logger.info(f"Registered agent {agent_id} for tenant {tenant_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to register agent {agent_id}: {e}")
            return False
    
    async def get_registered_agents(self, tenant_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get registered agents with optional tenant filtering"""
        try:
            agents = []
            
            # Load from Redis if available
            if self.redis_client:
                agent_data = await self.redis_client.hgetall("registered_agents")
                for agent_key, agent_json in agent_data.items():
                    agent = json.loads(agent_json)
                    if not tenant_id or agent["tenantId"] == tenant_id:
                        agents.append(agent)
            else:
                # Use in-memory storage
                for agent_key, agent in self.registered_agents.items():
                    if not tenant_id or agent["tenantId"] == tenant_id:
                        agents.append(agent)
            
            return agents
            
        except Exception as e:
            logger.error(f"Failed to get registered agents: {e}")
            return []
    
    async def update_agent_heartbeat(self, tenant_id: str, agent_id: str) -> bool:
        """Update agent heartbeat for health monitoring"""
        try:
            agent_key = f"{tenant_id}:{agent_id}"
            
            if agent_key in self.registered_agents:
                self.registered_agents[agent_key]["lastHeartbeat"] = datetime.now(timezone.utc).isoformat()
                
                # Update in Redis if available
                if self.redis_client:
                    await self.redis_client.hset(
                        "registered_agents",
                        agent_key,
                        json.dumps(self.registered_agents[agent_key])
                    )
                
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Failed to update agent heartbeat: {e}")
            return False
    
    # === UI Resource Management ===
    
    async def store_ui_resource(self, resource: Dict[str, Any]) -> bool:
        """Store UI resource with multi-tenant isolation"""
        try:
            resource_id = resource["id"]
            
            # Store in memory
            self.ui_resources[resource_id] = resource
            
            # Store in DynamoDB if available
            if self.dynamodb_table:
                # Create DynamoDB item with tenant isolation
                item = {
                    "PK": f"{resource['tenantId']}#{resource['sessionId']}",
                    "SK": resource_id,
                    "GSI1PK": resource["tenantId"],
                    "GSI1SK": f"{resource['agentId']}#{resource['createdAt']}",
                    **resource
                }
                
                # Add TTL if specified
                if resource.get("ttlSeconds"):
                    ttl_timestamp = int(
                        (datetime.now(timezone.utc) + timedelta(seconds=resource["ttlSeconds"])).timestamp()
                    )
                    item["TTL"] = ttl_timestamp
                
                self.dynamodb_table.put_item(Item=item)
            
            # Cache in Redis if available
            if self.redis_client:
                await self.redis_client.hset(
                    "ui_resources",
                    resource_id,
                    json.dumps(resource)
                )
                
                # Set TTL in Redis
                if resource.get("ttlSeconds"):
                    await self.redis_client.expire(f"ui_resources:{resource_id}", resource["ttlSeconds"])
            
            logger.debug(f"Stored UI resource {resource_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to store UI resource: {e}")
            return False
    
    async def get_ui_resources(
        self,
        tenant_id: Optional[str] = None,
        session_id: Optional[str] = None,
        agent_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get UI resources with multi-tenant filtering"""
        try:
            resources = []
            
            # Load from DynamoDB if available
            if self.dynamodb_table and tenant_id:
                if session_id:
                    # Query specific tenant and session
                    response = self.dynamodb_table.query(
                        KeyConditionExpression=boto3.dynamodb.conditions.Key('PK').eq(f"{tenant_id}#{session_id}")
                    )
                    resources = response.get('Items', [])
                else:
                    # Query all sessions for tenant using GSI
                    response = self.dynamodb_table.query(
                        IndexName='GSI1',
                        KeyConditionExpression=boto3.dynamodb.conditions.Key('GSI1PK').eq(tenant_id)
                    )
                    resources = response.get('Items', [])
            else:
                # Use in-memory storage with filtering
                for resource in self.ui_resources.values():
                    if tenant_id and resource["tenantId"] != tenant_id:
                        continue
                    if session_id and resource["sessionId"] != session_id:
                        continue
                    if agent_id and resource["agentId"] != agent_id:
                        continue
                    resources.append(resource)
            
            return resources
            
        except Exception as e:
            logger.error(f"Failed to get UI resources: {e}")
            return []
    
    async def delete_ui_resource(self, resource_id: str) -> bool:
        """Delete UI resource with cleanup"""
        try:
            # Remove from memory
            if resource_id in self.ui_resources:
                resource = self.ui_resources[resource_id]
                del self.ui_resources[resource_id]
                
                # Remove from DynamoDB if available
                if self.dynamodb_table:
                    self.dynamodb_table.delete_item(
                        Key={
                            "PK": f"{resource['tenantId']}#{resource['sessionId']}",
                            "SK": resource_id
                        }
                    )
                
                # Remove from Redis if available
                if self.redis_client:
                    await self.redis_client.hdel("ui_resources", resource_id)
                
                logger.debug(f"Deleted UI resource {resource_id}")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Failed to delete UI resource: {e}")
            return False
    
    # === Real-time Broadcasting ===
    
    async def broadcast_event(
        self,
        event_type: str,
        resource: Dict[str, Any],
        old_resource: Optional[Dict[str, Any]] = None
    ):
        """Broadcast UI event to WebSocket subscribers"""
        try:
            topic = f"ui.{resource['tenantId']}.{resource['sessionId']}"
            
            event_data = {
                "type": event_type,
                "resourceId": resource["id"],
                "tenantId": resource["tenantId"],
                "sessionId": resource["sessionId"],
                "agentId": resource["agentId"],
                "resource": resource if event_type != "delete" else None,
                "oldResource": old_resource,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            
            # Broadcast to WebSocket connections
            if topic in self.active_websockets:
                message = json.dumps(event_data)
                dead_connections = set()
                
                for websocket in self.active_websockets[topic]:
                    try:
                        await websocket.send_text(message)
                    except Exception as e:
                        logger.warning(f"Failed to send WebSocket message: {e}")
                        dead_connections.add(websocket)
                
                # Clean up dead connections
                for websocket in dead_connections:
                    self.active_websockets[topic].discard(websocket)
                
                if not self.active_websockets[topic]:
                    del self.active_websockets[topic]
            
            # Publish to Redis for horizontal scaling
            if self.redis_client:
                await self.redis_client.publish(topic, json.dumps(event_data))
            
            logger.debug(f"Broadcasted {event_type} event for resource {resource['id']}")
            
        except Exception as e:
            logger.error(f"Failed to broadcast event: {e}")
    
    def add_websocket_connection(self, topic: str, websocket):
        """Add WebSocket connection for real-time updates"""
        if topic not in self.active_websockets:
            self.active_websockets[topic] = set()
        self.active_websockets[topic].add(websocket)
    
    def remove_websocket_connection(self, topic: str, websocket):
        """Remove WebSocket connection"""
        if topic in self.active_websockets:
            self.active_websockets[topic].discard(websocket)
            if not self.active_websockets[topic]:
                del self.active_websockets[topic]
    
    # === Platform Health and Monitoring ===
    
    async def get_platform_health(self) -> Dict[str, Any]:
        """Get comprehensive platform health status"""
        try:
            # Count resources by tenant
            tenant_stats = {}
            for tenant_id in self.tenant_configs.keys():
                tenant_resources = await self.get_ui_resources(tenant_id=tenant_id)
                tenant_agents = await self.get_registered_agents(tenant_id=tenant_id)
                
                tenant_stats[tenant_id] = {
                    "resources": len(tenant_resources),
                    "agents": len(tenant_agents),
                    "websockets": sum(
                        len(ws_set) for topic, ws_set in self.active_websockets.items()
                        if topic.startswith(f"ui.{tenant_id}.")
                    )
                }
            
            return {
                "status": "healthy",
                "platform": "MCP UI Hub",
                "version": "2025-10-21",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "infrastructure": {
                    "redis_enabled": self.use_redis and self.redis_client is not None,
                    "dynamodb_enabled": self.use_dynamodb and self.dynamodb_table is not None,
                    "storage_mode": "hybrid" if (self.use_redis or self.use_dynamodb) else "memory"
                },
                "stats": {
                    "total_resources": len(self.ui_resources),
                    "registered_agents": len(self.registered_agents),
                    "active_websockets": sum(len(ws_set) for ws_set in self.active_websockets.values()),
                    "supported_tenants": list(self.tenant_configs.keys()),
                    "tenant_stats": tenant_stats
                }
            }
            
        except Exception as e:
            logger.error(f"Failed to get platform health: {e}")
            return {
                "status": "error",
                "error": str(e),
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
    
    async def cleanup_expired_resources(self):
        """Clean up expired resources (TTL handling)"""
        try:
            current_time = datetime.now(timezone.utc)
            expired_resources = []
            
            for resource_id, resource in self.ui_resources.items():
                if resource.get("ttlSeconds"):
                    created_at = datetime.fromisoformat(resource["createdAt"].replace("Z", "+00:00"))
                    expiry_time = created_at + timedelta(seconds=resource["ttlSeconds"])
                    
                    if current_time > expiry_time:
                        expired_resources.append(resource_id)
            
            # Remove expired resources
            for resource_id in expired_resources:
                await self.delete_ui_resource(resource_id)
                logger.debug(f"Cleaned up expired resource {resource_id}")
            
            if expired_resources:
                logger.info(f"Cleaned up {len(expired_resources)} expired resources")
            
        except Exception as e:
            logger.error(f"Failed to cleanup expired resources: {e}")


# Global platform service instance
_platform_service: Optional[MCPUIHubService] = None


async def get_platform_service() -> MCPUIHubService:
    """Get the global platform service instance"""
    global _platform_service
    
    if _platform_service is None:
        _platform_service = MCPUIHubService(use_redis=False, use_dynamodb=False)
        await _platform_service.initialize()
    
    return _platform_service


async def initialize_platform_service():
    """Initialize the platform service on startup"""
    await get_platform_service()


async def cleanup_platform_service():
    """Cleanup the platform service on shutdown"""
    global _platform_service
    
    if _platform_service and _platform_service.redis_client:
        await _platform_service.redis_client.close()
    
    _platform_service = None