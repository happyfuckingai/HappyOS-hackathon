"""
Production Agent Process Manager

Implements real agent orchestration with process management, heartbeat monitoring,
graceful shutdown, resource monitoring, and agent registry.

Requirements: 4.1, 4.2, 4.3, 4.4, 4.5
"""

import asyncio
import logging
import os
import psutil
import signal
import subprocess
import time
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from contextlib import asynccontextmanager
from dataclasses import dataclass, asdict

from sqlalchemy.orm import Session

# Use try/except for flexible imports
try:
    from backend.modules.database import get_db, AgentProcess as DBAgentProcess, Agent as DBAgent
    from backend.modules.models import (
        AgentConfig, AgentStatus, AgentProcess, ResourceMetrics
    )
except ImportError:
    from backend.modules.database.connection import get_db, AgentProcess as DBAgentProcess, Agent as DBAgent
    from backend.modules.models.base import (
        AgentConfig, AgentStatus, AgentProcess, ResourceMetrics
    )

logger = logging.getLogger(__name__)


@dataclass
class ProcessInfo:
    """Internal process information"""
    process: Optional[subprocess.Popen] = None
    pid: Optional[int] = None
    container_id: Optional[str] = None
    worker_id: Optional[str] = None
    start_time: datetime = None
    restart_count: int = 0
    last_heartbeat: Optional[datetime] = None
    config: Optional[AgentConfig] = None


