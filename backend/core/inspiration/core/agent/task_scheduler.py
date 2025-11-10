"""
🎯 TASK SCHEDULER

Intelligent task scheduling system with:
- Priority-based task execution
- Resource allocation optimization
- Load balancing across agents
- Deadline-aware scheduling
- Performance monitoring and reporting
"""

import asyncio
import logging
from typing import Dict, Any, List, Optional, Tuple, Set
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from collections import defaultdict
import heapq

from .enhanced_task_models import EnhancedTaskInfo, TaskState, TaskResourceRequirements
from .task_prioritization_engine import TaskPrioritizationEngine
from .task_dependency_manager import TaskDependencyManager

logger = logging.getLogger(__name__)


@dataclass
class SchedulerMetrics:
    """Metrics for scheduler performance."""
    tasks_scheduled: int = 0
    tasks_completed: int = 0
    tasks_failed: int = 0
    average_queue_time: float = 0.0
    average_execution_time: float = 0.0
    resource_utilization: Dict[str, float] = field(default_factory=dict)
    scheduling_efficiency: float = 0.0
    load_balance_score: float = 0.0


@dataclass
class ResourcePool:
    """Resource pool for task execution."""
    available_cpu_cores: int = 4
    available_memory_mb: int = 4096
    available_storage_mb: int = 10240
    special_resources: Dict[str, int] = field(default_factory=dict)  # resource_name -> count

    def can_allocate(self, requirements: TaskResourceRequirements) -> bool:
        """Check if resources can be allocated for task."""
        return (
            self.available_cpu_cores >= requirements.cpu_cores and
            self.available_memory_mb >= requirements.memory_mb and
            self.available_storage_mb >= requirements.storage_mb and
            all(self.special_resources.get(resource, 0) >= 1
                for resource in requirements.special_resources)
        )

    def allocate(self, requirements: TaskResourceRequirements) -> bool:
        """Allocate resources for task."""
        if not self.can_allocate(requirements):
            return False

        self.available_cpu_cores -= requirements.cpu_cores
        self.available_memory_mb -= requirements.memory_mb
        self.available_storage_mb -= requirements.storage_mb

        for resource in requirements.special_resources:
            if resource in self.special_resources:
                self.special_resources[resource] -= 1

        return True

    def deallocate(self, requirements: TaskResourceRequirements) -> None:
        """Deallocate resources."""
        self.available_cpu_cores += requirements.cpu_cores
        self.available_memory_mb += requirements.memory_mb
        self.available_storage_mb += requirements.storage_mb

        for resource in requirements.special_resources:
            self.special_resources[resource] = self.special_resources.get(resource, 0) + 1

    def get_utilization(self) -> Dict[str, float]:
        """Get resource utilization percentages."""
        total_cpu = 8  # Assume 8 cores total
        total_memory = 8192  # Assume 8GB total
        total_storage = 20480  # Assume 20GB total

        return {
            'cpu_utilization': ((total_cpu - self.available_cpu_cores) / total_cpu) * 100,
            'memory_utilization': ((total_memory - self.available_memory_mb) / total_memory) * 100,
            'storage_utilization': ((total_storage - self.available_storage_mb) / total_storage) * 100
        }


