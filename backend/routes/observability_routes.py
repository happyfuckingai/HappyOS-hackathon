"""
Observability and monitoring API routes.
"""

from typing import Dict, Any
from fastapi import APIRouter, HTTPException, status
from fastapi.responses import PlainTextResponse

try:
    from backend.services.observability import (
        get_health_checker, 
        get_metrics_collector,
        get_tracing_manager
    )
    from backend.services.observability.logger import get_logger
except ImportError:
    import sys
    import os
    sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
    from backend.services.observability import (
        get_health_checker, 
        get_metrics_collector,
        get_tracing_manager
    )
    from backend.services.observability.logger import get_logger

router = APIRouter()
logger = get_logger(__name__)


@router.get("/health/dashboard")
async def get_health_dashboard() -> Dict[str, Any]:
    """Get comprehensive health dashboard data."""
    try:
        health_checker = get_health_checker()
        dashboard_data = await health_checker.get_health_dashboard_data()
        return dashboard_data
    except Exception as e:
        logger.error(f"Failed to get health dashboard data: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Health dashboard unavailable"
        )


@router.get("/health/components")
async def check_all_components() -> Dict[str, Any]:
    """Perform fresh health check on all components."""
    try:
        health_checker = get_health_checker()
        component_health = await health_checker.perform_full_health_check()
        
        return {
            "status": "success",
            "components": {
                name: health.to_dict() 
                for name, health in component_health.items()
            }
        }
    except Exception as e:
        logger.error(f"Component health check failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Component health check failed"
        )


@router.get("/health/component/{component_name}")
async def check_specific_component(component_name: str) -> Dict[str, Any]:
    """Check health of a specific component."""
    try:
        health_checker = get_health_checker()
        
        # Map component names to check methods
        check_methods = {
            "database": health_checker.check_database_health,
            "redis": health_checker.check_redis_health,
            "qdrant": health_checker.check_qdrant_health,
            "system_resources": health_checker.check_system_resources,
            "worker_processes": health_checker.check_worker_processes,
        }
        
        if component_name == "ai_providers":
            # Special case for AI providers (returns list)
            ai_health = await health_checker.check_ai_providers_health()
            return {
                "status": "success",
                "components": [health.to_dict() for health in ai_health]
            }
        
        if component_name not in check_methods:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Component '{component_name}' not found"
            )
        
        component_health = await check_methods[component_name]()
        
        return {
            "status": "success",
            "component": component_health.to_dict()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Health check failed for {component_name}: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Health check failed for {component_name}"
        )


@router.get("/metrics", response_class=PlainTextResponse)
async def get_prometheus_metrics() -> str:
    """Get Prometheus metrics in text format."""
    try:
        metrics_collector = get_metrics_collector()
        metrics_data = metrics_collector.get_metrics()
        return metrics_data.decode('utf-8')
    except Exception as e:
        logger.error(f"Failed to get metrics: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Metrics unavailable"
        )


@router.get("/traces/{trace_id}")
async def get_trace_details(trace_id: str) -> Dict[str, Any]:
    """Get detailed information about a specific trace."""
    try:
        tracing_manager = get_tracing_manager()
        trace_summary = tracing_manager.get_trace_summary(trace_id)
        
        if not trace_summary:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Trace '{trace_id}' not found"
            )
        
        return trace_summary
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get trace details for {trace_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Trace details unavailable"
        )


@router.get("/system/info")
async def get_system_info() -> Dict[str, Any]:
    """Get system information and observability status."""
    try:
        health_checker = get_health_checker()
        overall_health = health_checker.get_overall_health_status()
        
        return {
            "observability": {
                "structured_logging": True,
                "metrics_collection": True,
                "distributed_tracing": True,
                "health_monitoring": True
            },
            "health_summary": {
                "status": overall_health["status"],
                "message": overall_health["message"],
                "component_counts": overall_health["component_counts"]
            },
            "endpoints": {
                "health_dashboard": "/observability/health/dashboard",
                "component_health": "/observability/health/components",
                "metrics": "/observability/metrics",
                "traces": "/observability/traces/{trace_id}"
            }
        }
        
    except Exception as e:
        logger.error(f"Failed to get system info: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="System info unavailable"
        )