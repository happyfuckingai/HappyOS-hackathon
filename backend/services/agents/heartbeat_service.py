"""
Agent Heartbeat Service

Provides heartbeat monitoring and health tracking for agent processes.
Agents can report their health status and the service tracks their vitals.

Requirements: 4.2
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass

from sqlalchemy.orm import Session

# Use try/except for flexible imports
try:
    from backend.modules.database import get_db, AgentProcess as DBAgentProcess
    from backend.modules.models import ResourceMetrics
except ImportError:
    from backend.modules.database.connection import get_db, AgentProcess as DBAgentProcess
    from backend.modules.models.base import ResourceMetrics

logger = logging.getLogger(__name__)


@dataclass
class HeartbeatData:
    """Heartbeat data from an agent"""
    process_id: str
    timestamp: datetime
    status: str = "healthy"
    resource_usage: Optional[Dict[str, Any]] = None
    custom_metrics: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None


class AgentHeartbeatService:
    """
    Service for managing agent heartbeats and health monitoring.
    """
    
    def __init__(self):
        self.heartbeat_timeout = 60  # seconds
        self.health_check_interval = 30  # seconds
        self.unhealthy_threshold = 3  # consecutive failed heartbeats
        self._shutdown_event = asyncio.Event()
        self._health_monitor_task: Optional[asyncio.Task] = None
        
        # In-memory tracking for performance
        self._heartbeat_cache: Dict[str, HeartbeatData] = {}
        self._consecutive_failures: Dict[str, int] = {}
        
        logger.info("AgentHeartbeatService initialized")
    
    async def report_heartbeat(self, heartbeat: HeartbeatData) -> bool:
        """
        Process a heartbeat report from an agent.
        
        Args:
            heartbeat: Heartbeat data from the agent
            
        Returns:
            bool: True if heartbeat was processed successfully
        """
        try:
            # Update in-memory cache
            self._heartbeat_cache[heartbeat.process_id] = heartbeat
            
            # Reset failure counter on successful heartbeat
            if heartbeat.status == "healthy":
                self._consecutive_failures[heartbeat.process_id] = 0
            else:
                self._consecutive_failures[heartbeat.process_id] = (
                    self._consecutive_failures.get(heartbeat.process_id, 0) + 1
                )
            
            # Update database
            db = next(get_db())
            try:
                db_process = db.query(DBAgentProcess).filter(
                    DBAgentProcess.id == heartbeat.process_id
                ).first()
                
                if not db_process:
                    logger.warning(f"Process {heartbeat.process_id} not found in database")
                    return False
                
                # Update heartbeat timestamp and resource usage
                db_process.last_heartbeat = heartbeat.timestamp
                
                if heartbeat.resource_usage:
                    db_process.resource_usage = heartbeat.resource_usage
                
                # Update status if unhealthy
                if heartbeat.status != "healthy":
                    if heartbeat.error_message:
                        db_process.error_message = heartbeat.error_message
                    
                    # Mark as failed if too many consecutive failures
                    failures = self._consecutive_failures.get(heartbeat.process_id, 0)
                    if failures >= self.unhealthy_threshold:
                        db_process.status = "failed"
                        logger.warning(
                            f"Process {heartbeat.process_id} marked as failed after "
                            f"{failures} consecutive unhealthy heartbeats"
                        )
                
                db_process.updated_at = datetime.utcnow()
                db.commit()
                
                logger.debug(f"Processed heartbeat for process {heartbeat.process_id}")
                return True
                
            finally:
                db.close()
                
        except Exception as e:
            logger.error(f"Failed to process heartbeat for {heartbeat.process_id}: {e}")
            return False
    
    async def get_agent_health(self, process_id: str) -> Optional[Dict[str, Any]]:
        """
        Get health information for a specific agent.
        
        Args:
            process_id: Process identifier
            
        Returns:
            Dict containing health information or None if not found
        """
        try:
            # Check in-memory cache first
            cached_heartbeat = self._heartbeat_cache.get(process_id)
            
            db = next(get_db())
            try:
                db_process = db.query(DBAgentProcess).filter(
                    DBAgentProcess.id == process_id
                ).first()
                
                if not db_process:
                    return None
                
                # Calculate health status
                now = datetime.utcnow()
                last_heartbeat = db_process.last_heartbeat
                
                if not last_heartbeat:
                    health_status = "unknown"
                    time_since_heartbeat = None
                else:
                    time_since_heartbeat = int((now - last_heartbeat).total_seconds())
                    
                    if time_since_heartbeat > self.heartbeat_timeout:
                        health_status = "unhealthy"
                    elif cached_heartbeat and cached_heartbeat.status != "healthy":
                        health_status = "degraded"
                    else:
                        health_status = "healthy"
                
                consecutive_failures = self._consecutive_failures.get(process_id, 0)
                
                health_info = {
                    "process_id": process_id,
                    "agent_id": db_process.agent_id,
                    "health_status": health_status,
                    "last_heartbeat": last_heartbeat,
                    "time_since_heartbeat_seconds": time_since_heartbeat,
                    "consecutive_failures": consecutive_failures,
                    "resource_usage": db_process.resource_usage,
                    "process_status": db_process.status,
                    "error_message": db_process.error_message
                }
                
                # Add cached custom metrics if available
                if cached_heartbeat and cached_heartbeat.custom_metrics:
                    health_info["custom_metrics"] = cached_heartbeat.custom_metrics
                
                return health_info
                
            finally:
                db.close()
                
        except Exception as e:
            logger.error(f"Failed to get agent health for {process_id}: {e}")
            return None
    
    async def get_all_agent_health(self) -> List[Dict[str, Any]]:
        """
        Get health information for all agents.
        
        Returns:
            List of health information dictionaries
        """
        try:
            db = next(get_db())
            try:
                db_processes = db.query(DBAgentProcess).filter(
                    DBAgentProcess.status.in_(["starting", "running", "stopping"])
                ).all()
                
                health_reports = []
                for db_process in db_processes:
                    health_info = await self.get_agent_health(db_process.id)
                    if health_info:
                        health_reports.append(health_info)
                
                return health_reports
                
            finally:
                db.close()
                
        except Exception as e:
            logger.error(f"Failed to get all agent health: {e}")
            return []
    
    async def check_stale_agents(self) -> List[str]:
        """
        Check for agents with stale heartbeats and return their process IDs.
        
        Returns:
            List of process IDs with stale heartbeats
        """
        stale_agents = []
        
        try:
            cutoff_time = datetime.utcnow() - timedelta(seconds=self.heartbeat_timeout)
            
            db = next(get_db())
            try:
                stale_processes = db.query(DBAgentProcess).filter(
                    DBAgentProcess.status == "running",
                    DBAgentProcess.last_heartbeat < cutoff_time
                ).all()
                
                for db_process in stale_processes:
                    stale_agents.append(db_process.id)
                    logger.warning(
                        f"Agent {db_process.id} has stale heartbeat "
                        f"(last: {db_process.last_heartbeat})"
                    )
                
            finally:
                db.close()
                
        except Exception as e:
            logger.error(f"Failed to check stale agents: {e}")
        
        return stale_agents
    
    async def cleanup_stale_heartbeats(self) -> int:
        """
        Clean up heartbeat data for terminated processes.
        
        Returns:
            Number of cleaned up entries
        """
        cleaned_count = 0
        
        try:
            db = next(get_db())
            try:
                # Get all process IDs from database
                active_process_ids = set(
                    row[0] for row in db.query(DBAgentProcess.id).filter(
                        DBAgentProcess.status.in_(["starting", "running", "stopping"])
                    ).all()
                )
                
                # Clean up in-memory cache
                cached_process_ids = set(self._heartbeat_cache.keys())
                stale_cached_ids = cached_process_ids - active_process_ids
                
                for process_id in stale_cached_ids:
                    del self._heartbeat_cache[process_id]
                    if process_id in self._consecutive_failures:
                        del self._consecutive_failures[process_id]
                    cleaned_count += 1
                
                if cleaned_count > 0:
                    logger.info(f"Cleaned up {cleaned_count} stale heartbeat entries")
                
            finally:
                db.close()
                
        except Exception as e:
            logger.error(f"Failed to cleanup stale heartbeats: {e}")
        
        return cleaned_count
    
    async def start_health_monitoring(self):
        """Start background health monitoring task"""
        
        if self._health_monitor_task is None or self._health_monitor_task.done():
            self._health_monitor_task = asyncio.create_task(self._health_monitor_loop())
            logger.info("Started agent health monitoring")
    
    async def stop_health_monitoring(self):
        """Stop background health monitoring task"""
        
        self._shutdown_event.set()
        
        if self._health_monitor_task and not self._health_monitor_task.done():
            self._health_monitor_task.cancel()
            try:
                await self._health_monitor_task
            except asyncio.CancelledError:
                pass
        
        logger.info("Stopped agent health monitoring")
    
    async def _health_monitor_loop(self):
        """Background health monitoring loop"""
        
        while not self._shutdown_event.is_set():
            try:
                # Check for stale agents
                stale_agents = await self.check_stale_agents()
                
                if stale_agents:
                    logger.warning(f"Found {len(stale_agents)} agents with stale heartbeats")
                
                # Cleanup stale heartbeat data
                await self.cleanup_stale_heartbeats()
                
                await asyncio.sleep(self.health_check_interval)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in health monitoring loop: {e}")
                await asyncio.sleep(10)


# Global instance
agent_heartbeat_service = AgentHeartbeatService()


async def startup_heartbeat_service():
    """Initialize the heartbeat service on startup"""
    await agent_heartbeat_service.start_health_monitoring()
    logger.info("Agent heartbeat service started")


async def shutdown_heartbeat_service():
    """Shutdown the heartbeat service"""
    await agent_heartbeat_service.stop_health_monitoring()
    logger.info("Agent heartbeat service shutdown complete")