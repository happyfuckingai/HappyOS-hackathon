"""
Health check dashboard with component status monitoring.
"""

import asyncio
import time
import psutil
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum

try:
    from backend.modules.config.settings import settings
except ImportError:
    # Fallback for direct execution
    import sys
    import os
    sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))
    from backend.modules.config.settings import settings
from .logger import get_logger
from .metrics import get_metrics_collector


class HealthStatus(Enum):
    """Health status enumeration."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


@dataclass
class ComponentHealth:
    """Represents health status of a system component."""
    
    name: str
    status: HealthStatus = HealthStatus.UNKNOWN
    message: str = ""
    last_check: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    response_time_ms: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "name": self.name,
            "status": self.status.value,
            "message": self.message,
            "last_check": self.last_check.isoformat(),
            "response_time_ms": self.response_time_ms,
            "metadata": self.metadata
        }


class HealthChecker:
    """Comprehensive health checking for all system components."""
    
    def __init__(self):
        self.logger = get_logger(__name__)
        self.metrics = get_metrics_collector()
        self.component_health: Dict[str, ComponentHealth] = {}
        self.last_full_check: Optional[datetime] = None
    
    async def check_database_health(self) -> ComponentHealth:
        """Check database connectivity and performance."""
        health = ComponentHealth(name="database")
        start_time = time.time()
        
        try:
            # Import here to avoid circular imports
            from backend.modules.database import get_db_session
            
            async with get_db_session() as session:
                # Simple query to test connectivity
                result = await session.execute("SELECT 1")
                await result.fetchone()
                
                health.status = HealthStatus.HEALTHY
                health.message = "Database connection successful"
                health.response_time_ms = (time.time() - start_time) * 1000
                
                # Add connection pool info if available
                if hasattr(session.bind, 'pool'):
                    pool = session.bind.pool
                    health.metadata.update({
                        "pool_size": pool.size(),
                        "checked_in": pool.checkedin(),
                        "checked_out": pool.checkedout(),
                        "overflow": pool.overflow(),
                        "invalid": pool.invalid()
                    })
                
        except Exception as e:
            health.status = HealthStatus.UNHEALTHY
            health.message = f"Database connection failed: {str(e)}"
            health.response_time_ms = (time.time() - start_time) * 1000
            self.logger.error(f"Database health check failed: {e}")
        
        return health
    
    async def check_redis_health(self) -> ComponentHealth:
        """Check Redis connectivity and performance."""
        health = ComponentHealth(name="redis")
        start_time = time.time()
        
        if not settings.REDIS_URL:
            health.status = HealthStatus.UNKNOWN
            health.message = "Redis not configured"
            return health
        
        try:
            import redis.asyncio as redis
            
            redis_client = redis.from_url(settings.REDIS_URL)
            
            # Test basic operations
            await redis_client.ping()
            await redis_client.set("health_check", "ok", ex=10)
            result = await redis_client.get("health_check")
            
            if result == b"ok":
                health.status = HealthStatus.HEALTHY
                health.message = "Redis connection successful"
                
                # Get Redis info
                info = await redis_client.info()
                health.metadata.update({
                    "version": info.get("redis_version"),
                    "connected_clients": info.get("connected_clients"),
                    "used_memory": info.get("used_memory"),
                    "used_memory_human": info.get("used_memory_human"),
                    "keyspace_hits": info.get("keyspace_hits"),
                    "keyspace_misses": info.get("keyspace_misses")
                })
            else:
                health.status = HealthStatus.DEGRADED
                health.message = "Redis operations not working correctly"
            
            health.response_time_ms = (time.time() - start_time) * 1000
            await redis_client.close()
            
        except ImportError:
            health.status = HealthStatus.UNKNOWN
            health.message = "Redis client not available"
        except Exception as e:
            health.status = HealthStatus.UNHEALTHY
            health.message = f"Redis connection failed: {str(e)}"
            health.response_time_ms = (time.time() - start_time) * 1000
            self.logger.error(f"Redis health check failed: {e}")
        
        return health
    
    async def check_qdrant_health(self) -> ComponentHealth:
        """Check Qdrant vector database connectivity."""
        health = ComponentHealth(name="qdrant")
        start_time = time.time()
        
        try:
            from qdrant_client import QdrantClient
            from qdrant_client.http.exceptions import UnexpectedResponse
            
            client = QdrantClient(
                url=f"http://{settings.QDRANT_URL}",
                api_key=settings.QDRANT_API_KEY if settings.QDRANT_API_KEY else None,
                timeout=5.0
            )
            
            # Test connection
            collections = client.get_collections()
            
            health.status = HealthStatus.HEALTHY
            health.message = "Qdrant connection successful"
            health.response_time_ms = (time.time() - start_time) * 1000
            health.metadata.update({
                "collections_count": len(collections.collections),
                "collections": [col.name for col in collections.collections]
            })
            
        except ImportError:
            health.status = HealthStatus.UNKNOWN
            health.message = "Qdrant client not available"
        except UnexpectedResponse as e:
            if e.status_code == 404:
                health.status = HealthStatus.HEALTHY
                health.message = "Qdrant accessible (no collections yet)"
                health.response_time_ms = (time.time() - start_time) * 1000
            else:
                health.status = HealthStatus.UNHEALTHY
                health.message = f"Qdrant error: {str(e)}"
                health.response_time_ms = (time.time() - start_time) * 1000
        except Exception as e:
            health.status = HealthStatus.UNHEALTHY
            health.message = f"Qdrant connection failed: {str(e)}"
            health.response_time_ms = (time.time() - start_time) * 1000
            self.logger.error(f"Qdrant health check failed: {e}")
        
        return health
    
    async def check_ai_providers_health(self) -> List[ComponentHealth]:
        """Check AI provider connectivity and quotas."""
        providers = []
        
        # OpenAI
        if settings.OPENAI_API_KEY:
            health = ComponentHealth(name="openai")
            start_time = time.time()
            
            try:
                import openai
                
                client = openai.AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
                
                # Test with minimal request
                response = await client.chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages=[{"role": "user", "content": "test"}],
                    max_tokens=1
                )
                
                health.status = HealthStatus.HEALTHY
                health.message = "OpenAI API accessible"
                health.response_time_ms = (time.time() - start_time) * 1000
                health.metadata.update({
                    "model_tested": "gpt-3.5-turbo",
                    "tokens_used": response.usage.total_tokens if response.usage else 0
                })
                
            except ImportError:
                health.status = HealthStatus.UNKNOWN
                health.message = "OpenAI client not available"
            except Exception as e:
                health.status = HealthStatus.UNHEALTHY
                health.message = f"OpenAI API error: {str(e)}"
                health.response_time_ms = (time.time() - start_time) * 1000
                self.logger.error(f"OpenAI health check failed: {e}")
            
            providers.append(health)
        
        # Google AI
        if settings.GOOGLE_AI_API_KEY:
            health = ComponentHealth(name="google_ai")
            start_time = time.time()
            
            try:
                import google.generativeai as genai
                
                genai.configure(api_key=settings.GOOGLE_AI_API_KEY)
                model = genai.GenerativeModel('gemini-pro')
                
                # Test with minimal request
                response = model.generate_content("test")
                
                health.status = HealthStatus.HEALTHY
                health.message = "Google AI API accessible"
                health.response_time_ms = (time.time() - start_time) * 1000
                health.metadata.update({
                    "model_tested": "gemini-pro",
                    "response_length": len(response.text) if response.text else 0
                })
                
            except ImportError:
                health.status = HealthStatus.UNKNOWN
                health.message = "Google AI client not available"
            except Exception as e:
                health.status = HealthStatus.UNHEALTHY
                health.message = f"Google AI API error: {str(e)}"
                health.response_time_ms = (time.time() - start_time) * 1000
                self.logger.error(f"Google AI health check failed: {e}")
            
            providers.append(health)
        
        return providers
    
    async def check_system_resources(self) -> ComponentHealth:
        """Check system resource usage."""
        health = ComponentHealth(name="system_resources")
        
        try:
            # CPU usage
            cpu_percent = psutil.cpu_percent(interval=1)
            
            # Memory usage
            memory = psutil.virtual_memory()
            
            # Disk usage
            disk = psutil.disk_usage('/')
            
            health.metadata.update({
                "cpu_percent": cpu_percent,
                "memory_total": memory.total,
                "memory_available": memory.available,
                "memory_percent": memory.percent,
                "disk_total": disk.total,
                "disk_free": disk.free,
                "disk_percent": (disk.used / disk.total) * 100
            })
            
            # Determine health status based on resource usage
            if cpu_percent > 90 or memory.percent > 90 or (disk.used / disk.total) > 0.9:
                health.status = HealthStatus.UNHEALTHY
                health.message = "High resource usage detected"
            elif cpu_percent > 70 or memory.percent > 70 or (disk.used / disk.total) > 0.8:
                health.status = HealthStatus.DEGRADED
                health.message = "Elevated resource usage"
            else:
                health.status = HealthStatus.HEALTHY
                health.message = "System resources normal"
            
            # Update metrics
            self.metrics.set_cpu_usage("system", cpu_percent)
            self.metrics.set_memory_usage("system", memory.used)
            
        except Exception as e:
            health.status = HealthStatus.UNKNOWN
            health.message = f"Failed to check system resources: {str(e)}"
            self.logger.error(f"System resource check failed: {e}")
        
        return health
    
    async def check_worker_processes(self) -> ComponentHealth:
        """Check status of background worker processes."""
        health = ComponentHealth(name="worker_processes")
        
        try:
            # Import here to avoid circular imports
            from backend.services.agents.orchestration_service import get_orchestration_service
            
            orchestration = get_orchestration_service()
            active_agents = await orchestration.list_agents()
            
            # Count active workers by type
            worker_counts = {}
            healthy_workers = 0
            total_workers = len(active_agents)
            
            for agent in active_agents:
                agent_type = agent.get("type", "unknown")
                worker_counts[agent_type] = worker_counts.get(agent_type, 0) + 1
                
                if agent.get("status") == "running":
                    healthy_workers += 1
            
            health.metadata.update({
                "total_workers": total_workers,
                "healthy_workers": healthy_workers,
                "worker_types": worker_counts
            })
            
            if total_workers == 0:
                health.status = HealthStatus.DEGRADED
                health.message = "No worker processes running"
            elif healthy_workers == total_workers:
                health.status = HealthStatus.HEALTHY
                health.message = f"All {total_workers} workers healthy"
            elif healthy_workers > 0:
                health.status = HealthStatus.DEGRADED
                health.message = f"{healthy_workers}/{total_workers} workers healthy"
            else:
                health.status = HealthStatus.UNHEALTHY
                health.message = "No healthy workers"
            
            # Update metrics
            for agent_type, count in worker_counts.items():
                self.metrics.set_active_agents(agent_type, count)
            
        except Exception as e:
            health.status = HealthStatus.UNKNOWN
            health.message = f"Failed to check worker processes: {str(e)}"
            self.logger.error(f"Worker process check failed: {e}")
        
        return health
    
    async def perform_full_health_check(self) -> Dict[str, ComponentHealth]:
        """Perform comprehensive health check of all components."""
        self.logger.info("Starting full health check")
        start_time = time.time()
        
        # Run all health checks concurrently
        tasks = [
            self.check_database_health(),
            self.check_redis_health(),
            self.check_qdrant_health(),
            self.check_system_resources(),
            self.check_worker_processes(),
        ]
        
        # Add AI provider checks
        ai_providers_task = self.check_ai_providers_health()
        
        # Execute all checks
        results = await asyncio.gather(*tasks, ai_providers_task, return_exceptions=True)
        
        # Process results
        health_results = {}
        
        for i, result in enumerate(results[:-1]):  # All except AI providers
            if isinstance(result, Exception):
                component_name = ["database", "redis", "qdrant", "system_resources", "worker_processes"][i]
                health = ComponentHealth(
                    name=component_name,
                    status=HealthStatus.UNKNOWN,
                    message=f"Health check failed: {str(result)}"
                )
                health_results[component_name] = health
                self.logger.error(f"Health check failed for {component_name}: {result}")
            else:
                health_results[result.name] = result
        
        # Process AI providers
        ai_results = results[-1]
        if isinstance(ai_results, Exception):
            self.logger.error(f"AI providers health check failed: {ai_results}")
        else:
            for ai_health in ai_results:
                health_results[ai_health.name] = ai_health
        
        # Update component health cache
        self.component_health.update(health_results)
        self.last_full_check = datetime.now(timezone.utc)
        
        total_time = (time.time() - start_time) * 1000
        self.logger.info(f"Full health check completed in {total_time:.2f}ms")
        
        return health_results
    
    def get_overall_health_status(self) -> Dict[str, Any]:
        """Get overall system health status."""
        if not self.component_health:
            return {
                "status": HealthStatus.UNKNOWN.value,
                "message": "No health checks performed yet",
                "components": {}
            }
        
        # Count component statuses
        status_counts = {status.value: 0 for status in HealthStatus}
        for health in self.component_health.values():
            status_counts[health.status.value] += 1
        
        # Determine overall status
        if status_counts["unhealthy"] > 0:
            overall_status = HealthStatus.UNHEALTHY
            message = f"{status_counts['unhealthy']} components unhealthy"
        elif status_counts["degraded"] > 0:
            overall_status = HealthStatus.DEGRADED
            message = f"{status_counts['degraded']} components degraded"
        elif status_counts["healthy"] > 0:
            overall_status = HealthStatus.HEALTHY
            message = f"{status_counts['healthy']} components healthy"
        else:
            overall_status = HealthStatus.UNKNOWN
            message = "All components status unknown"
        
        return {
            "status": overall_status.value,
            "message": message,
            "last_check": self.last_full_check.isoformat() if self.last_full_check else None,
            "component_counts": status_counts,
            "components": {
                name: health.to_dict() 
                for name, health in self.component_health.items()
            }
        }
    
    async def get_health_dashboard_data(self) -> Dict[str, Any]:
        """Get comprehensive health dashboard data."""
        # Perform fresh health check if needed
        if (not self.last_full_check or 
            (datetime.now(timezone.utc) - self.last_full_check).total_seconds() > 300):  # 5 minutes
            await self.perform_full_health_check()
        
        overall_health = self.get_overall_health_status()
        
        # Add system metrics
        try:
            system_metrics = {
                "cpu_percent": psutil.cpu_percent(),
                "memory_percent": psutil.virtual_memory().percent,
                "disk_percent": (psutil.disk_usage('/').used / psutil.disk_usage('/').total) * 100,
                "load_average": psutil.getloadavg() if hasattr(psutil, 'getloadavg') else None,
                "boot_time": psutil.boot_time(),
                "process_count": len(psutil.pids())
            }
        except Exception as e:
            self.logger.error(f"Failed to get system metrics: {e}")
            system_metrics = {}
        
        return {
            **overall_health,
            "system_metrics": system_metrics,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }


# Global health checker instance
_health_checker: Optional[HealthChecker] = None


def get_health_checker() -> HealthChecker:
    """Get or create the global health checker."""
    global _health_checker
    if _health_checker is None:
        _health_checker = HealthChecker()
    return _health_checker