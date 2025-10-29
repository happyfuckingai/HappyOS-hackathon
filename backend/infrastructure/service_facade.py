"""
Service Facade Layer for Infrastructure Recovery

This module provides a unified interface for AWS and local service implementations
with automatic failover using circuit breaker patterns. It integrates with the
existing infrastructure and provides seamless switching between cloud and local services.
"""

import asyncio
import logging
import uuid
from typing import Any, Dict, List, Optional, Type, Union, Callable
from enum import Enum

from backend.core.interfaces import (
    ServiceFactory, AgentCoreService, SearchService, ComputeService,
    CacheService, StorageService, SecretsService, HealthService,
    CircuitBreakerService, CircuitState, ServiceHealth
)

# Import existing services
from backend.services.integration.resilience import (
    CircuitBreaker, CircuitBreakerConfig, CircuitBreakerOpenError,
    GracefulDegradationHandler, create_default_circuit_breaker
)
from backend.services.observability.health import get_health_checker

# Import AWS adapters
from backend.infrastructure.aws.services import (
    AWSAgentCoreAdapter, AWSOpenSearchAdapter, AWSLambdaAdapter,
    AWSElastiCacheAdapter, AWSS3Adapter, AWSSecretsManagerAdapter
)

# Import local services
try:
    from backend.infrastructure.local.services import (
        LocalMemoryService, LocalSearchService, LocalJobRunner, LocalFileStoreService
    )
    LOCAL_SERVICES_AVAILABLE = True
except ImportError:
    LOCAL_SERVICES_AVAILABLE = False
    # Create mock classes for when local services aren't available
    class LocalMemoryService:
        pass
    class LocalSearchService:
        pass
    class LocalJobRunner:
        pass
    class LocalFileStoreService:
        pass

# Agent-specific imports
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from backend.agents.agent_svea import AgentSveaWrapper
    from backend.agents.felicias_finance import FeliciasFinanceWrapper
    from backend.agents.meetmind import MeetMindWrapper

logger = logging.getLogger(__name__)


class ServiceMode(Enum):
    """Service operation modes."""
    AWS_ONLY = "aws_only"
    LOCAL_ONLY = "local_only"
    HYBRID = "hybrid"  # AWS with local fallback


class ServiceFacadeConfig:
    """Configuration for service facade."""
    
    def __init__(
        self,
        mode: ServiceMode = ServiceMode.HYBRID,
        aws_region: str = "us-east-1",
        circuit_breaker_config: Optional[CircuitBreakerConfig] = None,
        health_check_interval: int = 30,
        enable_metrics: bool = True,
        enable_agent_services: bool = True,
        gcp_migration_enabled: bool = False
    ):
        self.mode = mode
        self.aws_region = aws_region
        self.circuit_breaker_config = circuit_breaker_config or CircuitBreakerConfig()
        self.health_check_interval = health_check_interval
        self.enable_metrics = enable_metrics
        self.enable_agent_services = enable_agent_services
        self.gcp_migration_enabled = gcp_migration_enabled


