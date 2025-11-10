"""
Optimization Engine - Self-tuning and benchmarking system.
Continuously benchmarks components and optimizes performance automatically.
"""

import logging
import asyncio
import time
import statistics
import json
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
import psutil

from app.config.settings import get_settings
from app.core.error_handler import safe_execute

from ...registry.dynamic_registry import dynamic_registry, ComponentStatus
from ...intelligence.audit_logger import audit_logger
from app.core.skill_executor import execute_skill # Added top-level import

logger = logging.getLogger(__name__)
settings = get_settings()


class BenchmarkType(Enum):
    """Types of benchmarks."""
    PERFORMANCE = "performance"
    MEMORY = "memory"
    ACCURACY = "accuracy"
    RELIABILITY = "reliability"
    LATENCY = "latency"
    THROUGHPUT = "throughput"


class OptimizationStrategy(Enum):
    """Optimization strategies."""
    PARAMETER_TUNING = "parameter_tuning"
    ALGORITHM_REPLACEMENT = "algorithm_replacement"
    CACHING = "caching"
    PARALLELIZATION = "parallelization"
    RESOURCE_ALLOCATION = "resource_allocation"
    CODE_OPTIMIZATION = "code_optimization"


@dataclass
class BenchmarkResult:
    """Result of a benchmark test."""
    component_name: str
    benchmark_type: BenchmarkType
    score: float
    unit: str
    timestamp: datetime
    test_data: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PerformanceMetrics:
    """Performance metrics for a component."""
    component_name: str
    execution_time: float
    memory_usage: float
    cpu_usage: float
    success_rate: float
    error_count: int
    total_executions: int
    last_updated: datetime
    trend: str = "stable"  # "improving", "degrading", "stable"


@dataclass
class OptimizationResult:
    """Result of an optimization attempt."""
    component_name: str
    strategy: OptimizationStrategy
    before_score: float
    after_score: float
    improvement: float
    timestamp: datetime
    success: bool
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ABTestVariant:
    """A/B test variant."""
    variant_id: str
    component_name: str
    variant_code: str
    variant_params: Dict[str, Any]
    test_results: List[BenchmarkResult] = field(default_factory=list)
    active: bool = True
    created_at: datetime = field(default_factory=datetime.now)


