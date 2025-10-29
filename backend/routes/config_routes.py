"""
Secure Configuration and Health Check Routes

Provides endpoints for configuration validation and health monitoring
without exposing sensitive information.
"""

import time
from typing import Dict, Any, Optional
from fastapi import APIRouter, HTTPException, status, Depends
from fastapi.responses import JSONResponse

try:
    from backend.modules.config import (
        settings, 
        validate_configuration, 
        validate_secrets_strength,
        get_health_checker,
        get_system_health,
        get_component_health
    )
    from backend.modules.config.settings import ConfigurationError
except ImportError:
    from modules.config import (
        settings, 
        validate_configuration, 
        validate_secrets_strength,
        get_health_checker,
        get_system_health,
        get_component_health
    )
    from modules.config.settings import ConfigurationError

router = APIRouter()


@router.get("/health")
async def basic_health_check():
    """
    Basic health check endpoint - no sensitive information exposed
    
    Returns basic system status suitable for load balancers and monitoring.
    """
    try:
        system_health = await get_system_health()
        
        return {
            "status": system_health["status"],
            "timestamp": time.time(),
            "environment": settings.ENVIRONMENT,
            "version": "2.0.0",
            "message": system_health["message"]
        }
    except Exception as e:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "status": "unhealthy",
                "timestamp": time.time(),
                "environment": settings.ENVIRONMENT,
                "version": "2.0.0",
                "message": "Health check failed",
                "error": str(e)
            }
        )


@router.get("/health/detailed")
async def detailed_health_check():
    """
    Detailed health check with component status - no secrets exposed
    
    Provides comprehensive health information for monitoring dashboards.
    """
    try:
        health_data = await get_component_health()
        
        return {
            "timestamp": time.time(),
            "environment": settings.ENVIRONMENT,
            "version": "2.0.0",
            **health_data
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Detailed health check failed: {str(e)}"
        )


@router.get("/health/component/{component_name}")
async def component_health_check(component_name: str):
    """
    Check health of a specific component
    
    Available components: configuration, secrets, database, ai_services, external_services
    """
    try:
        component_data = await get_component_health(component_name)
        
        if "error" in component_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=component_data["error"]
            )
        
        return {
            "timestamp": time.time(),
            "component": component_data
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Component health check failed for {component_name}: {str(e)}"
        )


@router.post("/health/refresh")
async def refresh_health_checks():
    """
    Manually trigger fresh health checks on all components
    
    Useful for forcing a health check update after configuration changes.
    """
    try:
        health_checker = get_health_checker()
        health_results = await health_checker.perform_full_health_check()
        
        return {
            "status": "success",
            "timestamp": time.time(),
            "message": "Health checks refreshed",
            "components": {
                name: comp.to_dict()
                for name, comp in health_results.items()
            }
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Health check refresh failed: {str(e)}"
        )


@router.get("/config/status")
async def configuration_status():
    """
    Get configuration validation status without exposing secrets
    
    Returns configuration validation results and recommendations.
    """
    try:
        # Validate configuration
        validation_messages = validate_configuration(fail_fast=False)
        
        # Count critical vs warning messages
        critical_count = len([msg for msg in validation_messages if "CRITICAL" in msg])
        warning_count = len(validation_messages) - critical_count
        
        # Determine overall status
        if critical_count > 0:
            status_value = "error"
            message = f"{critical_count} critical configuration errors"
        elif warning_count > 0:
            status_value = "warning"
            message = f"{warning_count} configuration warnings"
        else:
            status_value = "ok"
            message = "Configuration is valid"
        
        # Prepare safe configuration info
        config_info = {
            "environment": settings.ENVIRONMENT,
            "fail_fast_enabled": settings.FAIL_FAST_ON_CONFIG_ERROR,
            "secret_validation_enabled": settings.VALIDATE_SECRETS_ON_STARTUP,
            "external_secrets_enabled": settings.AWS_SECRETS_MANAGER_ENABLED or settings.VAULT_ENABLED,
            "services": {
                "database": bool(settings.DATABASE_URL),
                "ai_services": bool(settings.OPENAI_API_KEY or settings.GOOGLE_AI_API_KEY or settings.ANTHROPIC_API_KEY),
                "livekit": bool(settings.LIVEKIT_URL and settings.LIVEKIT_API_KEY),
                "qdrant": bool(settings.QDRANT_URL),
                "redis": bool(settings.REDIS_URL),
                "monitoring": bool(settings.SENTRY_DSN)
            }
        }
        
        return {
            "status": status_value,
            "message": message,
            "timestamp": time.time(),
            "validation": {
                "critical_errors": critical_count,
                "warnings": warning_count,
                "total_issues": len(validation_messages)
            },
            "configuration": config_info
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Configuration status check failed: {str(e)}"
        )


