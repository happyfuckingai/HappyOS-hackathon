"""
WebSocket System Initialization

Initializes and coordinates all WebSocket-related services:
- WebSocket connection manager
- Event broadcaster
- Hydration service
- Resource provider integration
- AWS Lambda agent integration
- Agent Core gateway routing

Requirements: 3.1, 3.2, 3.3, 7.1, 7.3
"""

import asyncio
import logging
from typing import List, Optional, Callable

from ..modules.models.ui_resource import UIResource
from ..services.observability import get_logger
from .websocket_manager import websocket_manager
from .performance.websocket_scaling import create_scalable_websocket_manager
from .event_broadcaster import initialize_event_broadcaster, get_event_broadcaster
from .hydration_service import initialize_hydration_service, get_hydration_service

logger = get_logger(__name__)


class WebSocketSystem:
    """
    Coordinated WebSocket system manager
    
    Manages the lifecycle of all WebSocket-related services and ensures
    proper initialization order and cleanup. Supports both standard and
    scalable WebSocket managers for concurrent demo support, with AWS
    Lambda agent integration and Agent Core gateway routing.
    """
    
    def __init__(self, 
                 use_scalable_manager: bool = True, 
                 max_connections: int = 1000,
                 enable_aws_integration: bool = True):
        self.initialized = False
        self.started = False
        self.resource_provider: Optional[Callable[[str, str], List[UIResource]]] = None
        self.use_scalable_manager = use_scalable_manager
        self.max_connections = max_connections
        self.enable_aws_integration = enable_aws_integration
        self.active_manager = None
        self.aws_manager = None
    
    def set_resource_provider(self, provider: Callable[[str, str], List[UIResource]]):
        """Set the resource provider function for hydration"""
        self.resource_provider = provider
        
        # Set provider on active manager
        if self.active_manager:
            self.active_manager.resource_provider = provider
        else:
            websocket_manager.resource_provider = provider
        
        logger.info("Resource provider configured for WebSocket system")
    
    async def initialize(self):
        """Initialize all WebSocket services"""
        if self.initialized:
            logger.warning("WebSocket system already initialized")
            return
        
        try:
            # Choose WebSocket manager based on configuration
            if self.use_scalable_manager:
                logger.info(f"Initializing scalable WebSocket manager (max_connections: {self.max_connections})")
                self.active_manager = create_scalable_websocket_manager(
                    resource_provider=self.resource_provider,
                    max_connections=self.max_connections,
                    max_per_tenant=min(200, self.max_connections // 3)  # Distribute across 3+ tenants
                )
            else:
                logger.info("Using standard WebSocket manager")
                self.active_manager = websocket_manager
                if self.resource_provider:
                    self.active_manager.resource_provider = self.resource_provider
            
            # Initialize AWS integration if enabled
            if self.enable_aws_integration:
                try:
                    from .websocket_aws_integration import get_aws_websocket_manager, AWSWebSocketConfig
                    
                    aws_config = AWSWebSocketConfig(
                        enable_lambda_agents=True,
                        enable_agent_gateway=True,
                        enable_backward_compatibility=True
                    )
                    
                    self.aws_manager = await get_aws_websocket_manager(
                        base_manager=self.active_manager,
                        config=aws_config
                    )
                    
                    logger.info("AWS WebSocket integration initialized")
                    
                except Exception as e:
                    logger.warning(f"AWS integration failed, continuing without: {e}")
                    self.aws_manager = None
            
            # Initialize event broadcaster with active manager
            event_broadcaster = initialize_event_broadcaster(self.active_manager)
            logger.info("Event broadcaster initialized")
            
            # Initialize hydration service with resource provider
            if not self.resource_provider:
                logger.warning("No resource provider set, using default empty provider")
                self.resource_provider = lambda tenant_id, session_id: []
            
            hydration_service = initialize_hydration_service(self.resource_provider)
            logger.info("Hydration service initialized")
            
            self.initialized = True
            integration_type = "AWS-enhanced" if self.aws_manager else "standard"
            manager_type = "scalable" if self.use_scalable_manager else "standard"
            logger.info(f"WebSocket system initialized successfully ({integration_type} {manager_type} manager)")
            
        except Exception as e:
            logger.error(f"Failed to initialize WebSocket system: {e}")
            raise
    
    async def start(self):
        """Start all WebSocket services"""
        if not self.initialized:
            await self.initialize()
        
        if self.started:
            logger.warning("WebSocket system already started")
            return
        
        try:
            # Start active WebSocket manager
            await self.active_manager.start()
            
            # AWS manager is already started during initialization
            # No additional start needed for AWS integration
            
            # Start event broadcaster
            event_broadcaster = get_event_broadcaster()
            await event_broadcaster.start()
            
            # Start hydration service
            hydration_service = get_hydration_service()
            await hydration_service.start()
            
            self.started = True
            logger.info("WebSocket system started successfully")
            
        except Exception as e:
            logger.error(f"Failed to start WebSocket system: {e}")
            raise
    
    async def stop(self):
        """Stop all WebSocket services"""
        if not self.started:
            logger.warning("WebSocket system not started")
            return
        
        try:
            # Stop services in reverse order
            hydration_service = get_hydration_service()
            await hydration_service.stop()
            
            event_broadcaster = get_event_broadcaster()
            await event_broadcaster.stop()
            
            # Stop AWS integration if active
            if self.aws_manager:
                await self.aws_manager.cleanup()
            
            await self.active_manager.stop()
            
            self.started = False
            logger.info("WebSocket system stopped successfully")
            
        except Exception as e:
            logger.error(f"Failed to stop WebSocket system: {e}")
            raise
    
    def get_statistics(self) -> dict:
        """Get comprehensive statistics from all services"""
        if not self.initialized:
            return {"error": "WebSocket system not initialized"}
        
        try:
            # Get stats from active manager
            if hasattr(self.active_manager, 'get_scaling_stats'):
                manager_stats = self.active_manager.get_scaling_stats()
            else:
                manager_stats = self.active_manager.get_connection_stats()
            
            stats = {
                "websocket_manager": manager_stats,
                "event_broadcaster": get_event_broadcaster().get_statistics(),
                "hydration_service": get_hydration_service().get_statistics(),
                "system_status": {
                    "initialized": self.initialized,
                    "started": self.started,
                    "manager_type": "scalable" if self.use_scalable_manager else "standard",
                    "max_connections": self.max_connections if self.use_scalable_manager else "unlimited",
                    "aws_integration_enabled": self.aws_manager is not None
                }
            }
            
            # Add AWS integration stats if available
            if self.aws_manager:
                try:
                    aws_stats = await self.aws_manager.get_health_status()
                    stats["aws_integration"] = aws_stats
                except Exception as e:
                    stats["aws_integration"] = {"error": str(e)}
            
            return stats
            
        except Exception as e:
            logger.error(f"Failed to get WebSocket system statistics: {e}")
            return {"error": str(e)}


# Global WebSocket system instance (using scalable manager by default for concurrent demo support)
websocket_system = WebSocketSystem(
    use_scalable_manager=True, 
    max_connections=1000,
    enable_aws_integration=True
)


# Convenience functions for external use

async def initialize_websocket_system(resource_provider: Optional[Callable[[str, str], List[UIResource]]] = None):
    """Initialize the WebSocket system with optional resource provider"""
    if resource_provider:
        websocket_system.set_resource_provider(resource_provider)
    await websocket_system.initialize()


async def start_websocket_system():
    """Start the WebSocket system"""
    await websocket_system.start()


async def stop_websocket_system():
    """Stop the WebSocket system"""
    await websocket_system.stop()


def get_websocket_system() -> WebSocketSystem:
    """Get the global WebSocket system instance"""
    return websocket_system


# Resource provider factory for MCP UI routes integration

def create_ui_resource_provider(ui_resources_dict: dict) -> Callable[[str, str], List[UIResource]]:
    """
    Create a resource provider function from the UI resources dictionary
    
    Args:
        ui_resources_dict: Dictionary of UI resources (resource_id -> UIResource)
        
    Returns:
        Resource provider function for hydration
    """
    def resource_provider(tenant_id: str, session_id: str) -> List[UIResource]:
        """Get resources for a specific tenant and session"""
        matching_resources = []
        
        for resource in ui_resources_dict.values():
            if resource.tenantId == tenant_id and resource.sessionId == session_id:
                # Skip expired resources unless explicitly requested
                if not resource.is_expired():
                    matching_resources.append(resource)
        
        # Sort by creation time (newest first)
        matching_resources.sort(key=lambda r: r.createdAt, reverse=True)
        
        return matching_resources
    
    return resource_provider


# Integration helper for startup coordination

async def setup_websocket_system_for_mcp_ui(ui_resources_dict: dict):
    """
    Set up the WebSocket system for MCP UI routes integration
    
    Args:
        ui_resources_dict: The ui_resources dictionary from mcp_ui_routes
    """
    try:
        # Create resource provider
        resource_provider = create_ui_resource_provider(ui_resources_dict)
        
        # Initialize and start the system
        await initialize_websocket_system(resource_provider)
        await start_websocket_system()
        
        logger.info("WebSocket system set up for MCP UI integration")
        
    except Exception as e:
        logger.error(f"Failed to set up WebSocket system for MCP UI: {e}")
        raise


# Health check integration

async def register_lambda_agent(agent_name: str, function_name: str, function_arn: str, **kwargs) -> bool:
    """Register a Lambda-deployed agent with the WebSocket system"""
    try:
        if websocket_system.aws_manager:
            return await websocket_system.aws_manager.register_lambda_agent(
                agent_name, function_name, function_arn, **kwargs
            )
        else:
            logger.warning("AWS integration not available for Lambda agent registration")
            return False
    except Exception as e:
        logger.error(f"Failed to register Lambda agent {agent_name}: {e}")
        return False


async def register_gateway_agent(agent_name: str, agent_config: dict) -> bool:
    """Register an agent with the Agent Core Gateway"""
    try:
        if websocket_system.aws_manager:
            return await websocket_system.aws_manager.register_gateway_agent(
                agent_name, agent_config
            )
        else:
            logger.warning("AWS integration not available for gateway agent registration")
            return False
    except Exception as e:
        logger.error(f"Failed to register gateway agent {agent_name}: {e}")
        return False


def get_aws_websocket_manager():
    """Get the AWS WebSocket manager if available"""
    return websocket_system.aws_manager


def websocket_system_health_check() -> dict:
    """Health check for the WebSocket system"""
    try:
        stats = websocket_system.get_statistics()
        
        # Determine health status
        is_healthy = (
            websocket_system.initialized and 
            websocket_system.started and
            "error" not in stats
        )
        
        return {
            "status": "healthy" if is_healthy else "unhealthy",
            "initialized": websocket_system.initialized,
            "started": websocket_system.started,
            "statistics": stats
        }
        
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e),
            "initialized": websocket_system.initialized,
            "started": websocket_system.started
        }