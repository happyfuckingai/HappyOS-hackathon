"""
Monitoring and Health Check System for HappyOS
Provides health endpoints, metrics collection, and system monitoring.
"""
import time
import asyncio
import json
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from dataclasses import dataclass, field
import psutil
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
import uvicorn
from prometheus_client import Counter, Histogram, Gauge, generate_latest
import threading

from app.core.config.settings import get_config
from app.core.logging.logger import get_logger
from app.core.service_manager.service_manager import ServiceManager, ServiceStatus


@dataclass
class SystemMetrics:
    """System metrics container."""
    timestamp: float = field(default_factory=time.time)
    cpu_percent: float = 0.0
    memory_percent: float = 0.0
    memory_used: int = 0
    memory_total: int = 0
    disk_percent: float = 0.0
    disk_free: int = 0
    disk_total: int = 0
    network_sent: int = 0
    network_recv: int = 0
    uptime: float = 0.0


@dataclass
class ServiceMetrics:
    """Service-specific metrics container."""
    service_name: str
    status: str
    response_time: float = 0.0
    cpu_percent: float = 0.0
    memory_percent: float = 0.0
    restart_count: int = 0
    last_health_check: float = 0.0
    health_check_failures: int = 0


class HealthChecker:
    """Health check management system."""

    def __init__(self, service_manager: ServiceManager):
        self.service_manager = service_manager
        self.config = get_config()
        self.logger = get_logger("health_checker")
        self.health_status: Dict[str, Dict[str, Any]] = {}
        self._last_check = 0.0

    async def check_system_health(self) -> Dict[str, Any]:
        """Perform comprehensive system health check."""
        start_time = time.time()

        try:
            # System resource checks
            system_checks = await self._check_system_resources()

            # Service health checks
            service_checks = await self._check_services_health()

            # Database connectivity (if applicable)
            database_checks = await self._check_database_connectivity()

            # External service checks
            external_checks = await self._check_external_services()

            # Overall status
            overall_status = self._determine_overall_status([
                system_checks,
                service_checks,
                database_checks,
                external_checks
            ])

            health_data = {
                "status": overall_status,
                "timestamp": datetime.utcnow().isoformat(),
                "response_time": time.time() - start_time,
                "checks": {
                    "system": system_checks,
                    "services": service_checks,
                    "database": database_checks,
                    "external": external_checks
                },
                "version": "1.0.0",
                "uptime": time.time() - getattr(self.service_manager, '_start_time', time.time())
            }

            self.health_status = health_data
            return health_data

        except Exception as e:
            self.logger.error(f"Health check failed: {e}")
            return {
                "status": "unhealthy",
                "timestamp": datetime.utcnow().isoformat(),
                "error": str(e)
            }

    async def _check_system_resources(self) -> Dict[str, Any]:
        """Check system resource usage."""
        try:
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')

            status = "healthy"
            issues = []

            # CPU threshold check
            if cpu_percent > 90:
                status = "warning"
                issues.append(".1f")

            # Memory threshold check
            if memory.percent > 85:
                status = "warning"
                issues.append(".1f")

            # Disk threshold check
            if disk.percent > 90:
                status = "warning"
                issues.append(".1f")

            return {
                "status": status,
                "details": {
                    "cpu_percent": cpu_percent,
                    "memory_percent": memory.percent,
                    "memory_used": memory.used,
                    "memory_total": memory.total,
                    "disk_percent": disk.percent,
                    "disk_free": disk.free,
                    "disk_total": disk.total
                },
                "issues": issues
            }

        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e)
            }

    async def _check_services_health(self) -> Dict[str, Any]:
        """Check health of all services."""
        try:
            service_health = {}
            healthy_count = 0
            total_count = len(self.service_manager.services)

            for service_name, service_instance in self.service_manager.services.items():
                status = service_instance.status.value

                if service_instance.config.health_check_url:
                    # Perform actual health check
                    health_status = await self._check_service_endpoint(service_instance.config.health_check_url)
                    status = "healthy" if health_status else "unhealthy"

                service_health[service_name] = {
                    "status": status,
                    "port": service_instance.config.port,
                    "restart_count": service_instance.restart_count,
                    "uptime": time.time() - (service_instance.start_time or time.time())
                }

                if status in ["healthy", "running"]:
                    healthy_count += 1

            overall_status = "healthy" if healthy_count == total_count else "degraded"

            return {
                "status": overall_status,
                "healthy_count": healthy_count,
                "total_count": total_count,
                "services": service_health
            }

        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e)
            }

    async def _check_service_endpoint(self, url: str, timeout: float = 5.0) -> bool:
        """Check if a service endpoint is responding."""
        try:
            import aiohttp

            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=timeout)) as session:
                async with session.get(url) as response:
                    return response.status == 200

        except Exception as e:
            self.logger.debug(f"Service endpoint check failed for {url}: {e}")
            return False

    async def _check_database_connectivity(self) -> Dict[str, Any]:
        """Check database connectivity if applicable."""
        # Placeholder for database checks
        # In a real implementation, this would check actual database connections
        return {
            "status": "healthy",
            "message": "No database connectivity checks configured"
        }

    async def _check_external_services(self) -> Dict[str, Any]:
        """Check external service dependencies."""
        # Placeholder for external service checks
        return {
            "status": "healthy",
            "message": "No external service checks configured"
        }

    def _determine_overall_status(self, checks: List[Dict[str, Any]]) -> str:
        """Determine overall system status from individual checks."""
        for check in checks:
            if check.get("status") == "unhealthy":
                return "unhealthy"
            elif check.get("status") == "warning":
                return "warning"

        return "healthy"

    def get_cached_health(self) -> Optional[Dict[str, Any]]:
        """Get cached health status."""
        return self.health_status if self.health_status else None


