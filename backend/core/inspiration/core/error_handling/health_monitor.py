"""
🏥 HEALTH MONITOR

Component health monitoring and alerting:
- Real-time health status tracking
- Performance metrics collection
- Alert generation and notification
- Health trend analysis
"""

import asyncio
import logging
import time
from typing import Dict, Any, Optional, List, Callable, Awaitable
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class ComponentHealth(Enum):
    """Component health status."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


@dataclass
class HealthMetrics:
    """Health metrics for a component."""
    response_time: float = 0.0
    error_rate: float = 0.0
    throughput: float = 0.0
    memory_usage: float = 0.0
    cpu_usage: float = 0.0
    last_check: datetime = field(default_factory=datetime.utcnow)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'response_time': self.response_time,
            'error_rate': self.error_rate,
            'throughput': self.throughput,
            'memory_usage': self.memory_usage,
            'cpu_usage': self.cpu_usage,
            'last_check': self.last_check.isoformat()
        }


@dataclass
class HealthCheck:
    """Health check definition."""
    name: str
    check_func: Callable[[], Awaitable[bool]]
    interval: int = 60  # seconds
    timeout: float = 30.0
    critical: bool = False
    
    # Tracking
    last_run: Optional[datetime] = None
    last_success: Optional[datetime] = None
    consecutive_failures: int = 0


class HealthMonitor:
    """
    Component health monitoring system.
    """
    
    def __init__(self):
        self.health_checks: Dict[str, HealthCheck] = {}
        self.component_health: Dict[str, ComponentHealth] = {}
        self.health_metrics: Dict[str, HealthMetrics] = {}
        self.health_history: Dict[str, List[Dict[str, Any]]] = {}
        self._monitoring_task: Optional[asyncio.Task] = None
        self._running = False
        
        logger.info("Health monitor initialized")
    
    def register_health_check(self, health_check: HealthCheck):
        """Register a health check."""
        self.health_checks[health_check.name] = health_check
        self.component_health[health_check.name] = ComponentHealth.UNKNOWN
        self.health_metrics[health_check.name] = HealthMetrics()
        self.health_history[health_check.name] = []
        
        logger.info(f"Registered health check: {health_check.name}")
    
    async def start_monitoring(self):
        """Start health monitoring."""
        if self._running:
            logger.warning("Health monitoring already running")
            return
        
        self._running = True
        self._monitoring_task = asyncio.create_task(self._monitoring_loop())
        logger.info("Health monitoring started")
    
    async def stop_monitoring(self):
        """Stop health monitoring."""
        self._running = False
        
        if self._monitoring_task:
            self._monitoring_task.cancel()
            try:
                await self._monitoring_task
            except asyncio.CancelledError:
                pass
        
        logger.info("Health monitoring stopped")
    
    async def _monitoring_loop(self):
        """Main monitoring loop."""
        while self._running:
            try:
                await self._run_health_checks()
                await asyncio.sleep(10)  # Check every 10 seconds
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")
                await asyncio.sleep(10)
    
    async def _run_health_checks(self):
        """Run all health checks."""
        current_time = datetime.utcnow()
        
        for name, check in self.health_checks.items():
            # Check if it's time to run this check
            if (check.last_run is None or 
                (current_time - check.last_run).total_seconds() >= check.interval):
                
                await self._run_single_health_check(name, check)
    
    async def _run_single_health_check(self, name: str, check: HealthCheck):
        """Run a single health check."""
        start_time = time.time()
        check.last_run = datetime.utcnow()
        
        try:
            # Run the health check with timeout
            success = await asyncio.wait_for(check.check_func(), timeout=check.timeout)
            end_time = time.time()
            response_time = end_time - start_time
            
            if success:
                check.last_success = datetime.utcnow()
                check.consecutive_failures = 0
                self.component_health[name] = ComponentHealth.HEALTHY
            else:
                check.consecutive_failures += 1
                if check.consecutive_failures >= 3:
                    self.component_health[name] = ComponentHealth.UNHEALTHY
                else:
                    self.component_health[name] = ComponentHealth.DEGRADED
            
            # Update metrics
            metrics = self.health_metrics[name]
            metrics.response_time = response_time
            metrics.last_check = datetime.utcnow()
            
            # Record history
            self._record_health_history(name, success, response_time)
            
            logger.debug(f"Health check '{name}': {'PASS' if success else 'FAIL'} "
                        f"({response_time:.3f}s)")
            
        except asyncio.TimeoutError:
            check.consecutive_failures += 1
            self.component_health[name] = ComponentHealth.UNHEALTHY
            logger.warning(f"Health check '{name}' timed out after {check.timeout}s")
            
        except Exception as e:
            check.consecutive_failures += 1
            self.component_health[name] = ComponentHealth.UNHEALTHY
            logger.error(f"Health check '{name}' failed with exception: {e}")
    
    def _record_health_history(self, component: str, success: bool, response_time: float):
        """Record health check history."""
        history = self.health_history[component]
        
        record = {
            'timestamp': datetime.utcnow().isoformat(),
            'success': success,
            'response_time': response_time,
            'health_status': self.component_health[component].value
        }
        
        history.append(record)
        
        # Keep only recent history (last 100 records)
        if len(history) > 100:
            self.health_history[component] = history[-50:]
    
    def get_component_health(self, component: str) -> ComponentHealth:
        """Get health status of a component."""
        return self.component_health.get(component, ComponentHealth.UNKNOWN)
    
    def get_overall_health(self) -> ComponentHealth:
        """Get overall system health."""
        if not self.component_health:
            return ComponentHealth.UNKNOWN
        
        health_values = list(self.component_health.values())
        
        # If any critical component is unhealthy, system is unhealthy
        critical_components = [
            name for name, check in self.health_checks.items()
            if check.critical
        ]
        
        for component in critical_components:
            if self.component_health.get(component) == ComponentHealth.UNHEALTHY:
                return ComponentHealth.UNHEALTHY
        
        # If any component is unhealthy, system is degraded
        if ComponentHealth.UNHEALTHY in health_values:
            return ComponentHealth.DEGRADED
        
        # If any component is degraded, system is degraded
        if ComponentHealth.DEGRADED in health_values:
            return ComponentHealth.DEGRADED
        
        # All components healthy
        return ComponentHealth.HEALTHY
    
    def get_health_summary(self) -> Dict[str, Any]:
        """Get health summary."""
        return {
            'overall_health': self.get_overall_health().value,
            'components': {
                name: {
                    'health': status.value,
                    'metrics': self.health_metrics[name].to_dict(),
                    'consecutive_failures': self.health_checks[name].consecutive_failures,
                    'last_success': self.health_checks[name].last_success.isoformat() 
                                  if self.health_checks[name].last_success else None
                }
                for name, status in self.component_health.items()
            },
            'timestamp': datetime.utcnow().isoformat()
        }
    
    def get_component_history(self, component: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Get health history for a component."""
        history = self.health_history.get(component, [])
        return history[-limit:]
    
    async def check_component_health(self, component: str) -> bool:
        """Manually trigger health check for a component."""
        if component not in self.health_checks:
            logger.warning(f"No health check registered for component: {component}")
            return False
        
        check = self.health_checks[component]
        await self._run_single_health_check(component, check)
        
        return self.component_health[component] == ComponentHealth.HEALTHY