class OptimizationEngine:
    """
    Self-tuning and benchmarking system.
    Continuously monitors performance and applies optimizations.
    """
    
    def __init__(self):
        self.benchmark_results: Dict[str, List[BenchmarkResult]] = {}
        self.performance_metrics: Dict[str, PerformanceMetrics] = {}
        self.optimization_results: List[OptimizationResult] = []
        self.ab_test_variants: Dict[str, List[ABTestVariant]] = {}
        
        # Configuration
        self.config = {
            "benchmark_interval": 3600,  # 1 hour
            "optimization_threshold": 0.1,  # 10% improvement needed
            "ab_test_duration": 86400,  # 24 hours
            "max_variants_per_component": 3,
            "performance_history_days": 30,
            "auto_optimization_enabled": True,
            "benchmark_timeout": 300  # 5 minutes
        }
        
        # Benchmark test cases
        self.test_cases = {
            "small_data": {"size": 100, "complexity": "low"},
            "medium_data": {"size": 1000, "complexity": "medium"},
            "large_data": {"size": 10000, "complexity": "high"},
            "stress_test": {"size": 50000, "complexity": "extreme"}
        }
        
        # Statistics
        self.stats = {
            "total_benchmarks": 0,
            "total_optimizations": 0,
            "successful_optimizations": 0,
            "active_ab_tests": 0,
            "average_improvement": 0.0,
            "last_benchmark_run": None
        }
    
    async def initialize(self):
        """Initialize the optimization engine."""
        
        try:
            # Load existing data
            await self._load_optimization_data()
            
            # Start background tasks
            asyncio.create_task(self._continuous_benchmarking())
            asyncio.create_task(self._optimization_monitor())
            asyncio.create_task(self._ab_test_manager())
            
            logger.info("Optimization engine initialized")
            
        except Exception as e:
            logger.error(f"Failed to initialize optimization engine: {e}")
            raise
    
    async def benchmark_component(
        self, 
        component_name: str, 
        benchmark_types: List[BenchmarkType] = None
    ) -> Dict[str, BenchmarkResult]:
        """Benchmark a specific component."""
        
        if benchmark_types is None:
            benchmark_types = [BenchmarkType.PERFORMANCE, BenchmarkType.MEMORY]
        
        results = {}
        
        try:
            logger.info(f"Benchmarking component: {component_name}")
            
            # Get component
            component_entry = dynamic_registry.get_component(component_name)
            if not component_entry or component_entry.status != ComponentStatus.ACTIVE:
                logger.error(f"Component not active: {component_name}")
                return {}
            
            for benchmark_type in benchmark_types:
                try:
                    result = await self._run_benchmark(component_name, benchmark_type)
                    if result:
                        results[benchmark_type.value] = result
                        
                        # Store result
                        if component_name not in self.benchmark_results:
                            self.benchmark_results[component_name] = []
                        self.benchmark_results[component_name].append(result)
                        
                        # Keep only recent results
                        cutoff_date = datetime.now() - timedelta(days=self.config["performance_history_days"])
                        self.benchmark_results[component_name] = [
                            r for r in self.benchmark_results[component_name]
                            if r.timestamp > cutoff_date
                        ]
                        
                except Exception as e:
                    logger.error(f"Error benchmarking {component_name} for {benchmark_type}: {e}")
            
            # Update performance metrics
            await self._update_performance_metrics(component_name, results)
            
            self.stats["total_benchmarks"] += len(results)
            self.stats["last_benchmark_run"] = datetime.now()
            
            logger.info(f"Benchmark completed for {component_name}: {len(results)} tests")
            return results
            
        except Exception as e:
            logger.error(f"Error benchmarking component {component_name}: {e}")
            return {}
    
    async def _run_benchmark(self, component_name: str, benchmark_type: BenchmarkType) -> Optional[BenchmarkResult]:
        """Run a specific benchmark test."""
        
        try:
            if benchmark_type == BenchmarkType.PERFORMANCE:
                return await self._benchmark_performance(component_name)
            elif benchmark_type == BenchmarkType.MEMORY:
                return await self._benchmark_memory(component_name)
            elif benchmark_type == BenchmarkType.LATENCY:
                return await self._benchmark_latency(component_name)
            elif benchmark_type == BenchmarkType.THROUGHPUT:
                return await self._benchmark_throughput(component_name)
            elif benchmark_type == BenchmarkType.RELIABILITY:
                return await self._benchmark_reliability(component_name)
            else:
                logger.warning(f"Unsupported benchmark type: {benchmark_type}")
                return None
                
        except Exception as e:
            logger.error(f"Error running {benchmark_type} benchmark: {e}")
            return None
    
    async def _benchmark_performance(self, component_name: str) -> Optional[BenchmarkResult]:
        """Benchmark component performance (execution time)."""
        
        try:
            # execute_skill is now imported at the top level
            execution_times = []
            
            # Run multiple test cases
            for test_case_name, test_data in self.test_cases.items():
                try:
                    # Create test request
                    test_request = f"Test request for {test_case_name} with {test_data['size']} items"
                    
                    # Measure execution time
                    start_time = time.time()
                    
                    result = await asyncio.wait_for(
                        safe_execute(execute_skill, component_name, test_request, test_data),
                        timeout=self.config["benchmark_timeout"]
                    )
                    
                    end_time = time.time()
                    execution_time = end_time - start_time
                    
                    if result and result.get("success"):
                        execution_times.append(execution_time)
                    
                except asyncio.TimeoutError:
                    logger.warning(f"Benchmark timeout for {component_name} on {test_case_name}")
                except Exception as e:
                    logger.warning(f"Benchmark error for {component_name} on {test_case_name}: {e}")
            
            if not execution_times:
                return None
            
            # Calculate average execution time
            avg_time = statistics.mean(execution_times)
            
            return BenchmarkResult(
                component_name=component_name,
                benchmark_type=BenchmarkType.PERFORMANCE,
                score=avg_time,
                unit="seconds",
                timestamp=datetime.now(),
                test_data={
                    "execution_times": execution_times,
                    "test_cases": len(execution_times),
                    "min_time": min(execution_times),
                    "max_time": max(execution_times),
                    "std_dev": statistics.stdev(execution_times) if len(execution_times) > 1 else 0
                }
            )
            
        except Exception as e:
            logger.error(f"Error in performance benchmark: {e}")
            return None
    
    async def _benchmark_memory(self, component_name: str) -> Optional[BenchmarkResult]:
        """Benchmark component memory usage."""
        
        try:
            # execute_skill is now imported at the top level
            # Get initial memory usage
            process = psutil.Process()
            initial_memory = process.memory_info().rss
            
            memory_usages = []
            
            # Run test cases and monitor memory
            for test_case_name, test_data in self.test_cases.items():
                try:
                    test_request = f"Memory test for {test_case_name}"
                    
                    # Execute and monitor memory
                    before_memory = process.memory_info().rss
                    
                    result = await asyncio.wait_for(
                        safe_execute(execute_skill, component_name, test_request, test_data),
                        timeout=self.config["benchmark_timeout"]
                    )
                    
                    after_memory = process.memory_info().rss
                    memory_delta = after_memory - before_memory
                    
                    if result and result.get("success"):
                        memory_usages.append(memory_delta)
                    
                except Exception as e:
                    logger.warning(f"Memory benchmark error for {component_name}: {e}")
            
            if not memory_usages:
                return None
            
            # Calculate average memory usage
            avg_memory = statistics.mean(memory_usages)
            
            return BenchmarkResult(
                component_name=component_name,
                benchmark_type=BenchmarkType.MEMORY,
                score=avg_memory / 1024 / 1024,  # Convert to MB
                unit="MB",
                timestamp=datetime.now(),
                test_data={
                    "memory_usages": memory_usages,
                    "test_cases": len(memory_usages),
                    "peak_memory": max(memory_usages) / 1024 / 1024,
                    "min_memory": min(memory_usages) / 1024 / 1024
                }
            )
            
        except Exception as e:
            logger.error(f"Error in memory benchmark: {e}")
            return None
    
    async def _benchmark_latency(self, component_name: str) -> Optional[BenchmarkResult]:
        """Benchmark component latency (response time)."""
        
        try:
            # execute_skill is now imported at the top level
            latencies = []
            
            # Run quick latency tests
            for i in range(10):  # 10 quick tests
                try:
                    test_request = f"Latency test {i+1}"
                    test_data = {"size": 10, "quick_test": True}
                    
                    start_time = time.perf_counter()
                    
                    result = await asyncio.wait_for(
                        safe_execute(execute_skill, component_name, test_request, test_data),
                        timeout=30  # Shorter timeout for latency tests
                    )
                    
                    end_time = time.perf_counter()
                    latency = (end_time - start_time) * 1000  # Convert to milliseconds
                    
                    if result and result.get("success"):
                        latencies.append(latency)
                    
                except Exception as e:
                    logger.warning(f"Latency test error: {e}")
            
            if not latencies:
                return None
            
            avg_latency = statistics.mean(latencies)
            
            return BenchmarkResult(
                component_name=component_name,
                benchmark_type=BenchmarkType.LATENCY,
                score=avg_latency,
                unit="ms",
                timestamp=datetime.now(),
                test_data={
                    "latencies": latencies,
                    "p50": statistics.median(latencies),
                    "p95": sorted(latencies)[int(len(latencies) * 0.95)] if len(latencies) > 1 else latencies[0],
                    "p99": sorted(latencies)[int(len(latencies) * 0.99)] if len(latencies) > 1 else latencies[0]
                }
            )
            
        except Exception as e:
            logger.error(f"Error in latency benchmark: {e}")
            return None
    
    async def _benchmark_throughput(self, component_name: str) -> Optional[BenchmarkResult]:
        """Benchmark component throughput (requests per second)."""
        
        try:
            # execute_skill is now imported at the top level
            # Run concurrent requests to measure throughput
            test_duration = 30  # 30 seconds
            concurrent_requests = 5
            
            start_time = time.time()
            completed_requests = 0
            
            async def run_request():
                nonlocal completed_requests
                try:
                    test_request = "Throughput test request"
                    test_data = {"size": 100, "throughput_test": True}
                    
                    result = await safe_execute(execute_skill, component_name, test_request, test_data)
                    
                    if result and result.get("success"):
                        completed_requests += 1
                        
                except Exception as e:
                    logger.warning(f"Throughput test request failed: {e}")
            
            # Run concurrent requests for the test duration
            end_time = start_time + test_duration
            
            while time.time() < end_time:
                # Start concurrent requests
                tasks = [run_request() for _ in range(concurrent_requests)]
                await asyncio.gather(*tasks, return_exceptions=True)
                
                # Small delay to prevent overwhelming
                await asyncio.sleep(0.1)
            
            actual_duration = time.time() - start_time
            throughput = completed_requests / actual_duration
            
            return BenchmarkResult(
                component_name=component_name,
                benchmark_type=BenchmarkType.THROUGHPUT,
                score=throughput,
                unit="requests/second",
                timestamp=datetime.now(),
                test_data={
                    "completed_requests": completed_requests,
                    "test_duration": actual_duration,
                    "concurrent_requests": concurrent_requests
                }
            )
            
        except Exception as e:
            logger.error(f"Error in throughput benchmark: {e}")
            return None
    
    async def _benchmark_reliability(self, component_name: str) -> Optional[BenchmarkResult]:
        """Benchmark component reliability (success rate)."""
        
        try:
            # execute_skill is now imported at the top level
            total_tests = 50
            successful_tests = 0
            
            for i in range(total_tests):
                try:
                    test_request = f"Reliability test {i+1}"
                    test_data = {"size": 100, "reliability_test": True}
                    
                    result = await asyncio.wait_for(
                        safe_execute(execute_skill, component_name, test_request, test_data),
                        timeout=60
                    )
                    
                    if result and result.get("success"):
                        successful_tests += 1
                        
                except Exception as e:
                    logger.warning(f"Reliability test {i+1} failed: {e}")
            
            success_rate = (successful_tests / total_tests) * 100
            
            return BenchmarkResult(
                component_name=component_name,
                benchmark_type=BenchmarkType.RELIABILITY,
                score=success_rate,
                unit="percent",
                timestamp=datetime.now(),
                test_data={
                    "total_tests": total_tests,
                    "successful_tests": successful_tests,
                    "failed_tests": total_tests - successful_tests
                }
            )
            
        except Exception as e:
            logger.error(f"Error in reliability benchmark: {e}")
            return None
    
    async def _update_performance_metrics(self, component_name: str, benchmark_results: Dict[str, BenchmarkResult]):
        """Update performance metrics for a component."""
        
        try:
            # Get existing metrics or create new
            if component_name not in self.performance_metrics:
                self.performance_metrics[component_name] = PerformanceMetrics(
                    component_name=component_name,
                    execution_time=0.0,
                    memory_usage=0.0,
                    cpu_usage=0.0,
                    success_rate=0.0,
                    error_count=0,
                    total_executions=0,
                    last_updated=datetime.now()
                )
            
            metrics = self.performance_metrics[component_name]
            
            # Update metrics from benchmark results
            for result in benchmark_results.values():
                if result.benchmark_type == BenchmarkType.PERFORMANCE:
                    old_time = metrics.execution_time
                    metrics.execution_time = result.score
                    
                    # Determine trend
                    if old_time > 0:
                        if result.score < old_time * 0.9:
                            metrics.trend = "improving"
                        elif result.score > old_time * 1.1:
                            metrics.trend = "degrading"
                        else:
                            metrics.trend = "stable"
                
                elif result.benchmark_type == BenchmarkType.MEMORY:
                    metrics.memory_usage = result.score
                
                elif result.benchmark_type == BenchmarkType.RELIABILITY:
                    metrics.success_rate = result.score
            
            metrics.last_updated = datetime.now()
            metrics.total_executions += 1
            
        except Exception as e:
            logger.error(f"Error updating performance metrics: {e}")
    
    async def optimize_component(self, component_name: str) -> Optional[OptimizationResult]:
        """Attempt to optimize a component."""
        
        if not self.config["auto_optimization_enabled"]:
            logger.debug("Auto-optimization disabled")
            return None
        
        try:
            logger.info(f"Attempting optimization for: {component_name}")
            
            # Get current performance
            current_metrics = self.performance_metrics.get(component_name)
            if not current_metrics:
                logger.warning(f"No performance metrics for {component_name}")
                return None
            
            # Determine optimization strategy
            strategy = await self._determine_optimization_strategy(component_name, current_metrics)
            
            if not strategy:
                logger.debug(f"No optimization strategy determined for {component_name}")
                return None
            
            # Get baseline score
            baseline_result = await self.benchmark_component(component_name, [BenchmarkType.PERFORMANCE])
            if not baseline_result:
                logger.error(f"Failed to get baseline benchmark for {component_name}")
                return None
            
            baseline_score = baseline_result[BenchmarkType.PERFORMANCE.value].score
            
            # Apply optimization
            optimization_success = await self._apply_optimization(component_name, strategy)
            
            if not optimization_success:
                logger.error(f"Failed to apply optimization for {component_name}")
                return None
            
            # Benchmark after optimization
            await asyncio.sleep(5)  # Allow time for changes to take effect
            
            optimized_result = await self.benchmark_component(component_name, [BenchmarkType.PERFORMANCE])
            if not optimized_result:
                logger.error(f"Failed to get post-optimization benchmark for {component_name}")
                return None
            
            optimized_score = optimized_result[BenchmarkType.PERFORMANCE.value].score
            
            # Calculate improvement (lower is better for execution time)
            improvement = (baseline_score - optimized_score) / baseline_score * 100
            
            # Create optimization result
            result = OptimizationResult(
                component_name=component_name,
                strategy=strategy,
                before_score=baseline_score,
                after_score=optimized_score,
                improvement=improvement,
                timestamp=datetime.now(),
                success=improvement > self.config["optimization_threshold"]
            )
            
            self.optimization_results.append(result)
            self.stats["total_optimizations"] += 1
            
            if result.success:
                self.stats["successful_optimizations"] += 1
                logger.info(f"Optimization successful for {component_name}: {improvement:.2f}% improvement")
            else:
                logger.info(f"Optimization had minimal impact for {component_name}: {improvement:.2f}%")
            
            # Update average improvement
            if self.optimization_results:
                self.stats["average_improvement"] = statistics.mean([
                    r.improvement for r in self.optimization_results if r.success
                ])
            
            return result
            
        except Exception as e:
            logger.error(f"Error optimizing component {component_name}: {e}")
            return None
    
    async def _determine_optimization_strategy(
        self, 
        component_name: str, 
        metrics: PerformanceMetrics
    ) -> Optional[OptimizationStrategy]:
        """Determine the best optimization strategy for a component."""
        
        try:
            # Simple heuristics for strategy selection
            if metrics.execution_time > 5.0:  # Slow execution
                return OptimizationStrategy.PERFORMANCE_TUNING
            
            elif metrics.memory_usage > 100:  # High memory usage
                return OptimizationStrategy.MEMORY_OPTIMIZATION
            
            elif metrics.success_rate < 95:  # Low reliability
                return OptimizationStrategy.ERROR_HANDLING
            
            elif metrics.trend == "degrading":  # Performance degrading
                return OptimizationStrategy.CODE_OPTIMIZATION
            
            else:
                # No clear optimization needed
                return None
                
        except Exception as e:
            logger.error(f"Error determining optimization strategy: {e}")
            return None
    
    async def _apply_optimization(self, component_name: str, strategy: OptimizationStrategy) -> bool:
        """Apply an optimization strategy to a component."""
        
        try:
            # This is a simplified implementation
            # In a real system, this would apply actual optimizations
            
            if strategy == OptimizationStrategy.PARAMETER_TUNING:
                return await self._tune_parameters(component_name)
            
            elif strategy == OptimizationStrategy.CACHING:
                return await self._add_caching(component_name)
            
            elif strategy == OptimizationStrategy.CODE_OPTIMIZATION:
                return await self._optimize_code(component_name)
            
            else:
                logger.warning(f"Optimization strategy not implemented: {strategy}")
                return False
                
        except Exception as e:
            logger.error(f"Error applying optimization: {e}")
            return False
    
    async def _tune_parameters(self, component_name: str) -> bool:
        """Tune component parameters for better performance."""
        
        # This would implement parameter tuning logic
        # For now, return True to simulate successful tuning
        logger.info(f"Parameter tuning applied to {component_name}")
        return True
    
    async def _add_caching(self, component_name: str) -> bool:
        """Add caching to improve component performance."""
        
        # This would implement caching logic
        logger.info(f"Caching optimization applied to {component_name}")
        return True
    
    async def _optimize_code(self, component_name: str) -> bool:
        """Optimize component code for better performance."""
        
        # This would implement code optimization
        logger.info(f"Code optimization applied to {component_name}")
        return True
    
    async def start_ab_test(self, component_name: str, variants: List[Dict[str, Any]]) -> str:
        """Start an A/B test for a component."""
        
        try:
            if not variants:
                logger.warning("Cannot start A/B test with empty variants")
                return ""
            
            test_id = f"ab_test_{component_name}_{int(datetime.now().timestamp())}"
            
            # Create test variants
            test_variants = []
            for i, variant_data in enumerate(variants):
                variant = ABTestVariant(
                    variant_id=f"{test_id}_variant_{i}",
                    component_name=component_name,
                    variant_code=variant_data.get("code", ""),
                    variant_params=variant_data.get("params", {})
                )
                test_variants.append(variant)
            
            self.ab_test_variants[test_id] = test_variants
            self.stats["active_ab_tests"] += 1
            
            logger.info(f"Started A/B test {test_id} for {component_name} with {len(variants)} variants")
            
            # Schedule test completion
            asyncio.create_task(self._complete_ab_test(test_id))
            
            return test_id
            
        except Exception as e:
            logger.error(f"Error starting A/B test: {e}")
            return ""
    
    async def _complete_ab_test(self, test_id: str):
        """Complete an A/B test and select the best variant."""
        
        try:
            # Wait for test duration
            await asyncio.sleep(self.config["ab_test_duration"])
            
            if test_id not in self.ab_test_variants:
                return
            
            variants = self.ab_test_variants[test_id]
            
            # Analyze results and select best variant
            best_variant = None
            best_score = float('inf')
            
            for variant in variants:
                if variant.test_results:
                    avg_score = statistics.mean([r.score for r in variant.test_results])
                    if avg_score < best_score:  # Lower is better for execution time
                        best_score = avg_score
                        best_variant = variant
            
            if best_variant:
                logger.info(f"A/B test {test_id} completed. Best variant: {best_variant.variant_id}")
                
                # Apply best variant (simplified)
                # In a real system, this would deploy the best variant
                
            # Clean up
            del self.ab_test_variants[test_id]
            self.stats["active_ab_tests"] -= 1
            
        except Exception as e:
            logger.error(f"Error completing A/B test: {e}")
    
    async def _continuous_benchmarking(self):
        """Background task for continuous benchmarking."""
        
        while True:
            try:
                await asyncio.sleep(self.config["benchmark_interval"])
                
                # Get all active components
                active_components = dynamic_registry.list_components(status=ComponentStatus.ACTIVE)
                
                for entry in active_components:
                    component_name = entry.component.name
                    
                    try:
                        # Skip if recently benchmarked
                        if component_name in self.benchmark_results:
                            last_benchmark = max(
                                r.timestamp for r in self.benchmark_results[component_name]
                            )
                            if datetime.now() - last_benchmark < timedelta(hours=1):
                                continue
                        
                        # Run benchmark
                        await self.benchmark_component(component_name)
                        
                        # Small delay between benchmarks
                        await asyncio.sleep(10)
                        
                    except Exception as e:
                        logger.error(f"Error in continuous benchmarking for {component_name}: {e}")
                
            except Exception as e:
                logger.error(f"Error in continuous benchmarking task: {e}")
    
    async def _optimization_monitor(self):
        """Background task for monitoring and triggering optimizations."""
        
        while True:
            try:
                await asyncio.sleep(3600)  # Check every hour
                
                # Check components for optimization opportunities
                for component_name, metrics in self.performance_metrics.items():
                    try:
                        # Check if optimization is needed
                        needs_optimization = (
                            metrics.trend == "degrading" or
                            metrics.execution_time > 10.0 or
                            metrics.success_rate < 90.0
                        )
                        
                        if needs_optimization:
                            logger.info(f"Component {component_name} needs optimization")
                            await self.optimize_component(component_name)
                            
                    except Exception as e:
                        logger.error(f"Error in optimization monitor for {component_name}: {e}")
                
            except Exception as e:
                logger.error(f"Error in optimization monitor task: {e}")
    
    async def _ab_test_manager(self):
        """Background task for managing A/B tests."""
        
        while True:
            try:
                await asyncio.sleep(1800)  # Check every 30 minutes
                
                # Monitor active A/B tests
                for test_id, variants in list(self.ab_test_variants.items()):
                    try:
                        # Run benchmarks on variants
                        for variant in variants:
                            if variant.active:
                                # This would run the variant and collect results
                                # For now, simulate results
                                pass
                                
                    except Exception as e:
                        logger.error(f"Error managing A/B test {test_id}: {e}")
                
            except Exception as e:
                logger.error(f"Error in A/B test manager task: {e}")
    
    async def _load_optimization_data(self):
        """Load existing optimization data."""
        
        # This would load data from persistent storage
        # For now, start with empty data
        pass
    
    def get_optimization_stats(self) -> Dict[str, Any]:
        """Get optimization statistics."""
        
        return {
            **self.stats,
            "components_monitored": len(self.performance_metrics),
            "benchmark_history": len(self.benchmark_results),
            "optimization_success_rate": (
                self.stats["successful_optimizations"] / max(self.stats["total_optimizations"], 1) * 100
            ),
            "performance_trends": {
                "improving": len([m for m in self.performance_metrics.values() if m.trend == "improving"]),
                "stable": len([m for m in self.performance_metrics.values() if m.trend == "stable"]),
                "degrading": len([m for m in self.performance_metrics.values() if m.trend == "degrading"])
            }
        }
    
    def get_component_performance(self, component_name: str) -> Optional[Dict[str, Any]]:
        """Get performance data for a specific component."""
        
        if component_name not in self.performance_metrics:
            return None
        
        metrics = self.performance_metrics[component_name]
        recent_benchmarks = self.benchmark_results.get(component_name, [])
        
        return {
            "metrics": {
                "execution_time": metrics.execution_time,
                "memory_usage": metrics.memory_usage,
                "success_rate": metrics.success_rate,
                "trend": metrics.trend,
                "last_updated": metrics.last_updated.isoformat()
            },
            "recent_benchmarks": [
                {
                    "type": r.benchmark_type.value,
                    "score": r.score,
                    "unit": r.unit,
                    "timestamp": r.timestamp.isoformat()
                }
                for r in recent_benchmarks[-10:]  # Last 10 benchmarks
            ],
            "optimizations": [
                {
                    "strategy": opt.strategy.value,
                    "improvement": opt.improvement,
                    "timestamp": opt.timestamp.isoformat(),
                    "success": opt.success
                }
                for opt in self.optimization_results
                if opt.component_name == component_name
            ]
        }


# Global optimization engine instance
optimization_engine = OptimizationEngine()


# Convenience functions
async def benchmark_all_components() -> Dict[str, Dict[str, BenchmarkResult]]:
    """Benchmark all active components."""
    results = {}
    active_components = dynamic_registry.list_components(status=ComponentStatus.ACTIVE)
    
    for entry in active_components:
        component_name = entry.component.name
        results[component_name] = await optimization_engine.benchmark_component(component_name)
    
    return results


async def optimize_all_components() -> List[OptimizationResult]:
    """Attempt to optimize all components."""
    results = []
    
    for component_name in optimization_engine.performance_metrics.keys():
        result = await optimization_engine.optimize_component(component_name)
        if result:
            results.append(result)
    
    return results


def get_optimization_stats() -> Dict[str, Any]:
    """Get optimization statistics."""
    return optimization_engine.get_optimization_stats()