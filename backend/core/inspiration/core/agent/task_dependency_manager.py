"""
🎯 TASK DEPENDENCY MANAGER

Advanced dependency management system for task relationships:
- Dependency graph management and traversal
- Cycle detection and resolution
- Parallel execution planning
- Resource conflict resolution
- Dynamic dependency injection
"""

import asyncio
import logging
from typing import Dict, Any, List, Optional, Set, Tuple
from collections import defaultdict, deque
from datetime import datetime

from .enhanced_task_models import (
    EnhancedTaskInfo,
    TaskDependency,
    DependencyType,
    TaskState
)

logger = logging.getLogger(__name__)


class DependencyGraph:
    """
    Graph representation of task dependencies.

    Provides efficient traversal and analysis of dependency relationships.
    """

    def __init__(self):
        """Initialize empty dependency graph."""
        self.adjacency_list: Dict[str, List[str]] = defaultdict(list)  # task_id -> [dependent_task_ids]
        self.reverse_adjacency: Dict[str, List[str]] = defaultdict(list)  # task_id -> [dependency_task_ids]
        self.tasks: Dict[str, EnhancedTaskInfo] = {}  # task_id -> task
        self.dependencies: Dict[str, TaskDependency] = {}  # dependency_id -> dependency

    def add_task(self, task: EnhancedTaskInfo) -> None:
        """Add a task to the graph."""
        self.tasks[task.task_id] = task

        # Add existing dependencies to graph structure
        for dependency in task.dependencies:
            self._add_dependency_edge(dependency)

    def add_dependency(self, dependency: TaskDependency) -> None:
        """Add a dependency relationship."""
        self._add_dependency_edge(dependency)
        self.dependencies[dependency.dependency_id] = dependency

        # Update task dependency lists
        if dependency.task_id in self.tasks:
            self.tasks[dependency.task_id].dependencies.append(dependency)
        if dependency.dependent_task_id in self.tasks:
            self.tasks[dependency.dependent_task_id].dependents.append(dependency.task_id)

    def _add_dependency_edge(self, dependency: TaskDependency) -> None:
        """Add dependency edge to adjacency lists."""
        # dependency.task_id must complete before dependency.dependent_task_id can start
        self.adjacency_list[dependency.task_id].append(dependency.dependent_task_id)
        self.reverse_adjacency[dependency.dependent_task_id].append(dependency.task_id)

    def remove_dependency(self, dependency_id: str) -> bool:
        """Remove a dependency relationship."""
        if dependency_id not in self.dependencies:
            return False

        dependency = self.dependencies[dependency_id]

        # Remove from adjacency lists
        if dependency.dependent_task_id in self.reverse_adjacency[dependency.task_id]:
            self.reverse_adjacency[dependency.task_id].remove(dependency.dependent_task_id)

        if dependency.task_id in self.adjacency_list:
            if dependency.dependent_task_id in self.adjacency_list[dependency.task_id]:
                self.adjacency_list[dependency.task_id].remove(dependency.dependent_task_id)

        # Remove from task dependency lists
        if dependency.task_id in self.tasks:
            self.tasks[dependency.task_id].dependencies = [
                d for d in self.tasks[dependency.task_id].dependencies
                if d.dependency_id != dependency_id
            ]

        if dependency.dependent_task_id in self.tasks:
            if dependency.task_id in self.tasks[dependency.dependent_task_id].dependents:
                self.tasks[dependency.dependent_task_id].dependents.remove(dependency.task_id)

        # Remove from dependencies dict
        del self.dependencies[dependency_id]

        return True

    def get_dependencies(self, task_id: str) -> List[str]:
        """Get all tasks that the given task depends on."""
        return self.reverse_adjacency.get(task_id, [])

    def get_dependents(self, task_id: str) -> List[str]:
        """Get all tasks that depend on the given task."""
        return self.adjacency_list.get(task_id, [])

    def get_execution_order(self, task_ids: List[str]) -> List[str]:
        """
        Get execution order for a set of tasks considering dependencies.

        Returns tasks in order where dependencies are satisfied.
        """
        # Kahn's algorithm for topological sorting
        result = []
        in_degree = defaultdict(int)
        queue = deque()

        # Calculate in-degrees for the subgraph
        subgraph_tasks = set(task_ids)
        for task_id in subgraph_tasks:
            for dependent in self.get_dependents(task_id):
                if dependent in subgraph_tasks:
                    in_degree[dependent] += 1

        # Add tasks with no dependencies to queue
        for task_id in subgraph_tasks:
            if in_degree[task_id] == 0:
                queue.append(task_id)

        # Process queue
        while queue:
            task_id = queue.popleft()
            result.append(task_id)

            # Update in-degrees of dependents
            for dependent in self.get_dependents(task_id):
                if dependent in subgraph_tasks:
                    in_degree[dependent] -= 1
                    if in_degree[dependent] == 0:
                        queue.append(dependent)

        # Check for cycles
        if len(result) != len(subgraph_tasks):
            logger.warning("Cycle detected in dependency graph")
            return []  # Return empty list if cycle detected

        return result

    def detect_cycles(self) -> List[List[str]]:
        """Detect cycles in the dependency graph."""
        cycles = []
        visited = set()
        rec_stack = set()

        def dfs(node: str, path: List[str]) -> None:
            visited.add(node)
            rec_stack.add(node)
            path.append(node)

            for neighbor in self.adjacency_list[node]:
                if neighbor not in visited:
                    dfs(neighbor, path)
                elif neighbor in rec_stack:
                    # Cycle found
                    cycle_start = path.index(neighbor)
                    cycles.append(path[cycle_start:] + [neighbor])

            path.pop()
            rec_stack.remove(node)

        for node in self.adjacency_list:
            if node not in visited:
                dfs(node, [])

        return cycles

    def get_parallel_groups(self, task_ids: List[str]) -> List[List[str]]:
        """
        Group tasks into parallel execution groups.

        Returns list of lists where each inner list contains tasks
        that can be executed in parallel.
        """
        execution_order = self.get_execution_order(task_ids)
        if not execution_order:
            return []

        groups = []
        current_group = []

        for task_id in execution_order:
            # Check if this task can be added to current group
            can_add = True
            for existing_task in current_group:
                # Check if there's a dependency between tasks in current group
                if (task_id in self.get_dependents(existing_task) or
                    existing_task in self.get_dependents(task_id)):
                    can_add = False
                    break

            if can_add:
                current_group.append(task_id)
            else:
                if current_group:
                    groups.append(current_group)
                current_group = [task_id]

        if current_group:
            groups.append(current_group)

        return groups

    def resolve_resource_conflicts(self, task_ids: List[str]) -> Dict[str, List[str]]:
        """
        Resolve resource conflicts between tasks.

        Returns mapping of resource types to lists of conflicting task groups.
        """
        conflicts = defaultdict(list)

        # Group tasks by resource requirements
        resource_groups = defaultdict(list)

        for task_id in task_ids:
            if task_id in self.tasks:
                task = self.tasks[task_id]
                req = task.resource_requirements

                # Group by CPU requirements
                cpu_key = f"cpu_{req.cpu_cores}"
                resource_groups[cpu_key].append(task_id)

                # Group by memory requirements
                memory_key = f"memory_{req.memory_mb}"
                resource_groups[memory_key].append(task_id)

                # Group by special resources
                for special in req.special_resources:
                    resource_groups[f"special_{special}"].append(task_id)

        # Find conflicts within each resource group
        for resource_key, tasks_in_group in resource_groups.items():
            if len(tasks_in_group) > 1:
                conflicts[resource_key] = tasks_in_group

        return dict(conflicts)