@router.get("/config/secrets/status")
async def secrets_status():
    """
    Get secret validation status without exposing actual secret values
    
    Returns information about secret configuration and validation results.
    """
    try:
        if not settings.VALIDATE_SECRETS_ON_STARTUP:
            return {
                "status": "disabled",
                "message": "Secret validation is disabled",
                "timestamp": time.time()
            }
        
        # Validate secrets
        secret_results = validate_secrets_strength()
        
        # Count secrets with issues
        total_secrets = len(secret_results)
        secrets_with_issues = len([name for name, issues in secret_results.items() if issues])
        configured_secrets = len([name for name, issues in secret_results.items() 
                                if not any("not configured" in issue for issue in issues)])
        
        # Determine status
        if secrets_with_issues == 0:
            status_value = "ok"
            message = f"All {configured_secrets} secrets are properly configured"
        elif secrets_with_issues < total_secrets / 2:
            status_value = "warning"
            message = f"{secrets_with_issues}/{total_secrets} secrets have issues"
        else:
            status_value = "error"
            message = f"{secrets_with_issues}/{total_secrets} secrets have issues"
        
        # Prepare secret status (without values)
        secret_status = {}
        for name, issues in secret_results.items():
            if not issues:
                secret_status[name] = "valid"
            elif any("not configured" in issue for issue in issues):
                secret_status[name] = "not_configured"
            else:
                secret_status[name] = "issues"
        
        return {
            "status": status_value,
            "message": message,
            "timestamp": time.time(),
            "summary": {
                "total_secrets": total_secrets,
                "configured_secrets": configured_secrets,
                "secrets_with_issues": secrets_with_issues
            },
            "secrets": secret_status
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Secret status check failed: {str(e)}"
        )


@router.get("/config/validate")
async def validate_configuration_endpoint():
    """
    Validate current configuration and return detailed results
    
    Performs comprehensive configuration validation without exposing secrets.
    """
    try:
        # Validate configuration
        validation_messages = validate_configuration(fail_fast=False)
        
        # Separate critical errors from warnings
        critical_errors = [msg for msg in validation_messages if "CRITICAL" in msg]
        warnings = [msg for msg in validation_messages if "CRITICAL" not in msg]
        
        # Validate secrets if enabled
        secret_validation = {}
        if settings.VALIDATE_SECRETS_ON_STARTUP:
            secret_results = validate_secrets_strength()
            secret_validation = {
                "enabled": True,
                "total_secrets": len(secret_results),
                "secrets_with_issues": len([name for name, issues in secret_results.items() if issues])
            }
        else:
            secret_validation = {"enabled": False}
        
        # Determine overall validation status
        if critical_errors:
            overall_status = "failed"
            overall_message = f"Validation failed with {len(critical_errors)} critical errors"
        elif warnings:
            overall_status = "passed_with_warnings"
            overall_message = f"Validation passed with {len(warnings)} warnings"
        else:
            overall_status = "passed"
            overall_message = "All validation checks passed"
        
        return {
            "status": overall_status,
            "message": overall_message,
            "timestamp": time.time(),
            "validation_results": {
                "critical_errors": len(critical_errors),
                "warnings": len(warnings),
                "total_issues": len(validation_messages)
            },
            "secret_validation": secret_validation,
            "environment": settings.ENVIRONMENT,
            "configuration": {
                "fail_fast_enabled": settings.FAIL_FAST_ON_CONFIG_ERROR,
                "secret_validation_enabled": settings.VALIDATE_SECRETS_ON_STARTUP,
                "external_secrets_enabled": settings.AWS_SECRETS_MANAGER_ENABLED or settings.VAULT_ENABLED
            }
        }
        
    except ConfigurationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Configuration validation failed: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Configuration validation failed: {str(e)}"
        )


