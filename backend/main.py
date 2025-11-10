"""
Meetmind Backend Main Application

Integrated FastAPI application with MCP server support, startup coordination,
and comprehensive health monitoring with full observability.
"""

import asyncio
import logging
import time
from contextlib import asynccontextmanager
from typing import Dict, Any

from fastapi import FastAPI, Request, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

# Import configuration and settings
try:
    from backend.modules.config import settings, get_environment_info, validate_configuration
except ImportError:
    import sys
    sys.path.append('.')
    from modules.config import settings, get_environment_info, validate_configuration, ConfigurationError

# Import observability components
try:
    from backend.services.observability import setup_structured_logging, get_logger
    from backend.services.observability.middleware import ObservabilityMiddleware, MetricsEndpointMiddleware
    from backend.services.observability.health import get_health_checker
except ImportError:
    from services.observability import setup_structured_logging, get_logger
    from services.observability.middleware import ObservabilityMiddleware, MetricsEndpointMiddleware
    from services.observability.health import get_health_checker

# Import route modules - AWS deployment (minimal routes)
try:
    from backend.routes.auth_routes import router as auth_router
    from backend.routes.meeting_routes import router as meeting_router  
    from backend.routes.observability_routes import router as observability_router
    from backend.routes.observability_enhanced_routes import router as observability_enhanced_router
    from backend.routes.rate_limit_routes import router as rate_limit_router
    from backend.routes.config_routes import router as config_router
    from backend.routes.security_routes import router as security_router
    from backend.routes.mcp_ui_routes import router as mcp_ui_router
    from backend.routes.mcp_adapter_routes import router as mcp_adapter_router
    from backend.routes.agent_registry import router as agent_registry_router
except ImportError:
    from routes.auth_routes import router as auth_router
    from routes.meeting_routes import router as meeting_router  
    from routes.observability_routes import router as observability_router
    from routes.agent_registry import router as agent_registry_router
    from routes.observability_enhanced_routes import router as observability_enhanced_router
    from routes.rate_limit_routes import router as rate_limit_router
    from routes.config_routes import router as config_router
    from routes.security_routes import router as security_router
    from routes.mcp_ui_routes import router as mcp_ui_router
    from routes.mcp_adapter_routes import router as mcp_adapter_router

# Disabled routes - require missing services
# from backend.routes.agent_routes import router as agent_router  # Missing: agent_process_manager
# from backend.routes.mcp_routes import router as mcp_router  # Missing: summarizer_client
# from backend.routes.streaming_routes import router as streaming_router  # Missing: summarizer_client
# from backend.routes.export_routes import router as export_router  # Missing: export_service
# from backend.routes.mem0_routes import router as mem0_router  # Missing: mem0 integration
# from backend.routes.pipeline_routes import router as pipeline_router  # Missing: pipeline services

# Import startup coordination
try:
    from backend.services.infrastructure.startup_coordinator import (
        get_startup_coordinator,
        startup_all_components,
        shutdown_all_components,
        wait_for_shutdown_signal,
        get_system_health,
        perform_health_checks
    )
    # Import rate limiting
    from backend.services.infrastructure.rate_limit_middleware import RateLimitMiddleware
    from backend.services.infrastructure.rate_limiter import cleanup_rate_limiter
    from backend.services.infrastructure.rate_limit_monitor import cleanup_rate_limit_monitor
    # Import security middleware
    from backend.middleware.security_middleware import SecurityMiddleware
    from backend.middleware.json_schema_validation_middleware import JSONSchemaValidationMiddleware
    from backend.services.infrastructure.api_key_manager import cleanup_api_key_manager
    from backend.services.infrastructure.audit_logger import cleanup_audit_logger
    from backend.services.infrastructure.ip_whitelist import cleanup_ip_whitelist_manager
    from backend.services.infrastructure.threat_detection import cleanup_threat_detector
except ImportError:
    from services.infrastructure.startup_coordinator import (
        get_startup_coordinator,
        startup_all_components,
        shutdown_all_components,
        wait_for_shutdown_signal,
        get_system_health,
        perform_health_checks
    )
    # Import rate limiting
    from services.infrastructure.rate_limit_middleware import RateLimitMiddleware
    from services.infrastructure.rate_limiter import cleanup_rate_limiter
    from services.infrastructure.rate_limit_monitor import cleanup_rate_limit_monitor
    # Import security middleware
    from middleware.security_middleware import SecurityMiddleware
    from middleware.json_schema_validation_middleware import JSONSchemaValidationMiddleware
    from services.infrastructure.api_key_manager import cleanup_api_key_manager
    from services.infrastructure.audit_logger import cleanup_audit_logger
    from services.infrastructure.ip_whitelist import cleanup_ip_whitelist_manager
    from services.infrastructure.threat_detection import cleanup_threat_detector