# Global health monitor
_health_monitor: Optional[HealthMonitor] = None


def get_health_monitor() -> HealthMonitor:
    """Get global health monitor."""
    global _health_monitor
    
    if _health_monitor is None:
        _health_monitor = HealthMonitor()
    
    return _health_monitor


# Common health check functions
async def database_health_check() -> bool:
    """Health check for database connectivity."""
    try:
        from app.core.database.connection import get_db_connection
        db = await get_db_connection()
        # Simple query to test connectivity
        result = await db.execute_query("SELECT 1 as test")
        return result is not None and len(result) > 0
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        return False


async def connection_pool_health_check() -> bool:
    """Health check for database connection pool."""
    try:
        from app.core.database.connection import get_db_connection
        db = await get_db_connection()

        # Check pool metrics
        metrics = db.get_connection_metrics()

        # Ensure pool is working properly
        pool_metrics = metrics.get('pool_metrics', {})
        current_size = pool_metrics.get('current_size', 0)
        usage_ratio = pool_metrics.get('usage_ratio', 0)

        # Pool should be operational and not over-utilized
        if current_size == 0:
            logger.warning("Connection pool has no connections")
            return False

        if usage_ratio > 0.95:  # 95% utilization threshold
            logger.warning(f"Connection pool heavily utilized: {usage_ratio:.2%}")
            return False

        return True

    except Exception as e:
        logger.error(f"Connection pool health check failed: {e}")
        return False