class TaskDependencyManager:
    """
    Advanced task dependency management system.

    Handles complex dependency relationships, cycle detection,
    parallel execution planning, and resource conflict resolution.
    """

    def __init__(self):
        """Initialize dependency manager."""
        self.graph = DependencyGraph()
        self.execution_cache: Dict[str, List[str]] = {}  # Cache for execution orders
        self.parallel_cache: Dict[str, List[List[str]]] = {}  # Cache for parallel groups

        # Statistics
        self.stats = {
            'total_dependencies': 0,
            'cycles_detected': 0,
            'conflicts_resolved': 0,
            'parallel_groups_created': 0
        }

        logger.info("Initialized TaskDependencyManager")

    async def add_task(self, task: EnhancedTaskInfo) -> None:
        """Add a task to the dependency system."""
        self.graph.add_task(task)
        logger.debug(f"Added task {task.task_id} to dependency system")

    async def add_dependency(self, task_id: str, dependent_task_id: str,
                           dependency_type: DependencyType = DependencyType.HARD,
                           condition: Optional[str] = None) -> Optional[str]:
        """
        Add a dependency relationship between two tasks.

        Args:
            task_id: Task that must complete first
            dependent_task_id: Task that depends on the first
            dependency_type: Type of dependency
            condition: Optional condition for conditional dependencies

        Returns:
            Dependency ID if successful, None otherwise
        """
        import uuid

        # Validate tasks exist
        if task_id not in self.graph.tasks or dependent_task_id not in self.graph.tasks:
            logger.warning(f"Cannot add dependency: task(s) not found")
            return None

        # Check for cycles before adding
        dependency = TaskDependency(
            dependency_id=f"dep_{uuid.uuid4().hex[:8]}",
            task_id=task_id,
            dependent_task_id=dependent_task_id,
            dependency_type=dependency_type,
            condition=condition
        )

        # Temporarily add to check for cycles
        temp_graph = DependencyGraph()
        temp_graph.adjacency_list = self.graph.adjacency_list.copy()
        temp_graph.reverse_adjacency = self.graph.reverse_adjacency.copy()
        temp_graph.tasks = self.graph.tasks.copy()
        temp_graph.dependencies = self.graph.dependencies.copy()

        temp_graph.add_dependency(dependency)

        if temp_graph.detect_cycles():
            logger.warning(f"Cannot add dependency: would create cycle")
            return None

        # Add the dependency
        self.graph.add_dependency(dependency)
        self.stats['total_dependencies'] += 1

        # Clear caches
        self._clear_caches()

        logger.info(f"Added {dependency_type.value} dependency: {task_id} -> {dependent_task_id}")
        return dependency.dependency_id

    async def remove_dependency(self, dependency_id: str) -> bool:
        """Remove a dependency relationship."""
        success = self.graph.remove_dependency(dependency_id)
        if success:
            self.stats['total_dependencies'] -= 1
            self._clear_caches()
            logger.info(f"Removed dependency {dependency_id}")
        return success

    async def get_ready_tasks(self, task_ids: Optional[List[str]] = None) -> List[str]:
        """
        Get tasks that are ready to execute (all dependencies satisfied).

        Args:
            task_ids: Specific tasks to check, or None for all tasks

        Returns:
            List of task IDs that are ready to execute
        """
        target_tasks = task_ids or list(self.graph.tasks.keys())
        ready_tasks = []

        for task_id in target_tasks:
            if task_id not in self.graph.tasks:
                continue

            task = self.graph.tasks[task_id]
            dependencies_satisfied = True

            # Check hard dependencies
            for dependency in task.dependencies:
                if dependency.dependency_type == DependencyType.HARD:
                    dep_task = self.graph.tasks.get(dependency.task_id)
                    if not dep_task or dep_task.task_state != TaskState.COMPLETED:
                        dependencies_satisfied = False
                        break

            if dependencies_satisfied and task.can_be_executed_now():
                ready_tasks.append(task_id)

        return ready_tasks

    async def get_execution_plan(self, task_ids: List[str]) -> Dict[str, Any]:
        """
        Generate a complete execution plan for a set of tasks.

        Args:
            task_ids: Tasks to plan execution for

        Returns:
            Execution plan with order, parallel groups, and conflicts
        """
        cache_key = ",".join(sorted(task_ids))
        if cache_key in self.execution_cache:
            execution_order = self.execution_cache[cache_key]
        else:
            execution_order = self.graph.get_execution_order(task_ids)
            if execution_order:
                self.execution_cache[cache_key] = execution_order

        if not execution_order:
            return {
                'success': False,
                'error': 'Cannot create execution plan due to dependency cycles',
                'cycles': self.graph.detect_cycles()
            }

        # Get parallel execution groups
        if cache_key in self.parallel_cache:
            parallel_groups = self.parallel_cache[cache_key]
        else:
            parallel_groups = self.graph.get_parallel_groups(execution_order)
            if parallel_groups:
                self.parallel_cache[cache_key] = parallel_groups
                self.stats['parallel_groups_created'] += len(parallel_groups)

        # Check for resource conflicts
        conflicts = self.graph.resolve_resource_conflicts(task_ids)
        if conflicts:
            self.stats['conflicts_resolved'] += len(conflicts)

        return {
            'success': True,
            'execution_order': execution_order,
            'parallel_groups': parallel_groups,
            'resource_conflicts': conflicts,
            'estimated_parallelism': len(parallel_groups) / max(len(execution_order), 1),
            'total_tasks': len(task_ids)
        }

    async def update_task_status(self, task_id: str, new_state: TaskState) -> List[str]:
        """
        Update task status and return newly ready tasks.

        Args:
            task_id: Task that changed status
            new_state: New task state

        Returns:
            List of tasks that are now ready to execute
        """
        if task_id not in self.graph.tasks:
            return []

        task = self.graph.tasks[task_id]
        task.update_state(new_state)

        # Update dependency satisfaction
        newly_ready = []
        for dependent_id in self.graph.get_dependents(task_id):
            if dependent_id in self.graph.tasks:
                dependent_task = self.graph.tasks[dependent_id]

                # Check if this task satisfies any dependencies
                for dependency in dependent_task.dependencies:
                    if dependency.task_id == task_id and task.satisfies_dependency(dependency):
                        dependency.satisfied = True
                        dependency.satisfied_at = datetime.utcnow()

                        # Check if dependent task is now ready
                        if await self._is_task_ready(dependent_task):
                            newly_ready.append(dependent_id)

        # Clear caches since dependencies may have changed
        self._clear_caches()

        if newly_ready:
            logger.info(f"Tasks now ready due to {task_id} completion: {newly_ready}")

        return newly_ready

    async def _is_task_ready(self, task: EnhancedTaskInfo) -> bool:
        """Check if a task is ready to execute."""
        for dependency in task.dependencies:
            if dependency.dependency_type == DependencyType.HARD and not dependency.satisfied:
                dep_task = self.graph.tasks.get(dependency.task_id)
                if not dep_task or not task.satisfies_dependency(dependency):
                    return False
        return True

    def _clear_caches(self) -> None:
        """Clear execution and parallel caches."""
        self.execution_cache.clear()
        self.parallel_cache.clear()

    async def detect_cycles(self) -> List[List[str]]:
        """Detect cycles in the dependency graph."""
        cycles = self.graph.detect_cycles()
        self.stats['cycles_detected'] = len(cycles)
        return cycles

    async def get_dependency_stats(self) -> Dict[str, Any]:
        """Get dependency statistics."""
        dependency_types = defaultdict(int)
        for dependency in self.graph.dependencies.values():
            dependency_types[dependency.dependency_type.value] += 1

        return {
            'total_dependencies': self.stats['total_dependencies'],
            'dependency_types': dict(dependency_types),
            'total_tasks': len(self.graph.tasks),
            'cycles_detected': self.stats['cycles_detected'],
            'conflicts_resolved': self.stats['conflicts_resolved'],
            'parallel_groups_created': self.stats['parallel_groups_created']
        }

    async def validate_dependencies(self, task_ids: List[str]) -> Dict[str, Any]:
        """
        Validate dependency relationships for a set of tasks.

        Args:
            task_ids: Tasks to validate

        Returns:
            Validation results
        """
        validation_results = {
            'valid': True,
            'errors': [],
            'warnings': [],
            'cycles': [],
            'missing_tasks': []
        }

        # Check for missing tasks
        for task_id in task_ids:
            if task_id not in self.graph.tasks:
                validation_results['missing_tasks'].append(task_id)
                validation_results['errors'].append(f"Task {task_id} not found")

        if validation_results['missing_tasks']:
            validation_results['valid'] = False
            return validation_results

        # Check for cycles
        cycles = await self.detect_cycles()
        if cycles:
            validation_results['cycles'] = cycles
            validation_results['errors'].append(f"Dependency cycles detected: {len(cycles)}")

        # Check dependency satisfaction
        for task_id in task_ids:
            task = self.graph.tasks[task_id]
            for dependency in task.dependencies:
                if dependency.task_id not in self.graph.tasks:
                    validation_results['warnings'].append(
                        f"Dependency {dependency.dependency_id}: referenced task {dependency.task_id} not found"
                    )

        validation_results['valid'] = len(validation_results['errors']) == 0
        return validation_results

    async def optimize_execution_plan(self, task_ids: List[str]) -> Dict[str, Any]:
        """
        Optimize execution plan for better performance.

        Args:
            task_ids: Tasks to optimize

        Returns:
            Optimized execution plan
        """
        base_plan = await self.get_execution_plan(task_ids)

        if not base_plan['success']:
            return base_plan

        optimization = {
            'original_parallelism': base_plan['estimated_parallelism'],
            'resource_balancing': await self._optimize_resource_balancing(task_ids),
            'dependency_reduction': await self._optimize_dependency_reduction(task_ids),
            'estimated_improvement': 0.0
        }

        # Calculate estimated improvement
        parallelism_improvement = optimization['resource_balancing']['parallelism_gain']
        dependency_improvement = optimization['dependency_reduction']['dependencies_removed'] * 0.1

        optimization['estimated_improvement'] = min(parallelism_improvement + dependency_improvement, 50.0)

        return {
            **base_plan,
            'optimization': optimization,
            'optimized_parallelism': base_plan['estimated_parallelism'] + optimization['estimated_improvement'] / 100
        }

    async def _optimize_resource_balancing(self, task_ids: List[str]) -> Dict[str, Any]:
        """Optimize resource balancing for parallel execution."""
        conflicts = self.graph.resolve_resource_conflicts(task_ids)

        balancing = {
            'resource_conflicts': len(conflicts),
            'parallelism_gain': 0.0,
            'balancing_suggestions': []
        }

        # Simple balancing suggestions
        for resource, conflicting_tasks in conflicts.items():
            if len(conflicting_tasks) > 1:
                balancing['balancing_suggestions'].append({
                    'resource': resource,
                    'conflicting_tasks': conflicting_tasks,
                    'suggestion': f"Consider sequential execution or resource allocation for {resource}"
                })
                balancing['parallelism_gain'] += 5.0  # Estimated gain per resolved conflict

        return balancing

    async def _optimize_dependency_reduction(self, task_ids: List[str]) -> Dict[str, Any]:
        """Optimize by reducing unnecessary dependencies."""
        reduction = {
            'dependencies_removed': 0,
            'optimization_suggestions': []
        }

        # Check for soft dependencies that could be removed
        for task_id in task_ids:
            if task_id in self.graph.tasks:
                task = self.graph.tasks[task_id]
                soft_deps = [d for d in task.dependencies if d.dependency_type == DependencyType.SOFT]

                if len(soft_deps) > 2:  # If too many soft dependencies
                    reduction['optimization_suggestions'].append({
                        'task': task_id,
                        'suggestion': f"Review {len(soft_deps)} soft dependencies for potential reduction"
                    })

        return reduction