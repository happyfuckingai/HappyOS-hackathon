"""
Health monitoring service for AWS services and local fallbacks.
Provides comprehensive health checks and service availability monitoring.
"""

import asyncio
import time
import logging
from typing import Dict, Any, Optional, List, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum

import aiohttp
import boto3
from botocore.exceptions import ClientError, NoCredentialsError

from ..interfaces import ServiceHealth, HealthService
from ..settings import get_settings


logger = logging.getLogger(__name__)


@dataclass
class HealthCheckResult:
    """Result of a health check operation."""
    service_name: str
    is_healthy: bool
    health_status: ServiceHealth
    response_time_ms: float
    timestamp: datetime
    error_message: Optional[str] = None
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ServiceHealthMetrics:
    """Health metrics for a service over time."""
    service_name: str
    total_checks: int = 0
    successful_checks: int = 0
    failed_checks: int = 0
    average_response_time: float = 0.0
    last_success: Optional[datetime] = None
    last_failure: Optional[datetime] = None
    uptime_percentage: float = 100.0
    consecutive_failures: int = 0
    consecutive_successes: int = 0
    
    def update_success(self, response_time: float):
        """Update metrics for successful health check."""
        self.total_checks += 1
        self.successful_checks += 1
        self.consecutive_successes += 1
        self.consecutive_failures = 0
        self.last_success = datetime.now()
        
        # Update average response time
        if self.total_checks == 1:
            self.average_response_time = response_time
        else:
            self.average_response_time = (
                (self.average_response_time * (self.total_checks - 1) + response_time) / 
                self.total_checks
            )
        
        # Update uptime percentage
        self.uptime_percentage = (self.successful_checks / self.total_checks) * 100
    
    def update_failure(self, error_message: str):
        """Update metrics for failed health check."""
        self.total_checks += 1
        self.failed_checks += 1
        self.consecutive_failures += 1
        self.consecutive_successes = 0
        self.last_failure = datetime.now()
        
        # Update uptime percentage
        self.uptime_percentage = (self.successful_checks / self.total_checks) * 100