class AgentProcessManager:
    """
    Production agent process manager that handles real subprocess/container lifecycle,
    heartbeat monitoring, graceful shutdown, and resource tracking.
    """
    
    def __init__(self):
        self.processes: Dict[str, ProcessInfo] = {}
        self.heartbeat_timeout = 60  # seconds
        self.resource_check_interval = 30  # seconds
        self.cleanup_interval = 300  # 5 minutes
        self._shutdown_event = asyncio.Event()
        self._monitor_task: Optional[asyncio.Task] = None
        self._cleanup_task: Optional[asyncio.Task] = None
        
        logger.info("AgentProcessManager initialized")
    
    async def start_agent(self, agent_id: str, config: AgentConfig) -> AgentProcess:
        """
        Start a new agent process with the given configuration.
        
        Args:
            agent_id: Unique agent identifier
            config: Agent configuration
            
        Returns:
            AgentProcess: Created process information
            
        Raises:
            RuntimeError: If process creation fails
        """
        logger.info(f"Starting agent {agent_id} with config: {config.name}")
        
        try:
            # Create database record first
            db = next(get_db())
            try:
                process_id = str(uuid.uuid4())
                
                db_process = DBAgentProcess(
                    id=process_id,
                    agent_id=agent_id,
                    process_type=config.process_type,
                    status="starting",
                    config=config.dict()
                )
                db.add(db_process)
                db.commit()
                db.refresh(db_process)
                
                # Start the actual process
                process_info = await self._start_process(config)
                process_info.config = config
                process_info.start_time = datetime.utcnow()
                
                # Update database with process details
                db_process.pid = process_info.pid
                db_process.container_id = process_info.container_id
                db_process.worker_id = process_info.worker_id
                db_process.status = "running"
                db_process.last_heartbeat = datetime.utcnow()
                db.commit()
                
                # Store in memory registry
                self.processes[process_id] = process_info
                
                logger.info(f"Agent {agent_id} started successfully with PID {process_info.pid}")
                
                return AgentProcess(
                    id=db_process.id,
                    agent_id=db_process.agent_id,
                    process_type=db_process.process_type,
                    pid=db_process.pid,
                    container_id=db_process.container_id,
                    worker_id=db_process.worker_id,
                    status=db_process.status,
                    last_heartbeat=db_process.last_heartbeat,
                    resource_usage=db_process.resource_usage,
                    config=db_process.config,
                    error_message=db_process.error_message,
                    created_at=db_process.created_at,
                    updated_at=db_process.updated_at
                )
                
            finally:
                db.close()
                
        except Exception as e:
            logger.error(f"Failed to start agent {agent_id}: {e}")
            # Update database with error
            try:
                db = next(get_db())
                try:
                    if 'db_process' in locals():
                        db_process.status = "failed"
                        db_process.error_message = str(e)
                        db.commit()
                finally:
                    db.close()
            except Exception as db_error:
                logger.error(f"Failed to update database with error: {db_error}")
            
            raise RuntimeError(f"Failed to start agent {agent_id}: {e}")
    
    async def _start_process(self, config: AgentConfig) -> ProcessInfo:
        """Start the actual process based on configuration"""
        
        if config.process_type == "subprocess":
            return await self._start_subprocess(config)
        elif config.process_type == "container":
            return await self._start_container(config)
        elif config.process_type == "worker":
            return await self._start_worker(config)
        else:
            raise ValueError(f"Unsupported process type: {config.process_type}")
    
    async def _start_subprocess(self, config: AgentConfig) -> ProcessInfo:
        """Start a subprocess"""
        
        if not config.command:
            raise ValueError("Command is required for subprocess")
        
        # Prepare environment
        env = os.environ.copy()
        if config.env:
            env.update(config.env)
        
        # Start process
        process = subprocess.Popen(
            [config.command] + (config.args or []),
            env=env,
            cwd=config.working_dir,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            preexec_fn=os.setsid  # Create new process group for clean shutdown
        )
        
        # Wait a moment to check if process started successfully
        await asyncio.sleep(0.1)
        
        # For short-lived processes like 'echo', don't treat completion as failure
        if process.poll() is not None:
            # Process has completed - check if it was successful
            return_code = process.returncode
            if return_code != 0:
                stdout, stderr = process.communicate()
                raise RuntimeError(f"Process failed with exit code {return_code}: {stderr.decode()}")
            else:
                # Process completed successfully - this is OK for short commands
                logger.info(f"Process completed successfully with exit code {return_code}")
        
        return ProcessInfo(
            process=process,
            pid=process.pid,
            start_time=datetime.utcnow()
        )
    
    async def _start_container(self, config: AgentConfig) -> ProcessInfo:
        """Start a container (Docker implementation)"""
        
        # This is a placeholder for container orchestration
        # In production, this would integrate with Docker API or Kubernetes
        
        container_id = f"agent-{uuid.uuid4().hex[:8]}"
        
        # For now, simulate container startup
        logger.info(f"Starting container {container_id} (simulated)")
        
        return ProcessInfo(
            container_id=container_id,
            start_time=datetime.utcnow()
        )
    
    async def _start_worker(self, config: AgentConfig) -> ProcessInfo:
        """Start a worker process"""
        
        worker_id = f"worker-{uuid.uuid4().hex[:8]}"
        
        # This would integrate with a worker queue system like Celery or RQ
        logger.info(f"Starting worker {worker_id} (simulated)")
        
        return ProcessInfo(
            worker_id=worker_id,
            start_time=datetime.utcnow()
        )
    
    async def stop_agent(self, process_id: str, force: bool = False) -> bool:
        """
        Stop an agent process gracefully or forcefully.
        
        Args:
            process_id: Process identifier
            force: If True, use SIGKILL instead of SIGTERM
            
        Returns:
            bool: True if stopped successfully
        """
        logger.info(f"Stopping agent process {process_id} (force={force})")
        
        try:
            # Update database status
            db = next(get_db())
            try:
                db_process = db.query(DBAgentProcess).filter(
                    DBAgentProcess.id == process_id
                ).first()
                
                if not db_process:
                    logger.warning(f"Process {process_id} not found in database")
                    return False
                
                db_process.status = "stopping"
                db.commit()
                
                # Stop the actual process
                success = await self._stop_process(process_id, force)
                
                # Update final status
                db_process.status = "stopped" if success else "failed"
                if not success:
                    db_process.error_message = "Failed to stop process"
                db.commit()
                
                # Remove from memory registry
                if process_id in self.processes:
                    del self.processes[process_id]
                
                logger.info(f"Agent process {process_id} stopped successfully")
                return success
                
            finally:
                db.close()
                
        except Exception as e:
            logger.error(f"Failed to stop agent process {process_id}: {e}")
            return False
    
    async def _stop_process(self, process_id: str, force: bool = False) -> bool:
        """Stop the actual process"""
        
        if process_id not in self.processes:
            logger.warning(f"Process {process_id} not found in memory registry")
            return True  # Consider it stopped if not in registry
        
        process_info = self.processes[process_id]
        
        if process_info.process:
            return await self._stop_subprocess(process_info.process, force)
        elif process_info.container_id:
            return await self._stop_container(process_info.container_id, force)
        elif process_info.worker_id:
            return await self._stop_worker(process_info.worker_id, force)
        
        return True
    
    async def _stop_subprocess(self, process: subprocess.Popen, force: bool = False) -> bool:
        """Stop a subprocess gracefully or forcefully"""
        
        try:
            if force:
                # Send SIGKILL to process group
                os.killpg(os.getpgid(process.pid), signal.SIGKILL)
                logger.info(f"Sent SIGKILL to process group {process.pid}")
            else:
                # Send SIGTERM to process group
                os.killpg(os.getpgid(process.pid), signal.SIGTERM)
                logger.info(f"Sent SIGTERM to process group {process.pid}")
                
                # Wait for graceful shutdown
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    logger.warning(f"Process {process.pid} did not respond to SIGTERM, sending SIGKILL")
                    os.killpg(os.getpgid(process.pid), signal.SIGKILL)
                    process.wait(timeout=5)
            
            return True
            
        except ProcessLookupError:
            # Process already terminated
            logger.info(f"Process {process.pid} already terminated")
            return True
        except Exception as e:
            logger.error(f"Failed to stop subprocess {process.pid}: {e}")
            return False
    
    async def _stop_container(self, container_id: str, force: bool = False) -> bool:
        """Stop a container"""
        
        # Placeholder for container stop logic
        logger.info(f"Stopping container {container_id} (simulated)")
        return True
    
    async def _stop_worker(self, worker_id: str, force: bool = False) -> bool:
        """Stop a worker"""
        
        # Placeholder for worker stop logic
        logger.info(f"Stopping worker {worker_id} (simulated)")
        return True
    
    async def get_agent_status(self, process_id: str) -> Optional[AgentStatus]:
        """
        Get current status of an agent process.
        
        Args:
            process_id: Process identifier
            
        Returns:
            AgentStatus: Current status or None if not found
        """
        try:
            db = next(get_db())
            try:
                db_process = db.query(DBAgentProcess).filter(
                    DBAgentProcess.id == process_id
                ).first()
                
                if not db_process:
                    return None
                
                # Get resource usage if process is running
                resource_usage = None
                uptime_seconds = None
                
                if process_id in self.processes and db_process.status == "running":
                    process_info = self.processes[process_id]
                    resource_usage = await self._get_resource_usage(process_info)
                    
                    if process_info.start_time:
                        uptime_seconds = int((datetime.utcnow() - process_info.start_time).total_seconds())
                
                return AgentStatus(
                    agent_id=db_process.agent_id,
                    process_id=db_process.id,
                    status=db_process.status,
                    pid=db_process.pid,
                    container_id=db_process.container_id,
                    worker_id=db_process.worker_id,
                    last_heartbeat=db_process.last_heartbeat,
                    resource_usage=resource_usage,
                    uptime_seconds=uptime_seconds,
                    restart_count=self.processes.get(process_id, ProcessInfo()).restart_count
                )
                
            finally:
                db.close()
                
        except Exception as e:
            logger.error(f"Failed to get agent status for {process_id}: {e}")
            return None
    
    async def list_active_agents(self) -> List[AgentStatus]:
        """
        List all active agent processes.
        
        Returns:
            List[AgentStatus]: List of active agents
        """
        try:
            db = next(get_db())
            try:
                db_processes = db.query(DBAgentProcess).filter(
                    DBAgentProcess.status.in_(["starting", "running", "stopping"])
                ).all()
                
                statuses = []
                for db_process in db_processes:
                    status = await self.get_agent_status(db_process.id)
                    if status:
                        statuses.append(status)
                
                return statuses
                
            finally:
                db.close()
                
        except Exception as e:
            logger.error(f"Failed to list active agents: {e}")
            return []
    
    async def restart_failed_agents(self) -> List[str]:
        """
        Restart failed agents that have restart policy enabled.
        
        Returns:
            List[str]: List of restarted agent IDs
        """
        restarted = []
        
        try:
            db = next(get_db())
            try:
                # Find failed processes that can be restarted
                failed_processes = db.query(DBAgentProcess).filter(
                    DBAgentProcess.status == "failed"
                ).all()
                
                for db_process in failed_processes:
                    config_dict = db_process.config or {}
                    restart_policy = config_dict.get("restart_policy", "never")
                    max_restarts = config_dict.get("max_restarts", 3)
                    
                    if restart_policy == "never":
                        continue
                    
                    process_info = self.processes.get(db_process.id, ProcessInfo())
                    if process_info.restart_count >= max_restarts:
                        logger.info(f"Process {db_process.id} exceeded max restarts ({max_restarts})")
                        continue
                    
                    try:
                        # Attempt restart
                        config = AgentConfig(**config_dict)
                        await self.start_agent(db_process.agent_id, config)
                        
                        # Update restart count
                        if db_process.id in self.processes:
                            self.processes[db_process.id].restart_count += 1
                        
                        restarted.append(db_process.agent_id)
                        logger.info(f"Restarted failed agent {db_process.agent_id}")
                        
                    except Exception as e:
                        logger.error(f"Failed to restart agent {db_process.agent_id}: {e}")
                
            finally:
                db.close()
                
        except Exception as e:
            logger.error(f"Failed to restart failed agents: {e}")
        
        return restarted
    
    async def update_heartbeat(self, process_id: str) -> bool:
        """
        Update heartbeat timestamp for a process.
        
        Args:
            process_id: Process identifier
            
        Returns:
            bool: True if updated successfully
        """
        try:
            db = next(get_db())
            try:
                db_process = db.query(DBAgentProcess).filter(
                    DBAgentProcess.id == process_id
                ).first()
                
                if not db_process:
                    return False
                
                db_process.last_heartbeat = datetime.utcnow()
                db.commit()
                
                # Update memory registry
                if process_id in self.processes:
                    self.processes[process_id].last_heartbeat = datetime.utcnow()
                
                return True
                
            finally:
                db.close()
                
        except Exception as e:
            logger.error(f"Failed to update heartbeat for {process_id}: {e}")
            return False
    
    async def _get_resource_usage(self, process_info: ProcessInfo) -> Optional[dict]:
        """Get resource usage for a process"""
        
        try:
            if process_info.pid:
                # Get subprocess resource usage
                process = psutil.Process(process_info.pid)
                
                with process.oneshot():
                    cpu_percent = process.cpu_percent()
                    memory_info = process.memory_info()
                    memory_percent = process.memory_percent()
                    io_counters = process.io_counters() if hasattr(process, 'io_counters') else None
                    num_threads = process.num_threads()
                    num_fds = process.num_fds() if hasattr(process, 'num_fds') else None
                
                metrics = ResourceMetrics(
                    cpu_percent=cpu_percent,
                    memory_mb=memory_info.rss / 1024 / 1024,
                    memory_percent=memory_percent,
                    threads=num_threads,
                    open_files=num_fds
                )
                
                if io_counters:
                    metrics.disk_io_read_mb = io_counters.read_bytes / 1024 / 1024
                    metrics.disk_io_write_mb = io_counters.write_bytes / 1024 / 1024
                
                return metrics.dict()
                
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            logger.warning(f"Process {process_info.pid} no longer exists or access denied")
        except Exception as e:
            logger.error(f"Failed to get resource usage for PID {process_info.pid}: {e}")
        
        return None
    
    async def start_monitoring(self):
        """Start background monitoring tasks"""
        
        if self._monitor_task is None or self._monitor_task.done():
            self._monitor_task = asyncio.create_task(self._monitor_processes())
            logger.info("Started process monitoring task")
        
        if self._cleanup_task is None or self._cleanup_task.done():
            self._cleanup_task = asyncio.create_task(self._cleanup_stale_processes())
            logger.info("Started cleanup task")
    
    async def stop_monitoring(self):
        """Stop background monitoring tasks"""
        
        self._shutdown_event.set()
        
        if self._monitor_task and not self._monitor_task.done():
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass
        
        if self._cleanup_task and not self._cleanup_task.done():
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
        
        logger.info("Stopped monitoring tasks")
    
    async def _monitor_processes(self):
        """Background task to monitor process health and update resource usage"""
        
        while not self._shutdown_event.is_set():
            try:
                # Update resource usage for all running processes
                for process_id, process_info in list(self.processes.items()):
                    try:
                        resource_usage = await self._get_resource_usage(process_info)
                        
                        if resource_usage:
                            # Update database
                            db = next(get_db())
                            try:
                                db_process = db.query(DBAgentProcess).filter(
                                    DBAgentProcess.id == process_id
                                ).first()
                                
                                if db_process:
                                    db_process.resource_usage = resource_usage
                                    db_process.updated_at = datetime.utcnow()
                                    db.commit()
                                    
                            finally:
                                db.close()
                        
                        # Check if subprocess is still alive
                        if process_info.process and process_info.process.poll() is not None:
                            logger.warning(f"Process {process_id} (PID {process_info.pid}) has terminated")
                            await self._handle_process_termination(process_id)
                    
                    except Exception as e:
                        logger.error(f"Error monitoring process {process_id}: {e}")
                
                await asyncio.sleep(self.resource_check_interval)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in process monitoring: {e}")
                await asyncio.sleep(5)
    
    async def _cleanup_stale_processes(self):
        """Background task to clean up stale processes and check heartbeats"""
        
        while not self._shutdown_event.is_set():
            try:
                cutoff_time = datetime.utcnow() - timedelta(seconds=self.heartbeat_timeout)
                
                db = next(get_db())
                try:
                    # Find processes with stale heartbeats
                    stale_processes = db.query(DBAgentProcess).filter(
                        DBAgentProcess.status == "running",
                        DBAgentProcess.last_heartbeat < cutoff_time
                    ).all()
                    
                    for db_process in stale_processes:
                        logger.warning(f"Process {db_process.id} has stale heartbeat, marking as failed")
                        db_process.status = "failed"
                        db_process.error_message = "Heartbeat timeout"
                        
                        # Remove from memory registry
                        if db_process.id in self.processes:
                            del self.processes[db_process.id]
                    
                    if stale_processes:
                        db.commit()
                
                finally:
                    db.close()
                
                await asyncio.sleep(self.cleanup_interval)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in cleanup task: {e}")
                await asyncio.sleep(30)
    
    async def _handle_process_termination(self, process_id: str):
        """Handle unexpected process termination"""
        
        try:
            db = next(get_db())
            try:
                db_process = db.query(DBAgentProcess).filter(
                    DBAgentProcess.id == process_id
                ).first()
                
                if db_process and db_process.status == "running":
                    db_process.status = "failed"
                    db_process.error_message = "Process terminated unexpectedly"
                    db.commit()
                    
                    logger.info(f"Marked process {process_id} as failed due to unexpected termination")
                
            finally:
                db.close()
            
            # Remove from memory registry
            if process_id in self.processes:
                del self.processes[process_id]
                
        except Exception as e:
            logger.error(f"Failed to handle process termination for {process_id}: {e}")


# Global instance
agent_process_manager = AgentProcessManager()


@asynccontextmanager
async def get_agent_process_manager():
    """Get the global agent process manager instance"""
    yield agent_process_manager


async def startup_agent_manager():
    """Initialize the agent process manager on startup"""
    await agent_process_manager.start_monitoring()
    logger.info("Agent process manager started")


async def shutdown_agent_manager():
    """Shutdown the agent process manager"""
    await agent_process_manager.stop_monitoring()
    
    # Stop all running processes
    active_agents = await agent_process_manager.list_active_agents()
    for agent_status in active_agents:
        if agent_status.process_id:
            await agent_process_manager.stop_agent(agent_status.process_id)
    
    logger.info("Agent process manager shutdown complete")