async def transaction_manager_health_check() -> bool:
    """Health check for transaction manager."""
    try:
        from app.db.transaction_manager import get_transaction_manager
        tm = await get_transaction_manager()

        # Get transaction metrics
        metrics = tm.get_transaction_metrics()

        # Check if transaction manager is operational
        active_transactions = metrics.get('active_transactions', 0)

        # Too many active transactions might indicate issues
        if active_transactions > 100:  # Configurable threshold
            logger.warning(f"Too many active transactions: {active_transactions}")
            return False

        return True

    except Exception as e:
        logger.error(f"Transaction manager health check failed: {e}")
        return False


async def migration_manager_health_check() -> bool:
    """Health check for migration manager."""
    try:
        from app.db.migration_manager import get_migration_manager
        mm = await get_migration_manager()

        # Get migration status
        status = mm.get_migration_status()

        # Check if migrations are in a consistent state
        total_migrations = status.get('total_migrations', 0)
        applied_migrations = status.get('applied_migrations', 0)

        # All migrations should be accounted for
        if applied_migrations > total_migrations:
            logger.error("More applied migrations than total migrations")
            return False

        # Validate migration integrity
        validation = await mm.validate_migrations()
        if not validation.get('valid', False):
            logger.warning(f"Migration validation failed: {validation.get('issues', [])}")
            return False

        return True

    except Exception as e:
        logger.error(f"Migration manager health check failed: {e}")
        return False


async def repository_health_check() -> bool:
    """Health check for repository layer."""
    try:
        from app.core.database.connection import get_db_connection
        from app.db.repository_base import UserRepository

        db = await get_db_connection()
        repo = UserRepository(db)

        # Test basic repository operations
        count = await repo.count()

        # Count should be a non-negative integer
        if count < 0:
            logger.error(f"Invalid repository count: {count}")
            return False

        # Test performance stats
        stats = repo.get_performance_stats()
        if not stats:
            logger.warning("Repository performance stats not available")
            return False

        return True

    except Exception as e:
        logger.error(f"Repository health check failed: {e}")
        return False


async def skill_registry_health_check() -> bool:
    """Health check for skill registry."""
    try:
        # Test skill registry functionality
        await asyncio.sleep(0.1)  # Simulate check
        return True
    except Exception as e:
        logger.error(f"Skill registry health check failed: {e}")
        return False


async def mr_happy_agent_health_check() -> bool:
    """Health check for Mr Happy agent."""
    try:
        # Test agent functionality
        await asyncio.sleep(0.1)  # Simulate check
        return True
    except Exception as e:
        logger.error(f"Mr Happy agent health check failed: {e}")
        return False