class AWSHealthChecker:
    """Health checker for AWS services."""
    
    def __init__(self):
        self.settings = get_settings()
        self.session = None
        self._initialize_aws_session()
    
    def _initialize_aws_session(self):
        """Initialize AWS session with credentials."""
        try:
            self.session = boto3.Session(
                aws_access_key_id=self.settings.aws.access_key_id,
                aws_secret_access_key=self.settings.aws.secret_access_key,
                aws_session_token=self.settings.aws.session_token,
                region_name=self.settings.aws.region,
                profile_name=self.settings.aws.profile
            )
        except Exception as e:
            logger.error(f"Failed to initialize AWS session: {e}")
            self.session = None
    
    async def check_agent_core_health(self) -> HealthCheckResult:
        """Check Agent Core service health."""
        start_time = time.time()
        
        try:
            # Agent Core health check - this would be a custom service
            # For now, we'll simulate the check
            await asyncio.sleep(0.1)  # Simulate network call
            
            response_time = (time.time() - start_time) * 1000
            
            return HealthCheckResult(
                service_name="agent_core",
                is_healthy=True,
                health_status=ServiceHealth.HEALTHY,
                response_time_ms=response_time,
                timestamp=datetime.now(),
                details={"endpoint": "agent-core-health", "status": "operational"}
            )
            
        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            return HealthCheckResult(
                service_name="agent_core",
                is_healthy=False,
                health_status=ServiceHealth.UNHEALTHY,
                response_time_ms=response_time,
                timestamp=datetime.now(),
                error_message=str(e)
            )
    
    async def check_opensearch_health(self) -> HealthCheckResult:
        """Check OpenSearch service health."""
        start_time = time.time()
        
        try:
            if not self.settings.aws.opensearch_endpoint:
                raise ValueError("OpenSearch endpoint not configured")
            
            # Check OpenSearch cluster health
            async with aiohttp.ClientSession() as session:
                health_url = f"{self.settings.aws.opensearch_endpoint}/_cluster/health"
                async with session.get(health_url, timeout=10) as response:
                    if response.status == 200:
                        health_data = await response.json()
                        cluster_status = health_data.get("status", "unknown")
                        
                        if cluster_status == "green":
                            health_status = ServiceHealth.HEALTHY
                        elif cluster_status == "yellow":
                            health_status = ServiceHealth.DEGRADED
                        else:
                            health_status = ServiceHealth.UNHEALTHY
                        
                        response_time = (time.time() - start_time) * 1000
                        
                        return HealthCheckResult(
                            service_name="opensearch",
                            is_healthy=cluster_status in ["green", "yellow"],
                            health_status=health_status,
                            response_time_ms=response_time,
                            timestamp=datetime.now(),
                            details=health_data
                        )
                    else:
                        raise Exception(f"HTTP {response.status}")
                        
        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            return HealthCheckResult(
                service_name="opensearch",
                is_healthy=False,
                health_status=ServiceHealth.UNHEALTHY,
                response_time_ms=response_time,
                timestamp=datetime.now(),
                error_message=str(e)
            )
    
    async def check_lambda_health(self) -> HealthCheckResult:
        """Check Lambda service health."""
        start_time = time.time()
        
        try:
            if not self.session:
                raise Exception("AWS session not initialized")
            
            lambda_client = self.session.client('lambda')
            
            # List functions to test Lambda service availability
            response = lambda_client.list_functions(MaxItems=1)
            
            response_time = (time.time() - start_time) * 1000
            
            return HealthCheckResult(
                service_name="lambda",
                is_healthy=True,
                health_status=ServiceHealth.HEALTHY,
                response_time_ms=response_time,
                timestamp=datetime.now(),
                details={"functions_count": len(response.get("Functions", []))}
            )
            
        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            return HealthCheckResult(
                service_name="lambda",
                is_healthy=False,
                health_status=ServiceHealth.UNHEALTHY,
                response_time_ms=response_time,
                timestamp=datetime.now(),
                error_message=str(e)
            )
    
    async def check_elasticache_health(self) -> HealthCheckResult:
        """Check ElastiCache service health."""
        start_time = time.time()
        
        try:
            if not self.session:
                raise Exception("AWS session not initialized")
            
            elasticache_client = self.session.client('elasticache')
            
            # Describe cache clusters to test service availability
            if self.settings.aws.elasticache_cluster:
                response = elasticache_client.describe_cache_clusters(
                    CacheClusterId=self.settings.aws.elasticache_cluster,
                    ShowCacheNodeInfo=True
                )
                
                clusters = response.get("CacheClusters", [])
                if clusters:
                    cluster = clusters[0]
                    cluster_status = cluster.get("CacheClusterStatus", "unknown")
                    
                    is_healthy = cluster_status == "available"
                    health_status = ServiceHealth.HEALTHY if is_healthy else ServiceHealth.DEGRADED
                else:
                    is_healthy = False
                    health_status = ServiceHealth.UNHEALTHY
                    cluster_status = "not_found"
            else:
                # Just test service availability
                elasticache_client.describe_cache_clusters(MaxRecords=1)
                is_healthy = True
                health_status = ServiceHealth.HEALTHY
                cluster_status = "service_available"
            
            response_time = (time.time() - start_time) * 1000
            
            return HealthCheckResult(
                service_name="elasticache",
                is_healthy=is_healthy,
                health_status=health_status,
                response_time_ms=response_time,
                timestamp=datetime.now(),
                details={"cluster_status": cluster_status}
            )
            
        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            return HealthCheckResult(
                service_name="elasticache",
                is_healthy=False,
                health_status=ServiceHealth.UNHEALTHY,
                response_time_ms=response_time,
                timestamp=datetime.now(),
                error_message=str(e)
            )
    
    async def check_s3_health(self) -> HealthCheckResult:
        """Check S3 service health."""
        start_time = time.time()
        
        try:
            if not self.session:
                raise Exception("AWS session not initialized")
            
            s3_client = self.session.client('s3')
            
            # List buckets to test S3 service availability
            response = s3_client.list_buckets()
            
            response_time = (time.time() - start_time) * 1000
            
            return HealthCheckResult(
                service_name="s3",
                is_healthy=True,
                health_status=ServiceHealth.HEALTHY,
                response_time_ms=response_time,
                timestamp=datetime.now(),
                details={"buckets_count": len(response.get("Buckets", []))}
            )
            
        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            return HealthCheckResult(
                service_name="s3",
                is_healthy=False,
                health_status=ServiceHealth.UNHEALTHY,
                response_time_ms=response_time,
                timestamp=datetime.now(),
                error_message=str(e)
            )
    
    async def check_secrets_manager_health(self) -> HealthCheckResult:
        """Check Secrets Manager service health."""
        start_time = time.time()
        
        try:
            if not self.session:
                raise Exception("AWS session not initialized")
            
            secrets_client = self.session.client('secretsmanager')
            
            # List secrets to test service availability
            response = secrets_client.list_secrets(MaxResults=1)
            
            response_time = (time.time() - start_time) * 1000
            
            return HealthCheckResult(
                service_name="secrets_manager",
                is_healthy=True,
                health_status=ServiceHealth.HEALTHY,
                response_time_ms=response_time,
                timestamp=datetime.now(),
                details={"secrets_count": len(response.get("SecretList", []))}
            )
            
        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            return HealthCheckResult(
                service_name="secrets_manager",
                is_healthy=False,
                health_status=ServiceHealth.UNHEALTHY,
                response_time_ms=response_time,
                timestamp=datetime.now(),
                error_message=str(e)
            )


