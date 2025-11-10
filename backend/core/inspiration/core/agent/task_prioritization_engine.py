"""
🎯 TASK PRIORITIZATION ENGINE

Intelligent engine for calculating task priorities based on multiple criteria:
- Urgency and deadlines
- Resource availability
- Dependency relationships
- Performance history
- Context importance
- Business rules
"""

import asyncio
import logging
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timedelta
from heapq import heappush, heappop

from .enhanced_task_models import (
    EnhancedTaskInfo,
    TaskPriorityMetadata,
    TaskState,
    TaskResourceRequirements,
    TaskSchedulingConstraints,
    TaskDependency,
    DependencyType
)

logger = logging.getLogger(__name__)


class PriorityCalculationEngine:
    """
    Engine for calculating task priorities based on multiple weighted factors.
    """

    def __init__(self, weights: Optional[Dict[str, float]] = None):
        """
        Initialize priority calculation engine.

        Args:
            weights: Custom weights for priority factors (0.0 to 1.0)
        """
        # Default weights for priority calculation
        self.weights = weights or {
            'urgency': 0.25,
            'resource_availability': 0.15,
            'dependency_pressure': 0.15,
            'performance_bonus': 0.15,
            'context_importance': 0.10,
            'business_rules': 0.20
        }

        # Validate weights sum to 1.0
        total_weight = sum(self.weights.values())
        if abs(total_weight - 1.0) > 0.001:
            logger.warning(f"Priority weights don't sum to 1.0: {total_weight}")

        # Configuration
        self.max_urgency_bonus = 50.0  # Max points for urgent tasks
        self.max_dependency_pressure_bonus = 30.0  # Max points for dependency pressure
        self.performance_bonus_multiplier = 20.0  # Performance bonus scaling
        self.context_importance_multiplier = 15.0  # Context importance scaling

    async def calculate_priority(self, task: EnhancedTaskInfo,
                               system_context: Dict[str, Any] = None) -> float:
        """
        Calculate comprehensive priority score for a task.

        Args:
            task: The task to calculate priority for
            system_context: Current system state and context

        Returns:
            Priority score (0-100)
        """
        system_context = system_context or {}

        # Calculate individual priority factors
        urgency_score = await self._calculate_urgency_factor(task)
        resource_score = await self._calculate_resource_availability_factor(task, system_context)
        dependency_score = await self._calculate_dependency_pressure_factor(task)
        performance_score = await self._calculate_performance_bonus_factor(task)
        context_score = await self._calculate_context_importance_factor(task, system_context)
        business_score = await self._calculate_business_rules_factor(task, system_context)

        # Store factor scores in metadata
        task.priority_metadata.urgency_score = urgency_score
        task.priority_metadata.resource_availability_score = resource_score
        task.priority_metadata.dependency_pressure_score = dependency_score
        task.priority_metadata.performance_bonus_score = performance_score
        task.priority_metadata.context_importance_score = context_score

        # Calculate weighted priority score
        priority_score = (
            task.priority_metadata.base_priority * self.weights['business_rules'] +
            urgency_score * self.weights['urgency'] +
            resource_score * self.weights['resource_availability'] +
            dependency_score * self.weights['dependency_pressure'] +
            performance_score * self.weights['performance_bonus'] +
            context_score * self.weights['context_importance'] +
            business_score * self.weights['business_rules']
        )

        # Apply user override if specified
        if task.user_priority_override is not None:
            priority_score = task.user_priority_override

        # Clamp to valid range and update metadata
        final_priority = max(0.0, min(100.0, priority_score))
        task.priority_metadata.calculated_priority = final_priority
        task.priority_metadata.last_priority_update = datetime.utcnow()

        logger.debug(f"Calculated priority {final_priority:.1f} for task {task.task_id}")
        return final_priority

    async def _calculate_urgency_factor(self, task: EnhancedTaskInfo) -> float:
        """Calculate urgency factor based on deadlines and time constraints."""
        if not task.scheduling_constraints.latest_end_time:
            return 0.0

        now = datetime.utcnow()
        deadline = task.scheduling_constraints.latest_end_time
        time_remaining = (deadline - now).total_seconds()

        if time_remaining <= 0:
            # Overdue - maximum urgency
            return self.max_urgency_bonus

        # Calculate urgency based on time remaining
        estimated_duration = task.resource_requirements.estimated_duration_seconds

        if time_remaining < estimated_duration:
            # Not enough time - high urgency
            return self.max_urgency_bonus * 0.9
        elif time_remaining < estimated_duration * 2:
            # Tight schedule - medium urgency
            return self.max_urgency_bonus * 0.6
        elif time_remaining < estimated_duration * 4:
            # Some pressure - low urgency
            return self.max_urgency_bonus * 0.3

        return 0.0

    async def _calculate_resource_availability_factor(self, task: EnhancedTaskInfo,
                                                    system_context: Dict[str, Any]) -> float:
        """
        Calculate resource availability factor.

        Higher score when required resources are readily available.
        Lower score when resources are scarce.
        """
        available_resources = system_context.get('available_resources', {})
        system_load = system_context.get('system_load', 0.5)  # 0.0 to 1.0

        # Check specific resource requirements
        resource_score = 1.0

        req = task.resource_requirements

        # CPU availability
        cpu_available = available_resources.get('cpu_cores', 4)
        if cpu_available < req.cpu_cores:
            resource_score *= 0.3  # Severe penalty
        elif cpu_available < req.cpu_cores * 2:
            resource_score *= 0.7  # Moderate penalty

        # Memory availability
        memory_available = available_resources.get('memory_mb', 4096)
        if memory_available < req.memory_mb:
            resource_score *= 0.2  # Severe penalty
        elif memory_available < req.memory_mb * 1.5:
            resource_score *= 0.6  # Moderate penalty

        # Network bandwidth
        network_load = system_context.get('network_load', 0.5)
        if req.network_bandwidth == 'high' and network_load > 0.8:
            resource_score *= 0.4
        elif req.network_bandwidth == 'medium' and network_load > 0.9:
            resource_score *= 0.6

        # Special resources
        for special_resource in req.special_resources:
            if special_resource not in available_resources.get('special_resources', []):
                resource_score *= 0.1  # Severe penalty for missing special resources

        # System load factor
        if system_load > 0.9:
            resource_score *= 0.5  # Heavy load penalty
        elif system_load > 0.7:
            resource_score *= 0.8  # Moderate load penalty

        return resource_score * 100.0  # Convert to 0-100 scale

    async def _calculate_dependency_pressure_factor(self, task: EnhancedTaskInfo) -> float:
        """Calculate dependency pressure factor."""
        if not task.dependents:
            return 0.0

        # Check how many tasks are waiting for this task
        waiting_tasks = len(task.dependents)

        # Check priority of dependent tasks
        high_priority_dependents = sum(
            1 for dep_task in task.dependents
            if hasattr(dep_task, 'calculate_current_priority') and
            dep_task.calculate_current_priority() > 70
        )

        # Calculate pressure based on waiting tasks and their priority
        pressure_score = min(waiting_tasks * 10 + high_priority_dependents * 20, self.max_dependency_pressure_bonus)

        return pressure_score

    async def _calculate_performance_bonus_factor(self, task: EnhancedTaskInfo) -> float:
        """Calculate performance bonus based on historical success."""
        metrics = task.metrics

        if not metrics.success_rate_history:
            return 0.0

        # Calculate success rate from recent history
        recent_history = metrics.success_rate_history[-10:]  # Last 10 executions
        success_rate = sum(recent_history) / len(recent_history)

        # Performance bonus based on success rate and speed
        performance_bonus = success_rate * self.performance_bonus_multiplier

        # Speed bonus (faster execution = higher bonus)
        if metrics.average_execution_time > 0:
            speed_factor = min(1.0, 60.0 / metrics.average_execution_time)  # Target: 60 seconds
            performance_bonus += speed_factor * 10

        return min(performance_bonus, self.performance_bonus_multiplier + 10)

    async def _calculate_context_importance_factor(self, task: EnhancedTaskInfo,
                                                 system_context: Dict[str, Any]) -> float:
        """Calculate context importance factor."""
        importance_score = task.context_importance

        # Boost based on tags
        priority_tags = ['urgent', 'critical', 'high_priority', 'vip', 'emergency']
        tag_boost = sum(1 for tag in task.tags if tag in priority_tags) * 5

        # Boost based on user role or department
        user_context = system_context.get('user_context', {})
        if user_context.get('role') in ['admin', 'manager', 'executive']:
            importance_score += 10

        # Boost based on conversation importance
        conversation_context = system_context.get('conversation_context', {})
        if conversation_context.get('priority') == 'high':
            importance_score += 15

        return min(importance_score + tag_boost, self.context_importance_multiplier)

    async def _calculate_business_rules_factor(self, task: EnhancedTaskInfo,
                                             system_context: Dict[str, Any]) -> float:
        """Calculate business rules factor."""
        business_score = 0.0

        # Business hours boost
        now = datetime.utcnow()
        if 9 <= now.hour <= 17:  # Business hours
            business_score += 10

        # Weekend penalty
        if now.weekday() >= 5:  # Saturday = 5, Sunday = 6
            business_score -= 5

        # Task type priorities
        if 'accounting' in task.description.lower():
            business_score += 15  # Financial tasks get priority
        elif 'security' in task.description.lower():
            business_score += 20  # Security tasks highest priority
        elif 'user_facing' in task.tags:
            business_score += 10  # User-facing tasks important

        return business_score