class ServiceFacade:
    """
    Unified service facade that provides automatic failover between AWS and local services.
    
    This facade integrates with the existing circuit breaker and health monitoring
    infrastructure to provide seamless service switching.
    """
    
    def __init__(self, config: ServiceFacadeConfig):
        self.config = config
        self.logger = logging.getLogger(f"{__name__}.ServiceFacade")
        
        # Service instances
        self._aws_services: Dict[str, Any] = {}
        self._local_services: Dict[str, Any] = {}
        
        # Circuit breakers for each service type
        self._circuit_breakers: Dict[str, CircuitBreaker] = {}
        
        # Health monitoring
        self._health_checker = get_health_checker()
        self._degradation_handler = GracefulDegradationHandler()
        
        # Service state tracking
        self._service_health: Dict[str, ServiceHealth] = {}
        self._last_health_check: Dict[str, float] = {}
        
        self.logger.info(f"Service facade initialized in {config.mode.value} mode")
    
    async def initialize(self):
        """Initialize all services and circuit breakers."""
        try:
            # Initialize AWS services if needed
            if self.config.mode in [ServiceMode.AWS_ONLY, ServiceMode.HYBRID]:
                await self._initialize_aws_services()
            
            # Initialize local services if needed
            if self.config.mode in [ServiceMode.LOCAL_ONLY, ServiceMode.HYBRID]:
                await self._initialize_local_services()
            
            # Initialize circuit breakers
            self._initialize_circuit_breakers()
            
            self.logger.info("Service facade initialization completed")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize service facade: {e}")
            raise
    
    async def _initialize_aws_services(self):
        """Initialize AWS service adapters."""
        try:
            # Agent Core (DynamoDB + Lambda)
            self._aws_services['agent_core'] = AWSAgentCoreAdapter(
                region_name=self.config.aws_region
            )
            
            # OpenSearch
            # Note: Endpoint should be configurable
            opensearch_endpoint = "https://search-meetmind-dev.us-east-1.es.amazonaws.com"
            self._aws_services['search'] = AWSOpenSearchAdapter(
                endpoint=opensearch_endpoint,
                region_name=self.config.aws_region
            )
            
            # Lambda
            self._aws_services['compute'] = AWSLambdaAdapter(
                region_name=self.config.aws_region
            )
            
            # ElastiCache
            # Note: Endpoint should be configurable
            elasticache_endpoint = "meetmind-cache.abc123.cache.amazonaws.com"
            self._aws_services['cache'] = AWSElastiCacheAdapter(
                cluster_endpoint=elasticache_endpoint,
                region_name=self.config.aws_region
            )
            
            # S3
            s3_bucket = "meetmind-storage-prod"
            self._aws_services['storage'] = AWSS3Adapter(
                bucket_name=s3_bucket,
                region_name=self.config.aws_region
            )
            
            # Secrets Manager
            self._aws_services['secrets'] = AWSSecretsManagerAdapter(
                region_name=self.config.aws_region
            )
            
            self.logger.info("AWS services initialized")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize AWS services: {e}")
            if self.config.mode == ServiceMode.AWS_ONLY:
                raise
    
    async def _initialize_local_services(self):
        """Initialize local service implementations."""
        try:
            # Local memory service (Agent Core replacement)
            self._local_services['agent_core'] = LocalMemoryService()
            
            # Local search service
            self._local_services['search'] = LocalSearchService()
            
            # Local job runner (Lambda replacement)
            self._local_services['compute'] = LocalJobRunner()
            
            # Local cache service
            from backend.infrastructure.local.services.memory_service import LocalCacheService
            self._local_services['cache'] = LocalCacheService()
            
            # Local file store
            self._local_services['storage'] = LocalFileStoreService()
            
            # Local secrets (environment variables)
            from backend.infrastructure.local.services.local_secrets_service import LocalSecretsService
            self._local_services['secrets'] = LocalSecretsService()
            
            self.logger.info("Local services initialized")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize local services: {e}")
            if self.config.mode == ServiceMode.LOCAL_ONLY:
                raise
    
    def _initialize_circuit_breakers(self):
        """Initialize circuit breakers for each service type."""
        service_types = ['agent_core', 'search', 'compute', 'cache', 'storage', 'secrets']
        
        for service_type in service_types:
            self._circuit_breakers[service_type] = create_default_circuit_breaker()
            self.logger.debug(f"Circuit breaker initialized for {service_type}")
    
    async def _check_service_health(self, service_type: str) -> ServiceHealth:
        """Check health of a specific service type."""
        try:
            # Use existing health checker
            health_results = await self._health_checker.perform_full_health_check()
            
            # Map service types to health check results
            health_mapping = {
                'agent_core': 'database',  # Agent Core uses DynamoDB
                'search': 'qdrant',       # Search service
                'cache': 'redis',         # Cache service
                'storage': 'system_resources',  # File storage
                'secrets': 'system_resources',  # Secrets
                'compute': 'worker_processes'   # Compute/jobs
            }
            
            health_key = health_mapping.get(service_type, service_type)
            if health_key in health_results:
                health_status = health_results[health_key].status
                
                # Convert to ServiceHealth enum
                if health_status.value == 'healthy':
                    return ServiceHealth.HEALTHY
                elif health_status.value == 'degraded':
                    return ServiceHealth.DEGRADED
                else:
                    return ServiceHealth.UNHEALTHY
            
            return ServiceHealth.UNKNOWN
            
        except Exception as e:
            self.logger.error(f"Health check failed for {service_type}: {e}")
            return ServiceHealth.UNHEALTHY
    
    async def _get_service_instance(self, service_type: str, prefer_aws: bool = True) -> Any:
        """
        Get service instance with automatic failover.
        
        Args:
            service_type: Type of service (agent_core, search, etc.)
            prefer_aws: Whether to prefer AWS over local services
            
        Returns:
            Service instance (AWS or local)
        """
        circuit_breaker = self._circuit_breakers.get(service_type)
        
        # Determine service preference based on mode and health
        if self.config.mode == ServiceMode.LOCAL_ONLY:
            return self._local_services.get(service_type)
        elif self.config.mode == ServiceMode.AWS_ONLY:
            return self._aws_services.get(service_type)
        
        # Hybrid mode - check circuit breaker and health
        if prefer_aws and circuit_breaker and not circuit_breaker.is_open:
            aws_service = self._aws_services.get(service_type)
            if aws_service:
                return aws_service
        
        # Fall back to local service
        local_service = self._local_services.get(service_type)
        if local_service:
            self.logger.info(f"Using local fallback for {service_type}")
            return local_service
        
        # If no local service available, try AWS even if circuit breaker is open
        aws_service = self._aws_services.get(service_type)
        if aws_service:
            self.logger.warning(f"No local fallback available for {service_type}, using AWS")
            return aws_service
        
        raise ServiceUnavailableError(f"No service available for {service_type}")
    
    async def _execute_with_circuit_breaker(
        self, 
        service_type: str, 
        operation: str, 
        *args, 
        **kwargs
    ) -> Any:
        """Execute operation with circuit breaker protection."""
        circuit_breaker = self._circuit_breakers.get(service_type)
        
        if not circuit_breaker:
            # No circuit breaker, execute directly
            service = await self._get_service_instance(service_type)
            method = getattr(service, operation)
            return await method(*args, **kwargs)
        
        try:
            # Try AWS service first (if available and circuit breaker allows)
            if (self.config.mode in [ServiceMode.AWS_ONLY, ServiceMode.HYBRID] and 
                not circuit_breaker.is_open):
                
                async def aws_operation():
                    service = self._aws_services.get(service_type)
                    if not service:
                        raise ServiceUnavailableError(f"AWS {service_type} service not available")
                    method = getattr(service, operation)
                    return await method(*args, **kwargs)
                
                return await circuit_breaker.execute(aws_operation)
        
        except (CircuitBreakerOpenError, ServiceUnavailableError, Exception) as e:
            self.logger.warning(f"AWS {service_type} failed: {e}")
            
            # Fall back to local service if available
            if self.config.mode in [ServiceMode.LOCAL_ONLY, ServiceMode.HYBRID]:
                local_service = self._local_services.get(service_type)
                if local_service:
                    self.logger.info(f"Falling back to local {service_type}")
                    method = getattr(local_service, operation)
                    return await method(*args, **kwargs)
            
            # No fallback available
            if isinstance(e, CircuitBreakerOpenError):
                raise ServiceUnavailableError(f"{service_type} service unavailable (circuit breaker open)")
            raise
    
    # Service interface implementations
    
    def get_agent_core_service(self) -> 'AgentCoreFacade':
        """Get agent core service facade."""
        return AgentCoreFacade(self)
    
    def get_search_service(self) -> 'SearchFacade':
        """Get search service facade."""
        return SearchFacade(self)
    
    def get_compute_service(self) -> 'ComputeFacade':
        """Get compute service facade."""
        return ComputeFacade(self)
    
    def get_cache_service(self) -> 'CacheFacade':
        """Get cache service facade."""
        return CacheFacade(self)
    
    def get_storage_service(self) -> 'StorageFacade':
        """Get storage service facade."""
        return StorageFacade(self)
    
    def get_secrets_service(self) -> 'SecretsFacade':
        """Get secrets service facade."""
        return SecretsFacade(self)
    
    async def get_system_health(self) -> Dict[str, Any]:
        """Get overall system health status."""
        health_status = {}
        
        for service_type in self._circuit_breakers.keys():
            circuit_breaker = self._circuit_breakers[service_type]
            service_health = await self._check_service_health(service_type)
            
            health_status[service_type] = {
                'health': service_health.value,
                'circuit_breaker_state': circuit_breaker.state.value,
                'failure_count': circuit_breaker.failure_count,
                'aws_available': service_type in self._aws_services,
                'local_available': service_type in self._local_services
            }
        
        return {
            'mode': self.config.mode.value,
            'services': health_status,
            'overall_status': self._calculate_overall_health(health_status)
        }
    
    def _calculate_overall_health(self, service_health: Dict[str, Any]) -> str:
        """Calculate overall system health."""
        unhealthy_count = sum(
            1 for status in service_health.values() 
            if status['health'] == 'unhealthy'
        )
        degraded_count = sum(
            1 for status in service_health.values() 
            if status['health'] == 'degraded'
        )
        
        if unhealthy_count > 0:
            return 'unhealthy'
        elif degraded_count > 0:
            return 'degraded'
        else:
            return 'healthy'


