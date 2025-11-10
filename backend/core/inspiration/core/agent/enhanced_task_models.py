"""
🎯 ENHANCED TASK MODELS FOR PRIORITIZATION SYSTEM

Extended task models with prioritization metadata, dependencies, and scheduling support.
"""

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, Any, List, Optional, Set
from app.core.agent.models import TaskInfo


class TaskState(Enum):
    """Enhanced task states for prioritization system."""
    PENDING = "pending"
    QUEUED = "queued"
    READY = "ready"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    BLOCKED = "blocked"
    PAUSED = "paused"
    RETRY = "retry"


class TaskPriority(Enum):
    """Task priority levels."""
    CRITICAL = 100
    HIGH = 75
    NORMAL = 50
    LOW = 25
    BACKGROUND = 10


class DependencyType(Enum):
    """Types of task dependencies."""
    HARD = "hard"        # Must complete before dependent task can start
    SOFT = "soft"        # Preferred order but not strictly required
    RESOURCE = "resource"  # Requires specific resources/agents
    TIME = "time"        # Time-based dependency
    CONDITIONAL = "conditional"  # Based on conditions or other task outcomes


@dataclass
class TaskResourceRequirements:
    """Resource requirements for task execution."""
    cpu_cores: int = 1
    memory_mb: int = 256
    storage_mb: int = 100
    network_bandwidth: str = "low"  # "low", "medium", "high"
    special_resources: List[str] = field(default_factory=list)  # GPU, specific agents, etc.
    estimated_duration_seconds: int = 60


@dataclass
class TaskSchedulingConstraints:
    """Scheduling constraints for tasks."""
    earliest_start_time: Optional[datetime] = None
    latest_end_time: Optional[datetime] = None
    max_execution_time_seconds: Optional[int] = None
    retry_limit: int = 3
    retry_delay_seconds: int = 30
    timeout_seconds: int = 300  # 5 minutes default timeout


@dataclass
class TaskDependency:
    """Represents a dependency relationship between tasks."""
    dependency_id: str
    task_id: str
    dependent_task_id: str
    dependency_type: DependencyType
    condition: Optional[str] = None  # For conditional dependencies
    created_at: datetime = field(default_factory=datetime.utcnow)
    satisfied: bool = False
    satisfied_at: Optional[datetime] = None


@dataclass
class TaskMetrics:
    """Performance metrics for task execution."""
    queue_time_seconds: float = 0.0
    execution_time_seconds: float = 0.0
    total_time_seconds: float = 0.0
    resource_utilization: Dict[str, float] = field(default_factory=dict)
    retry_count: int = 0
    success_rate_history: List[bool] = field(default_factory=list)
    average_execution_time: float = 0.0
    performance_score: float = 1.0  # 0.0 to 1.0


@dataclass
class TaskPriorityMetadata:
    """Metadata for priority calculation and management."""
    base_priority: float = 50.0  # 0-100
    calculated_priority: float = 50.0
    priority_factors: Dict[str, float] = field(default_factory=dict)
    last_priority_update: datetime = field(default_factory=datetime.utcnow)
    priority_boost_count: int = 0
    urgency_score: float = 0.0
    importance_score: float = 0.0
    resource_availability_score: float = 1.0
    dependency_pressure_score: float = 0.0
    performance_bonus_score: float = 0.0
    context_importance_score: float = 0.0