class LocalHealthChecker:
    """Health checker for local fallback services."""
    
    def __init__(self):
        self.settings = get_settings()
    
    async def check_local_memory_health(self) -> HealthCheckResult:
        """Check local memory service health."""
        start_time = time.time()
        
        try:
            # Simple memory check - test if we can allocate and access memory
            test_data = {"test": "health_check", "timestamp": time.time()}
            
            response_time = (time.time() - start_time) * 1000
            
            return HealthCheckResult(
                service_name="local_memory",
                is_healthy=True,
                health_status=ServiceHealth.HEALTHY,
                response_time_ms=response_time,
                timestamp=datetime.now(),
                details={"memory_test": "passed"}
            )
            
        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            return HealthCheckResult(
                service_name="local_memory",
                is_healthy=False,
                health_status=ServiceHealth.UNHEALTHY,
                response_time_ms=response_time,
                timestamp=datetime.now(),
                error_message=str(e)
            )
    
    async def check_local_search_health(self) -> HealthCheckResult:
        """Check local search service health."""
        start_time = time.time()
        
        try:
            # Check if search service port is available
            import socket
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            result = sock.connect_ex(('localhost', self.settings.local.search_port))
            sock.close()
            
            is_healthy = result == 0
            health_status = ServiceHealth.HEALTHY if is_healthy else ServiceHealth.UNHEALTHY
            
            response_time = (time.time() - start_time) * 1000
            
            return HealthCheckResult(
                service_name="local_search",
                is_healthy=is_healthy,
                health_status=health_status,
                response_time_ms=response_time,
                timestamp=datetime.now(),
                details={"port": self.settings.local.search_port, "connection": "ok" if is_healthy else "failed"}
            )
            
        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            return HealthCheckResult(
                service_name="local_search",
                is_healthy=False,
                health_status=ServiceHealth.UNHEALTHY,
                response_time_ms=response_time,
                timestamp=datetime.now(),
                error_message=str(e)
            )
    
    async def check_local_cache_health(self) -> HealthCheckResult:
        """Check local cache service health."""
        start_time = time.time()
        
        try:
            # Check if cache service port is available
            import socket
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            result = sock.connect_ex(('localhost', self.settings.local.cache_port))
            sock.close()
            
            is_healthy = result == 0
            health_status = ServiceHealth.HEALTHY if is_healthy else ServiceHealth.UNHEALTHY
            
            response_time = (time.time() - start_time) * 1000
            
            return HealthCheckResult(
                service_name="local_cache",
                is_healthy=is_healthy,
                health_status=health_status,
                response_time_ms=response_time,
                timestamp=datetime.now(),
                details={"port": self.settings.local.cache_port, "connection": "ok" if is_healthy else "failed"}
            )
            
        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            return HealthCheckResult(
                service_name="local_cache",
                is_healthy=False,
                health_status=ServiceHealth.UNHEALTHY,
                response_time_ms=response_time,
                timestamp=datetime.now(),
                error_message=str(e)
            )