# Service-specific facades

class AgentCoreFacade(AgentCoreService):
    """Agent Core service facade with AWS/local failover."""
    
    def __init__(self, service_facade: ServiceFacade):
        self.facade = service_facade
    
    async def put_memory(self, user_id: str, key: str, value: Any, tenant_id: str) -> bool:
        return await self.facade._execute_with_circuit_breaker(
            'agent_core', 'put_memory', user_id, key, value, tenant_id
        )
    
    async def get_memory(self, user_id: str, key: str, tenant_id: str) -> Any:
        return await self.facade._execute_with_circuit_breaker(
            'agent_core', 'get_memory', user_id, key, tenant_id
        )
    
    async def create_session(self, tenant_id: str, agent_id: str, user_id: str, config: Dict[str, Any]) -> str:
        return await self.facade._execute_with_circuit_breaker(
            'agent_core', 'create_session', tenant_id, agent_id, user_id, config
        )
    
    async def get_session(self, session_id: str, tenant_id: str):
        return await self.facade._execute_with_circuit_breaker(
            'agent_core', 'get_session', session_id, tenant_id
        )
    
    async def update_session(self, session_id: str, tenant_id: str, updates: Dict[str, Any]) -> bool:
        return await self.facade._execute_with_circuit_breaker(
            'agent_core', 'update_session', session_id, tenant_id, updates
        )
    
    async def delete_session(self, session_id: str, tenant_id: str) -> bool:
        return await self.facade._execute_with_circuit_breaker(
            'agent_core', 'delete_session', session_id, tenant_id
        )


