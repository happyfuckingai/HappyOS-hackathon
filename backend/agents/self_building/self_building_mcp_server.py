#!/usr/bin/env python3
"""
Self-Building MCP Server

Provides MCP tools for autonomous system improvement, code generation,
and telemetry analysis.
"""

import asyncio
import json
import logging
import os
import secrets
import sys
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4

try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))
except ImportError:
    pass

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from mcp.server import FastMCP
import structlog

# Import configuration
try:
    from .config import get_config
except ImportError:
    from config import get_config

# Import self-building system components
try:
    from backend.core.inspiration.core.self_building.ultimate_self_building import (
        ultimate_self_building_system,
        initialize_ultimate_self_building,
        get_ultimate_system_status,
    )
except ImportError:
    # Fallback for development
    ultimate_self_building_system = None
    initialize_ultimate_self_building = None
    get_ultimate_system_status = None

# Import tenant validator
try:
    from backend.core.self_building.tenant_validator import tenant_validator
except ImportError:
    tenant_validator = None

# ---------------------------------------------------------------------------
# Logging configuration
# ---------------------------------------------------------------------------

config = get_config()

logging.basicConfig(
    level=getattr(logging, config.log_level.upper(), logging.INFO),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("self_building_mcp_server")

# Reduce noise from third-party libraries
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("botocore").setLevel(logging.WARNING)
logging.getLogger("boto3").setLevel(logging.WARNING)

# ---------------------------------------------------------------------------
# FastAPI and MCP setup
# ---------------------------------------------------------------------------

app = FastAPI(
    title="Self-Building MCP Server",
    version="1.0.0",
    description="Autonomous system improvement and code generation"
)

# CORS configuration
allowed_origins_list = [
    origin.strip() 
    for origin in config.allowed_origins.split(",") 
    if origin.strip()
]
if not allowed_origins_list:
    allowed_origins_list = ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize FastMCP
mcp = FastMCP(
    name="Self-Building Agent",
    host=config.mcp_host,
    port=config.mcp_port,
    mount_path="/mcp",
    log_level=config.log_level,
)

# Mount MCP at /mcp endpoint
app.mount("/mcp", mcp.sse_app(mount_path="/mcp"))

# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------

# API key security
API_KEY = config.mcp_api_key or os.getenv("MCP_API_KEY") or secrets.token_urlsafe(32)
if not config.mcp_api_key and "MCP_API_KEY" not in os.environ:
    logger.warning(f"Generated ephemeral MCP API key: {API_KEY[:8]}...")

security = HTTPBearer(auto_error=False)


async def verify_api_key(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
) -> str:
    """Verify bearer token matches configured MCP API key."""
    if credentials is None or credentials.credentials != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid or missing API key")
    return credentials.credentials

# ---------------------------------------------------------------------------
# Utility functions
# ---------------------------------------------------------------------------


def _json_default(obj: Any) -> str:
    """JSON serialization helper for datetime objects."""
    if isinstance(obj, datetime):
        return obj.isoformat()
    return str(obj)


def _format_tool_response(
    success: bool, 
    data: Any = None, 
    error: Optional[str] = None
) -> str:
    """Format MCP tool response as JSON string."""
    payload: Dict[str, Any] = {
        "success": success,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    if success:
        payload["data"] = data
    else:
        payload["error"] = error or "Unknown error"
    return json.dumps(payload, default=_json_default)


# ---------------------------------------------------------------------------
# Health check endpoint
# ---------------------------------------------------------------------------


@app.get("/health")
async def health_check() -> Dict[str, Any]:
    """Health probe for deployment checks."""
    system_ready = ultimate_self_building_system is not None
    system_running = (
        ultimate_self_building_system.running 
        if system_ready else False
    )
    
    return {
        "status": "ok" if system_ready else "degraded",
        "agent": "self-building",
        "version": "1.0.0",
        "system_ready": system_ready,
        "system_running": system_running,
        "features": {
            "autonomous_improvements": config.enable_autonomous_improvements,
            "component_generation": config.enable_component_generation,
            "cloudwatch_streaming": config.enable_cloudwatch_streaming,
            "improvement_rollback": config.enable_improvement_rollback,
        },
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


# ---------------------------------------------------------------------------
# MCP Tool: trigger_improvement_cycle
# ---------------------------------------------------------------------------


@mcp.tool()
async def trigger_improvement_cycle(
    analysis_window_hours: int = 24,
    max_improvements: int = 3,
    tenant_id: Optional[str] = None
) -> str:
    """
    Trigger an autonomous improvement cycle.
    
    Analyzes telemetry data from the specified time window, identifies
    improvement opportunities, generates code, and deploys changes with
    automatic monitoring and rollback.
    
    Args:
        analysis_window_hours: Hours of telemetry to analyze (default: 24)
        max_improvements: Maximum concurrent improvements (default: 3)
        tenant_id: Optional tenant scope for multi-tenant isolation
        
    Returns:
        JSON string with improvement cycle results
    """
    if not config.enable_autonomous_improvements:
        return _format_tool_response(
            False, 
            error="Autonomous improvements are disabled by configuration"
        )
    
    if ultimate_self_building_system is None:
        return _format_tool_response(
            False, 
            error="Self-building system not initialized"
        )
    
    # Validate tenant_id
    if tenant_validator:
        validation_result = tenant_validator.validate_tenant_id(
            tenant_id=tenant_id,
            allow_system_wide=True  # Allow system-wide improvements
        )
        
        if not validation_result.valid:
            logger.warning(f"Tenant validation failed: {validation_result.error_message}")
            return _format_tool_response(
                False,
                error=validation_result.error_message
            )
        
        # Use validated tenant_id
        tenant_id = validation_result.tenant_id
        logger.info(f"Tenant validation successful: {tenant_id} (system_wide={validation_result.is_system_wide})")
    
    try:
        logger.info(
            f"Triggering improvement cycle: window={analysis_window_hours}h, "
            f"max={max_improvements}, tenant={tenant_id}"
        )
        
        # TODO: Implement actual improvement cycle integration
        # This will be implemented in task 7
        result = {
            "cycle_id": str(uuid4()),
            "status": "initiated",
            "analysis_window_hours": analysis_window_hours,
            "max_improvements": max_improvements,
            "tenant_id": tenant_id or "system",
            "message": "Improvement cycle initiated (implementation pending)",
        }
        
        logger.info(f"Improvement cycle initiated: {result['cycle_id']}")
        
        return _format_tool_response(True, data=result)
        
    except Exception as e:
        logger.error(f"Failed to trigger improvement cycle: {e}", exc_info=True)
        return _format_tool_response(False, error=str(e))


# ---------------------------------------------------------------------------
# MCP Tool: generate_component
# ---------------------------------------------------------------------------


@mcp.tool()
async def generate_component(
    component_type: str,
    requirements: Dict[str, Any],
    context: Optional[Dict[str, Any]] = None
) -> str:
    """
    Generate a new system component.
    
    Uses the self-building system to generate a new component (skill, agent,
    service) based on requirements and context.
    
    Args:
        component_type: Type of component (skill, agent, service)
        requirements: Component requirements and specifications
        context: Additional context for generation
        
    Returns:
        JSON string with generated component details
    """
    if not config.enable_component_generation:
        return _format_tool_response(
            False, 
            error="Component generation is disabled by configuration"
        )
    
    if ultimate_self_building_system is None:
        return _format_tool_response(
            False, 
            error="Self-building system not initialized"
        )
    
    # Validate component_type
    valid_types = ["skill", "agent", "service", "plugin"]
    if component_type not in valid_types:
        return _format_tool_response(
            False, 
            error=f"Invalid component_type. Must be one of: {', '.join(valid_types)}"
        )
    
    # Validate requirements
    if not requirements:
        return _format_tool_response(
            False, 
            error="requirements parameter is required"
        )
    
    try:
        logger.info(
            f"Generating component: type={component_type}, "
            f"requirements={json.dumps(requirements)[:100]}..."
        )
        
        # Build user request from requirements
        user_request = requirements.get("description", "")
        if not user_request:
            user_request = f"Generate a {component_type} component"
        
        # Use SBO2's handle_generation_candidate_request method
        result = await ultimate_self_building_system.handle_generation_candidate_request(
            user_request=user_request,
            context=context or {}
        )
        
        if result.get("success"):
            component_data = {
                "component_id": str(uuid4()),
                "component_type": component_type,
                "component_name": result.get("component_name"),
                "file_path": result.get("file_path"),
                "auto_generated": result.get("auto_generated", True),
                "status": "registered",
                "generated_at": datetime.now(timezone.utc).isoformat(),
            }
            
            logger.info(f"Component generated successfully: {component_data['component_name']}")
            
            return _format_tool_response(True, data=component_data)
        else:
            error_msg = result.get("error", "Component generation failed")
            logger.error(f"Component generation failed: {error_msg}")
            return _format_tool_response(False, error=error_msg)
        
    except Exception as e:
        logger.error(f"Failed to generate component: {e}", exc_info=True)
        return _format_tool_response(False, error=str(e))


# ---------------------------------------------------------------------------
# MCP Tool: get_system_status
# ---------------------------------------------------------------------------


@mcp.tool()
async def get_system_status() -> str:
    """
    Get comprehensive self-building system status.
    
    Returns system health, active improvements, evolution level, and
    component statistics.
    
    Returns:
        JSON string with system status
    """
    if ultimate_self_building_system is None:
        return _format_tool_response(
            False, 
            error="Self-building system not initialized"
        )
    
    try:
        logger.debug("Fetching system status")
        
        # Get status from SBO2
        status = await get_ultimate_system_status()
        
        # Add server-specific information
        status["server"] = {
            "host": config.mcp_host,
            "port": config.mcp_port,
            "version": "1.0.0",
        }
        
        status["configuration"] = {
            "autonomous_improvements_enabled": config.enable_autonomous_improvements,
            "component_generation_enabled": config.enable_component_generation,
            "cloudwatch_streaming_enabled": config.enable_cloudwatch_streaming,
            "improvement_rollback_enabled": config.enable_improvement_rollback,
            "max_concurrent_improvements": config.max_concurrent_improvements,
            "improvement_cycle_interval_hours": config.improvement_cycle_interval_hours,
        }
        
        return _format_tool_response(True, data=status)
        
    except Exception as e:
        logger.error(f"Failed to get system status: {e}", exc_info=True)
        return _format_tool_response(False, error=str(e))


# ---------------------------------------------------------------------------
# MCP Tool: query_telemetry_insights
# ---------------------------------------------------------------------------


@mcp.tool()
async def query_telemetry_insights(
    metric_name: Optional[str] = None,
    time_range_hours: int = 1,
    tenant_id: Optional[str] = None
) -> str:
    """
    Query analyzed telemetry insights.
    
    Retrieves insights from the LearningEngine based on telemetry analysis.
    
    Args:
        metric_name: Specific metric to query (optional)
        time_range_hours: Time range for analysis (default: 1)
        tenant_id: Optional tenant filter for multi-tenant isolation
        
    Returns:
        JSON string with telemetry insights and recommendations
    """
    if not config.enable_cloudwatch_streaming:
        return _format_tool_response(
            False, 
            error="CloudWatch streaming is disabled by configuration"
        )
    
    if ultimate_self_building_system is None:
        return _format_tool_response(
            False, 
            error="Self-building system not initialized"
        )
    
    # Validate tenant_id
    if tenant_validator:
        validation_result = tenant_validator.validate_tenant_id(
            tenant_id=tenant_id,
            allow_system_wide=True  # Allow querying system-wide insights
        )
        
        if not validation_result.valid:
            logger.warning(f"Tenant validation failed: {validation_result.error_message}")
            return _format_tool_response(
                False,
                error=validation_result.error_message
            )
        
        # Use validated tenant_id
        tenant_id = validation_result.tenant_id
        logger.info(f"Tenant validation successful: {tenant_id} (system_wide={validation_result.is_system_wide})")
    
    try:
        logger.info(
            f"Querying telemetry insights: metric={metric_name}, "
            f"range={time_range_hours}h, tenant={tenant_id}"
        )
        
        # TODO: Implement actual telemetry insights query
        # This will be implemented in task 4 (LearningEngine)
        insights = {
            "query": {
                "metric_name": metric_name,
                "time_range_hours": time_range_hours,
                "tenant_id": tenant_id or "system",
            },
            "insights": [],
            "recommendations": [],
            "message": "Telemetry insights query (implementation pending)",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        
        return _format_tool_response(True, data=insights)
        
    except Exception as e:
        logger.error(f"Failed to query telemetry insights: {e}", exc_info=True)
        return _format_tool_response(False, error=str(e))


# ---------------------------------------------------------------------------
# Application lifespan
# ---------------------------------------------------------------------------


@app.on_event("startup")
async def startup_event():
    """Initialize self-building system on startup."""
    logger.info("Starting Self-Building MCP Server...")
    
    if not config.enable_self_building:
        logger.warning("Self-building system is disabled by configuration")
        return
    
    if ultimate_self_building_system is None:
        logger.warning("Self-building system components not available")
        return
    
    try:
        # Initialize the ultimate self-building system
        if initialize_ultimate_self_building:
            await initialize_ultimate_self_building()
            logger.info("Self-building system initialized successfully")
        else:
            logger.warning("initialize_ultimate_self_building function not available")
    except Exception as e:
        logger.error(f"Failed to initialize self-building system: {e}", exc_info=True)


@app.on_event("shutdown")
async def shutdown_event():
    """Shutdown self-building system gracefully."""
    logger.info("Shutting down Self-Building MCP Server...")
    
    if ultimate_self_building_system and ultimate_self_building_system.running:
        try:
            await ultimate_self_building_system.shutdown()
            logger.info("Self-building system shut down successfully")
        except Exception as e:
            logger.error(f"Error during shutdown: {e}", exc_info=True)


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        app,
        host=config.mcp_host,
        port=config.mcp_port,
        log_level=config.log_level.lower()
    )