# Configure logging - now using structured logging from observability
def setup_logging():
    """Setup comprehensive structured logging configuration"""
    setup_structured_logging()


# Application lifespan manager
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application startup and shutdown lifecycle"""
    # Setup structured logging first
    setup_logging()
    logger = get_logger(__name__)

    # Startup
    logger.info("Starting Meetmind Backend with full observability...")
    logger.info("Environment configuration", **get_environment_info())

    # Validate configuration with fail-fast behavior
    try:
        config_warnings = validate_configuration()
        if config_warnings:
            critical_count = len([w for w in config_warnings if "CRITICAL" in w])
            warning_count = len(config_warnings) - critical_count
            
            for warning in config_warnings:
                if "CRITICAL" in warning:
                    logger.error(f"Configuration error: {warning}")
                else:
                    logger.warning(f"Configuration warning: {warning}")
            
            if critical_count > 0:
                logger.error(f"Found {critical_count} critical configuration errors")
                if settings.FAIL_FAST_ON_CONFIG_ERROR:
                    logger.error("Fail-fast enabled, shutting down due to configuration errors")
                    raise RuntimeError(f"Configuration validation failed with {critical_count} critical errors")
            
            if warning_count > 0:
                logger.warning(f"Found {warning_count} configuration warnings")
        else:
            logger.info("Configuration validation passed")
            
    except Exception as e:
        if isinstance(e, RuntimeError) and "Configuration validation failed" in str(e):
            raise
        logger.error(f"Configuration validation error: {e}")
        if settings.FAIL_FAST_ON_CONFIG_ERROR:
            raise RuntimeError(f"Configuration validation failed: {e}")

    # Initialize health checker
    health_checker = get_health_checker()
    logger.info("Health checker initialized")

    # Startup all components
    startup_start = time.time()
    startup_success = await startup_all_components()

    if not startup_success:
        logger.error("Failed to startup components, shutting down...")
        raise RuntimeError("Component startup failed")

    # Initialize Agent Registry Service
    try:
        from backend.services.agents.agent_registry_service import agent_registry
        await agent_registry.initialize()
        logger.info("Agent Registry Service initialized")
    except ImportError:
        from services.agents.agent_registry_service import agent_registry
        await agent_registry.initialize()
        logger.info("Agent Registry Service initialized")
    except Exception as e:
        logger.error(f"Failed to initialize Agent Registry Service: {e}")
        # Don't fail startup for agent registry issues
        pass

    # Initialize Domain Agent Registries
    try:
        from backend.core.registry.init_registries import initialize_all_registries
        registry_success = initialize_all_registries()
        if registry_success:
            logger.info("Domain agent registries initialized successfully")
        else:
            logger.warning("Some domain registries failed to initialize")
    except ImportError:
        from core.registry.init_registries import initialize_all_registries
        registry_success = initialize_all_registries()
        if registry_success:
            logger.info("Domain agent registries initialized successfully")
        else:
            logger.warning("Some domain registries failed to initialize")
    except Exception as e:
        logger.error(f"Failed to initialize domain registries: {e}")
        # Don't fail startup for registry issues
        pass

    # Start Self-Building MCP Server
    self_building_server_task = None
    try:
        # Check if self-building is enabled
        if settings.ENABLE_SELF_BUILDING:
            logger.info("Starting Self-Building MCP Server...")
            
            # Import self-building server
            try:
                from backend.agents.self_building.self_building_mcp_server import app as self_building_app
                from backend.agents.self_building.config import get_config as get_self_building_config
            except ImportError:
                from agents.self_building.self_building_mcp_server import app as self_building_app
                from agents.self_building.config import get_config as get_self_building_config
            
            # Get self-building configuration
            sb_config = get_self_building_config()
            
            # Start self-building server in background
            import uvicorn
            
            async def run_self_building_server():
                """Run self-building MCP server in background."""
                config = uvicorn.Config(
                    self_building_app,
                    host=sb_config.mcp_host,
                    port=sb_config.mcp_port,
                    log_level=sb_config.log_level.lower()
                )
                server = uvicorn.Server(config)
                await server.serve()
            
            # Create background task
            self_building_server_task = asyncio.create_task(run_self_building_server())
            
            # Wait a moment for server to start
            await asyncio.sleep(2)
            
            # Register self-building agent in registry
            try:
                registration_result = await agent_registry.register_self_building_agent(
                    host=sb_config.mcp_host,
                    port=sb_config.mcp_port
                )
                
                if registration_result.get("success"):
                    logger.info(
                        f"Self-building agent registered at "
                        f"{registration_result.get('endpoint')}"
                    )
                else:
                    logger.error(
                        f"Failed to register self-building agent: "
                        f"{registration_result.get('error')}"
                    )
            except Exception as e:
                logger.error(f"Error registering self-building agent: {e}")
            
            logger.info("Self-Building MCP Server started successfully")
        else:
            logger.info("Self-building system is disabled by configuration")
            
    except Exception as e:
        logger.error(f"Failed to start Self-Building MCP Server: {e}")
        # Don't fail startup for self-building issues
        pass

    startup_duration = time.time() - startup_start
    logger.info("Backend startup completed", 
                startup_duration_seconds=startup_duration,
                observability_enabled=True)

    try:
        yield
    finally:
        # Shutdown
        logger.info("Shutting down Meetmind Backend...")
        
        # Shutdown Self-Building MCP Server
        if self_building_server_task and not self_building_server_task.done():
            try:
                logger.info("Shutting down Self-Building MCP Server...")
                self_building_server_task.cancel()
                try:
                    await self_building_server_task
                except asyncio.CancelledError:
                    pass
                logger.info("Self-Building MCP Server shutdown")
            except Exception as e:
                logger.error(f"Error shutting down Self-Building MCP Server: {e}")
        
        # Shutdown Agent Registry Service
        try:
            await agent_registry.shutdown()
            logger.info("Agent Registry Service shutdown")
        except Exception as e:
            logger.error(f"Error shutting down Agent Registry Service: {e}")
        
        await shutdown_all_components()
        
        # Cleanup rate limiting
        await cleanup_rate_limiter()
        await cleanup_rate_limit_monitor()
        
        # Cleanup security services
        await cleanup_api_key_manager()
        await cleanup_audit_logger()
        await cleanup_ip_whitelist_manager()
        await cleanup_threat_detector()
        
        logger.info("Backend shutdown completed")


# Create FastAPI application with lifespan management
app = FastAPI(
    title="Meetmind Backend API",
    description="Multi-User Agent Management API with MCP Integration",
    version="2.0.0",
    lifespan=lifespan
)

# Setup observability middleware
app.add_middleware(ObservabilityMiddleware)

# Setup enhanced observability middleware
try:
    from backend.modules.observability.middleware import ObservabilityMiddleware as EnhancedObservabilityMiddleware
    app.add_middleware(EnhancedObservabilityMiddleware)
except ImportError:
    from modules.observability.middleware import ObservabilityMiddleware as EnhancedObservabilityMiddleware
    app.add_middleware(EnhancedObservabilityMiddleware)

# Setup JSON schema validation middleware (before security for early validation)
app.add_middleware(JSONSchemaValidationMiddleware)

# Setup security middleware (before rate limiting for proper order)
app.add_middleware(SecurityMiddleware)

# Setup rate limiting middleware
app.add_middleware(RateLimitMiddleware)

# Setup CORS middleware
cors_origins = [
    settings.FRONTEND_URL,
    "http://localhost:3000",
    "http://localhost:3001",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:3001",
]

if settings.ENVIRONMENT == "development":
    cors_origins.append("*")

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global exception handler with observability
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler for unhandled errors with full observability"""
    logger = get_logger(__name__)
    
    error_id = f"err_{int(time.time())}"
    
    logger.error(
        f"Unhandled exception in {request.method} {request.url}",
        http_method=request.method,
        http_path=str(request.url.path),
        error_id=error_id,
        error_type=type(exc).__name__,
        error_message=str(exc),
        exc_info=True
    )

    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "detail": "Internal server error",
            "error_id": error_id,
            "error_type": type(exc).__name__
        },
        headers={
            "x-error-id": error_id
        }
    )