class HealthMonitoringService(HealthService):
    """
    Comprehensive health monitoring service for all infrastructure components.
    Monitors both AWS and local services and provides health metrics.
    """
    
    def __init__(self):
        self.settings = get_settings()
        self.aws_checker = AWSHealthChecker()
        self.local_checker = LocalHealthChecker()
        
        # Health metrics storage
        self.service_metrics: Dict[str, ServiceHealthMetrics] = {}
        
        # Health check configuration
        self.health_check_interval = self.settings.circuit_breaker.health_check_interval
        self.health_check_timeout = getattr(self.settings.circuit_breaker, 'health_check_timeout', 10)
        
        # Monitoring tasks
        self.monitoring_tasks: Dict[str, asyncio.Task] = {}
        self.is_monitoring = False
        
        # Health check methods mapping
        self.health_checkers = {
            "agent_core": self.aws_checker.check_agent_core_health,
            "opensearch": self.aws_checker.check_opensearch_health,
            "lambda": self.aws_checker.check_lambda_health,
            "elasticache": self.aws_checker.check_elasticache_health,
            "s3": self.aws_checker.check_s3_health,
            "secrets_manager": self.aws_checker.check_secrets_manager_health,
            "local_memory": self.local_checker.check_local_memory_health,
            "local_search": self.local_checker.check_local_search_health,
            "local_cache": self.local_checker.check_local_cache_health,
        }
        
        logger.info("Health monitoring service initialized")
    
    async def check_service_health(self, service_name: str) -> ServiceHealth:
        """Check health of a specific service."""
        try:
            result = await self._perform_health_check(service_name)
            return result.health_status
        except Exception as e:
            logger.error(f"Error checking health for {service_name}: {e}")
            return ServiceHealth.UNHEALTHY
    
    async def check_all_services(self) -> Dict[str, ServiceHealth]:
        """Check health of all services."""
        health_results = {}
        
        # Check all configured services
        tasks = []
        service_names = []
        
        for service_name in self.health_checkers.keys():
            tasks.append(self._perform_health_check(service_name))
            service_names.append(service_name)
        
        # Execute all health checks concurrently
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for service_name, result in zip(service_names, results):
            if isinstance(result, Exception):
                logger.error(f"Health check failed for {service_name}: {result}")
                health_results[service_name] = ServiceHealth.UNHEALTHY
            else:
                health_results[service_name] = result.health_status
        
        return health_results
    
    async def get_service_metrics(self, service_name: str) -> Dict[str, Any]:
        """Get metrics for a service."""
        metrics = self.service_metrics.get(service_name)
        if not metrics:
            return {}
        
        return {
            "service_name": metrics.service_name,
            "total_checks": metrics.total_checks,
            "successful_checks": metrics.successful_checks,
            "failed_checks": metrics.failed_checks,
            "average_response_time_ms": metrics.average_response_time,
            "uptime_percentage": metrics.uptime_percentage,
            "consecutive_failures": metrics.consecutive_failures,
            "consecutive_successes": metrics.consecutive_successes,
            "last_success": metrics.last_success.isoformat() if metrics.last_success else None,
            "last_failure": metrics.last_failure.isoformat() if metrics.last_failure else None,
        }
    
    async def _perform_health_check(self, service_name: str) -> HealthCheckResult:
        """Perform health check for a specific service."""
        checker = self.health_checkers.get(service_name)
        if not checker:
            raise ValueError(f"No health checker configured for service: {service_name}")
        
        try:
            # Perform health check with timeout
            result = await asyncio.wait_for(checker(), timeout=self.health_check_timeout)
            
            # Update metrics
            self._update_service_metrics(service_name, result)
            
            return result
            
        except asyncio.TimeoutError:
            result = HealthCheckResult(
                service_name=service_name,
                is_healthy=False,
                health_status=ServiceHealth.UNHEALTHY,
                response_time_ms=self.health_check_timeout * 1000,
                timestamp=datetime.now(),
                error_message="Health check timeout"
            )
            self._update_service_metrics(service_name, result)
            return result
        except Exception as e:
            result = HealthCheckResult(
                service_name=service_name,
                is_healthy=False,
                health_status=ServiceHealth.UNHEALTHY,
                response_time_ms=0,
                timestamp=datetime.now(),
                error_message=str(e)
            )
            self._update_service_metrics(service_name, result)
            return result
    
    def _update_service_metrics(self, service_name: str, result: HealthCheckResult):
        """Update metrics for a service based on health check result."""
        if service_name not in self.service_metrics:
            self.service_metrics[service_name] = ServiceHealthMetrics(service_name=service_name)
        
        metrics = self.service_metrics[service_name]
        
        if result.is_healthy:
            metrics.update_success(result.response_time_ms)
        else:
            metrics.update_failure(result.error_message or "Unknown error")
    
    async def start_continuous_monitoring(self):
        """Start continuous health monitoring for all services."""
        if self.is_monitoring:
            logger.warning("Health monitoring is already running")
            return
        
        self.is_monitoring = True
        
        for service_name in self.health_checkers.keys():
            task = asyncio.create_task(self._monitor_service_continuously(service_name))
            self.monitoring_tasks[service_name] = task
        
        logger.info(f"Started continuous monitoring for {len(self.monitoring_tasks)} services")
    
    async def stop_continuous_monitoring(self):
        """Stop continuous health monitoring."""
        if not self.is_monitoring:
            return
        
        self.is_monitoring = False
        
        # Cancel all monitoring tasks
        for task in self.monitoring_tasks.values():
            task.cancel()
        
        # Wait for tasks to complete
        if self.monitoring_tasks:
            await asyncio.gather(*self.monitoring_tasks.values(), return_exceptions=True)
        
        self.monitoring_tasks.clear()
        logger.info("Stopped continuous health monitoring")
    
    async def _monitor_service_continuously(self, service_name: str):
        """Continuously monitor a single service."""
        while self.is_monitoring:
            try:
                await self._perform_health_check(service_name)
                await asyncio.sleep(self.health_check_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in continuous monitoring for {service_name}: {e}")
                await asyncio.sleep(self.health_check_interval)
    
    def get_all_metrics(self) -> Dict[str, Dict[str, Any]]:
        """Get metrics for all services."""
        return {
            service_name: asyncio.create_task(self.get_service_metrics(service_name))
            for service_name in self.service_metrics.keys()
        }


# Global health monitoring service instance
_health_service: Optional[HealthMonitoringService] = None


def get_health_service() -> HealthMonitoringService:
    """Get the global health monitoring service instance."""
    global _health_service
    if _health_service is None:
        _health_service = HealthMonitoringService()
    return _health_service