class SearchFacade(SearchService):
    """Search service facade with AWS/local failover."""
    
    def __init__(self, service_facade: ServiceFacade):
        self.facade = service_facade
    
    async def index_document(self, doc: Dict[str, Any], tenant_id: str, index_name: str = None) -> str:
        return await self.facade._execute_with_circuit_breaker(
            'search', 'index_document', doc, tenant_id, index_name
        )
    
    async def search(self, query: str, tenant_id: str, filters: Dict[str, Any] = None, 
                    index_name: str = None) -> List[Dict[str, Any]]:
        return await self.facade._execute_with_circuit_breaker(
            'search', 'search', query, tenant_id, filters, index_name
        )
    
    async def hybrid_search(self, query: str, vector: List[float], tenant_id: str, 
                           filters: Dict[str, Any] = None, index_name: str = None) -> List[Dict[str, Any]]:
        return await self.facade._execute_with_circuit_breaker(
            'search', 'hybrid_search', query, vector, tenant_id, filters, index_name
        )
    
    async def delete_document(self, doc_id: str, tenant_id: str, index_name: str = None) -> bool:
        return await self.facade._execute_with_circuit_breaker(
            'search', 'delete_document', doc_id, tenant_id, index_name
        )


class ComputeFacade(ComputeService):
    """Compute service facade with AWS/local failover."""
    
    def __init__(self, service_facade: ServiceFacade):
        self.facade = service_facade
    
    async def invoke_function(self, function_name: str, payload: Dict[str, Any], 
                             tenant_id: str, async_mode: bool = False) -> Dict[str, Any]:
        return await self.facade._execute_with_circuit_breaker(
            'compute', 'invoke_function', function_name, payload, tenant_id, async_mode
        )
    
    async def schedule_job(self, job_config: Dict[str, Any], tenant_id: str) -> str:
        return await self.facade._execute_with_circuit_breaker(
            'compute', 'schedule_job', job_config, tenant_id
        )
    
    async def get_job_status(self, job_id: str, tenant_id: str) -> Dict[str, Any]:
        return await self.facade._execute_with_circuit_breaker(
            'compute', 'get_job_status', job_id, tenant_id
        )