class MetricsCollector:
    """Prometheus metrics collection system."""

    def __init__(self, service_manager: ServiceManager):
        self.service_manager = service_manager
        self.config = get_config()
        self.logger = get_logger("metrics_collector")

        # Prometheus metrics
        self.system_cpu_usage = Gauge('happyos_system_cpu_percent', 'System CPU usage percentage')
        self.system_memory_usage = Gauge('happyos_system_memory_percent', 'System memory usage percentage')
        self.system_disk_usage = Gauge('happyos_system_disk_percent', 'System disk usage percentage')

        self.service_status = Gauge('happyos_service_status', 'Service status (1=healthy, 0=unhealthy)', ['service'])
        self.service_restart_count = Counter('happyos_service_restarts_total', 'Total service restarts', ['service'])
        self.service_response_time = Histogram('happyos_service_response_time_seconds', 'Service response time', ['service'])

        self.health_check_duration = Histogram('happyos_health_check_duration_seconds', 'Health check duration')

    def collect_system_metrics(self) -> SystemMetrics:
        """Collect current system metrics."""
        try:
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            network = psutil.net_io_counters()

            metrics = SystemMetrics(
                cpu_percent=cpu_percent,
                memory_percent=memory.percent,
                memory_used=memory.used,
                memory_total=memory.total,
                disk_percent=disk.percent,
                disk_free=disk.free,
                disk_total=disk.total,
                network_sent=network.bytes_sent if network else 0,
                network_recv=network.bytes_recv if network else 0,
                uptime=time.time() - getattr(self.service_manager, '_start_time', time.time())
            )

            # Update Prometheus metrics
            self.system_cpu_usage.set(cpu_percent)
            self.system_memory_usage.set(memory.percent)
            self.system_disk_usage.set(disk.percent)

            return metrics

        except Exception as e:
            self.logger.error(f"Failed to collect system metrics: {e}")
            return SystemMetrics()

    def collect_service_metrics(self) -> List[ServiceMetrics]:
        """Collect metrics for all services."""
        metrics = []

        for service_name, service_instance in self.service_manager.services.items():
            try:
                service_metric = ServiceMetrics(
                    service_name=service_name,
                    status=service_instance.status.value,
                    restart_count=service_instance.restart_count,
                    last_health_check=service_instance.last_health_check or 0.0,
                    health_check_failures=service_instance.health_check_failures
                )

                if service_instance.process:
                    try:
                        service_metric.cpu_percent = service_instance.process.cpu_percent()
                        memory_info = service_instance.process.memory_percent()
                        service_metric.memory_percent = memory_info
                    except psutil.NoSuchProcess:
                        pass

                # Update Prometheus metrics
                status_value = 1 if service_instance.status == ServiceStatus.RUNNING else 0
                self.service_status.labels(service=service_name).set(status_value)

                metrics.append(service_metric)

            except Exception as e:
                self.logger.error(f"Failed to collect metrics for service {service_name}: {e}")

        return metrics

    def get_prometheus_metrics(self) -> str:
        """Get Prometheus metrics in text format."""
        return generate_latest().decode('utf-8')


