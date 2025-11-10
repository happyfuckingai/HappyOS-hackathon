"""
Optimization Engine Package

This package provides self-tuning and benchmarking capabilities for HappyOS components.
"""

from .optimization_engine import (
    OptimizationEngine,
    BenchmarkType,
    OptimizationStrategy,
    BenchmarkResult,
    PerformanceMetrics,
    OptimizationResult,
    ABTestVariant,
    optimization_engine,
    benchmark_all_components,
    optimize_all_components,
    get_optimization_stats
)

__all__ = [
    "OptimizationEngine",
    "BenchmarkType",
    "OptimizationStrategy",
    "BenchmarkResult",
    "PerformanceMetrics",
    "OptimizationResult",
    "ABTestVariant",
    "optimization_engine",
    "benchmark_all_components",
    "optimize_all_components",
    "get_optimization_stats"
]

__version__ = "1.0.0"
