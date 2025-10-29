"""
Unified Health Check Routes

Provides standardized health check endpoints that aggregate health status
from all HappyOS agent systems using the unified monitoring framework.
"""

import asyncio
import time
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import JSONResponse

# Import HappyOS SDK for standardized health monitoring
try:
    from happyos_sdk.health_monitoring import (
        StandardHealthResponse, HealthStatus, get_health_monitor
    )
    from happyos_sdk.metrics_collection import (
        get_metrics_collector, StandardizedMetrics
    )
    HAPPYOS_SDK_AVAILABLE = True
except ImportError:
    HAPPYOS_SDK_AVAILABLE = False

from backend.services.observability.logger import get_logger
from backend.modules.auth.dependencies import get_current_user
from backend.modules.models.user import UserModel

logger = get_logger(__name__)
router = APIRouter(prefix="/unified-health", tags=["Unified Health"])


@router.get("/status")
async def get_unified_health_status() -> JSONResponse:
    """
    Get unified health status across all HappyOS agent systems.
    
    Returns standardized health information for:
    - Agent Svea (Swedish ERP & compliance)
    - Felicia's Finance (Financial services & crypto)
    - MeetMind (Meeting intelligence & fan-in logic)
    - Backend Platform Services
    """
    start_time = time.time()
    
    try:
        # Collect health status from all agents
        agent_health_statuses = await _collect_agent_health_statuses()
        
        # Get backend platform health
        platform_health = await _get_platform_health()
        
        # Determine overall system health
        overall_status = _determine_overall_health(agent_health_statuses, platform_health)
        
        # Calculate response time
        response_time_ms = (time.time() - start_time) * 1000
        
        # Create unified response
        unified_response = {
            "system_status": overall_status,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "response_time_ms": response_time_ms,
            "agents": agent_health_statuses,
            "platform": platform_health,
            "summary": {
                "total_agents": len(agent_health_statuses),
                "healthy_agents": len([a for a in agent_health_statuses.values() if a.get("status") == "healthy"]),
                "degraded_agents": len([a for a in agent_health_statuses.values() if a.get("status") == "degraded"]),
                "unhealthy_agents": len([a for a in agent_health_statuses.values() if a.get("status") == "unhealthy"]),
                "sla_compliance": {
                    "response_time_target_ms": 5000,
                    "response_time_actual_ms": response_time_ms,
                    "meets_sla": response_time_ms < 5000
                }
            }
        }
        
        # Record unified health metrics if HappyOS SDK is available
        if HAPPYOS_SDK_AVAILABLE:
            try:
                metrics_collector = get_metrics_collector("platform", "unified_health")
                await metrics_collector.record_health_status(
                    overall_status,
                    response_time_ms
                )
            except Exception as e:
                logger.warning(f"Failed to record unified health metrics: {e}")
        
        # Return appropriate HTTP status code based on health
        status_code = 200 if overall_status == "healthy" else 503
        
        return JSONResponse(
            content=unified_response,
            status_code=status_code
        )
        
    except Exception as e:
        logger.error(f"Unified health check failed: {e}")
        
        return JSONResponse(
            content={
                "system_status": "unhealthy",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "error": str(e),
                "response_time_ms": (time.time() - start_time) * 1000
            },
            status_code=503
        )


@router.get("/agents")
async def get_agent_health_summary() -> JSONResponse:
    """Get health summary for all agent systems."""
    try:
        agent_health_statuses = await _collect_agent_health_statuses()
        
        return JSONResponse(content={
            "agents": agent_health_statuses,
            "timestamp": datetime.now(timezone.utc).isoformat()
        })
        
    except Exception as e:
        logger.error(f"Agent health summary failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/agents/{agent_type}")