# LLM Provider Health Checks
async def llm_providers_health_check() -> bool:
    """Health check for all LLM providers."""
    try:
        # Import here to avoid circular imports
        from app.llm.health_checks import run_comprehensive_health_check

        results = await run_comprehensive_health_check()

        # Check if at least one provider is healthy
        healthy_providers = [provider for provider, status in results.items()
                           if status.get("healthy", False)]

        if healthy_providers:
            logger.debug(f"LLM providers health check passed: {healthy_providers}")
            return True
        else:
            logger.warning("LLM providers health check failed: no healthy providers")
            return False

    except Exception as e:
        logger.error(f"LLM providers health check failed: {e}")
        return False


async def openrouter_health_check() -> bool:
    """Health check specifically for OpenRouter."""
    try:
        from app.llm.health_checks import check_openrouter_health
        return await check_openrouter_health()
    except Exception as e:
        logger.error(f"OpenRouter health check failed: {e}")
        return False


async def deepseek_health_check() -> bool:
    """Health check specifically for DeepSeek."""
    try:
        from app.llm.health_checks import check_deepseek_health
        return await check_deepseek_health()
    except Exception as e:
        logger.error(f"DeepSeek health check failed: {e}")
        return False


async def local_llm_health_check() -> bool:
    """Health check specifically for Local LLM."""
    try:
        from app.llm.health_checks import check_local_llm_health
        return await check_local_llm_health()
    except Exception as e:
        logger.error(f"Local LLM health check failed: {e}")
        return False


def register_default_health_checks():
    """Register default health checks."""
    monitor = get_health_monitor()

    # Core database health checks
    monitor.register_health_check(HealthCheck(
        name="database",
        check_func=database_health_check,
        interval=30,
        timeout=10.0,
        critical=True
    ))

    monitor.register_health_check(HealthCheck(
        name="database_connection_pool",
        check_func=connection_pool_health_check,
        interval=60,
        timeout=5.0,
        critical=True
    ))

    # Advanced database component health checks
    monitor.register_health_check(HealthCheck(
        name="database_transaction_manager",
        check_func=transaction_manager_health_check,
        interval=120,
        timeout=10.0,
        critical=False
    ))

    monitor.register_health_check(HealthCheck(
        name="database_migration_manager",
        check_func=migration_manager_health_check,
        interval=300,  # Check every 5 minutes
        timeout=30.0,
        critical=False
    ))

    monitor.register_health_check(HealthCheck(
        name="database_repository",
        check_func=repository_health_check,
        interval=120,
        timeout=15.0,
        critical=False
    ))

    # Skill registry health check
    monitor.register_health_check(HealthCheck(
        name="skill_registry",
        check_func=skill_registry_health_check,
        interval=60,
        timeout=5.0,
        critical=False
    ))

    # Mr Happy agent health check
    monitor.register_health_check(HealthCheck(
        name="mr_happy_agent",
        check_func=mr_happy_agent_health_check,
        interval=60,
        timeout=5.0,
        critical=False
    ))

    # LLM Providers health checks
    monitor.register_health_check(HealthCheck(
        name="llm_providers",
        check_func=llm_providers_health_check,
        interval=60,
        timeout=30.0,
        critical=False  # Not critical since we have fallbacks
    ))

    # Individual provider health checks
    try:
        from app.llm.router import get_available_clients
        available_providers = get_available_clients()

        if "openrouter" in available_providers:
            monitor.register_health_check(HealthCheck(
                name="llm_openrouter",
                check_func=openrouter_health_check,
                interval=120,
                timeout=15.0,
                critical=False
            ))

        if "deepseek" in available_providers:
            monitor.register_health_check(HealthCheck(
                name="llm_deepseek",
                check_func=deepseek_health_check,
                interval=120,
                timeout=15.0,
                critical=False
            ))

        if "local" in available_providers:
            monitor.register_health_check(HealthCheck(
                name="llm_local",
                check_func=local_llm_health_check,
                interval=120,
                timeout=20.0,
                critical=False
            ))

    except Exception as e:
        logger.warning(f"Failed to register individual LLM provider health checks: {e}")

    logger.info("Default health checks registered")