class CacheFacade(CacheService):
    """Cache service facade with AWS/local failover."""
    
    def __init__(self, service_facade: ServiceFacade):
        self.facade = service_facade
    
    async def get(self, key: str, tenant_id: str) -> Optional[Any]:
        return await self.facade._execute_with_circuit_breaker(
            'cache', 'get', key, tenant_id
        )
    
    async def set(self, key: str, value: Any, tenant_id: str, ttl: int = None) -> bool:
        return await self.facade._execute_with_circuit_breaker(
            'cache', 'set', key, value, tenant_id, ttl
        )
    
    async def delete(self, key: str, tenant_id: str) -> bool:
        return await self.facade._execute_with_circuit_breaker(
            'cache', 'delete', key, tenant_id
        )
    
    async def exists(self, key: str, tenant_id: str) -> bool:
        return await self.facade._execute_with_circuit_breaker(
            'cache', 'exists', key, tenant_id
        )


class StorageFacade(StorageService):
    """Storage service facade with AWS/local failover."""
    
    def __init__(self, service_facade: ServiceFacade):
        self.facade = service_facade
    
    async def put_object(self, key: str, data: bytes, tenant_id: str, 
                        metadata: Dict[str, str] = None) -> bool:
        return await self.facade._execute_with_circuit_breaker(
            'storage', 'put_object', key, data, tenant_id, metadata
        )
    
    async def get_object(self, key: str, tenant_id: str) -> Optional[bytes]:
        return await self.facade._execute_with_circuit_breaker(
            'storage', 'get_object', key, tenant_id
        )
    
    async def delete_object(self, key: str, tenant_id: str) -> bool:
        return await self.facade._execute_with_circuit_breaker(
            'storage', 'delete_object', key, tenant_id
        )
    
    async def list_objects(self, prefix: str, tenant_id: str) -> List[str]:
        return await self.facade._execute_with_circuit_breaker(
            'storage', 'list_objects', prefix, tenant_id
        )


class SecretsFacade(SecretsService):
    """Secrets service facade with AWS/local failover."""
    
    def __init__(self, service_facade: ServiceFacade):
        self.facade = service_facade
    
    async def get_secret(self, secret_name: str, tenant_id: str = None) -> Optional[str]:
        return await self.facade._execute_with_circuit_breaker(
            'secrets', 'get_secret', secret_name, tenant_id
        )
    
    async def put_secret(self, secret_name: str, secret_value: str, tenant_id: str = None) -> bool:
        return await self.facade._execute_with_circuit_breaker(
            'secrets', 'put_secret', secret_name, secret_value, tenant_id
        )
    
    async def delete_secret(self, secret_name: str, tenant_id: str = None) -> bool:
        return await self.facade._execute_with_circuit_breaker(
            'secrets', 'delete_secret', secret_name, tenant_id
        )


class ServiceUnavailableError(Exception):
    """Raised when no service implementation is available."""
    pass


