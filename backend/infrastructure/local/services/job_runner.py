"""
Local job runner service as fallback for AWS Lambda.
Provides task queue, execution engine, and job scheduling with retry mechanisms.
"""

import asyncio
import json
import logging
import time
import traceback
from typing import Any, Dict, List, Optional, Callable, Union
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict, field
from pathlib import Path
from enum import Enum
import threading
import uuid
import importlib
import sys
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor

from ....core.interfaces import ComputeService
from ....core.settings import get_settings


logger = logging.getLogger(__name__)


class JobStatus(Enum):
    """Job execution status."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    RETRYING = "retrying"


class JobPriority(Enum):
    """Job priority levels."""
    LOW = 1
    NORMAL = 2
    HIGH = 3
    CRITICAL = 4


@dataclass
class JobResult:
    """Result of job execution."""
    job_id: str
    status: JobStatus
    result: Optional[Any] = None
    error: Optional[str] = None
    execution_time_ms: Optional[float] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    retry_count: int = 0
    logs: List[str] = field(default_factory=list)


@dataclass
class JobConfig:
    """Configuration for job execution."""
    job_id: str
    tenant_id: str
    function_name: str
    payload: Dict[str, Any]
    priority: JobPriority = JobPriority.NORMAL
    timeout_seconds: int = 300
    max_retries: int = 3
    retry_delay_seconds: int = 5
    async_mode: bool = False
    created_at: datetime = field(default_factory=datetime.now)
    scheduled_at: Optional[datetime] = None
    
    def should_retry(self, current_retry_count: int) -> bool:
        """Check if job should be retried."""
        return current_retry_count < self.max_retries


class JobQueue:
    """Priority queue for job management."""
    
    def __init__(self):
        self.queues = {
            JobPriority.CRITICAL: asyncio.Queue(),
            JobPriority.HIGH: asyncio.Queue(),
            JobPriority.NORMAL: asyncio.Queue(),
            JobPriority.LOW: asyncio.Queue()
        }
        self._lock = asyncio.Lock()
    
    async def put(self, job_config: JobConfig):
        """Add job to appropriate priority queue."""
        await self.queues[job_config.priority].put(job_config)
    
    async def get(self) -> JobConfig:
        """Get next job from highest priority queue."""
        # Check queues in priority order
        for priority in [JobPriority.CRITICAL, JobPriority.HIGH, JobPriority.NORMAL, JobPriority.LOW]:
            try:
                return self.queues[priority].get_nowait()
            except asyncio.QueueEmpty:
                continue
        
        # If no jobs available, wait for any job
        tasks = [
            asyncio.create_task(queue.get())
            for queue in self.queues.values()
        ]
        
        done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        
        # Cancel pending tasks
        for task in pending:
            task.cancel()
        
        # Return the first completed job
        return done.pop().result()
    
    def qsize(self) -> Dict[JobPriority, int]:
        """Get queue sizes for each priority."""
        return {priority: queue.qsize() for priority, queue in self.queues.items()}


class FunctionRegistry:
    """Registry for available functions that can be executed."""
    
    def __init__(self):
        self.functions: Dict[str, Callable] = {}
        self.function_metadata: Dict[str, Dict[str, Any]] = {}
    
    def register_function(self, name: str, func: Callable, metadata: Dict[str, Any] = None):
        """Register a function for execution."""
        self.functions[name] = func
        self.function_metadata[name] = metadata or {}
        logger.info(f"Registered function: {name}")
    
    def unregister_function(self, name: str):
        """Unregister a function."""
        if name in self.functions:
            del self.functions[name]
            del self.function_metadata[name]
            logger.info(f"Unregistered function: {name}")
    
    def get_function(self, name: str) -> Optional[Callable]:
        """Get a registered function."""
        return self.functions.get(name)
    
    def list_functions(self) -> List[str]:
        """List all registered functions."""
        return list(self.functions.keys())
    
    def get_function_metadata(self, name: str) -> Dict[str, Any]:
        """Get metadata for a function."""
        return self.function_metadata.get(name, {})


class LocalJobRunner(ComputeService):
    """
    Local job runner that provides Lambda-like functionality.
    Supports async/sync execution, retry logic, and job scheduling.
    """
    
    def __init__(self):
        self.settings = get_settings()
        
        # Job management
        self.job_queue = JobQueue()
        self.active_jobs: Dict[str, JobConfig] = {}
        self.job_results: Dict[str, JobResult] = {}
        self.function_registry = FunctionRegistry()
        
        # Execution configuration
        self.max_concurrent_jobs = self.settings.local.max_concurrent_jobs
        self.worker_semaphore = asyncio.Semaphore(self.max_concurrent_jobs)
        
        # Thread pools for sync function execution
        self.thread_pool = ThreadPoolExecutor(max_workers=self.max_concurrent_jobs)
        self.process_pool = ProcessPoolExecutor(max_workers=max(1, self.max_concurrent_jobs // 2))
        
        # Storage
        self.data_directory = Path(self.settings.local.data_directory)
        self.data_directory.mkdir(parents=True, exist_ok=True)
        self.jobs_file = self.data_directory / "job_results.json"
        
        # Background tasks
        self.worker_tasks: List[asyncio.Task] = []
        self.scheduler_task: Optional[asyncio.Task] = None
        self.cleanup_task: Optional[asyncio.Task] = None
        
        # Thread safety
        self._lock = threading.RLock()
        
        # Load persisted data
        self._load_persisted_data()
        
        # Register built-in functions
        self._register_builtin_functions()
        
        # Start background tasks
        asyncio.create_task(self._start_background_tasks())
        
        logger.info("Local job runner initialized")
    
    async def _start_background_tasks(self):
        """Start background worker and scheduler tasks."""
        # Start worker tasks
        for i in range(self.max_concurrent_jobs):
            task = asyncio.create_task(self._worker_loop(f"worker-{i}"))
            self.worker_tasks.append(task)
        
        # Start scheduler and cleanup tasks
        self.scheduler_task = asyncio.create_task(self._scheduler_loop())
        self.cleanup_task = asyncio.create_task(self._cleanup_loop())
        
        logger.info(f"Started {len(self.worker_tasks)} worker tasks")
    
    def _register_builtin_functions(self):
        """Register built-in functions."""
        # Echo function for testing
        def echo(payload: Dict[str, Any]) -> Dict[str, Any]:
            return {"echo": payload, "timestamp": datetime.now().isoformat()}
        
        # Health check function
        def health_check(payload: Dict[str, Any]) -> Dict[str, Any]:
            return {
                "status": "healthy",
                "timestamp": datetime.now().isoformat(),
                "worker_info": {
                    "max_concurrent_jobs": self.max_concurrent_jobs,
                    "active_jobs": len(self.active_jobs),
                    "queue_sizes": self.job_queue.qsize()
                }
            }
        
        # Sleep function for testing
        def sleep_test(payload: Dict[str, Any]) -> Dict[str, Any]:
            import time
            sleep_time = payload.get("sleep_seconds", 1)
            time.sleep(sleep_time)
            return {"slept_for": sleep_time, "timestamp": datetime.now().isoformat()}
        
        self.function_registry.register_function("echo", echo, {"description": "Echo input payload"})
        self.function_registry.register_function("health_check", health_check, {"description": "Health check"})
        self.function_registry.register_function("sleep_test", sleep_test, {"description": "Sleep test function"})
    
    async def invoke_function(self, function_name: str, payload: Dict[str, Any], 
                             tenant_id: str, async_mode: bool = False) -> Dict[str, Any]:
        """Invoke a compute function."""
        try:
            # Create job configuration
            job_config = JobConfig(
                job_id=str(uuid.uuid4()),
                tenant_id=tenant_id,
                function_name=function_name,
                payload=payload,
                async_mode=async_mode,
                timeout_seconds=payload.get("timeout", 300),
                max_retries=payload.get("max_retries", 3)
            )
            
            if async_mode:
                # Queue job for async execution
                await self.job_queue.put(job_config)
                
                return {
                    "job_id": job_config.job_id,
                    "status": "queued",
                    "async": True
                }
            else:
                # Execute job synchronously
                result = await self._execute_job(job_config)
                
                if result.status == JobStatus.COMPLETED:
                    return result.result
                else:
                    raise Exception(f"Job failed: {result.error}")
                    
        except Exception as e:
            logger.error(f"Error invoking function {function_name}: {e}")
            raise
    
    async def schedule_job(self, job_config: Dict[str, Any], tenant_id: str) -> str:
        """Schedule a job for execution."""
        try:
            # Parse job configuration
            config = JobConfig(
                job_id=str(uuid.uuid4()),
                tenant_id=tenant_id,
                function_name=job_config["function_name"],
                payload=job_config.get("payload", {}),
                priority=JobPriority(job_config.get("priority", JobPriority.NORMAL.value)),
                timeout_seconds=job_config.get("timeout_seconds", 300),
                max_retries=job_config.get("max_retries", 3),
                async_mode=True
            )
            
            # Handle scheduled execution
            if "scheduled_at" in job_config:
                if isinstance(job_config["scheduled_at"], str):
                    config.scheduled_at = datetime.fromisoformat(job_config["scheduled_at"])
                else:
                    config.scheduled_at = job_config["scheduled_at"]
            
            # Queue the job
            await self.job_queue.put(config)
            
            logger.info(f"Scheduled job {config.job_id} for function {config.function_name}")
            return config.job_id
            
        except Exception as e:
            logger.error(f"Error scheduling job: {e}")
            raise
    
    async def get_job_status(self, job_id: str, tenant_id: str) -> Dict[str, Any]:
        """Get job execution status."""
        try:
            with self._lock:
                # Check active jobs
                if job_id in self.active_jobs:
                    job_config = self.active_jobs[job_id]
                    if job_config.tenant_id != tenant_id:
                        raise ValueError("Job not found or access denied")
                    
                    return {
                        "job_id": job_id,
                        "status": JobStatus.RUNNING.value,
                        "function_name": job_config.function_name,
                        "created_at": job_config.created_at.isoformat(),
                        "tenant_id": tenant_id
                    }
                
                # Check completed jobs
                if job_id in self.job_results:
                    result = self.job_results[job_id]
                    
                    return {
                        "job_id": job_id,
                        "status": result.status.value,
                        "result": result.result,
                        "error": result.error,
                        "execution_time_ms": result.execution_time_ms,
                        "started_at": result.started_at.isoformat() if result.started_at else None,
                        "completed_at": result.completed_at.isoformat() if result.completed_at else None,
                        "retry_count": result.retry_count,
                        "logs": result.logs
                    }
                
                return {"job_id": job_id, "status": "not_found"}
                
        except Exception as e:
            logger.error(f"Error getting job status for {job_id}: {e}")
            raise
    
    async def _worker_loop(self, worker_name: str):
        """Main worker loop for processing jobs."""
        logger.info(f"Started worker: {worker_name}")
        
        while True:
            try:
                # Get next job from queue
                job_config = await self.job_queue.get()
                
                # Check if job is scheduled for future execution
                if job_config.scheduled_at and job_config.scheduled_at > datetime.now():
                    # Put job back in queue for later
                    await asyncio.sleep(1)
                    await self.job_queue.put(job_config)
                    continue
                
                # Acquire semaphore for concurrent job limit
                async with self.worker_semaphore:
                    # Execute the job
                    await self._execute_job(job_config)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in worker {worker_name}: {e}")
                await asyncio.sleep(1)
        
        logger.info(f"Worker {worker_name} stopped")
    
    async def _execute_job(self, job_config: JobConfig) -> JobResult:
        """Execute a single job."""
        job_id = job_config.job_id
        start_time = time.time()
        
        # Create job result
        result = JobResult(
            job_id=job_id,
            status=JobStatus.RUNNING,
            started_at=datetime.now()
        )
        
        try:
            # Mark job as active
            with self._lock:
                self.active_jobs[job_id] = job_config
                self.job_results[job_id] = result
            
            logger.info(f"Executing job {job_id}: {job_config.function_name}")
            
            # Get function
            func = self.function_registry.get_function(job_config.function_name)
            if not func:
                raise ValueError(f"Function not found: {job_config.function_name}")
            
            # Execute function with timeout
            try:
                if asyncio.iscoroutinefunction(func):
                    # Async function
                    job_result = await asyncio.wait_for(
                        func(job_config.payload),
                        timeout=job_config.timeout_seconds
                    )
                else:
                    # Sync function - run in thread pool
                    loop = asyncio.get_event_loop()
                    job_result = await asyncio.wait_for(
                        loop.run_in_executor(self.thread_pool, func, job_config.payload),
                        timeout=job_config.timeout_seconds
                    )
                
                # Job completed successfully
                result.status = JobStatus.COMPLETED
                result.result = job_result
                result.completed_at = datetime.now()
                result.execution_time_ms = (time.time() - start_time) * 1000
                
                logger.info(f"Job {job_id} completed successfully in {result.execution_time_ms:.2f}ms")
                
            except asyncio.TimeoutError:
                raise Exception(f"Job timed out after {job_config.timeout_seconds} seconds")
            except Exception as e:
                # Job failed, check if we should retry
                if job_config.should_retry(result.retry_count):
                    result.status = JobStatus.RETRYING
                    result.retry_count += 1
                    result.error = str(e)
                    result.logs.append(f"Retry {result.retry_count}: {str(e)}")
                    
                    logger.warning(f"Job {job_id} failed, retrying ({result.retry_count}/{job_config.max_retries}): {e}")
                    
                    # Schedule retry
                    await asyncio.sleep(job_config.retry_delay_seconds)
                    await self.job_queue.put(job_config)
                    
                    return result
                else:
                    raise
        
        except Exception as e:
            # Job failed permanently
            result.status = JobStatus.FAILED
            result.error = str(e)
            result.completed_at = datetime.now()
            result.execution_time_ms = (time.time() - start_time) * 1000
            result.logs.append(f"Failed: {str(e)}")
            result.logs.append(traceback.format_exc())
            
            logger.error(f"Job {job_id} failed permanently: {e}")
        
        finally:
            # Remove from active jobs
            with self._lock:
                if job_id in self.active_jobs:
                    del self.active_jobs[job_id]
                
                # Update result
                self.job_results[job_id] = result
        
        return result
    
    async def _scheduler_loop(self):
        """Background scheduler for handling scheduled jobs."""
        while True:
            try:
                await asyncio.sleep(10)  # Check every 10 seconds
                # Scheduler logic would go here for more complex scheduling
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in scheduler loop: {e}")
    
    async def _cleanup_loop(self):
        """Background cleanup for old job results."""
        while True:
            try:
                await asyncio.sleep(3600)  # Run every hour
                
                # Clean up old job results (older than 24 hours)
                cutoff_time = datetime.now() - timedelta(hours=24)
                
                with self._lock:
                    old_jobs = []
                    for job_id, result in self.job_results.items():
                        if (result.completed_at and result.completed_at < cutoff_time):
                            old_jobs.append(job_id)
                    
                    for job_id in old_jobs:
                        del self.job_results[job_id]
                    
                    if old_jobs:
                        logger.info(f"Cleaned up {len(old_jobs)} old job results")
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in cleanup loop: {e}")
    
    def _load_persisted_data(self):
        """Load persisted job results from disk."""
        try:
            if self.jobs_file.exists():
                with open(self.jobs_file, 'r') as f:
                    data = json.load(f)
                
                for job_id, result_data in data.items():
                    # Convert datetime strings back to datetime objects
                    if result_data.get('started_at'):
                        result_data['started_at'] = datetime.fromisoformat(result_data['started_at'])
                    if result_data.get('completed_at'):
                        result_data['completed_at'] = datetime.fromisoformat(result_data['completed_at'])
                    
                    result_data['status'] = JobStatus(result_data['status'])
                    result = JobResult(**result_data)
                    self.job_results[job_id] = result
                
                logger.info(f"Loaded {len(self.job_results)} job results from persistence")
                
        except Exception as e:
            logger.error(f"Error loading persisted job data: {e}")
    
    async def persist_data(self):
        """Persist job results to disk."""
        try:
            with self._lock:
                persist_data = {}
                
                for job_id, result in self.job_results.items():
                    result_dict = asdict(result)
                    # Convert datetime objects to ISO strings
                    if result.started_at:
                        result_dict['started_at'] = result.started_at.isoformat()
                    if result.completed_at:
                        result_dict['completed_at'] = result.completed_at.isoformat()
                    
                    result_dict['status'] = result.status.value
                    persist_data[job_id] = result_dict
                
                with open(self.jobs_file, 'w') as f:
                    json.dump(persist_data, f, indent=2)
                
                logger.debug("Persisted job results to disk")
                
        except Exception as e:
            logger.error(f"Error persisting job data: {e}")
    
    def get_job_stats(self) -> Dict[str, Any]:
        """Get job runner statistics."""
        with self._lock:
            queue_sizes = self.job_queue.qsize()
            
            status_counts = {}
            for result in self.job_results.values():
                status = result.status.value
                status_counts[status] = status_counts.get(status, 0) + 1
            
            return {
                "active_jobs": len(self.active_jobs),
                "total_job_results": len(self.job_results),
                "queue_sizes": {priority.name: size for priority, size in queue_sizes.items()},
                "status_counts": status_counts,
                "max_concurrent_jobs": self.max_concurrent_jobs,
                "registered_functions": len(self.function_registry.functions),
                "available_functions": self.function_registry.list_functions()
            }
    
    async def shutdown(self):
        """Shutdown the job runner and cleanup resources."""
        logger.info("Shutting down local job runner")
        
        # Cancel all background tasks
        all_tasks = self.worker_tasks + [self.scheduler_task, self.cleanup_task]
        for task in all_tasks:
            if task:
                task.cancel()
        
        # Wait for tasks to complete
        if all_tasks:
            await asyncio.gather(*[t for t in all_tasks if t], return_exceptions=True)
        
        # Shutdown thread pools
        self.thread_pool.shutdown(wait=True)
        self.process_pool.shutdown(wait=True)
        
        # Final persistence
        await self.persist_data()
        
        logger.info("Local job runner shutdown complete")