@dataclass
class AgentNode:
    """Represents an agent/node that can execute tasks."""
    agent_id: str
    capabilities: List[str] = field(default_factory=list)
    resource_pool: ResourcePool = field(default_factory=ResourcePool)
    active_tasks: Set[str] = field(default_factory=set)
    max_concurrent_tasks: int = 5
    specialization_score: Dict[str, float] = field(default_factory=dict)  # task_type -> capability_score

    def can_execute_task(self, task: EnhancedTaskInfo) -> bool:
        """Check if agent can execute the given task."""
        # Check concurrent task limit
        if len(self.active_tasks) >= self.max_concurrent_tasks:
            return False

        # Check capabilities
        if task.assigned_agent and task.assigned_agent != self.agent_id:
            return False

        # Check resource requirements
        if not self.resource_pool.can_allocate(task.resource_requirements):
            return False

        return True

    def calculate_task_fit(self, task: EnhancedTaskInfo) -> float:
        """Calculate how well this agent fits the task (0-100)."""
        if not self.can_execute_task(task):
            return 0.0

        fit_score = 50.0  # Base score

        # Capability matching
        task_type = task.description.lower()
        best_capability_match = 0.0
        for capability in self.capabilities:
            if capability.lower() in task_type:
                best_capability_match = max(best_capability_match, 80.0)
            elif any(word in task_type for word in capability.lower().split()):
                best_capability_match = max(best_capability_match, 60.0)

        if best_capability_match > 0:
            fit_score += best_capability_match * 0.3

        # Specialization score
        for task_tag in task.tags:
            if task_tag in self.specialization_score:
                fit_score += self.specialization_score[task_tag] * 0.2

        # Resource availability bonus
        resource_utilization = self.resource_pool.get_utilization()
        avg_utilization = sum(resource_utilization.values()) / len(resource_utilization)
        if avg_utilization < 70:  # Prefer less utilized agents
            fit_score += (100 - avg_utilization) * 0.1

        return min(100.0, fit_score)


