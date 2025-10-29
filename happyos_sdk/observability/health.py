"""
Standardized Health Monitoring for HappyOS SDK

Provides unified health check interfaces and metrics collection that works
consistently across all HappyOS agent systems.
"""

import time
import psutil
import asyncio
from typing import Dict, Any, Optional, List, Callable
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum

from .logging import get_logger, LogContext
from .telemetry import get_telemetry

logger = get_logger(__name__)


class HealthStatus(Enum):
    """Standardized health status levels."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


class DependencyStatus(Enum):
    """Status of external dependencies."""
    AVAILABLE = "available"
    DEGRADED = "degraded"
    UNAVAILABLE = "unavailable"
    UNKNOWN = "unknown"


@dataclass
class DependencyHealth:
    """Health status of an external dependency."""
    name: str
    status: DependencyStatus
    response_time_ms: Optional[float] = None
    error_message: Optional[str] = None
    last_check: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "name": self.name,
            "status": self.status.value,
            "response_time_ms": self.response_time_ms,
            "error_message": self.error_message,
            "last_check": self.last_check.isoformat()
        }


@dataclass
class CircuitBreakerHealth:
    """Health status of circuit breakers."""
    service_name: str
    status: str  # "closed", "open", "half_open"
    failure_count: int = 0
    last_failure: Optional[datetime] = None
    success_rate_percent: float = 100.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "service_name": self.service_name,
            "status": self.status,
            "failure_count": self.failure_count,
            "last_failure": self.last_failure.isoformat() if self.last_failure else None,
            "success_rate_percent": self.success_rate_percent
        }


@dataclass
class AgentMetrics:
    """Agent-specific performance metrics."""
    mcp_calls_total: int = 0
    mcp_calls_success: int = 0
    mcp_calls_failed: int = 0
    avg_response_time_ms: float = 0.0
    active_connections: int = 0
    memory_usage_mb: float = 0.0
    cpu_usage_percent: float = 0.0
    
    @property
    def success_rate_percent(self) -> float:
        """Calculate success rate percentage."""
        if self.mcp_calls_total == 0:
            return 100.0
        return (self.mcp_calls_success / self.mcp_calls_total) * 100.0
    
    @property
    def error_rate_percent(self) -> float:
        """Calculate error rate percentage."""
        return 100.0 - self.success_rate_percent
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "mcp_calls_total": self.mcp_calls_total,
            "mcp_calls_success": self.mcp_calls_success,
            "mcp_calls_failed": self.mcp_calls_failed,
            "success_rate_percent": self.success_rate_percent,
            "error_rate_percent": self.error_rate_percent,
            "avg_response_time_ms": self.avg_response_time_ms,
            "active_connections": self.active_connections,
            "memory_usage_mb": self.memory_usage_mb,
            "cpu_usage_percent": self.cpu_usage_percent
        }


@dataclass
class StandardHealthResponse:
    """Standardized health response format for all HappyOS agents."""
    
    # Agent identification
    agent_type: str
    agent_id: str
    version: str = "1.0.0"
    
    # Overall status
    status: HealthStatus = HealthStatus.HEALTHY
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    uptime_seconds: float = 0.0
    
    # Core performance metrics
    response_time_ms: float = 0.0
    error_rate_percent: float = 0.0
    
    # Agent-specific metrics
    agent_metrics: AgentMetrics = field(default_factory=AgentMetrics)
    
    # Dependencies and circuit breakers
    dependencies: List[DependencyHealth] = field(default_factory=list)
    circuit_breakers: List[CircuitBreakerHealth] = field(default_factory=list)
    
    # Compliance and isolation
    isolation_status: bool = True  # No backend.* imports
    mcp_protocol_version: str = "1.0"
    
    # Additional context
    tenant_id: Optional[str] = None
    environment: str = "development"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "agent_type": self.agent_type,
            "agent_id": self.agent_id,
            "version": self.version,
            "status": self.status.value,
            "timestamp": self.timestamp.isoformat(),
            "uptime_seconds": self.uptime_seconds,
            "response_time_ms": self.response_time_ms,
            "error_rate_percent": self.error_rate_percent,
            "agent_metrics": self.agent_metrics.to_dict(),
            "dependencies": [dep.to_dict() for dep in self.dependencies],
            "circuit_breakers": [cb.to_dict() for cb in self.circuit_breakers],
            "isolation_status": self.isolation_status,
            "mcp_protocol_version": self.mcp_protocol_version,
            "tenant_id": self.tenant_id,
            "environment": self.environment
        }
    
    def determine_overall_status(self) -> HealthStatus:
        """Determine overall health status based on metrics and dependencies."""
        # Check critical failures
        if self.error_rate_percent > 10.0:  # More than 10% errors
            return HealthStatus.UNHEALTHY
        
        if self.response_time_ms > 5000:  # Exceeds 5-second SLA
            return HealthStatus.UNHEALTHY
        
        if not self.isolation_status:  # Backend.* imports detected
            return HealthStatus.UNHEALTHY
        
        # Check circuit breakers
        open_breakers = [cb for cb in self.circuit_breakers if cb.status == "open"]
        if len(open_breakers) > 2:  # More than 2 circuit breakers open
            return HealthStatus.UNHEALTHY
        elif len(open_breakers) > 0:  # Some circuit breakers open
            return HealthStatus.DEGRADED
        
        # Check dependencies
        unavailable_deps = [dep for dep in self.dependencies if dep.status == DependencyStatus.UNAVAILABLE]
        if len(unavailable_deps) > 1:  # More than 1 critical dependency down
            return HealthStatus.UNHEALTHY
        elif len(unavailable_deps) > 0:  # Some dependencies down
            return HealthStatus.DEGRADED
        
        # Check performance degradation
        if self.error_rate_percent > 1.0 or self.response_time_ms > 1000:
            return HealthStatus.DEGRADED
        
        return HealthStatus.HEALTHY


class StandardizedHealthMonitor:
    """Standardized health monitoring for HappyOS agents."""
    
    def __init__(self, agent_type: str, agent_id: str, version: str = "1.0.0"):
        """
        Initialize health monitor.
        
        Args:
            agent_type: Type of agent (agent_svea, felicias_finance, meetmind)
            agent_id: Unique agent identifier
            version: Agent version
        """
        self.agent_type = agent_type
        self.agent_id = agent_id
        self.version = version
        self.start_time = time.time()
        
        # Health check functions
        self.dependency_checks: Dict[str, Callable] = {}
        self.circuit_breaker_checks: Dict[str, Callable] = {}
        self.custom_checks: Dict[str, Callable] = {}
        
        # Metrics tracking
        self.metrics = AgentMetrics()
        self.telemetry = get_telemetry()
        
        logger.info(f"Initialized health monitor for {agent_type}:{agent_id}")
    
    def register_dependency_check(self, name: str, check_func: Callable):
        """Register a dependency health check function."""
        self.dependency_checks[name] = check_func
        logger.debug(f"Registered dependency check: {name}")
    
    def register_circuit_breaker_check(self, name: str, check_func: Callable):
        """Register a circuit breaker health check function."""
        self.circuit_breaker_checks[name] = check_func
        logger.debug(f"Registered circuit breaker check: {name}")
    
    def register_custom_check(self, name: str, check_func: Callable):
        """Register a custom health check function."""
        self.custom_checks[name] = check_func
        logger.debug(f"Registered custom check: {name}")
    
    async def get_health_status(self, tenant_id: str = None) -> StandardHealthResponse:
        """Get comprehensive health status."""
        start_time = time.time()
        
        try:
            # Calculate uptime
            uptime_seconds = time.time() - self.start_time
            
            # Get system metrics
            await self._update_system_metrics()
            
            # Check dependencies
            dependencies = await self._check_dependencies()
            
            # Check circuit breakers
            circuit_breakers = await self._check_circuit_breakers()
            
            # Check isolation status
            isolation_status = await self._check_isolation_status()
            
            # Calculate response time for this health check
            response_time_ms = (time.time() - start_time) * 1000
            
            # Create health response
            health_response = StandardHealthResponse(
                agent_type=self.agent_type,
                agent_id=self.agent_id,
                version=self.version,
                timestamp=datetime.now(timezone.utc),
                uptime_seconds=uptime_seconds,
                response_time_ms=response_time_ms,
                error_rate_percent=self.metrics.error_rate_percent,
                agent_metrics=self.metrics,
                dependencies=dependencies,
                circuit_breakers=circuit_breakers,
                isolation_status=isolation_status,
                tenant_id=tenant_id
            )
            
            # Determine overall status
            health_response.status = health_response.determine_overall_status()
            
            # Record health check metrics
            self.telemetry.record_value(
                "health_check_duration",
                response_time_ms,
                tags={"agent_type": self.agent_type, "status": health_response.status.value}
            )
            
            logger.debug(
                f"Health check completed: {health_response.status.value}",
                extra={
                    "agent_type": self.agent_type,
                    "agent_id": self.agent_id,
                    "status": health_response.status.value,
                    "response_time_ms": response_time_ms,
                    "tenant_id": tenant_id
                }
            )
            
            return health_response
            
        except Exception as e:
            logger.error(f"Health check failed: {e}", exc_info=True)
            
            # Return unhealthy status on error
            return StandardHealthResponse(
                agent_type=self.agent_type,
                agent_id=self.agent_id,
                version=self.version,
                status=HealthStatus.UNHEALTHY,
                response_time_ms=(time.time() - start_time) * 1000,
                error_rate_percent=100.0,
                tenant_id=tenant_id
            )
    
    async def _update_system_metrics(self):
        """Update system performance metrics."""
        try:
            # Get process info
            process = psutil.Process()
            
            # Memory usage
            memory_info = process.memory_info()
            self.metrics.memory_usage_mb = memory_info.rss / 1024 / 1024
            
            # CPU usage
            self.metrics.cpu_usage_percent = process.cpu_percent()
            
            # Get telemetry summary for MCP metrics
            telemetry_summary = self.telemetry.get_telemetry_summary()
            metrics_data = telemetry_summary.get("metrics", {})
            
            # Update MCP call metrics from telemetry
            counters = metrics_data.get("counters", {})
            self.metrics.mcp_calls_total = counters.get("mcp_calls", 0)
            self.metrics.mcp_calls_success = counters.get("mcp_calls_success", 0)
            self.metrics.mcp_calls_failed = counters.get("mcp_calls_failed", 0)
            
            # Calculate average response time from histograms
            histograms = metrics_data.get("histograms", {})
            mcp_duration = histograms.get("mcp_call_duration", {})
            if mcp_duration and mcp_duration.get("count", 0) > 0:
                self.metrics.avg_response_time_ms = mcp_duration.get("avg", 0.0)
            
        except Exception as e:
            logger.warning(f"Failed to update system metrics: {e}")
    
    async def _check_dependencies(self) -> List[DependencyHealth]:
        """Check health of all registered dependencies."""
        dependencies = []
        
        for name, check_func in self.dependency_checks.items():
            try:
                start_time = time.time()
                
                # Run dependency check
                if asyncio.iscoroutinefunction(check_func):
                    result = await check_func()
                else:
                    result = check_func()
                
                response_time_ms = (time.time() - start_time) * 1000
                
                # Parse result
                if isinstance(result, bool):
                    status = DependencyStatus.AVAILABLE if result else DependencyStatus.UNAVAILABLE
                    error_message = None
                elif isinstance(result, dict):
                    status = DependencyStatus(result.get("status", "unknown"))
                    error_message = result.get("error")
                else:
                    status = DependencyStatus.UNKNOWN
                    error_message = f"Invalid check result: {result}"
                
                dependencies.append(DependencyHealth(
                    name=name,
                    status=status,
                    response_time_ms=response_time_ms,
                    error_message=error_message
                ))
                
            except Exception as e:
                logger.error(f"Dependency check failed for {name}: {e}")
                dependencies.append(DependencyHealth(
                    name=name,
                    status=DependencyStatus.UNAVAILABLE,
                    error_message=str(e)
                ))
        
        return dependencies
    
    async def _check_circuit_breakers(self) -> List[CircuitBreakerHealth]:
        """Check status of all registered circuit breakers."""
        circuit_breakers = []
        
        for name, check_func in self.circuit_breaker_checks.items():
            try:
                # Run circuit breaker check
                if asyncio.iscoroutinefunction(check_func):
                    result = await check_func()
                else:
                    result = check_func()
                
                # Parse result
                if isinstance(result, dict):
                    circuit_breakers.append(CircuitBreakerHealth(
                        service_name=name,
                        status=result.get("status", "unknown"),
                        failure_count=result.get("failure_count", 0),
                        last_failure=result.get("last_failure"),
                        success_rate_percent=result.get("success_rate_percent", 100.0)
                    ))
                else:
                    logger.warning(f"Invalid circuit breaker check result for {name}: {result}")
                
            except Exception as e:
                logger.error(f"Circuit breaker check failed for {name}: {e}")
                circuit_breakers.append(CircuitBreakerHealth(
                    service_name=name,
                    status="unknown",
                    failure_count=0,
                    success_rate_percent=0.0
                ))
        
        return circuit_breakers
    
    async def _check_isolation_status(self) -> bool:
        """Check if agent maintains proper isolation (no backend.* imports)."""
        try:
            # Check for backend.* imports in current process modules
            import sys
            
            backend_imports = [
                module_name for module_name in sys.modules.keys()
                if module_name.startswith('backend.')
            ]
            
            # Allow specific backend modules that are part of the translation layer
            allowed_backend_modules = {
                'backend.modules.observability.audit_logger',
                'backend.modules.observability.cloudwatch',
                'backend.modules.observability.xray_tracing',
                'backend.services.observability.logger'
            }
            
            # Filter out allowed modules
            violation_imports = [
                module for module in backend_imports
                if module not in allowed_backend_modules
            ]
            
            if violation_imports:
                logger.warning(
                    f"Isolation violation detected: {violation_imports}",
                    extra={
                        "agent_type": self.agent_type,
                        "violation_imports": violation_imports
                    }
                )
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to check isolation status: {e}")
            return False
    
    def record_mcp_call(self, success: bool, duration_ms: float):
        """Record MCP call metrics."""
        self.telemetry.increment_counter("mcp_calls")
        
        if success:
            self.telemetry.increment_counter("mcp_calls_success")
        else:
            self.telemetry.increment_counter("mcp_calls_failed")
        
        self.telemetry.record_timing("mcp_call_duration", duration_ms)
    
    def record_connection_count(self, count: int):
        """Record active connection count."""
        self.metrics.active_connections = count
        self.telemetry.set_gauge("active_connections", count)


# Convenience functions for common dependency checks

async def check_http_endpoint(url: str, timeout: float = 5.0) -> Dict[str, Any]:
    """Check HTTP endpoint health."""
    import aiohttp
    
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=timeout)) as session:
            async with session.get(url) as response:
                if response.status == 200:
                    return {"status": "available"}
                else:
                    return {"status": "degraded", "error": f"HTTP {response.status}"}
    
    except Exception as e:
        return {"status": "unavailable", "error": str(e)}


async def check_database_connection(connection_func: Callable) -> Dict[str, Any]:
    """Check database connection health."""
    try:
        if asyncio.iscoroutinefunction(connection_func):
            result = await connection_func()
        else:
            result = connection_func()
        
        return {"status": "available" if result else "unavailable"}
    
    except Exception as e:
        return {"status": "unavailable", "error": str(e)}


def check_file_system_access(path: str) -> Dict[str, Any]:
    """Check file system access health."""
    import os
    
    try:
        if os.path.exists(path) and os.access(path, os.R_OK | os.W_OK):
            return {"status": "available"}
        else:
            return {"status": "unavailable", "error": "Path not accessible"}
    
    except Exception as e:
        return {"status": "unavailable", "error": str(e)}


# Global health monitor instances
_health_monitors: Dict[str, StandardizedHealthMonitor] = {}


def get_health_monitor(agent_type: str, agent_id: str, version: str = "1.0.0") -> StandardizedHealthMonitor:
    """Get or create standardized health monitor for an agent."""
    key = f"{agent_type}:{agent_id}"
    
    if key not in _health_monitors:
        _health_monitors[key] = StandardizedHealthMonitor(agent_type, agent_id, version)
    
    return _health_monitors[key]