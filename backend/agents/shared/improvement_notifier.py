"""
Agent Improvement Notification Module

Provides utilities for broadcasting and receiving improvement deployment notifications.
"""

import logging
from typing import Dict, Any, List, Optional, Callable
from datetime import datetime
import asyncio

logger = logging.getLogger(__name__)


class ImprovementNotification:
    """Represents an improvement deployment notification."""
    
    def __init__(
        self,
        improvement_id: str,
        agent_id: str,
        improvement_type: str,
        affected_components: List[str],
        deployment_time: datetime,
        change_summary: str,
        migration_guide: Optional[str] = None,
        breaking_changes: bool = False,
        metadata: Optional[Dict[str, Any]] = None
    ):
        self.improvement_id = improvement_id
        self.agent_id = agent_id
        self.improvement_type = improvement_type
        self.affected_components = affected_components
        self.deployment_time = deployment_time
        self.change_summary = change_summary
        self.migration_guide = migration_guide
        self.breaking_changes = breaking_changes
        self.metadata = metadata or {}
        self.notification_time = datetime.utcnow()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert notification to dictionary."""
        return {
            "improvement_id": self.improvement_id,
            "agent_id": self.agent_id,
            "improvement_type": self.improvement_type,
            "affected_components": self.affected_components,
            "deployment_time": self.deployment_time.isoformat(),
            "change_summary": self.change_summary,
            "migration_guide": self.migration_guide,
            "breaking_changes": self.breaking_changes,
            "metadata": self.metadata,
            "notification_time": self.notification_time.isoformat()
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ImprovementNotification":
        """Create notification from dictionary."""
        return cls(
            improvement_id=data["improvement_id"],
            agent_id=data["agent_id"],
            improvement_type=data["improvement_type"],
            affected_components=data["affected_components"],
            deployment_time=datetime.fromisoformat(data["deployment_time"]),
            change_summary=data["change_summary"],
            migration_guide=data.get("migration_guide"),
            breaking_changes=data.get("breaking_changes", False),
            metadata=data.get("metadata", {})
        )


class ImprovementNotifier:
    """
    Manages improvement deployment notifications across agents.
    """
    
    def __init__(
        self,
        agent_id: str,
        self_building_discovery=None
    ):
        """
        Initialize improvement notifier.
        
        Args:
            agent_id: Unique identifier for the agent
            self_building_discovery: Optional SelfBuildingAgentDiscovery instance
        """
        self.agent_id = agent_id
        self.self_building_discovery = self_building_discovery
        
        # Notification handlers
        self.notification_handlers: List[Callable] = []
        
        # Notification history
        self.received_notifications: List[ImprovementNotification] = []
        self.sent_notifications: List[ImprovementNotification] = []
        
        # Dependent agents
        self.dependent_agents: List[str] = []
        
        logger.info(f"Improvement notifier initialized for {agent_id}")
    
    def register_notification_handler(
        self,
        handler: Callable[[ImprovementNotification], None]
    ):
        """
        Register a handler for improvement notifications.
        
        Args:
            handler: Async function to handle notifications
        """
        self.notification_handlers.append(handler)
        logger.info(f"Registered notification handler for {self.agent_id}")
    
    def register_dependent_agent(self, agent_id: str):
        """
        Register an agent that depends on this agent.
        
        Args:
            agent_id: ID of the dependent agent
        """
        if agent_id not in self.dependent_agents:
            self.dependent_agents.append(agent_id)
            logger.info(f"Registered dependent agent: {agent_id}")
    
    async def broadcast_improvement(
        self,
        improvement_id: str,
        improvement_type: str,
        affected_components: List[str],
        change_summary: str,
        migration_guide: Optional[str] = None,
        breaking_changes: bool = False,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Broadcast an improvement deployment to dependent agents.
        
        Args:
            improvement_id: Unique identifier for the improvement
            improvement_type: Type of improvement
            affected_components: List of affected components
            change_summary: Summary of changes
            migration_guide: Optional migration guide
            breaking_changes: Whether there are breaking changes
            metadata: Additional metadata
            
        Returns:
            Broadcast result
        """
        try:
            # Create notification
            notification = ImprovementNotification(
                improvement_id=improvement_id,
                agent_id=self.agent_id,
                improvement_type=improvement_type,
                affected_components=affected_components,
                deployment_time=datetime.utcnow(),
                change_summary=change_summary,
                migration_guide=migration_guide,
                breaking_changes=breaking_changes,
                metadata=metadata
            )
            
            # Store in sent notifications
            self.sent_notifications.append(notification)
            
            # Broadcast to dependent agents
            broadcast_results = []
            
            for dependent_agent_id in self.dependent_agents:
                try:
                    result = await self._send_notification_to_agent(
                        dependent_agent_id,
                        notification
                    )
                    broadcast_results.append({
                        "agent_id": dependent_agent_id,
                        "success": result.get("success", False),
                        "message": result.get("message", "")
                    })
                except Exception as e:
                    logger.error(
                        f"Failed to send notification to {dependent_agent_id}: {e}"
                    )
                    broadcast_results.append({
                        "agent_id": dependent_agent_id,
                        "success": False,
                        "error": str(e)
                    })
            
            # Also notify self-building agent
            if self.self_building_discovery and self.self_building_discovery.is_discovered():
                try:
                    await self._notify_self_building_agent(notification)
                except Exception as e:
                    logger.warning(f"Failed to notify self-building agent: {e}")
            
            logger.info(
                f"Broadcasted improvement {improvement_id} to "
                f"{len(self.dependent_agents)} dependent agents"
            )
            
            return {
                "success": True,
                "improvement_id": improvement_id,
                "broadcast_results": broadcast_results,
                "notification_time": notification.notification_time.isoformat()
            }
            
        except Exception as e:
            logger.error(f"Failed to broadcast improvement: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def _send_notification_to_agent(
        self,
        agent_id: str,
        notification: ImprovementNotification
    ) -> Dict[str, Any]:
        """
        Send notification to a specific agent.
        
        Args:
            agent_id: Target agent ID
            notification: Notification to send
            
        Returns:
            Send result
        """
        # In a real implementation, this would use MCP or A2A protocol
        # For now, we'll simulate the notification
        logger.info(
            f"Sending improvement notification to {agent_id}: "
            f"{notification.improvement_id}"
        )
        
        return {
            "success": True,
            "message": f"Notification sent to {agent_id}",
            "agent_id": agent_id
        }
    
    async def _notify_self_building_agent(
        self,
        notification: ImprovementNotification
    ):
        """
        Notify self-building agent of improvement deployment.
        
        Args:
            notification: Notification to send
        """
        if not self.self_building_discovery:
            return
        
        # Send notification via MCP tool call
        await self.self_building_discovery.call_self_building_tool(
            tool_name="query_telemetry_insights",
            arguments={
                "metric_name": f"improvement_deployed_{notification.improvement_id}",
                "time_range_hours": 1
            }
        )
    
    async def receive_notification(
        self,
        notification_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Receive and process an improvement notification.
        
        Args:
            notification_data: Notification data dictionary
            
        Returns:
            Processing result
        """
        try:
            # Parse notification
            notification = ImprovementNotification.from_dict(notification_data)
            
            # Store in received notifications
            self.received_notifications.append(notification)
            
            logger.info(
                f"Received improvement notification from {notification.agent_id}: "
                f"{notification.improvement_id}"
            )
            
            # Log important details
            if notification.breaking_changes:
                logger.warning(
                    f"Breaking changes in improvement {notification.improvement_id}!"
                )
            
            if notification.migration_guide:
                logger.info(
                    f"Migration guide available for {notification.improvement_id}"
                )
            
            # Call registered handlers
            for handler in self.notification_handlers:
                try:
                    if asyncio.iscoroutinefunction(handler):
                        await handler(notification)
                    else:
                        handler(notification)
                except Exception as e:
                    logger.error(f"Notification handler failed: {e}")
            
            return {
                "success": True,
                "improvement_id": notification.improvement_id,
                "message": "Notification processed successfully"
            }
            
        except Exception as e:
            logger.error(f"Failed to process notification: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def get_received_notifications(
        self,
        limit: Optional[int] = None,
        agent_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get received notifications.
        
        Args:
            limit: Maximum number of notifications to return
            agent_id: Filter by source agent ID
            
        Returns:
            List of notification dictionaries
        """
        notifications = self.received_notifications
        
        # Filter by agent_id if specified
        if agent_id:
            notifications = [
                n for n in notifications
                if n.agent_id == agent_id
            ]
        
        # Sort by notification time (most recent first)
        notifications = sorted(
            notifications,
            key=lambda n: n.notification_time,
            reverse=True
        )
        
        # Apply limit
        if limit:
            notifications = notifications[:limit]
        
        return [n.to_dict() for n in notifications]
    
    def get_sent_notifications(
        self,
        limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Get sent notifications.
        
        Args:
            limit: Maximum number of notifications to return
            
        Returns:
            List of notification dictionaries
        """
        notifications = sorted(
            self.sent_notifications,
            key=lambda n: n.notification_time,
            reverse=True
        )
        
        if limit:
            notifications = notifications[:limit]
        
        return [n.to_dict() for n in notifications]
    
    def get_notification_summary(self) -> Dict[str, Any]:
        """Get summary of notifications."""
        return {
            "agent_id": self.agent_id,
            "received_count": len(self.received_notifications),
            "sent_count": len(self.sent_notifications),
            "dependent_agents": self.dependent_agents,
            "registered_handlers": len(self.notification_handlers)
        }