@router.get("/system/info")
async def system_information():
    """
    Get system information and configuration - no sensitive data exposed
    
    Provides system information suitable for monitoring and debugging.
    """
    try:
        # Safe environment information
        env_info = {
            "environment": settings.ENVIRONMENT,
            "backend_host": settings.BACKEND_HOST if settings.BACKEND_HOST != "0.0.0.0" else "configured",
            "backend_port": settings.BACKEND_PORT,
            "log_level": settings.LOG_LEVEL,
            "debug_mode": settings.BACKEND_DEBUG
        }
        
        # Configuration status
        config_status = {
            "has_ai_services": bool(settings.OPENAI_API_KEY or settings.GOOGLE_AI_API_KEY or settings.ANTHROPIC_API_KEY),
            "has_livekit": bool(settings.LIVEKIT_URL and settings.LIVEKIT_API_KEY),
            "has_database": bool(settings.DATABASE_URL),
            "has_redis": bool(settings.REDIS_URL),
            "has_qdrant": bool(settings.QDRANT_URL != "localhost:6333" or settings.QDRANT_API_KEY),
            "external_secrets_enabled": settings.AWS_SECRETS_MANAGER_ENABLED or settings.VAULT_ENABLED,
            "fail_fast_enabled": settings.FAIL_FAST_ON_CONFIG_ERROR,
            "secret_validation_enabled": settings.VALIDATE_SECRETS_ON_STARTUP
        }
        
        # Feature status
        features = {
            "summarizer": settings.SUMMARIZER_ENABLED,
            "analytics": settings.ANALYTICS_ENABLED,
            "monitoring": bool(settings.SENTRY_DSN)
        }
        
        return {
            "environment": env_info,
            "configuration": config_status,
            "features": features,
            "timestamp": time.time(),
            "version": "2.0.0"
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"System information retrieval failed: {str(e)}"
        )


# Production readiness check
@router.get("/config/production-readiness")
async def production_readiness_check():
    """
    Check if the system is ready for production deployment
    
    Validates all production requirements and returns a readiness score.
    """
    try:
        if settings.ENVIRONMENT != "production":
            return {
                "ready": True,
                "message": "Not in production environment",
                "environment": settings.ENVIRONMENT,
                "timestamp": time.time()
            }
        
        # Production readiness checklist
        checks = {
            "jwt_secret_secure": len(settings.SECRET_KEY) >= 32 and settings.SECRET_KEY not in ["your-secret-key", "change-me"],
            "debug_disabled": not settings.BACKEND_DEBUG,
            "fail_fast_enabled": settings.FAIL_FAST_ON_CONFIG_ERROR,
            "secret_validation_enabled": settings.VALIDATE_SECRETS_ON_STARTUP,
            "ai_service_configured": bool(settings.OPENAI_API_KEY or settings.GOOGLE_AI_API_KEY or settings.ANTHROPIC_API_KEY),
            "livekit_configured": bool(settings.LIVEKIT_URL and settings.LIVEKIT_API_KEY),
            "production_database": not settings.DATABASE_URL.startswith("sqlite:"),
            "external_secrets_enabled": settings.AWS_SECRETS_MANAGER_ENABLED or settings.VAULT_ENABLED,
            "monitoring_enabled": bool(settings.SENTRY_DSN),
            "https_frontend": settings.FRONTEND_URL.startswith("https://")
        }
        
        # Calculate readiness score
        passed_checks = sum(checks.values())
        total_checks = len(checks)
        readiness_score = (passed_checks / total_checks) * 100
        
        # Determine readiness status
        if readiness_score >= 90:
            ready = True
            message = f"Production ready ({readiness_score:.0f}% score)"
        elif readiness_score >= 70:
            ready = False
            message = f"Mostly ready with some issues ({readiness_score:.0f}% score)"
        else:
            ready = False
            message = f"Not ready for production ({readiness_score:.0f}% score)"
        
        return {
            "ready": ready,
            "message": message,
            "readiness_score": readiness_score,
            "checks_passed": passed_checks,
            "total_checks": total_checks,
            "checks": checks,
            "timestamp": time.time()
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Production readiness check failed: {str(e)}"
        )