# Note: MetricsEndpointMiddleware is an ASGI middleware, not wrapped here  
# It's added in the ASGI app creation in uvicorn



# Root endpoint
@app.get("/")
async def root():
    """Root endpoint with basic information"""
    return {
        "name": "Meetmind Backend API",
        "version": "2.0.0",
        "description": "Multi-User Agent Management API with MCP Integration",
        "environment": settings.ENVIRONMENT,
        "health_endpoint": "/health",
        "docs_endpoint": "/docs"
    }

# Include routers with updated prefixes and tags
app.include_router(
    auth_router,
    prefix="/auth",
    tags=["Authentication"],
    responses={401: {"description": "Unauthorized"}, 403: {"description": "Forbidden"}}
)

# app.include_router(
#     agent_router,
#     prefix="/api",
#     tags=["Agents"],
#     responses={404: {"description": "Agent not found"}}
# )

app.include_router(
    meeting_router,
    prefix="/api",
    tags=["Meetings"],
    responses={404: {"description": "Meeting not found"}}
)

# app.include_router(
#     mcp_router,
#     prefix="/api",
#     tags=["MCP Integration"],
#     responses={502: {"description": "MCP server error"}, 504: {"description": "MCP timeout"}}
# )

# Disabled routes - require missing services
# app.include_router(
#     streaming_router,
#     prefix="/api",
#     tags=["Streaming"],
#     responses={400: {"description": "Invalid channel or meeting ID"}}
# )