# Factory implementation
class InfrastructureServiceFactory(ServiceFactory):
    """Service factory that creates facade services."""
    
    def __init__(self, config: ServiceFacadeConfig):
        self.facade = ServiceFacade(config)
        self._initialized = False
    
    async def initialize(self):
        """Initialize the service facade."""
        if not self._initialized:
            await self.facade.initialize()
            self._initialized = True
    
    def create_agent_core_service(self) -> AgentCoreService:
        return self.facade.get_agent_core_service()
    
    def create_search_service(self) -> SearchService:
        return self.facade.get_search_service()
    
    def create_compute_service(self) -> ComputeService:
        return self.facade.get_compute_service()
    
    def create_cache_service(self) -> CacheService:
        return self.facade.get_cache_service()
    
    def create_storage_service(self) -> StorageService:
        return self.facade.get_storage_service()
    
    def create_secrets_service(self) -> SecretsService:
        return self.facade.get_secrets_service()
    
    def create_health_service(self) -> HealthService:
        # Return existing health service
        return self.facade._health_checker


# Global service factory instance
_service_factory: Optional[InfrastructureServiceFactory] = None


def get_service_factory(config: Optional[ServiceFacadeConfig] = None) -> InfrastructureServiceFactory:
    """Get or create the global service factory."""
    global _service_factory
    if _service_factory is None:
        if config is None:
            config = ServiceFacadeConfig()
        _service_factory = InfrastructureServiceFactory(config)
    return _service_factory


async def initialize_services(config: Optional[ServiceFacadeConfig] = None):
    """Initialize the global service factory."""
    factory = get_service_factory(config)
    await factory.initialize()


class UnifiedServiceFacade(ServiceFacade):
    """
    Extended service facade for agent systems unification.
    
    Provides agent-specific services, GCP migration utilities, and
    specialized circuit breaker configurations for multi-agent systems.
    """
    
    def __init__(self, config: ServiceFacadeConfig):
        super().__init__(config)
        
        # Agent-specific services
        self._agent_services: Dict[str, Any] = {}
        self._agent_circuit_breakers: Dict[str, CircuitBreaker] = {}
        
        # GCP migration utilities
        self._migration_tools: Optional['GCPMigrationService'] = None
        
        self.logger.info("UnifiedServiceFacade initialized for agent systems")
    
    async def initialize(self):
        """Initialize unified service facade with agent-specific services."""
        await super().initialize()
        
        if self.config.enable_agent_services:
            await self._initialize_agent_services()
        
        if self.config.gcp_migration_enabled:
            await self._initialize_migration_tools()
    
    async def _initialize_agent_services(self):
        """Initialize agent-specific services."""
        try:
            # Agent-specific circuit breaker configurations
            agent_types = ['agent_svea', 'felicias_finance', 'meetmind']
            
            for agent_type in agent_types:
                # Create specialized circuit breaker config for each agent
                agent_cb_config = CircuitBreakerConfig(
                    failure_threshold=3,
                    recovery_timeout=30,
                    expected_exception=Exception
                )
                self._agent_circuit_breakers[agent_type] = CircuitBreaker(agent_cb_config)
                
                self.logger.debug(f"Agent circuit breaker initialized for {agent_type}")
            
            self.logger.info("Agent-specific services initialized")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize agent services: {e}")
            raise
    
    async def _initialize_migration_tools(self):
        """Initialize GCP migration utilities."""
        try:
            from backend.infrastructure.migration.gcp_migrator import GCPMigrationService
            self._migration_tools = GCPMigrationService(
                aws_region=self.config.aws_region,
                service_facade=self
            )
            await self._migration_tools.initialize()
            
            self.logger.info("GCP migration tools initialized")
            
        except ImportError:
            self.logger.warning("GCP migration tools not available - will be implemented")
        except Exception as e:
            self.logger.error(f"Failed to initialize migration tools: {e}")
            raise
    
    # Agent-specific service methods
    
    def get_agent_database_service(self, agent_type: str) -> 'AgentDatabaseService':
        """Get database service for specific agent type."""
        return AgentDatabaseService(self, agent_type)
    
    def get_agent_storage_service(self, agent_type: str) -> 'AgentStorageService':
        """Get storage service for specific agent type."""
        return AgentStorageService(self, agent_type)
    
    def get_agent_compute_service(self, agent_type: str) -> 'AgentComputeService':
        """Get compute service for specific agent type."""
        return AgentComputeService(self, agent_type)
    
    async def migrate_gcp_resources(self, migration_config: 'GCPMigrationConfig') -> 'MigrationResult':
        """Migrate GCP resources to AWS."""
        if not self._migration_tools:
            raise ServiceUnavailableError("GCP migration tools not initialized")
        
        return await self._migration_tools.migrate_resources(migration_config)
    
    async def get_agent_health(self, agent_type: str) -> Dict[str, Any]:
        """Get health status for specific agent type."""
        circuit_breaker = self._agent_circuit_breakers.get(agent_type)
        
        if not circuit_breaker:
            return {
                "agent_type": agent_type,
                "status": "unknown",
                "error": "Agent type not configured"
            }
        
        return {
            "agent_type": agent_type,
            "circuit_breaker_state": circuit_breaker.state.value,
            "failure_count": circuit_breaker.failure_count,
            "is_open": circuit_breaker.is_open,
            "last_failure_time": getattr(circuit_breaker, 'last_failure_time', None)
        }
    
    async def execute_agent_operation(
        self, 
        agent_type: str, 
        operation: Callable, 
        *args, 
        **kwargs
    ) -> Any:
        """Execute operation with agent-specific circuit breaker protection."""
        circuit_breaker = self._agent_circuit_breakers.get(agent_type)
        
        if not circuit_breaker:
            # No circuit breaker, execute directly
            return await operation(*args, **kwargs)
        
        try:
            return await circuit_breaker.execute(operation, *args, **kwargs)
        except Exception as e:
            self.logger.error(f"Agent operation failed for {agent_type}: {e}")
            raise


