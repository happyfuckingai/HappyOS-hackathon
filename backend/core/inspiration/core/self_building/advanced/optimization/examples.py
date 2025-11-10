"""
Optimization Engine Examples

This module contains practical examples of how to use the Optimization Engine
for benchmarking, optimization, and A/B testing of HappyOS components.
"""

import asyncio
import logging
from typing import Dict, Any, List
from datetime import datetime

from app.core.self_building.advanced.optimization.optimization_engine import (
    optimization_engine,
    benchmark_all_components,
    optimize_all_components,
    get_optimization_stats,
    BenchmarkType,
    OptimizationStrategy
)

logger = logging.getLogger(__name__)


async def basic_benchmarking_example():
    """Basic benchmarking example for a single component."""

    print("=== Basic Benchmarking Example ===")

    # Initialize the optimization engine
    await optimization_engine.initialize()

    # Benchmark a specific component
    component_name = "example_component"
    results = await optimization_engine.benchmark_component(
        component_name,
        [BenchmarkType.PERFORMANCE, BenchmarkType.MEMORY]
    )

    if results:
        print(f"Benchmark results for {component_name}:")
        for benchmark_type, result in results.items():
            print(f"  {benchmark_type}: {result.score:.2f} {result.unit}")
            print(f"    Timestamp: {result.timestamp}")
            print(f"    Test data: {result.test_data}")
    else:
        print(f"No benchmark results for {component_name}")

    print()


async def comprehensive_monitoring_example():
    """Example of comprehensive system monitoring."""

    print("=== Comprehensive Monitoring Example ===")

    # Get system-wide statistics
    stats = optimization_engine.get_optimization_stats()
    print("System Statistics:")
    print(f"  Components monitored: {stats['components_monitored']}")
    print(f"  Total benchmarks: {stats['total_benchmarks']}")
    print(f"  Total optimizations: {stats['total_optimizations']}")
    print(f"  Successful optimizations: {stats['successful_optimizations']}")
    print(".2f")
    print(f"  Active A/B tests: {stats['active_ab_tests']}")

    # Show performance trends
    trends = stats['performance_trends']
    print("Performance Trends:")
    print(f"  Improving: {trends['improving']}")
    print(f"  Stable: {trends['stable']}")
    print(f"  Degrading: {trends['degrading']}")

    print()


async def component_performance_analysis_example():
    """Example of detailed component performance analysis."""

    print("=== Component Performance Analysis Example ===")

    # Analyze a specific component's performance
    component_name = "example_component"
    performance = optimization_engine.get_component_performance(component_name)

    if performance:
        metrics = performance['metrics']
        print(f"Performance metrics for {component_name}:")
        print(f"  Execution time: {metrics['execution_time']:.2f} seconds")
        print(f"  Memory usage: {metrics['memory_usage']:.2f} MB")
        print(".2f")
        print(f"  Trend: {metrics['trend']}")
        print(f"  Last updated: {metrics['last_updated']}")

        # Show recent benchmarks
        recent_benchmarks = performance['recent_benchmarks']
        if recent_benchmarks:
            print(f"Recent benchmarks ({len(recent_benchmarks)}):")
            for benchmark in recent_benchmarks[-3:]:  # Show last 3
                print(f"    {benchmark['type']}: {benchmark['score']:.2f} {benchmark['unit']}")

        # Show optimization history
        optimizations = performance['optimizations']
        if optimizations:
            print(f"Optimization history ({len(optimizations)} attempts):")
            for opt in optimizations[-3:]:  # Show last 3
                print(f"    {opt['strategy']}: {opt['improvement']:.2f}% improvement")

    else:
        print(f"No performance data available for {component_name}")

    print()


async def optimization_example():
    """Example of manual component optimization."""

    print("=== Optimization Example ===")

    component_name = "example_component"

    # Attempt optimization
    result = await optimization_engine.optimize_component(component_name)

    if result:
        print(f"Optimization attempt for {component_name}:")
        print(f"  Strategy: {result.strategy.value}")
        print(f"  Before score: {result.before_score:.2f}")
        print(f"  After score: {result.after_score:.2f}")
        print(".2f")
        print(f"  Success: {result.success}")
        print(f"  Timestamp: {result.timestamp}")
    else:
        print(f"Optimization not performed for {component_name}")

    print()


async def ab_testing_example():
    """Example of A/B testing with multiple variants."""

    print("=== A/B Testing Example ===")

    component_name = "sorting_component"

    # Define test variants
    variants = [
        {
            "code": "quick_sort_implementation",
            "params": {
                "algorithm": "quick_sort",
                "optimization_level": "O2"
            }
        },
        {
            "code": "merge_sort_implementation",
            "params": {
                "algorithm": "merge_sort",
                "optimization_level": "O3"
            }
        },
        {
            "code": "tim_sort_implementation",
            "params": {
                "algorithm": "tim_sort",
                "optimization_level": "O2"
            }
        }
    ]

    # Start A/B test
    test_id = await optimization_engine.start_ab_test(component_name, variants)

    if test_id:
        print(f"A/B test started successfully:")
        print(f"  Test ID: {test_id}")
        print(f"  Component: {component_name}")
        print(f"  Variants: {len(variants)}")
        print(f"  Expected duration: {optimization_engine.config['ab_test_duration']} seconds")

        # Note: In a real scenario, the test would run in the background
        # and complete automatically after the configured duration
    else:
        print(f"Failed to start A/B test for {component_name}")

    print()