# app.include_router(
#     export_router,
#     prefix="/api",
#     tags=["Exports"],
#     responses={500: {"description": "Export service error"}}
# )

# Optional: Mem0 routes (when available)
# app.include_router(mem0_router, prefix="/api", tags=["Memory"])

# Real-time pipeline routes
# app.include_router(
#     pipeline_router,
#     tags=["Real-time Pipeline"],
#     responses={500: {"description": "Pipeline processing error"}}
# )

# Observability routes
app.include_router(
    observability_router,
    prefix="/observability",
    tags=["Observability"],
    responses={503: {"description": "Service unavailable"}}
)

# Enhanced observability routes
app.include_router(
    observability_enhanced_router,
    prefix="/observability/enhanced",
    tags=["Enhanced Observability"],
    responses={503: {"description": "Service unavailable"}}
)

# Rate limiting routes
app.include_router(
    rate_limit_router,
    prefix="/admin/rate-limits",
    tags=["Rate Limiting"],
    responses={403: {"description": "Admin access required"}}
)

# Configuration and health routes
app.include_router(
    config_router,
    prefix="",  # No prefix for health endpoints
    tags=["Configuration & Health"],
    responses={503: {"description": "Service unavailable"}}
)

# Security management routes
app.include_router(
    security_router,
    prefix="/admin/security",
    tags=["Security Management"],
    responses={403: {"description": "Admin access required"}}
)

# MCP UI Hub routes - Central platform for multi-tenant UI resource management
app.include_router(
    mcp_ui_router,
    tags=["MCP UI Hub"],
    responses={401: {"description": "Unauthorized"}, 403: {"description": "Forbidden"}}
)

# MCP Adapter routes - Integration layer for MCP servers
app.include_router(
    mcp_adapter_router,
    tags=["MCP Adapter"],
    responses={401: {"description": "Unauthorized"}, 503: {"description": "MCP server unavailable"}}
)

# Agent Registry routes - Agent discovery and health monitoring
app.include_router(
    agent_registry_router,
    tags=["Agent Registry"],
)

# Development server configuration
if __name__ == "__main__":
    import uvicorn

    # Setup structured logging first
    setup_logging()

    # Get logger for main module
    logger = get_logger(__name__)

    # Server configuration
    server_config = {
        "host": settings.BACKEND_HOST,
        "port": settings.BACKEND_PORT,
        "log_level": settings.LOG_LEVEL.lower(),
        "access_log": True,
    }

    # Development-specific settings
    if settings.ENVIRONMENT == "development":
        server_config.update({
            "reload": True,
            "reload_dirs": ["backend"],
        })

        logger.info("Starting in development mode with auto-reload")
    else:
        logger.info("Starting in production mode")

    try:
        uvicorn.run(
            "main:app",
            **server_config
        )
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt, shutting down...")
    except Exception as e:
        logger.error(f"Server error: {e}")
        raise