class TaskScheduler:
    """
    Intelligent task scheduler with priority-based execution,
    resource optimization, and load balancing.
    """

    def __init__(self, prioritization_engine: TaskPrioritizationEngine,
                 dependency_manager: TaskDependencyManager):
        """
        Initialize task scheduler.

        Args:
            prioritization_engine: Engine for task prioritization
            dependency_manager: Manager for task dependencies
        """
        self.prioritization_engine = prioritization_engine
        self.dependency_manager = dependency_manager

        # Agent nodes
        self.agent_nodes: Dict[str, AgentNode] = {}
        self.task_assignments: Dict[str, str] = {}  # task_id -> agent_id

        # Execution tracking
        self.running_tasks: Dict[str, EnhancedTaskInfo] = {}
        self.completed_tasks: Dict[str, Tuple[EnhancedTaskInfo, datetime]] = {}
        self.failed_tasks: Dict[str, Tuple[EnhancedTaskInfo, str]] = {}

        # Scheduler state
        self.is_running = False
        self.scheduler_task: Optional[asyncio.Task] = None

        # Metrics
        self.metrics = SchedulerMetrics()
        self.execution_history: List[Dict[str, Any]] = []

        # Configuration
        self.max_concurrent_tasks = 10
        self.scheduling_interval = 5  # seconds
        self.resource_check_interval = 30  # seconds

        logger.info("Initialized TaskScheduler")

    async def start_scheduler(self) -> None:
        """Start the task scheduler."""
        if self.is_running:
            return

        self.is_running = True
        self.scheduler_task = asyncio.create_task(self._scheduling_loop())

        logger.info("TaskScheduler started")

    async def stop_scheduler(self) -> None:
        """Stop the task scheduler."""
        self.is_running = False

        if self.scheduler_task:
            self.scheduler_task.cancel()
            try:
                await self.scheduler_task
            except asyncio.CancelledError:
                pass

        logger.info("TaskScheduler stopped")

    def add_agent_node(self, agent: AgentNode) -> None:
        """Add an agent node to the scheduler."""
        self.agent_nodes[agent.agent_id] = agent
        logger.info(f"Added agent node: {agent.agent_id}")

    def remove_agent_node(self, agent_id: str) -> bool:
        """Remove an agent node."""
        if agent_id in self.agent_nodes:
            # Reassign any tasks from this agent
            tasks_to_reassign = [
                task_id for task_id, assigned_agent in self.task_assignments.items()
                if assigned_agent == agent_id
            ]

            for task_id in tasks_to_reassign:
                if task_id in self.task_assignments:
                    del self.task_assignments[task_id]

            del self.agent_nodes[agent_id]
            logger.info(f"Removed agent node: {agent_id}")
            return True

        return False

    async def schedule_task(self, task: EnhancedTaskInfo) -> bool:
        """
        Schedule a task for execution.

        Args:
            task: Task to schedule

        Returns:
            True if task was scheduled successfully
        """
        # Add to prioritization engine
        await self.prioritization_engine.add_task(task)

        # Add to dependency manager
        await self.dependency_manager.add_task(task)

        # Update task state
        task.update_state(TaskState.QUEUED, "Added to scheduler queue")

        logger.info(f"Scheduled task: {task.task_id}")
        return True

    async def _scheduling_loop(self) -> None:
        """Main scheduling loop."""
        last_resource_check = datetime.utcnow()

        while self.is_running:
            try:
                # Check for ready tasks
                await self._process_ready_tasks()

                # Periodic resource check
                now = datetime.utcnow()
                if (now - last_resource_check).seconds >= self.resource_check_interval:
                    await self._optimize_resource_allocation()
                    last_resource_check = now

                # Update metrics
                await self._update_scheduler_metrics()

                await asyncio.sleep(self.scheduling_interval)

            except Exception as e:
                logger.error(f"Error in scheduling loop: {e}")
                await asyncio.sleep(self.scheduling_interval)

    async def _process_ready_tasks(self) -> None:
        """Process tasks that are ready for execution."""
        # Get ready tasks from dependency manager
        all_tasks = list(self.prioritization_engine.task_index.keys())
        ready_task_ids = await self.dependency_manager.get_ready_tasks(all_tasks)

        if not ready_task_ids:
            return

        # Get highest priority ready task
        ready_tasks = [
            self.prioritization_engine.task_index[task_id]
            for task_id in ready_task_ids
            if task_id in self.prioritization_engine.task_index
        ]

        # Sort by priority (highest first)
        ready_tasks.sort(key=lambda t: t.calculate_current_priority(), reverse=True)

        # Try to execute tasks
        executed_count = 0
        for task in ready_tasks:
            if len(self.running_tasks) >= self.max_concurrent_tasks:
                break

            # Find best agent for task
            best_agent = await self._find_best_agent(task)
            if best_agent:
                success = await self._execute_task_on_agent(task, best_agent)
                if success:
                    executed_count += 1
                    self.metrics.tasks_scheduled += 1

        if executed_count > 0:
            logger.debug(f"Executed {executed_count} tasks in this cycle")

    async def _find_best_agent(self, task: EnhancedTaskInfo) -> Optional[AgentNode]:
        """Find the best agent for executing a task."""
        best_agent = None
        best_score = 0.0

        for agent in self.agent_nodes.values():
            if agent.can_execute_task(task):
                fit_score = agent.calculate_task_fit(task)
                if fit_score > best_score:
                    best_score = fit_score
                    best_agent = agent

        if best_agent:
            logger.debug(f"Selected agent {best_agent.agent_id} for task {task.task_id} (score: {best_score:.1f})")

        return best_agent

    async def _execute_task_on_agent(self, task: EnhancedTaskInfo, agent: AgentNode) -> bool:
        """
        Execute a task on a specific agent.

        Args:
            task: Task to execute
            agent: Agent to execute on

        Returns:
            True if execution started successfully
        """
        try:
            # Allocate resources
            if not agent.resource_pool.allocate(task.resource_requirements):
                logger.warning(f"Failed to allocate resources for task {task.task_id}")
                return False

            # Update task state
            task.update_state(TaskState.RUNNING, f"Assigned to agent {agent.agent_id}")
            task.actual_start_time = datetime.utcnow()
            task.assigned_agent = agent.agent_id
            task.processing_node = agent.agent_id

            # Add to tracking
            self.running_tasks[task.task_id] = task
            self.task_assignments[task.task_id] = agent.agent_id
            agent.active_tasks.add(task.task_id)

            # Start execution in background
            asyncio.create_task(self._execute_task_async(task, agent))

            logger.info(f"Started execution of task {task.task_id} on agent {agent.agent_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to execute task {task.task_id}: {e}")

            # Cleanup on failure
            agent.resource_pool.deallocate(task.resource_requirements)

            return False

    async def _execute_task_async(self, task: EnhancedTaskInfo, agent: AgentNode) -> None:
        """Execute task asynchronously."""
        try:
            # Simulate task execution (replace with actual execution logic)
            execution_time = task.resource_requirements.estimated_duration_seconds

            # Add some randomness to simulation
            import random
            actual_time = execution_time * (0.8 + random.random() * 0.4)  # 80-120% of estimated

            await asyncio.sleep(actual_time)

            # Mark as completed
            await self._complete_task(task, agent)

        except Exception as e:
            logger.error(f"Error executing task {task.task_id}: {e}")
            await self._fail_task(task, agent, str(e))

    async def _complete_task(self, task: EnhancedTaskInfo, agent: AgentNode) -> None:
        """Mark task as completed."""
        completion_time = datetime.utcnow()

        # Update task
        task.update_state(TaskState.COMPLETED, "Execution completed successfully")
        task.completion_time = completion_time

        # Update metrics
        if task.actual_start_time:
            execution_time = (completion_time - task.actual_start_time).total_seconds()
            task.metrics.execution_time_seconds = execution_time
            task.metrics.success_rate_history.append(True)

            # Update scheduler metrics
            self.metrics.tasks_completed += 1
            self.metrics.average_execution_time = (
                (self.metrics.average_execution_time * (self.metrics.tasks_completed - 1)) +
                execution_time
            ) / self.metrics.tasks_completed

        # Cleanup
        await self._cleanup_task_execution(task, agent)

        # Notify dependency manager
        newly_ready = await self.dependency_manager.update_task_status(task.task_id, TaskState.COMPLETED)

        # Add newly ready tasks to prioritization
        for ready_task_id in newly_ready:
            if ready_task_id in self.prioritization_engine.task_index:
                ready_task = self.prioritization_engine.task_index[ready_task_id]
                await self.prioritization_engine.update_task_priority(ready_task_id)

        logger.info(f"Completed task: {task.task_id}")

    async def _fail_task(self, task: EnhancedTaskInfo, agent: AgentNode, error: str) -> None:
        """Mark task as failed."""
        # Update task
        task.update_state(TaskState.FAILED, f"Execution failed: {error}")
        task.completion_time = datetime.utcnow()
        task.error = error
        task.metrics.retry_count += 1
        task.metrics.success_rate_history.append(False)

        # Update scheduler metrics
        self.metrics.tasks_failed += 1

        # Cleanup
        await self._cleanup_task_execution(task, agent)

        # Check retry logic
        if task.metrics.retry_count < task.scheduling_constraints.retry_limit:
            # Reschedule for retry
            retry_delay = task.scheduling_constraints.retry_delay_seconds
            asyncio.create_task(self._reschedule_task_with_delay(task, retry_delay))
            logger.info(f"Scheduled retry for task {task.task_id} in {retry_delay}s")
        else:
            logger.warning(f"Task {task.task_id} failed permanently after {task.metrics.retry_count} attempts")

    async def _reschedule_task_with_delay(self, task: EnhancedTaskInfo, delay: int) -> None:
        """Reschedule a task after a delay."""
        await asyncio.sleep(delay)

        # Reset task state for retry
        task.update_state(TaskState.QUEUED, f"Retrying after failure (attempt {task.metrics.retry_count})")
        task.error = None

        # Re-add to prioritization
        await self.prioritization_engine.add_task(task)

    async def _cleanup_task_execution(self, task: EnhancedTaskInfo, agent: AgentNode) -> None:
        """Clean up after task execution."""
        # Remove from running tasks
        if task.task_id in self.running_tasks:
            del self.running_tasks[task.task_id]

        # Remove from task assignments
        if task.task_id in self.task_assignments:
            del self.task_assignments[task.task_id]

        # Remove from agent active tasks
        if task.task_id in agent.active_tasks:
            agent.active_tasks.remove(task.task_id)

        # Deallocate resources
        agent.resource_pool.deallocate(task.resource_requirements)

    async def _optimize_resource_allocation(self) -> None:
        """Optimize resource allocation across agents."""
        try:
            # Calculate load balance score
            agent_loads = []
            for agent in self.agent_nodes.values():
                utilization = agent.resource_pool.get_utilization()
                avg_load = sum(utilization.values()) / len(utilization)
                agent_loads.append(avg_load)

            if agent_loads:
                # Load balance score (lower variance = better balance)
                avg_load = sum(agent_loads) / len(agent_loads)
                variance = sum((load - avg_load) ** 2 for load in agent_loads) / len(agent_loads)
                self.metrics.load_balance_score = max(0, 100 - variance * 2)

            # Log optimization results
            logger.debug(f"Resource optimization completed. Load balance score: {self.metrics.load_balance_score:.1f}")

        except Exception as e:
            logger.error(f"Error in resource optimization: {e}")

    async def _update_scheduler_metrics(self) -> None:
        """Update scheduler performance metrics."""
        try:
            # Calculate scheduling efficiency
            total_processed = self.metrics.tasks_scheduled + self.metrics.tasks_completed + self.metrics.tasks_failed
            if total_processed > 0:
                self.metrics.scheduling_efficiency = (
                    self.metrics.tasks_completed / total_processed
                ) * 100

            # Update resource utilization
            if self.agent_nodes:
                total_utilization = defaultdict(float)
                for agent in self.agent_nodes.values():
                    agent_utilization = agent.resource_pool.get_utilization()
                    for resource, utilization in agent_utilization.items():
                        total_utilization[resource] += utilization

                for resource in total_utilization:
                    total_utilization[resource] /= len(self.agent_nodes)

                self.metrics.resource_utilization = dict(total_utilization)

        except Exception as e:
            logger.error(f"Error updating scheduler metrics: {e}")

    def get_scheduler_status(self) -> Dict[str, Any]:
        """Get current scheduler status."""
        return {
            'is_running': self.is_running,
            'active_agents': len(self.agent_nodes),
            'running_tasks': len(self.running_tasks),
            'queued_tasks': len(self.prioritization_engine.task_queue),
            'completed_tasks': len(self.completed_tasks),
            'failed_tasks': len(self.failed_tasks),
            'metrics': {
                'tasks_scheduled': self.metrics.tasks_scheduled,
                'tasks_completed': self.metrics.tasks_completed,
                'tasks_failed': self.metrics.tasks_failed,
                'scheduling_efficiency': round(self.metrics.scheduling_efficiency, 1),
                'load_balance_score': round(self.metrics.load_balance_score, 1),
                'resource_utilization': {
                    k: round(v, 1) for k, v in self.metrics.resource_utilization.items()
                }
            },
            'agent_status': {
                agent_id: {
                    'active_tasks': len(agent.active_tasks),
                    'resource_utilization': agent.resource_pool.get_utilization()
                }
                for agent_id, agent in self.agent_nodes.items()
            }
        }

    async def cancel_task(self, task_id: str) -> bool:
        """Cancel a running task."""
        if task_id not in self.running_tasks:
            return False

        task = self.running_tasks[task_id]
        agent_id = self.task_assignments.get(task_id)

        if agent_id and agent_id in self.agent_nodes:
            agent = self.agent_nodes[agent_id]
            await self._cleanup_task_execution(task, agent)

        task.update_state(TaskState.CANCELLED, "Cancelled by scheduler")
        logger.info(f"Cancelled task: {task_id}")

        return True

    async def get_task_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Get status of a specific task."""
        # Check running tasks
        if task_id in self.running_tasks:
            task = self.running_tasks[task_id]
            return {
                'task_id': task_id,
                'status': 'running',
                'assigned_agent': task.assigned_agent,
                'started_at': task.actual_start_time.isoformat() if task.actual_start_time else None,
                'progress': 'N/A'  # Could be enhanced with progress tracking
            }

        # Check prioritization queue
        task = self.prioritization_engine.task_index.get(task_id)
        if task:
            return {
                'task_id': task_id,
                'status': task.task_state.value,
                'priority': task.calculate_current_priority(),
                'queue_position': getattr(task, 'queue_position', None),
                'created_at': task.started_at.isoformat() if task.started_at else None
            }

        # Check completed/failed tasks
        if task_id in self.completed_tasks:
            task, completed_at = self.completed_tasks[task_id]
            return {
                'task_id': task_id,
                'status': 'completed',
                'completed_at': completed_at.isoformat(),
                'execution_time': task.metrics.execution_time_seconds
            }

        if task_id in self.failed_tasks:
            task, error = self.failed_tasks[task_id]
            return {
                'task_id': task_id,
                'status': 'failed',
                'error': error,
                'retry_count': task.metrics.retry_count
            }

        return None