async def batch_operations_example():
    """Example of batch operations on all components."""

    print("=== Batch Operations Example ===")

    # Benchmark all components
    print("Benchmarking all components...")
    all_results = await benchmark_all_components()

    print(f"Benchmarked {len(all_results)} components:")
    for component_name, results in all_results.items():
        benchmark_count = len(results) if results else 0
        print(f"  {component_name}: {benchmark_count} benchmarks completed")

    # Optimize all components
    print("\nOptimizing all components...")
    optimization_results = await optimize_all_components()

    print(f"Optimization attempts: {len(optimization_results)}")
    successful = sum(1 for r in optimization_results if r.success)
    print(f"Successful optimizations: {successful}")

    if optimization_results:
        avg_improvement = sum(r.improvement for r in optimization_results if r.success) / max(successful, 1)
        print(".2f")

    print()


async def custom_configuration_example():
    """Example of customizing optimization engine configuration."""

    print("=== Custom Configuration Example ===")

    # Show current configuration
    print("Current configuration:")
    for key, value in optimization_engine.config.items():
        print(f"  {key}: {value}")

    # Modify configuration for high-frequency monitoring
    original_config = optimization_engine.config.copy()
    optimization_engine.config.update({
        "benchmark_interval": 1800,  # 30 minutes
        "optimization_threshold": 0.05,  # 5% improvement threshold
        "auto_optimization_enabled": True
    })

    print("\nUpdated configuration for high-frequency monitoring:")
    for key, value in optimization_engine.config.items():
        if key in ["benchmark_interval", "optimization_threshold", "auto_optimization_enabled"]:
            print(f"  {key}: {value}")

    # Note: Configuration changes take effect immediately for new operations
    # Running background tasks may need to be restarted for interval changes

    # Restore original configuration
    optimization_engine.config = original_config
    print("\nConfiguration restored to original values.")

    print()


async def performance_monitoring_example():
    """Example of continuous performance monitoring."""

    print("=== Performance Monitoring Example ===")

    # Simulate monitoring over time
    print("Starting performance monitoring simulation...")

    component_name = "monitored_component"

    # Take initial benchmark
    print("Initial benchmark...")
    initial_results = await optimization_engine.benchmark_component(component_name)
    if initial_results:
        perf_result = initial_results.get(BenchmarkType.PERFORMANCE.value)
        if perf_result:
            print(".2f")

    # Simulate some time passing and performance changes
    print("Simulating performance changes...")
    await asyncio.sleep(2)  # Simulate time passing

    # Take follow-up benchmark
    print("Follow-up benchmark...")
    follow_up_results = await optimization_engine.benchmark_component(component_name)
    if follow_up_results:
        perf_result = follow_up_results.get(BenchmarkType.PERFORMANCE.value)
        if perf_result:
            print(".2f")

    # Check performance trend
    performance = optimization_engine.get_component_performance(component_name)
    if performance:
        trend = performance['metrics']['trend']
        print(f"Performance trend: {trend}")

    print()


async def error_handling_example():
    """Example of error handling in optimization operations."""

    print("=== Error Handling Example ===")

    # Try to benchmark a non-existent component
    print("Attempting to benchmark non-existent component...")
    results = await optimization_engine.benchmark_component("non_existent_component")

    if not results:
        print("✓ Correctly handled non-existent component (returned empty results)")
    else:
        print("✗ Unexpected results for non-existent component")

    # Try to get performance for non-existent component
    print("Attempting to get performance for non-existent component...")
    performance = optimization_engine.get_component_performance("non_existent_component")

    if performance is None:
        print("✓ Correctly returned None for non-existent component")
    else:
        print("✗ Unexpected performance data for non-existent component")

    # Try optimization on non-existent component
    print("Attempting to optimize non-existent component...")
    result = await optimization_engine.optimize_component("non_existent_component")

    if result is None:
        print("✓ Correctly returned None for optimization of non-existent component")
    else:
        print("✗ Unexpected optimization result for non-existent component")

    print()


async def main():
    """Run all examples."""

    print("Optimization Engine Examples")
    print("=" * 50)
    print()

    try:
        # Run examples in sequence
        await basic_benchmarking_example()
        await comprehensive_monitoring_example()
        await component_performance_analysis_example()
        await optimization_example()
        await ab_testing_example()
        await batch_operations_example()
        await custom_configuration_example()
        await performance_monitoring_example()
        await error_handling_example()

        print("All examples completed successfully!")

    except Exception as e:
        logger.error(f"Error running examples: {e}")
        print(f"Error: {e}")


if __name__ == "__main__":
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # Run examples
    asyncio.run(main())