@dataclass
class EnhancedTaskInfo(TaskInfo):
    """
    Enhanced task information with prioritization and dependency support.

    Extends the base TaskInfo with advanced prioritization features,
    dependency management, resource requirements, and scheduling constraints.
    """

    # Enhanced state management
    task_state: TaskState = TaskState.PENDING
    previous_states: List[TaskState] = field(default_factory=list)

    # Priority and scoring
    priority_metadata: TaskPriorityMetadata = field(default_factory=TaskPriorityMetadata)

    # Dependencies
    dependencies: List[TaskDependency] = field(default_factory=list)
    dependents: List[str] = field(default_factory=list)  # Task IDs that depend on this task

    # Resource management
    resource_requirements: TaskResourceRequirements = field(default_factory=TaskResourceRequirements)
    allocated_resources: Dict[str, Any] = field(default_factory=dict)

    # Scheduling
    scheduling_constraints: TaskSchedulingConstraints = field(default_factory=TaskSchedulingConstraints)
    scheduled_start_time: Optional[datetime] = None
    actual_start_time: Optional[datetime] = None
    completion_time: Optional[datetime] = None

    # Performance tracking
    metrics: TaskMetrics = field(default_factory=TaskMetrics)

    # Advanced features
    tags: List[str] = field(default_factory=list)
    custom_metadata: Dict[str, Any] = field(default_factory=dict)
    context_importance: float = 1.0  # How important this task is in its context
    user_priority_override: Optional[float] = None  # Manual priority override

    # System metadata
    created_by: str = "system"
    assigned_agent: Optional[str] = None
    processing_node: Optional[str] = None
    queue_position: Optional[int] = None

    def __post_init__(self):
        """Initialize enhanced task features."""
        super().__post_init__()
        self._update_derived_fields()

    def _update_derived_fields(self):
        """Update calculated fields based on current state."""
        # Update timing metrics
        if self.actual_start_time and self.completion_time:
            self.metrics.execution_time_seconds = (
                self.completion_time - self.actual_start_time
            ).total_seconds()

        if self.started_at and self.completion_time:
            self.metrics.total_time_seconds = (
                self.completion_time - self.started_at
            ).total_seconds()

        if self.started_at and self.actual_start_time:
            self.metrics.queue_time_seconds = (
                self.actual_start_time - self.started_at
            ).total_seconds()

    def update_state(self, new_state: TaskState, reason: str = ""):
        """Update task state with history tracking."""
        if self.task_state != new_state:
            self.previous_states.append(self.task_state)
            old_state = self.task_state
            self.task_state = new_state

            # Update timing based on state changes
            now = datetime.utcnow()
            if new_state == TaskState.RUNNING and not self.actual_start_time:
                self.actual_start_time = now
            elif new_state in [TaskState.COMPLETED, TaskState.FAILED, TaskState.CANCELLED]:
                self.completion_time = now
                self._update_derived_fields()

            # Add state change to custom metadata
            if 'state_changes' not in self.custom_metadata:
                self.custom_metadata['state_changes'] = []
            self.custom_metadata['state_changes'].append({
                'from': old_state.value,
                'to': new_state.value,
                'timestamp': now.isoformat(),
                'reason': reason
            })

    def add_dependency(self, dependency_task_id: str, dependency_type: DependencyType = DependencyType.HARD,
                      condition: Optional[str] = None) -> str:
        """Add a dependency to this task."""
        dependency_id = f"dep_{uuid.uuid4().hex[:8]}"
        dependency = TaskDependency(
            dependency_id=dependency_id,
            task_id=dependency_task_id,
            dependent_task_id=self.task_id,
            dependency_type=dependency_type,
            condition=condition
        )
        self.dependencies.append(dependency)
        return dependency_id

    def remove_dependency(self, dependency_id: str):
        """Remove a dependency."""
        self.dependencies = [d for d in self.dependencies if d.dependency_id != dependency_id]

    def is_ready(self) -> bool:
        """Check if task is ready to execute (all hard dependencies satisfied)."""
        if self.task_state != TaskState.READY:
            return False

        # Check hard dependencies
        hard_deps = [d for d in self.dependencies if d.dependency_type == DependencyType.HARD]
        return all(d.satisfied for d in hard_deps)

    def satisfies_dependency(self, dependency: TaskDependency) -> bool:
        """Check if this task satisfies a given dependency."""
        if dependency.task_id != self.task_id:
            return False

        if dependency.dependency_type == DependencyType.HARD:
            return self.task_state == TaskState.COMPLETED
        elif dependency.dependency_type == DependencyType.SOFT:
            return self.task_state in [TaskState.COMPLETED, TaskState.RUNNING]
        elif dependency.dependency_type == DependencyType.CONDITIONAL:
            # Check condition if specified
            if dependency.condition and 'result' in self.result:
                return self._evaluate_condition(dependency.condition, self.result)
            return self.task_state == TaskState.COMPLETED

        return False

    def _evaluate_condition(self, condition: str, result: Dict[str, Any]) -> bool:
        """Evaluate a conditional dependency."""
        try:
            # Simple condition evaluation - can be extended
            if 'success' in condition.lower():
                return result.get('success', False)
            elif 'error' in condition.lower():
                return 'error' in result
            return True
        except Exception:
            return False

    def calculate_current_priority(self) -> float:
        """Calculate current priority score based on all factors."""
        # Use user override if specified
        if self.user_priority_override is not None:
            return self.user_priority_override

        # Calculate priority based on metadata
        pm = self.priority_metadata

        priority_score = (
            pm.base_priority * 0.2 +
            pm.urgency_score * 0.25 +
            pm.importance_score * 0.15 +
            pm.resource_availability_score * 0.15 +
            pm.dependency_pressure_score * 0.10 +
            pm.performance_bonus_score * 0.10 +
            pm.context_importance_score * 0.05
        )

        # Clamp to 0-100 range
        pm.calculated_priority = max(0.0, min(100.0, priority_score))
        pm.last_priority_update = datetime.utcnow()

        return pm.calculated_priority

    def update_metrics(self, execution_success: bool, execution_time: Optional[float] = None):
        """Update performance metrics after execution."""
        self.metrics.success_rate_history.append(execution_success)

        if execution_time is not None:
            self.metrics.execution_time_seconds = execution_time
            # Update rolling average
            history_count = len(self.metrics.success_rate_history)
            if history_count > 0:
                self.metrics.average_execution_time = (
                    (self.metrics.average_execution_time * (history_count - 1)) + execution_time
                ) / history_count

        # Calculate performance score
        recent_history = self.metrics.success_rate_history[-10:]  # Last 10 executions
        if recent_history:
            success_rate = sum(recent_history) / len(recent_history)
            speed_factor = min(1.0, 60.0 / max(self.metrics.average_execution_time, 1))  # Faster is better
            self.metrics.performance_score = (success_rate + speed_factor) / 2

    def get_resource_utilization(self) -> Dict[str, float]:
        """Get current resource utilization."""
        return {
            'cpu_percent': self.metrics.resource_utilization.get('cpu_percent', 0.0),
            'memory_percent': self.metrics.resource_utilization.get('memory_percent', 0.0),
            'storage_mb': self.metrics.resource_utilization.get('storage_mb', 0.0),
            'network_utilization': self.metrics.resource_utilization.get('network_utilization', 0.0)
        }

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'task_id': self.task_id,
            'description': self.description,
            'task_state': self.task_state.value,
            'priority': self.calculate_current_priority(),
            'created_at': self.started_at.isoformat() if self.started_at else None,
            'dependencies_count': len(self.dependencies),
            'resource_requirements': {
                'cpu_cores': self.resource_requirements.cpu_cores,
                'memory_mb': self.resource_requirements.memory_mb,
                'estimated_duration': self.resource_requirements.estimated_duration_seconds
            },
            'tags': self.tags,
            'assigned_agent': self.assigned_agent,
            'performance_score': self.metrics.performance_score
        }

    def can_be_executed_now(self) -> bool:
        """Check if task can be executed right now."""
        if not self.is_ready():
            return False

        # Check scheduling constraints
        now = datetime.utcnow()
        if self.scheduling_constraints.earliest_start_time:
            if now < self.scheduling_constraints.earliest_start_time:
                return False

        if self.scheduling_constraints.latest_end_time:
            estimated_end = now + timedelta(seconds=self.resource_requirements.estimated_duration_seconds)
            if estimated_end > self.scheduling_constraints.latest_end_time:
                return False

        return True

    def get_estimated_completion_time(self) -> Optional[datetime]:
        """Get estimated completion time."""
        if not self.actual_start_time:
            return None

        return self.actual_start_time + timedelta(seconds=self.resource_requirements.estimated_duration_seconds)

    def add_tag(self, tag: str):
        """Add a tag to the task."""
        if tag not in self.tags:
            self.tags.append(tag)

    def remove_tag(self, tag: str):
        """Remove a tag from the task."""
        if tag in self.tags:
            self.tags.remove(tag)

    def set_custom_property(self, key: str, value: Any):
        """Set a custom property."""
        self.custom_properties[key] = value

    def get_custom_property(self, key: str, default: Any = None) -> Any:
        """Get a custom property."""
        return self.custom_properties.get(key, default)