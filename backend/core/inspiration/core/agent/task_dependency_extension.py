"""
🎯 TASK DEPENDENCY MANAGEMENT EXTENSION

Advanced task dependency management extension for Analysis and Task Engine.
Provides intelligent dependency resolution, graph analysis, and execution planning.

Features:
- Dynamic dependency injection based on task analysis
- Intelligent dependency suggestion using LLM
- Real-time dependency validation and cycle detection
- Performance-aware dependency resolution
- Context-based dependency optimization
"""

import asyncio
import logging
from typing import Dict, Any, List, Optional, Set, Tuple
from datetime import datetime
from collections import defaultdict

from .enhanced_task_models import EnhancedTaskInfo, TaskDependency, DependencyType
from .task_dependency_manager import TaskDependencyManager
from app.llm.router import get_llm_client

logger = logging.getLogger(__name__)


class TaskDependencyAnalyzer:
    """
    Advanced dependency analyzer using LLM for intelligent dependency detection
    and suggestion based on task content analysis.
    """

    def __init__(self):
        self.llm_client = None
        self.dependency_cache: Dict[str, List[Dict[str, Any]]] = {}
        self.analysis_cache_ttl = 3600  # 1 hour
        self.cache_timestamps: Dict[str, datetime] = {}

    async def initialize(self):
        """Initialize the dependency analyzer."""
        try:
            self.llm_client = await get_llm_client()
            logger.info("TaskDependencyAnalyzer initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize TaskDependencyAnalyzer: {e}")
            raise

    async def analyze_task_dependencies(self, task_description: str,
                                      context: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Analyze task description to identify potential dependencies using LLM.

        Args:
            task_description: The task to analyze
            context: Additional context for analysis

        Returns:
            Analysis results with suggested dependencies and reasoning
        """
        try:
            # Check cache first
            cache_key = self._generate_cache_key(task_description, context)
            if self._is_cache_valid(cache_key):
                logger.debug(f"Using cached dependency analysis for: {task_description[:50]}...")
                return self.dependency_cache[cache_key]

            # Prepare analysis prompt
            analysis_prompt = self._build_analysis_prompt(task_description, context)

            # Get LLM analysis
            response = await self.llm_client.generate_text(
                prompt=analysis_prompt,
                max_tokens=1000,
                temperature=0.3
            )

            # Parse and validate analysis
            analysis_result = self._parse_llm_analysis(response, task_description)

            # Cache the result
            self.dependency_cache[cache_key] = analysis_result
            self.cache_timestamps[cache_key] = datetime.utcnow()

            # Clean old cache entries
            await self._cleanup_cache()

            logger.info(f"Analyzed dependencies for task: {task_description[:50]}...")
            return analysis_result

        except Exception as e:
            logger.error(f"Error analyzing task dependencies: {e}")
            return self._get_fallback_analysis(task_description)

    def _build_analysis_prompt(self, task_description: str, context: Dict[str, Any] = None) -> str:
        """Build analysis prompt for LLM."""
        context_str = ""
        if context:
            context_str = f"\nContext: {context}"

        return f"""
Analyze the following task and identify what other tasks or prerequisites would be needed to complete it successfully.

Task: {task_description}{context_str}

Please provide analysis in the following JSON format:
{{
    "dependencies": [
        {{
            "type": "prerequisite|resource|information|coordination",
            "description": "Brief description of what is needed",
            "importance": "critical|high|medium|low",
            "reasoning": "Why this dependency is needed",
            "estimated_effort": "small|medium|large",
            "parallel_possible": true/false
        }}
    ],
    "execution_strategy": {{
        "sequential_steps": ["step1", "step2", "step3"],
        "parallel_groups": [["task1", "task2"], ["task3"]],
        "critical_path": ["most_important_step"]
    }},
    "risks": [
        {{
            "risk": "Potential problem",
            "impact": "high|medium|low",
            "mitigation": "How to handle it"
        }}
    ],
    "estimated_complexity": "low|medium|high",
    "suggested_dependencies_count": 3-5
}}

Focus on identifying:
1. Data or information prerequisites
2. System or tool requirements
3. Coordination with other teams/processes
4. Quality assurance steps
5. Documentation requirements

Be specific and actionable in your analysis.
"""

    def _parse_llm_analysis(self, llm_response: str, original_task: str) -> Dict[str, Any]:
        """Parse LLM analysis response."""
        try:
            # Extract JSON from response (LLM might add extra text)
            json_start = llm_response.find('{')
            json_end = llm_response.rfind('}') + 1

            if json_start == -1 or json_end == 0:
                raise ValueError("No JSON found in LLM response")

            json_str = llm_response[json_start:json_end]
            analysis = json.loads(json_str)

            # Validate and enhance analysis
            return self._validate_and_enhance_analysis(analysis, original_task)

        except (json.JSONDecodeError, ValueError) as e:
            logger.warning(f"Failed to parse LLM analysis: {e}")
            return self._get_fallback_analysis(original_task)

    def _validate_and_enhance_analysis(self, analysis: Dict[str, Any], original_task: str) -> Dict[str, Any]:
        """Validate and enhance the LLM analysis."""
        validated = {
            'task_description': original_task,
            'dependencies': [],
            'execution_strategy': {},
            'risks': [],
            'estimated_complexity': 'medium',
            'analysis_timestamp': datetime.utcnow().isoformat(),
            'confidence_score': 0.8
        }

        # Validate dependencies
        if 'dependencies' in analysis:
            for dep in analysis['dependencies'][:5]:  # Limit to 5 dependencies
                validated_dep = {
                    'type': dep.get('type', 'prerequisite'),
                    'description': dep.get('description', ''),
                    'importance': dep.get('importance', 'medium'),
                    'reasoning': dep.get('reasoning', ''),
                    'estimated_effort': dep.get('estimated_effort', 'medium'),
                    'parallel_possible': dep.get('parallel_possible', True)
                }
                validated['dependencies'].append(validated_dep)

        # Validate execution strategy
        if 'execution_strategy' in analysis:
            validated['execution_strategy'] = analysis['execution_strategy']

        # Validate risks
        if 'risks' in analysis:
            validated['risks'] = analysis['risks'][:3]  # Limit to 3 risks

        # Set complexity
        validated['estimated_complexity'] = analysis.get('estimated_complexity', 'medium')

        return validated

    def _get_fallback_analysis(self, task_description: str) -> Dict[str, Any]:
        """Provide fallback analysis when LLM fails."""
        return {
            'task_description': task_description,
            'dependencies': [
                {
                    'type': 'prerequisite',
                    'description': 'Basic requirements analysis',
                    'importance': 'medium',
                    'reasoning': 'Standard prerequisite for task completion',
                    'estimated_effort': 'small',
                    'parallel_possible': True
                }
            ],
            'execution_strategy': {
                'sequential_steps': ['analyze', 'execute', 'verify'],
                'parallel_groups': [],
                'critical_path': ['execute']
            },
            'risks': [
                {
                    'risk': 'Unexpected requirements',
                    'impact': 'medium',
                    'mitigation': 'Regular progress checks'
                }
            ],
            'estimated_complexity': 'medium',
            'analysis_timestamp': datetime.utcnow().isoformat(),
            'confidence_score': 0.5,
            'fallback': True
        }

    def _generate_cache_key(self, task_description: str, context: Dict[str, Any] = None) -> str:
        """Generate cache key for analysis."""
        import hashlib
        key_data = f"{task_description}_{str(sorted(context.items()) if context else '')}"
        return hashlib.md5(key_data.encode()).hexdigest()[:16]

    def _is_cache_valid(self, cache_key: str) -> bool:
        """Check if cache entry is still valid."""
        if cache_key not in self.cache_timestamps:
            return False

        age = datetime.utcnow() - self.cache_timestamps[cache_key]
        return age.total_seconds() < self.analysis_cache_ttl

    async def _cleanup_cache(self):
        """Clean up expired cache entries."""
        current_time = datetime.utcnow()
        expired_keys = [
            key for key, timestamp in self.cache_timestamps.items()
            if (current_time - timestamp).total_seconds() > self.analysis_cache_ttl
        ]

        for key in expired_keys:
            self.dependency_cache.pop(key, None)
            self.cache_timestamps.pop(key, None)

        if expired_keys:
            logger.debug(f"Cleaned up {len(expired_keys)} expired cache entries")


class IntelligentDependencyInjector:
    """
    Intelligent dependency injection system that analyzes task relationships
    and automatically suggests appropriate dependencies.
    """

    def __init__(self, dependency_manager: TaskDependencyManager):
        self.dependency_manager = dependency_manager
        self.injector_cache: Dict[str, List[str]] = {}

    async def inject_dependencies(self, task: EnhancedTaskInfo,
                                context_tasks: List[EnhancedTaskInfo] = None) -> List[TaskDependency]:
        """
        Intelligently inject dependencies for a task based on context and analysis.

        Args:
            task: The task to analyze for dependencies
            context_tasks: Other tasks in the same context

        Returns:
            List of suggested dependencies to inject
        """
        try:
            injected_dependencies = []

            # Analyze task content for implicit dependencies
            content_deps = await self._analyze_content_dependencies(task)
            injected_dependencies.extend(content_deps)

            # Analyze resource dependencies
            resource_deps = await self._analyze_resource_dependencies(task, context_tasks or [])
            injected_dependencies.extend(resource_deps)

            # Analyze temporal dependencies
            temporal_deps = await self._analyze_temporal_dependencies(task, context_tasks or [])
            injected_dependencies.extend(temporal_deps)

            # Filter and validate dependencies
            validated_deps = await self._validate_dependency_injections(task, injected_dependencies)

            logger.info(f"Injected {len(validated_deps)} dependencies for task {task.task_id}")
            return validated_deps

        except Exception as e:
            logger.error(f"Error injecting dependencies: {e}")
            return []

    async def _analyze_content_dependencies(self, task: EnhancedTaskInfo) -> List[TaskDependency]:
        """Analyze task content for implicit dependencies."""
        dependencies = []

        content_lower = task.description.lower()

        # Data dependencies
        if any(word in content_lower for word in ['analyze', 'report', 'data', 'statistics']):
            dependencies.append(self._create_dependency(
                task.task_id,
                f"data_collection_{task.task_id}",
                DependencyType.SOFT,
                "Data collection and preparation"
            ))

        # Documentation dependencies
        if any(word in content_lower for word in ['document', 'write', 'create', 'design']):
            dependencies.append(self._create_dependency(
                task.task_id,
                f"documentation_review_{task.task_id}",
                DependencyType.SOFT,
                "Documentation review and approval"
            ))

        # Testing dependencies
        if any(word in content_lower for word in ['implement', 'build', 'develop', 'code']):
            dependencies.append(self._create_dependency(
                task.task_id,
                f"testing_{task.task_id}",
                DependencyType.SOFT,
                "Testing and quality assurance"
            ))

        return dependencies

    async def _analyze_resource_dependencies(self, task: EnhancedTaskInfo,
                                           context_tasks: List[EnhancedTaskInfo]) -> List[TaskDependency]:
        """Analyze resource dependencies with other tasks."""
        dependencies = []

        # Check for resource conflicts
        for other_task in context_tasks:
            if self._has_resource_conflict(task, other_task):
                dependencies.append(self._create_dependency(
                    task.task_id,
                    other_task.task_id,
                    DependencyType.RESOURCE,
                    f"Resource conflict resolution with {other_task.task_id}"
                ))

        # Check for shared resource requirements
        for other_task in context_tasks:
            if self._shares_resources(task, other_task):
                dependencies.append(self._create_dependency(
                    task.task_id,
                    other_task.task_id,
                    DependencyType.SOFT,
                    f"Coordinated resource usage with {other_task.task_id}"
                ))

        return dependencies

    async def _analyze_temporal_dependencies(self, task: EnhancedTaskInfo,
                                           context_tasks: List[EnhancedTaskInfo]) -> List[TaskDependency]:
        """Analyze temporal dependencies and scheduling constraints."""
        dependencies = []

        # Check deadline dependencies
        for other_task in context_tasks:
            if self._has_temporal_dependency(task, other_task):
                dep_type = DependencyType.HARD if task.scheduling_constraints.latest_end_time else DependencyType.SOFT
                dependencies.append(self._create_dependency(
                    task.task_id,
                    other_task.task_id,
                    dep_type,
                    f"Temporal dependency with {other_task.task_id}"
                ))

        return dependencies

    def _create_dependency(self, task_id: str, depends_on_id: str,
                          dep_type: DependencyType, description: str) -> TaskDependency:
        """Create a standardized dependency object."""
        import uuid
        return TaskDependency(
            dependency_id=f"dep_{uuid.uuid4().hex[:8]}",
            task_id=depends_on_id,  # This task depends on depends_on_id
            dependent_task_id=task_id,
            dependency_type=dep_type,
            condition=description
        )

    def _has_resource_conflict(self, task1: EnhancedTaskInfo, task2: EnhancedTaskInfo) -> bool:
        """Check if two tasks have resource conflicts."""
        req1 = task1.resource_requirements
        req2 = task2.resource_requirements

        # CPU conflict
        if req1.cpu_cores + req2.cpu_cores > 8:  # Assuming 8 CPU cores available
            return True

        # Memory conflict
        if req1.memory_mb + req2.memory_mb > 8192:  # Assuming 8GB available
            return True

        # Special resource conflicts
        special1 = set(req1.special_resources)
        special2 = set(req2.special_resources)
        if special1 & special2:  # Intersection means conflict
            return True

        return False

    def _shares_resources(self, task1: EnhancedTaskInfo, task2: EnhancedTaskInfo) -> bool:
        """Check if tasks share resource requirements."""
        return bool(
            set(task1.resource_requirements.special_resources) &
            set(task2.resource_requirements.special_resources)
        )

    def _has_temporal_dependency(self, task1: EnhancedTaskInfo, task2: EnhancedTaskInfo) -> bool:
        """Check if tasks have temporal dependencies."""
        # Simple heuristic: if both have deadlines within 1 hour of each other
        if (task1.scheduling_constraints.latest_end_time and
            task2.scheduling_constraints.latest_end_time):
            time_diff = abs((task1.scheduling_constraints.latest_end_time -
                           task2.scheduling_constraints.latest_end_time).total_seconds())
            return time_diff < 3600  # Within 1 hour

        return False

    async def _validate_dependency_injections(self, task: EnhancedTaskInfo,
                                            dependencies: List[TaskDependency]) -> List[TaskDependency]:
        """Validate and filter dependency injections."""
        validated = []

        for dep in dependencies:
            # Check for cycles
            if await self._would_create_cycle(dep):
                logger.debug(f"Skipping dependency that would create cycle: {dep.dependency_id}")
                continue

            # Check if dependency is reasonable
            if await self._is_reasonable_dependency(task, dep):
                validated.append(dep)
            else:
                logger.debug(f"Skipping unreasonable dependency: {dep.dependency_id}")

        return validated[:5]  # Limit to 5 injected dependencies

    async def _would_create_cycle(self, dependency: TaskDependency) -> bool:
        """Check if adding this dependency would create a cycle."""
        try:
            # Temporarily add dependency to check for cycles
            await self.dependency_manager.add_dependency(
                dependency.task_id,
                dependency.dependent_task_id,
                dependency.dependency_type
            )

            # Check for cycles
            cycles = await self.dependency_manager.detect_cycles()

            # Remove the temporary dependency
            await self.dependency_manager.remove_dependency(dependency.dependency_id)

            return len(cycles) > 0

        except Exception:
            return True  # Assume cycle if check fails

    async def _is_reasonable_dependency(self, task: EnhancedTaskInfo, dependency: TaskDependency) -> bool:
        """Check if a dependency injection is reasonable."""
        # Basic heuristics for reasonable dependencies
        if len(task.dependencies) > 10:
            return False  # Too many dependencies already

        # Check if dependency type makes sense
        if dependency.dependency_type == DependencyType.HARD:
            # Hard dependencies should be truly critical
            return len(dependency.condition or "") > 20  # Detailed reasoning required

        return True


class TaskDependencyExtension:
    """
    Main extension class providing advanced task dependency management
    capabilities to the Analysis and Task Engine.
    """

    def __init__(self, dependency_manager: TaskDependencyManager):
        self.dependency_manager = dependency_manager
        self.analyzer = TaskDependencyAnalyzer()
        self.injector = IntelligentDependencyInjector(dependency_manager)

        self.statistics = {
            'dependencies_analyzed': 0,
            'dependencies_injected': 0,
            'cycles_prevented': 0,
            'execution_plans_generated': 0
        }

    async def initialize(self):
        """Initialize the dependency extension."""
        await self.analyzer.initialize()
        logger.info("TaskDependencyExtension initialized")

    async def analyze_and_enhance_task(self, task: EnhancedTaskInfo,
                                     context: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Analyze a task and enhance it with intelligent dependency suggestions.

        Args:
            task: Task to analyze and enhance
            context: Additional context for analysis

        Returns:
            Enhancement results with suggested improvements
        """
        try:
            self.statistics['dependencies_analyzed'] += 1

            # Analyze task for dependencies
            analysis = await self.analyzer.analyze_task_dependencies(task.description, context)

            # Inject intelligent dependencies
            context_tasks = context.get('related_tasks', []) if context else []
            injected_deps = await self.injector.inject_dependencies(task, context_tasks)

            # Create execution plan
            related_task_ids = [t.task_id for t in context_tasks] + [task.task_id]
            execution_plan = await self.dependency_manager.get_execution_plan(related_task_ids)

            enhancement_result = {
                'task_id': task.task_id,
                'analysis': analysis,
                'injected_dependencies': len(injected_deps),
                'execution_plan': execution_plan,
                'enhancement_confidence': analysis.get('confidence_score', 0.5),
                'estimated_complexity': analysis.get('estimated_complexity', 'medium'),
                'risks_identified': len(analysis.get('risks', [])),
                'enhancement_timestamp': datetime.utcnow().isoformat()
            }

            self.statistics['dependencies_injected'] += len(injected_deps)

            if execution_plan.get('success'):
                self.statistics['execution_plans_generated'] += 1

            logger.info(f"Enhanced task {task.task_id} with {len(injected_deps)} injected dependencies")
            return enhancement_result

        except Exception as e:
            logger.error(f"Error enhancing task: {e}")
            return {
                'task_id': task.task_id,
                'error': str(e),
                'enhancement_confidence': 0.0
            }

    async def optimize_execution_plan(self, task_ids: List[str],
                                    optimization_criteria: List[str] = None) -> Dict[str, Any]:
        """
        Optimize execution plan based on specified criteria.

        Args:
            task_ids: Tasks to optimize
            optimization_criteria: Criteria for optimization

        Returns:
            Optimized execution plan
        """
        try:
            # Get base execution plan
            base_plan = await self.dependency_manager.get_execution_plan(task_ids)

            if not base_plan.get('success'):
                return base_plan

            # Apply optimizations
            optimization_criteria = optimization_criteria or ['parallelism', 'resource_balance', 'critical_path']

            optimized_plan = await self.dependency_manager.optimize_execution_plan(task_ids)

            # Add extension-specific optimizations
            optimized_plan['extension_optimizations'] = {
                'dependency_injection_suggestions': await self._suggest_dependency_injections(task_ids),
                'parallelization_opportunities': await self._analyze_parallelization(task_ids),
                'resource_optimization': await self._optimize_resource_usage(task_ids)
            }

            logger.info(f"Optimized execution plan for {len(task_ids)} tasks")
            return optimized_plan

        except Exception as e:
            logger.error(f"Error optimizing execution plan: {e}")
            return {'error': str(e)}

    async def _suggest_dependency_injections(self, task_ids: List[str]) -> List[Dict[str, Any]]:
        """Suggest additional dependencies that could improve execution."""
        suggestions = []

        try:
            # Analyze patterns in task set
            for task_id in task_ids:
                if task_id in self.dependency_manager.graph.tasks:
                    task = self.dependency_manager.graph.tasks[task_id]

                    # Suggest testing dependencies for development tasks
                    if any(word in task.description.lower() for word in ['develop', 'implement', 'build']):
                        if not any('test' in dep.condition.lower() for dep in task.dependencies):
                            suggestions.append({
                                'task_id': task_id,
                                'suggested_dependency': 'testing_phase',
                                'type': 'quality_assurance',
                                'benefit': 'Improved reliability'
                            })

                    # Suggest documentation for complex tasks
                    if len(task.description) > 200:  # Complex task indicator
                        suggestions.append({
                            'task_id': task_id,
                            'suggested_dependency': 'documentation_review',
                            'type': 'compliance',
                            'benefit': 'Better maintainability'
                        })

        except Exception as e:
            logger.error(f"Error suggesting dependency injections: {e}")

        return suggestions[:5]  # Limit suggestions

    async def _analyze_parallelization(self, task_ids: List[str]) -> Dict[str, Any]:
        """Analyze opportunities for parallel execution."""
        try:
            parallel_groups = self.dependency_manager.graph.get_parallel_groups(task_ids)

            return {
                'parallel_groups_count': len(parallel_groups),
                'max_parallel_tasks': max(len(group) for group in parallel_groups) if parallel_groups else 0,
                'parallelization_efficiency': len(parallel_groups) / max(len(task_ids), 1),
                'bottleneck_tasks': await self._identify_bottlenecks(task_ids)
            }

        except Exception as e:
            logger.error(f"Error analyzing parallelization: {e}")
            return {'error': str(e)}

    async def _optimize_resource_usage(self, task_ids: List[str]) -> Dict[str, Any]:
        """Optimize resource usage across tasks."""
        try:
            conflicts = self.dependency_manager.graph.resolve_resource_conflicts(task_ids)

            optimization = {
                'resource_conflicts_count': len(conflicts),
                'optimization_suggestions': []
            }

            # Generate optimization suggestions
            for resource, conflicting_tasks in conflicts.items():
                if len(conflicting_tasks) > 1:
                    optimization['optimization_suggestions'].append({
                        'resource': resource,
                        'conflicting_tasks': conflicting_tasks,
                        'suggestion': f"Consider sequential execution or resource allocation for {resource}"
                    })

            return optimization

        except Exception as e:
            logger.error(f"Error optimizing resource usage: {e}")
            return {'error': str(e)}

    async def _identify_bottlenecks(self, task_ids: List[str]) -> List[str]:
        """Identify potential bottleneck tasks."""
        bottlenecks = []

        try:
            for task_id in task_ids:
                if task_id in self.dependency_manager.graph.tasks:
                    dependents = self.dependency_manager.graph.get_dependents(task_id)
                    if len(dependents) > 3:  # Many tasks depend on this one
                        bottlenecks.append(task_id)

        except Exception as e:
            logger.error(f"Error identifying bottlenecks: {e}")

        return bottlenecks

    def get_extension_statistics(self) -> Dict[str, Any]:
        """Get statistics about the dependency extension."""
        return {
            **self.statistics,
            'cache_size': len(self.analyzer.dependency_cache),
            'active_injections': len(self.injector.injector_cache),
            'uptime': 'active'  # Could be enhanced with actual uptime tracking
        }

    async def cleanup(self):
        """Clean up extension resources."""
        try:
            # Clear caches
            self.analyzer.dependency_cache.clear()
            self.analyzer.cache_timestamps.clear()
            self.injector.injector_cache.clear()

            logger.info("TaskDependencyExtension cleaned up")

        except Exception as e:
            logger.error(f"Error during cleanup: {e}")