async def get_specific_agent_health(agent_type: str) -> JSONResponse:
    """Get detailed health status for a specific agent."""
    try:
        if agent_type not in ["agent_svea", "felicias_finance", "meetmind"]:
            raise HTTPException(status_code=404, detail=f"Agent type '{agent_type}' not found")
        
        agent_health = await _get_agent_health(agent_type)
        
        if not agent_health:
            raise HTTPException(status_code=503, detail=f"Agent '{agent_type}' is not responding")
        
        return JSONResponse(content=agent_health)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Specific agent health check failed for {agent_type}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/metrics/summary")
async def get_unified_metrics_summary(
    current_user: UserModel = Depends(get_current_user)
) -> JSONResponse:
    """Get unified metrics summary across all agent systems."""
    try:
        if not HAPPYOS_SDK_AVAILABLE:
            raise HTTPException(status_code=503, detail="HappyOS SDK not available")
        
        # Collect metrics from all agents
        metrics_summary = {}
        
        for agent_type in ["agent_svea", "felicias_finance", "meetmind", "platform"]:
            try:
                metrics_collector = get_metrics_collector(agent_type, agent_type)
                agent_metrics = metrics_collector.get_metrics_summary()
                metrics_summary[agent_type] = agent_metrics
            except Exception as e:
                logger.warning(f"Failed to get metrics for {agent_type}: {e}")
                metrics_summary[agent_type] = {"error": str(e)}
        
        return JSONResponse(content={
            "metrics": metrics_summary,
            "timestamp": datetime.now(timezone.utc).isoformat()
        })
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unified metrics summary failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/sla/compliance")
async def get_sla_compliance_status() -> JSONResponse:
    """Get SLA compliance status across all systems."""
    try:
        # Define SLA targets
        sla_targets = {
            "response_time_ms": 5000,  # Sub-5-second response
            "uptime_percent": 99.9,    # 99.9% uptime
            "error_rate_percent": 1.0,  # Less than 1% error rate
            "availability_percent": 99.9  # 99.9% availability
        }
        
        # Collect current metrics
        agent_health_statuses = await _collect_agent_health_statuses()
        
        # Calculate SLA compliance
        sla_compliance = {}
        
        for agent_type, health_data in agent_health_statuses.items():
            agent_compliance = {
                "response_time": {
                    "target_ms": sla_targets["response_time_ms"],
                    "actual_ms": health_data.get("response_time_ms", 0),
                    "compliant": health_data.get("response_time_ms", 0) < sla_targets["response_time_ms"]
                },
                "error_rate": {
                    "target_percent": sla_targets["error_rate_percent"],
                    "actual_percent": health_data.get("error_rate_percent", 0),
                    "compliant": health_data.get("error_rate_percent", 0) < sla_targets["error_rate_percent"]
                },
                "availability": {
                    "target_percent": sla_targets["availability_percent"],
                    "actual_percent": 100.0 if health_data.get("status") == "healthy" else 0.0,
                    "compliant": health_data.get("status") == "healthy"
                }
            }
            
            # Overall compliance for this agent
            agent_compliance["overall_compliant"] = all([
                agent_compliance["response_time"]["compliant"],
                agent_compliance["error_rate"]["compliant"],
                agent_compliance["availability"]["compliant"]
            ])
            
            sla_compliance[agent_type] = agent_compliance
        
        # System-wide SLA compliance
        system_compliance = {
            "overall_compliant": all([
                agent["overall_compliant"] for agent in sla_compliance.values()
            ]),
            "compliant_agents": len([
                agent for agent in sla_compliance.values() 
                if agent["overall_compliant"]
            ]),
            "total_agents": len(sla_compliance)
        }
        
        return JSONResponse(content={
            "sla_targets": sla_targets,
            "agent_compliance": sla_compliance,
            "system_compliance": system_compliance,
            "timestamp": datetime.now(timezone.utc).isoformat()
        })
        
    except Exception as e:
        logger.error(f"SLA compliance check failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


async def _collect_agent_health_statuses() -> Dict[str, Dict[str, Any]]:
    """Collect health status from all agent systems."""
    agent_health_statuses = {}
    
    # Define agent endpoints and methods
    agents = {
        "agent_svea": _get_agent_svea_health,
        "felicias_finance": _get_felicias_finance_health,
        "meetmind": _get_meetmind_health
    }
    
    # Collect health status concurrently
    tasks = []
    for agent_type, health_func in agents.items():
        tasks.append(_safe_get_agent_health(agent_type, health_func))
    
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    for i, (agent_type, _) in enumerate(agents.items()):
        result = results[i]
        if isinstance(result, Exception):
            agent_health_statuses[agent_type] = {
                "status": "unhealthy",
                "error": str(result),
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        else:
            agent_health_statuses[agent_type] = result
    
    return agent_health_statuses


async def _safe_get_agent_health(agent_type: str, health_func) -> Dict[str, Any]:
    """Safely get agent health with timeout."""
    try:
        # Set timeout for health checks
        return await asyncio.wait_for(health_func(), timeout=10.0)
    except asyncio.TimeoutError:
        return {
            "status": "unhealthy",
            "error": "Health check timeout",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }


async def _get_agent_svea_health() -> Dict[str, Any]:
    """Get Agent Svea health status."""
    # This would typically make an HTTP request to Agent Svea's health endpoint
    # For now, return a mock response
    return {
        "status": "healthy",
        "agent_type": "agent_svea",
        "response_time_ms": 150.0,
        "error_rate_percent": 0.5,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


async def _get_felicias_finance_health() -> Dict[str, Any]:
    """Get Felicia's Finance health status."""
    # This would typically make an HTTP request to Felicia's Finance health endpoint
    # For now, return a mock response
    return {
        "status": "healthy",
        "agent_type": "felicias_finance",
        "response_time_ms": 200.0,
        "error_rate_percent": 0.3,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


async def _get_meetmind_health() -> Dict[str, Any]:
    """Get MeetMind health status."""
    # This would typically make an HTTP request to MeetMind's health endpoint
    # For now, return a mock response
    return {
        "status": "healthy",
        "agent_type": "meetmind",
        "response_time_ms": 100.0,
        "error_rate_percent": 0.2,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


async def _get_agent_health(agent_type: str) -> Optional[Dict[str, Any]]:
    """Get health status for a specific agent."""
    health_functions = {
        "agent_svea": _get_agent_svea_health,
        "felicias_finance": _get_felicias_finance_health,
        "meetmind": _get_meetmind_health
    }
    
    health_func = health_functions.get(agent_type)
    if not health_func:
        return None
    
    return await _safe_get_agent_health(agent_type, health_func)


async def _get_platform_health() -> Dict[str, Any]:
    """Get backend platform health status."""
    try:
        # Check core platform services
        platform_services = {
            "database": True,  # Would check actual database connectivity
            "redis": True,     # Would check actual Redis connectivity
            "websockets": True, # Would check WebSocket system
            "mcp_ui_hub": True  # Would check MCP UI Hub
        }
        
        # Determine platform status
        all_healthy = all(platform_services.values())
        platform_status = "healthy" if all_healthy else "degraded"
        
        return {
            "status": platform_status,
            "services": platform_services,
            "response_time_ms": 50.0,  # Would measure actual response time
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
    except Exception as e:
        logger.error(f"Platform health check failed: {e}")
        return {
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }


def _determine_overall_health(agent_health: Dict[str, Dict[str, Any]], 
                            platform_health: Dict[str, Any]) -> str:
    """Determine overall system health status."""
    # Check platform health
    if platform_health.get("status") == "unhealthy":
        return "unhealthy"
    
    # Check agent health
    agent_statuses = [agent.get("status", "unknown") for agent in agent_health.values()]
    
    # If any agent is unhealthy, system is unhealthy
    if "unhealthy" in agent_statuses:
        return "unhealthy"
    
    # If any agent is degraded, system is degraded
    if "degraded" in agent_statuses:
        return "degraded"
    
    # If platform is degraded, system is degraded
    if platform_health.get("status") == "degraded":
        return "degraded"
    
    # All systems healthy
    return "healthy"