# Agent-specific service facades

class AgentDatabaseService:
    """Database service facade for agent-specific data operations."""
    
    def __init__(self, unified_facade: UnifiedServiceFacade, agent_type: str):
        self.facade = unified_facade
        self.agent_type = agent_type
        self.logger = logging.getLogger(f"{__name__}.AgentDatabaseService.{agent_type}")
    
    async def store_agent_data(self, data: Dict[str, Any], tenant_id: str) -> str:
        """Store agent-specific data with tenant isolation."""
        async def operation():
            # Use the existing agent core service with agent-specific prefixing
            agent_core = self.facade.get_agent_core_service()
            key = f"{self.agent_type}:data:{data.get('id', str(uuid.uuid4()))}"
            success = await agent_core.put_memory(
                user_id=f"agent:{self.agent_type}",
                key=key,
                value=data,
                tenant_id=tenant_id
            )
            return key if success else None
        
        return await self.facade.execute_agent_operation(
            self.agent_type, operation
        )
    
    async def get_agent_data(self, data_id: str, tenant_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve agent-specific data."""
        async def operation():
            agent_core = self.facade.get_agent_core_service()
            key = f"{self.agent_type}:data:{data_id}"
            return await agent_core.get_memory(
                user_id=f"agent:{self.agent_type}",
                key=key,
                tenant_id=tenant_id
            )
        
        return await self.facade.execute_agent_operation(
            self.agent_type, operation
        )
    
    async def query_agent_data(self, query: Dict[str, Any], tenant_id: str) -> List[Dict[str, Any]]:
        """Query agent-specific data with filters."""
        async def operation():
            # Use search service for complex queries
            search_service = self.facade.get_search_service()
            query_str = query.get('query', '*')
            filters = query.get('filters', {})
            filters['agent_type'] = self.agent_type  # Add agent type filter
            
            return await search_service.search(
                query=query_str,
                tenant_id=tenant_id,
                filters=filters,
                index_name=f"agent_{self.agent_type}"
            )
        
        return await self.facade.execute_agent_operation(
            self.agent_type, operation
        )


class AgentStorageService:
    """Storage service facade for agent-specific file operations."""
    
    def __init__(self, unified_facade: UnifiedServiceFacade, agent_type: str):
        self.facade = unified_facade
        self.agent_type = agent_type
        self.logger = logging.getLogger(f"{__name__}.AgentStorageService.{agent_type}")
    
    async def store_agent_file(self, file_key: str, data: bytes, tenant_id: str, 
                              metadata: Dict[str, str] = None) -> bool:
        """Store agent-specific files with proper prefixing."""
        async def operation():
            storage_service = self.facade.get_storage_service()
            prefixed_key = f"agents/{self.agent_type}/{file_key}"
            
            agent_metadata = metadata or {}
            agent_metadata['agent_type'] = self.agent_type
            
            return await storage_service.put_object(
                key=prefixed_key,
                data=data,
                tenant_id=tenant_id,
                metadata=agent_metadata
            )
        
        return await self.facade.execute_agent_operation(
            self.agent_type, operation
        )
    
    async def get_agent_file(self, file_key: str, tenant_id: str) -> Optional[bytes]:
        """Retrieve agent-specific files."""
        async def operation():
            storage_service = self.facade.get_storage_service()
            prefixed_key = f"agents/{self.agent_type}/{file_key}"
            
            return await storage_service.get_object(
                key=prefixed_key,
                tenant_id=tenant_id
            )
        
        return await self.facade.execute_agent_operation(
            self.agent_type, operation
        )
    
    async def list_agent_files(self, prefix: str, tenant_id: str) -> List[str]:
        """List agent-specific files."""
        async def operation():
            storage_service = self.facade.get_storage_service()
            agent_prefix = f"agents/{self.agent_type}/{prefix}"
            
            files = await storage_service.list_objects(
                prefix=agent_prefix,
                tenant_id=tenant_id
            )
            
            # Remove agent prefix from returned file names
            agent_prefix_len = len(f"agents/{self.agent_type}/")
            return [f[agent_prefix_len:] for f in files]
        
        return await self.facade.execute_agent_operation(
            self.agent_type, operation
        )


class AgentComputeService:
    """Compute service facade for agent-specific operations."""
    
    def __init__(self, unified_facade: UnifiedServiceFacade, agent_type: str):
        self.facade = unified_facade
        self.agent_type = agent_type
        self.logger = logging.getLogger(f"{__name__}.AgentComputeService.{agent_type}")
    
    async def invoke_agent_function(self, function_name: str, payload: Dict[str, Any], 
                                   tenant_id: str, async_mode: bool = False) -> Dict[str, Any]:
        """Invoke agent-specific compute functions."""
        async def operation():
            compute_service = self.facade.get_compute_service()
            
            # Add agent context to payload
            agent_payload = {
                **payload,
                'agent_type': self.agent_type,
                'agent_context': {
                    'tenant_id': tenant_id,
                    'function_name': function_name
                }
            }
            
            # Use agent-specific function naming
            agent_function_name = f"{self.agent_type}_{function_name}"
            
            return await compute_service.invoke_function(
                function_name=agent_function_name,
                payload=agent_payload,
                tenant_id=tenant_id,
                async_mode=async_mode
            )
        
        return await self.facade.execute_agent_operation(
            self.agent_type, operation
        )
    
    async def schedule_agent_job(self, job_config: Dict[str, Any], tenant_id: str) -> str:
        """Schedule agent-specific background jobs."""
        async def operation():
            compute_service = self.facade.get_compute_service()
            
            # Add agent context to job config
            agent_job_config = {
                **job_config,
                'agent_type': self.agent_type,
                'job_name': f"{self.agent_type}_{job_config.get('job_name', 'job')}",
                'agent_context': {
                    'tenant_id': tenant_id
                }
            }
            
            return await compute_service.schedule_job(
                job_config=agent_job_config,
                tenant_id=tenant_id
            )
        
        return await self.facade.execute_agent_operation(
            self.agent_type, operation
        )


# GCP Migration data classes (to be implemented)
class GCPMigrationConfig:
    """Configuration for GCP to AWS migration."""
    
    def __init__(self, 
                 source_project: str,
                 target_aws_region: str,
                 migration_type: str = "full",
                 preserve_data: bool = True):
        self.source_project = source_project
        self.target_aws_region = target_aws_region
        self.migration_type = migration_type
        self.preserve_data = preserve_data


class MigrationResult:
    """Result of GCP to AWS migration operation."""
    
    def __init__(self, 
                 success: bool,
                 migrated_resources: List[str],
                 errors: List[str] = None):
        self.success = success
        self.migrated_resources = migrated_resources
        self.errors = errors or []