"""
Secure health check endpoints that report status without exposing secrets
"""

import asyncio
import time
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
import logging

from .settings import settings, validate_configuration, validate_secrets_strength


logger = logging.getLogger(__name__)


class HealthStatus:
    """Health status constants"""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


class ComponentHealth:
    """Represents the health status of a system component"""
    
    def __init__(self, name: str, status: str = HealthStatus.UNKNOWN, 
                 message: str = "", details: Optional[Dict[str, Any]] = None):
        self.name = name
        self.status = status
        self.message = message
        self.details = details or {}
        self.last_checked = datetime.now(timezone.utc)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            "name": self.name,
            "status": self.status,
            "message": self.message,
            "last_checked": self.last_checked.isoformat(),
            "details": self.details
        }


class SecureHealthChecker:
    """Secure health checker that doesn't expose sensitive information"""
    
    def __init__(self):
        self.components = {}
        self.last_full_check = None
    
    async def check_configuration_health(self) -> ComponentHealth:
        """Check configuration health without exposing secrets"""
        try:
            # Validate configuration
            validation_messages = validate_configuration(fail_fast=False)
            
            # Count critical vs warning messages
            critical_count = len([msg for msg in validation_messages if "CRITICAL" in msg])
            warning_count = len(validation_messages) - critical_count
            
            if critical_count > 0:
                status = HealthStatus.UNHEALTHY
                message = f"{critical_count} critical configuration errors"
            elif warning_count > 0:
                status = HealthStatus.DEGRADED
                message = f"{warning_count} configuration warnings"
            else:
                status = HealthStatus.HEALTHY
                message = "Configuration is valid"
            
            details = {
                "environment": settings.ENVIRONMENT,
                "critical_errors": critical_count,
                "warnings": warning_count,
                "has_ai_keys": bool(settings.OPENAI_API_KEY or settings.GOOGLE_AI_API_KEY),
                "has_livekit_config": bool(settings.LIVEKIT_URL and settings.LIVEKIT_API_KEY),
                "has_database_config": bool(settings.DATABASE_URL),
                "external_secrets_enabled": settings.AWS_SECRETS_MANAGER_ENABLED or settings.VAULT_ENABLED
            }
            
            return ComponentHealth("configuration", status, message, details)
            
        except Exception as e:
            logger.error(f"Configuration health check failed: {e}")
            return ComponentHealth(
                "configuration", 
                HealthStatus.UNHEALTHY, 
                "Configuration check failed",
                {"error": str(e)}
            )
    
    async def check_secrets_health(self) -> ComponentHealth:
        """Check secrets health without exposing actual values"""
        try:
            if not settings.VALIDATE_SECRETS_ON_STARTUP:
                return ComponentHealth(
                    "secrets", 
                    HealthStatus.UNKNOWN, 
                    "Secret validation disabled"
                )
            
            secret_results = validate_secrets_strength()
            
            # Count secrets with issues
            total_secrets = len(secret_results)
            secrets_with_issues = len([name for name, issues in secret_results.items() if issues])
            configured_secrets = len([name for name, issues in secret_results.items() 
                                    if not any("not configured" in issue for issue in issues)])
            
            if secrets_with_issues == 0:
                status = HealthStatus.HEALTHY
                message = f"All {configured_secrets} secrets are properly configured"
            elif secrets_with_issues < total_secrets / 2:
                status = HealthStatus.DEGRADED
                message = f"{secrets_with_issues}/{total_secrets} secrets have issues"
            else:
                status = HealthStatus.UNHEALTHY
                message = f"{secrets_with_issues}/{total_secrets} secrets have issues"
            
            details = {
                "total_secrets": total_secrets,
                "configured_secrets": configured_secrets,
                "secrets_with_issues": secrets_with_issues,
                "secret_names": list(secret_results.keys())
            }
            
            return ComponentHealth("secrets", status, message, details)
            
        except Exception as e:
            logger.error(f"Secrets health check failed: {e}")
            return ComponentHealth(
                "secrets", 
                HealthStatus.UNHEALTHY, 
                "Secrets check failed",
                {"error": str(e)}
            )
    
    async def check_database_health(self) -> ComponentHealth:
        """Check database connectivity"""
        try:
            # Basic database configuration check
            if not settings.DATABASE_URL:
                return ComponentHealth(
                    "database", 
                    HealthStatus.UNHEALTHY, 
                    "Database URL not configured"
                )
            
            # Check if it's a production-appropriate database
            is_sqlite = settings.DATABASE_URL.startswith("sqlite:")
            is_production = settings.ENVIRONMENT == "production"
            
            if is_sqlite and is_production:
                status = HealthStatus.DEGRADED
                message = "Using SQLite in production"
            else:
                status = HealthStatus.HEALTHY
                message = "Database configuration looks good"
            
            details = {
                "database_type": "sqlite" if is_sqlite else "external",
                "is_production": is_production,
                "url_configured": bool(settings.DATABASE_URL)
            }
            
            return ComponentHealth("database", status, message, details)
            
        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            return ComponentHealth(
                "database", 
                HealthStatus.UNHEALTHY, 
                "Database check failed",
                {"error": str(e)}
            )
    
    async def check_ai_services_health(self) -> ComponentHealth:
        """Check AI services configuration"""
        try:
            ai_keys = {
                "openai": bool(settings.OPENAI_API_KEY),
                "google_ai": bool(settings.GOOGLE_AI_API_KEY),
                "anthropic": bool(settings.ANTHROPIC_API_KEY)
            }
            
            configured_count = sum(ai_keys.values())
            
            if configured_count == 0:
                if settings.ENVIRONMENT == "production":
                    status = HealthStatus.UNHEALTHY
                    message = "No AI services configured in production"
                else:
                    status = HealthStatus.DEGRADED
                    message = "No AI services configured"
            elif configured_count == 1:
                status = HealthStatus.DEGRADED
                message = f"Only 1 AI service configured (no fallback)"
            else:
                status = HealthStatus.HEALTHY
                message = f"{configured_count} AI services configured"
            
            details = {
                "configured_services": configured_count,
                "available_services": list(ai_keys.keys()),
                "service_status": ai_keys
            }
            
            return ComponentHealth("ai_services", status, message, details)
            
        except Exception as e:
            logger.error(f"AI services health check failed: {e}")
            return ComponentHealth(
                "ai_services", 
                HealthStatus.UNHEALTHY, 
                "AI services check failed",
                {"error": str(e)}
            )
    
    async def check_external_services_health(self) -> ComponentHealth:
        """Check external services configuration"""
        try:
            services = {
                "livekit": bool(settings.LIVEKIT_URL and settings.LIVEKIT_API_KEY),
                "qdrant": bool(settings.QDRANT_URL),
                "redis": bool(settings.REDIS_URL),
                "sentry": bool(settings.SENTRY_DSN)
            }
            
            configured_count = sum(services.values())
            required_services = ["livekit"]  # Services required for basic functionality
            required_configured = sum(services[svc] for svc in required_services if svc in services)
            
            if required_configured < len(required_services):
                status = HealthStatus.UNHEALTHY
                message = f"Missing required services: {[svc for svc in required_services if not services.get(svc)]}"
            elif configured_count >= 3:
                status = HealthStatus.HEALTHY
                message = f"{configured_count} external services configured"
            else:
                status = HealthStatus.DEGRADED
                message = f"Only {configured_count} external services configured"
            
            details = {
                "configured_services": configured_count,
                "service_status": services,
                "required_services": required_services
            }
            
            return ComponentHealth("external_services", status, message, details)
            
        except Exception as e:
            logger.error(f"External services health check failed: {e}")
            return ComponentHealth(
                "external_services", 
                HealthStatus.UNHEALTHY, 
                "External services check failed",
                {"error": str(e)}
            )
    
    async def perform_full_health_check(self) -> Dict[str, ComponentHealth]:
        """Perform comprehensive health check on all components"""
        try:
            # Run all health checks concurrently
            health_checks = await asyncio.gather(
                self.check_configuration_health(),
                self.check_secrets_health(),
                self.check_database_health(),
                self.check_ai_services_health(),
                self.check_external_services_health(),
                return_exceptions=True
            )
            
            # Process results
            component_names = [
                "configuration", "secrets", "database", 
                "ai_services", "external_services"
            ]
            
            results = {}
            for i, result in enumerate(health_checks):
                if isinstance(result, Exception):
                    logger.error(f"Health check failed for {component_names[i]}: {result}")
                    results[component_names[i]] = ComponentHealth(
                        component_names[i], 
                        HealthStatus.UNHEALTHY, 
                        f"Health check failed: {str(result)}"
                    )
                else:
                    results[component_names[i]] = result
            
            self.components = results
            self.last_full_check = datetime.now(timezone.utc)
            
            return results
            
        except Exception as e:
            logger.error(f"Full health check failed: {e}")
            return {
                "system": ComponentHealth(
                    "system", 
                    HealthStatus.UNHEALTHY, 
                    f"Health check system failed: {str(e)}"
                )
            }
    
    def get_overall_status(self) -> Dict[str, Any]:
        """Get overall system health status"""
        if not self.components:
            return {
                "status": HealthStatus.UNKNOWN,
                "message": "No health checks performed yet",
                "last_checked": None
            }
        
        # Determine overall status
        statuses = [comp.status for comp in self.components.values()]
        
        if HealthStatus.UNHEALTHY in statuses:
            overall_status = HealthStatus.UNHEALTHY
            unhealthy_count = statuses.count(HealthStatus.UNHEALTHY)
            message = f"{unhealthy_count} components unhealthy"
        elif HealthStatus.DEGRADED in statuses:
            overall_status = HealthStatus.DEGRADED
            degraded_count = statuses.count(HealthStatus.DEGRADED)
            message = f"{degraded_count} components degraded"
        else:
            overall_status = HealthStatus.HEALTHY
            message = "All components healthy"
        
        return {
            "status": overall_status,
            "message": message,
            "last_checked": self.last_full_check.isoformat() if self.last_full_check else None,
            "component_count": len(self.components),
            "healthy_components": statuses.count(HealthStatus.HEALTHY),
            "degraded_components": statuses.count(HealthStatus.DEGRADED),
            "unhealthy_components": statuses.count(HealthStatus.UNHEALTHY)
        }


# Global health checker instance
_health_checker = SecureHealthChecker()


def get_health_checker() -> SecureHealthChecker:
    """Get the global health checker instance"""
    return _health_checker


async def get_system_health() -> Dict[str, Any]:
    """Get current system health status"""
    health_checker = get_health_checker()
    
    # Perform health check if not done recently
    if (not health_checker.last_full_check or 
        (datetime.now(timezone.utc) - health_checker.last_full_check).seconds > 300):
        await health_checker.perform_full_health_check()
    
    return health_checker.get_overall_status()


async def get_component_health(component_name: str = None) -> Dict[str, Any]:
    """Get health status for specific component or all components"""
    health_checker = get_health_checker()
    
    # Ensure we have recent health data
    if not health_checker.components:
        await health_checker.perform_full_health_check()
    
    if component_name:
        if component_name in health_checker.components:
            return health_checker.components[component_name].to_dict()
        else:
            return {
                "error": f"Component '{component_name}' not found",
                "available_components": list(health_checker.components.keys())
            }
    else:
        return {
            "overall": health_checker.get_overall_status(),
            "components": {
                name: comp.to_dict() 
                for name, comp in health_checker.components.items()
            }
        }