class MonitoringServer:
    """FastAPI monitoring server."""

    def __init__(self, service_manager: ServiceManager):
        self.service_manager = service_manager
        self.config = get_config()
        self.logger = get_logger("monitoring_server")

        self.app = FastAPI(title="HappyOS Monitoring", version="1.0.0")
        self.health_checker = HealthChecker(service_manager)
        self.metrics_collector = MetricsCollector(service_manager)

        self._setup_routes()

    def _setup_routes(self):
        """Setup FastAPI routes."""

        @self.app.get("/health")
        async def health_check():
            """Basic health check endpoint."""
            try:
                health_data = await self.health_checker.check_system_health()
                status_code = 200 if health_data["status"] == "healthy" else 503
                return JSONResponse(content=health_data, status_code=status_code)
            except Exception as e:
                return JSONResponse(
                    content={"status": "error", "error": str(e)},
                    status_code=500
                )

        @self.app.get("/health/detailed")
        async def detailed_health_check():
            """Detailed health check with all metrics."""
            try:
                health_data = await self.health_checker.check_system_health()
                system_metrics = self.metrics_collector.collect_system_metrics()
                service_metrics = self.metrics_collector.collect_service_metrics()

                detailed_data = {
                    **health_data,
                    "system_metrics": {
                        "cpu_percent": system_metrics.cpu_percent,
                        "memory_percent": system_metrics.memory_percent,
                        "disk_percent": system_metrics.disk_percent,
                        "uptime": system_metrics.uptime
                    },
                    "service_metrics": [
                        {
                            "service_name": m.service_name,
                            "status": m.status,
                            "cpu_percent": m.cpu_percent,
                            "memory_percent": m.memory_percent,
                            "restart_count": m.restart_count
                        }
                        for m in service_metrics
                    ]
                }

                return JSONResponse(content=detailed_data)
            except Exception as e:
                return JSONResponse(
                    content={"status": "error", "error": str(e)},
                    status_code=500
                )

        @self.app.get("/metrics")
        async def prometheus_metrics():
            """Prometheus metrics endpoint."""
            try:
                # Collect fresh metrics
                self.metrics_collector.collect_system_metrics()
                self.metrics_collector.collect_service_metrics()

                metrics_text = self.metrics_collector.get_prometheus_metrics()
                return JSONResponse(
                    content={"metrics": metrics_text},
                    media_type="text/plain"
                )
            except Exception as e:
                return JSONResponse(
                    content={"error": str(e)},
                    status_code=500
                )

        @self.app.get("/services")
        async def service_status():
            """Get status of all services."""
            try:
                services_data = {}
                for service_name, service_instance in self.service_manager.services.items():
                    services_data[service_name] = {
                        "status": service_instance.status.value,
                        "port": service_instance.config.port,
                        "restart_count": service_instance.restart_count,
                        "uptime": time.time() - (service_instance.start_time or time.time()),
                        "health_check_failures": service_instance.health_check_failures
                    }

                return JSONResponse(content=services_data)
            except Exception as e:
                return JSONResponse(
                    content={"error": str(e)},
                    status_code=500
                )

        @self.app.get("/system")
        async def system_info():
            """Get system information."""
            try:
                system_metrics = self.metrics_collector.collect_system_metrics()

                return JSONResponse(content={
                    "cpu_percent": system_metrics.cpu_percent,
                    "memory": {
                        "percent": system_metrics.memory_percent,
                        "used": system_metrics.memory_used,
                        "total": system_metrics.memory_total
                    },
                    "disk": {
                        "percent": system_metrics.disk_percent,
                        "free": system_metrics.disk_free,
                        "total": system_metrics.disk_total
                    },
                    "network": {
                        "bytes_sent": system_metrics.network_sent,
                        "bytes_recv": system_metrics.network_recv
                    },
                    "uptime": system_metrics.uptime,
                    "timestamp": system_metrics.timestamp
                })
            except Exception as e:
                return JSONResponse(
                    content={"error": str(e)},
                    status_code=500
                )

    async def start_server(self):
        """Start the monitoring server."""
        if not self.config.monitoring.enabled:
            self.logger.info("Monitoring server disabled in configuration")
            return

        try:
            config = uvicorn.Config(
                app=self.app,
                host="0.0.0.0",
                port=self.config.monitoring.health_check_port,
                log_level="error"
            )
            server = uvicorn.Server(config)

            self.logger.info(f"Starting monitoring server on port {self.config.monitoring.health_check_port}")
            await server.serve()

        except Exception as e:
            self.logger.error(f"Failed to start monitoring server: {e}")

    def start_in_background(self):
        """Start the monitoring server in a background thread."""
        if not self.config.monitoring.enabled:
            return

        def run_server():
            asyncio.run(self.start_server())

        thread = threading.Thread(target=run_server, daemon=True)
        thread.start()
        self.logger.info("Monitoring server started in background thread")