class TaskPrioritizationEngine:
    """
    Main engine for task prioritization and queue management.
    """

    def __init__(self, calculation_engine: Optional[PriorityCalculationEngine] = None):
        """
        Initialize task prioritization engine.

        Args:
            calculation_engine: Custom priority calculation engine
        """
        self.calculation_engine = calculation_engine or PriorityCalculationEngine()
        self.task_queue: List[Tuple[float, EnhancedTaskInfo]] = []  # Priority queue
        self.task_index: Dict[str, EnhancedTaskInfo] = {}  # Fast lookup by task_id
        self.system_context: Dict[str, Any] = {}

        # Statistics
        self.stats = {
            'total_tasks_processed': 0,
            'average_priority': 0.0,
            'queue_size': 0,
            'tasks_by_priority_range': {'low': 0, 'medium': 0, 'high': 0, 'critical': 0}
        }

        logger.info("Initialized TaskPrioritizationEngine")

    async def add_task(self, task: EnhancedTaskInfo) -> None:
        """
        Add a task to the prioritization queue.

        Args:
            task: Task to add
        """
        # Calculate initial priority
        priority = await self.calculation_engine.calculate_priority(task, self.system_context)

        # Add to priority queue (negative priority for max-heap behavior)
        heappush(self.task_queue, (-priority, task))
        self.task_index[task.task_id] = task

        # Update statistics
        self.stats['total_tasks_processed'] += 1
        self.stats['queue_size'] = len(self.task_queue)
        self._update_priority_stats(priority)

        logger.info(f"Added task {task.task_id} with priority {priority:.1f}")

    async def get_next_task(self) -> Optional[EnhancedTaskInfo]:
        """
        Get the highest priority task from the queue.

        Returns:
            Next task to execute, or None if queue is empty
        """
        while self.task_queue:
            negative_priority, task = heappop(self.task_queue)

            # Recalculate priority in case conditions have changed
            current_priority = await self.calculation_engine.calculate_priority(task, self.system_context)

            # If priority has changed significantly, re-queue
            if abs(current_priority - (-negative_priority)) > 10:
                heappush(self.task_queue, (-current_priority, task))
                continue

            # Check if task is ready to execute
            if task.can_be_executed_now():
                task.queue_position = None
                return task
            else:
                # Task not ready, put back in queue with updated priority
                heappush(self.task_queue, (-current_priority, task))

        return None

    async def update_task_priority(self, task_id: str) -> bool:
        """
        Recalculate and update priority for a specific task.

        Args:
            task_id: Task to update

        Returns:
            True if task was found and updated
        """
        if task_id not in self.task_index:
            return False

        task = self.task_index[task_id]

        # Remove from queue (will be inefficient with heap, but necessary for updates)
        self.task_queue = [(p, t) for p, t in self.task_queue if t.task_id != task_id]

        # Recalculate priority
        new_priority = await self.calculation_engine.calculate_priority(task, self.system_context)

        # Re-add to queue
        heappush(self.task_queue, (-new_priority, task))

        # Update statistics
        self._update_priority_stats(new_priority)

        logger.debug(f"Updated priority for task {task_id} to {new_priority:.1f}")
        return True

    async def remove_task(self, task_id: str) -> bool:
        """
        Remove a task from the queue.

        Args:
            task_id: Task to remove

        Returns:
            True if task was found and removed
        """
        if task_id not in self.task_index:
            return False

        # Remove from queue
        self.task_queue = [(p, t) for p, t in self.task_queue if t.task_id != task_id]

        # Remove from index
        del self.task_index[task_id]

        self.stats['queue_size'] = len(self.task_queue)

        logger.info(f"Removed task {task_id} from queue")
        return True

    async def update_system_context(self, context: Dict[str, Any]) -> None:
        """
        Update system context that affects priority calculations.

        Args:
            context: New system context
        """
        self.system_context.update(context)

        # Recalculate priorities for all tasks
        await self._recalculate_all_priorities()

        logger.debug("Updated system context and recalculated priorities")

    async def _recalculate_all_priorities(self) -> None:
        """Recalculate priorities for all tasks in the queue."""
        if not self.task_queue:
            return

        # Extract all tasks
        tasks = [task for _, task in self.task_queue]

        # Clear queue
        self.task_queue.clear()

        # Re-add all tasks with updated priorities
        for task in tasks:
            priority = await self.calculation_engine.calculate_priority(task, self.system_context)
            heappush(self.task_queue, (-priority, task))
            self._update_priority_stats(priority)

        logger.debug(f"Recalculated priorities for {len(tasks)} tasks")

    def _update_priority_stats(self, priority: float) -> None:
        """Update priority statistics."""
        self.stats['average_priority'] = (
            (self.stats['average_priority'] * (self.stats['total_tasks_processed'] - 1)) + priority
        ) / self.stats['total_tasks_processed']

        # Categorize by priority range
        if priority >= 80:
            self.stats['tasks_by_priority_range']['critical'] += 1
        elif priority >= 60:
            self.stats['tasks_by_priority_range']['high'] += 1
        elif priority >= 40:
            self.stats['tasks_by_priority_range']['medium'] += 1
        else:
            self.stats['tasks_by_priority_range']['low'] += 1

    def get_queue_status(self) -> Dict[str, Any]:
        """Get current queue status and statistics."""
        return {
            'queue_size': len(self.task_queue),
            'tasks_by_state': self._count_tasks_by_state(),
            'priority_distribution': self.stats['tasks_by_priority_range'].copy(),
            'average_priority': round(self.stats['average_priority'], 1),
            'system_load': self.system_context.get('system_load', 0.5)
        }

    def _count_tasks_by_state(self) -> Dict[str, int]:
        """Count tasks by their current state."""
        state_counts = {}
        for _, task in self.task_queue:
            state = task.task_state.value
            state_counts[state] = state_counts.get(state, 0) + 1
        return state_counts

    async def get_task_by_id(self, task_id: str) -> Optional[EnhancedTaskInfo]:
        """Get task by ID."""
        return self.task_index.get(task_id)

    def get_all_tasks(self) -> List[EnhancedTaskInfo]:
        """Get all tasks in the queue."""
        return [task for _, task in self.task_queue]

    async def prioritize_task_manually(self, task_id: str, priority: float) -> bool:
        """
        Manually set priority for a task.

        Args:
            task_id: Task to prioritize
            priority: New priority (0-100)

        Returns:
            True if successful
        """
        if task_id not in self.task_index:
            return False

        task = self.task_index[task_id]
        task.user_priority_override = max(0.0, min(100.0, priority))

        # Update in queue
        await self.update_task_priority(task_id)

        logger.info(f"Manually set priority {priority} for task {task_id}")
        return True

    async def clear_user_priority_override(self, task_id: str) -> bool:
        """
        Clear manual priority override.

        Args:
            task_id: Task to clear override for

        Returns:
            True if successful
        """
        if task_id not in self.task_index:
            return False

        task = self.task_index[task_id]
        task.user_priority_override = None

        # Update in queue
        await self.update_task_priority(task_id)

        logger.info(f"Cleared priority override for task {task_id}")
        return True