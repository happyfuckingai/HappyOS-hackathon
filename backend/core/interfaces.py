"""
Core service interfaces for the infrastructure recovery system.
These interfaces define the contracts for AWS and local service implementations.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Union, AsyncIterator
from datetime import datetime
from dataclasses import dataclass
from enum import Enum


# Core data models
@dataclass
class AgentSession:
    """Agent session model for managing agent state and context."""
    session_id: str
    tenant_id: str
    agent_id: str
    user_id: str
    created_at: datetime
    last_activity: datetime
    status: str
    memory_context: Dict[str, Any]
    configuration: Dict[str, Any]


@dataclass
class A2AMessage:
    """Agent-to-Agent message model for secure communication."""
    message_id: str
    conversation_id: str
    sender_agent: str
    recipient_agent: str
    tenant_id: str
    message_type: str
    payload: Dict[str, Any]
    timestamp: datetime
    signature: Optional[str] = None
    encryption_key_id: Optional[str] = None


@dataclass
class TenantResource:
    """Tenant resource model for multi-tenant isolation."""
    tenant_id: str
    resource_type: str
    resource_id: str
    configuration: Dict[str, Any]
    access_policy: Dict[str, Any]
    created_at: datetime
    updated_at: datetime


@dataclass
class LLMRequest:
    """LLM request model for tracking LLM operations."""
    agent_id: str
    team: str
    prompt: str
    model: str
    temperature: float
    max_tokens: int
    response_format: str
    metadata: Dict[str, Any]
    timestamp: datetime


@dataclass
class LLMResponse:
    """LLM response model for tracking LLM results."""
    request_id: str
    agent_id: str
    content: str
    model: str
    provider: str
    tokens_used: int
    estimated_cost: float
    latency_ms: int
    cached: bool
    timestamp: datetime


@dataclass
class LLMUsageStats:
    """LLM usage statistics model for monitoring and cost tracking."""
    agent_id: str
    team: str
    time_range: str
    total_requests: int
    cached_requests: int
    failed_requests: int
    total_tokens: int
    total_cost: float
    average_latency_ms: float
    provider_breakdown: Dict[str, int]


class CircuitState(Enum):
    """Circuit breaker states."""
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class ServiceHealth(Enum):
    """Service health status."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


# Core service interfaces
class AgentCoreService(ABC):
    """Interface for agent memory and runtime management."""
    
    @abstractmethod
    async def put_memory(self, user_id: str, key: str, value: Any, tenant_id: str) -> bool:
        """Store memory data for a user within a tenant context."""
        pass
    
    @abstractmethod
    async def get_memory(self, user_id: str, key: str, tenant_id: str) -> Any:
        """Retrieve memory data for a user within a tenant context."""
        pass
    
    @abstractmethod
    async def create_session(self, tenant_id: str, agent_id: str, user_id: str, config: Dict[str, Any]) -> str:
        """Create a new agent session."""
        pass
    
    @abstractmethod
    async def get_session(self, session_id: str, tenant_id: str) -> Optional[AgentSession]:
        """Retrieve an agent session."""
        pass
    
    @abstractmethod
    async def update_session(self, session_id: str, tenant_id: str, updates: Dict[str, Any]) -> bool:
        """Update an agent session."""
        pass
    
    @abstractmethod
    async def delete_session(self, session_id: str, tenant_id: str) -> bool:
        """Delete an agent session."""
        pass


class SearchService(ABC):
    """Interface for search operations with tenant isolation."""
    
    @abstractmethod
    async def index_document(self, doc: Dict[str, Any], tenant_id: str, index_name: str = None) -> str:
        """Index a document for search."""
        pass
    
    @abstractmethod
    async def search(self, query: str, tenant_id: str, filters: Dict[str, Any] = None, 
                    index_name: str = None) -> List[Dict[str, Any]]:
        """Perform text search."""
        pass
    
    @abstractmethod
    async def hybrid_search(self, query: str, vector: List[float], tenant_id: str, 
                           filters: Dict[str, Any] = None, index_name: str = None) -> List[Dict[str, Any]]:
        """Perform hybrid text and vector search."""
        pass
    
    @abstractmethod
    async def delete_document(self, doc_id: str, tenant_id: str, index_name: str = None) -> bool:
        """Delete a document from search index."""
        pass


class ComputeService(ABC):
    """Interface for compute/function execution."""
    
    @abstractmethod
    async def invoke_function(self, function_name: str, payload: Dict[str, Any], 
                             tenant_id: str, async_mode: bool = False) -> Dict[str, Any]:
        """Invoke a compute function."""
        pass
    
    @abstractmethod
    async def schedule_job(self, job_config: Dict[str, Any], tenant_id: str) -> str:
        """Schedule a job for execution."""
        pass
    
    @abstractmethod
    async def get_job_status(self, job_id: str, tenant_id: str) -> Dict[str, Any]:
        """Get job execution status."""
        pass


class CacheService(ABC):
    """Interface for caching operations."""
    
    @abstractmethod
    async def get(self, key: str, tenant_id: str) -> Optional[Any]:
        """Get value from cache."""
        pass
    
    @abstractmethod
    async def set(self, key: str, value: Any, tenant_id: str, ttl: int = None) -> bool:
        """Set value in cache with optional TTL."""
        pass
    
    @abstractmethod
    async def delete(self, key: str, tenant_id: str) -> bool:
        """Delete value from cache."""
        pass
    
    @abstractmethod
    async def exists(self, key: str, tenant_id: str) -> bool:
        """Check if key exists in cache."""
        pass


class StorageService(ABC):
    """Interface for object storage operations."""
    
    @abstractmethod
    async def put_object(self, key: str, data: bytes, tenant_id: str, 
                        metadata: Dict[str, str] = None) -> bool:
        """Store an object."""
        pass
    
    @abstractmethod
    async def get_object(self, key: str, tenant_id: str) -> Optional[bytes]:
        """Retrieve an object."""
        pass
    
    @abstractmethod
    async def delete_object(self, key: str, tenant_id: str) -> bool:
        """Delete an object."""
        pass
    
    @abstractmethod
    async def list_objects(self, prefix: str, tenant_id: str) -> List[str]:
        """List objects with prefix."""
        pass


class SecretsService(ABC):
    """Interface for secrets management."""
    
    @abstractmethod
    async def get_secret(self, secret_name: str, tenant_id: str = None) -> Optional[str]:
        """Retrieve a secret value."""
        pass
    
    @abstractmethod
    async def put_secret(self, secret_name: str, secret_value: str, tenant_id: str = None) -> bool:
        """Store a secret value."""
        pass
    
    @abstractmethod
    async def delete_secret(self, secret_name: str, tenant_id: str = None) -> bool:
        """Delete a secret."""
        pass


class HealthService(ABC):
    """Interface for health monitoring."""
    
    @abstractmethod
    async def check_service_health(self, service_name: str) -> ServiceHealth:
        """Check health of a specific service."""
        pass
    
    @abstractmethod
    async def check_all_services(self) -> Dict[str, ServiceHealth]:
        """Check health of all services."""
        pass
    
    @abstractmethod
    async def get_service_metrics(self, service_name: str) -> Dict[str, Any]:
        """Get metrics for a service."""
        pass


class CircuitBreakerService(ABC):
    """Interface for circuit breaker functionality."""
    
    @abstractmethod
    async def call_with_circuit_breaker(self, service_name: str, func, *args, **kwargs) -> Any:
        """Execute function with circuit breaker protection."""
        pass
    
    @abstractmethod
    async def get_circuit_state(self, service_name: str) -> CircuitState:
        """Get current circuit breaker state."""
        pass
    
    @abstractmethod
    async def force_open_circuit(self, service_name: str) -> bool:
        """Force circuit breaker to open state."""
        pass
    
    @abstractmethod
    async def force_close_circuit(self, service_name: str) -> bool:
        """Force circuit breaker to closed state."""
        pass


class A2AProtocolService(ABC):
    """Interface for Agent-to-Agent communication."""
    
    @abstractmethod
    async def send_message(self, message: A2AMessage) -> bool:
        """Send a message to another agent."""
        pass
    
    @abstractmethod
    async def receive_messages(self, agent_id: str, tenant_id: str) -> List[A2AMessage]:
        """Receive messages for an agent."""
        pass
    
    @abstractmethod
    async def encrypt_message(self, message: A2AMessage, recipient_key: str) -> A2AMessage:
        """Encrypt a message for secure transmission."""
        pass
    
    @abstractmethod
    async def decrypt_message(self, encrypted_message: A2AMessage, private_key: str) -> A2AMessage:
        """Decrypt a received message."""
        pass


class TenantService(ABC):
    """Interface for tenant management."""
    
    @abstractmethod
    async def get_tenant_config(self, tenant_id: str) -> Optional[Dict[str, Any]]:
        """Get configuration for a tenant."""
        pass
    
    @abstractmethod
    async def validate_tenant_access(self, tenant_id: str, resource_type: str, resource_id: str) -> bool:
        """Validate tenant access to a resource."""
        pass
    
    @abstractmethod
    async def get_tenant_resources(self, tenant_id: str, resource_type: str = None) -> List[TenantResource]:
        """Get resources for a tenant."""
        pass
    
    @abstractmethod
    async def create_tenant_resource(self, resource: TenantResource) -> bool:
        """Create a new tenant resource."""
        pass


class LLMService(ABC):
    """Interface for LLM operations with tenant isolation."""
    
    @abstractmethod
    async def generate_completion(
        self,
        prompt: str,
        agent_id: str,
        tenant_id: str,
        model: str = "gpt-4",
        temperature: float = 0.3,
        max_tokens: int = 500,
        response_format: str = "json"
    ) -> Dict[str, Any]:
        """Generate LLM completion.
        
        Args:
            prompt: The prompt to send to the LLM
            agent_id: Identifier of the agent making the request
            tenant_id: Tenant identifier for isolation
            model: Model to use (e.g., "gpt-4", "claude-3-sonnet", "gemini-1.5-pro")
            temperature: Sampling temperature (0.0-1.0)
            max_tokens: Maximum tokens in response
            response_format: Expected response format ("json" or "text")
            
        Returns:
            Dict containing:
                - content: The generated text
                - model: Model used
                - tokens: Token count
                - cached: Whether response was cached
        """
        pass
    
    @abstractmethod
    async def generate_streaming_completion(
        self,
        prompt: str,
        agent_id: str,
        tenant_id: str,
        model: str = "gpt-4",
        temperature: float = 0.3,
        max_tokens: int = 500
    ) -> AsyncIterator[str]:
        """Generate streaming LLM completion.
        
        Args:
            prompt: The prompt to send to the LLM
            agent_id: Identifier of the agent making the request
            tenant_id: Tenant identifier for isolation
            model: Model to use
            temperature: Sampling temperature (0.0-1.0)
            max_tokens: Maximum tokens in response
            
        Yields:
            Chunks of generated text as they arrive
        """
        pass
    
    @abstractmethod
    async def get_usage_stats(
        self,
        agent_id: Optional[str] = None,
        tenant_id: Optional[str] = None,
        time_range: str = "24h"
    ) -> Dict[str, Any]:
        """Get LLM usage statistics.
        
        Args:
            agent_id: Optional agent ID to filter stats
            tenant_id: Optional tenant ID to filter stats
            time_range: Time range for stats (e.g., "1h", "24h", "7d")
            
        Returns:
            Dict containing usage statistics
        """
        pass


# Service factory interface
class ServiceFactory(ABC):
    """Factory interface for creating service instances."""
    
    @abstractmethod
    def create_agent_core_service(self) -> AgentCoreService:
        """Create agent core service instance."""
        pass
    
    @abstractmethod
    def create_search_service(self) -> SearchService:
        """Create search service instance."""
        pass
    
    @abstractmethod
    def create_compute_service(self) -> ComputeService:
        """Create compute service instance."""
        pass
    
    @abstractmethod
    def create_cache_service(self) -> CacheService:
        """Create cache service instance."""
        pass
    
    @abstractmethod
    def create_storage_service(self) -> StorageService:
        """Create storage service instance."""
        pass
    
    @abstractmethod
    def create_secrets_service(self) -> SecretsService:
        """Create secrets service instance."""
        pass
    
    @abstractmethod
    def create_health_service(self) -> HealthService:
        """Create health service instance."""
        pass
    
    @abstractmethod
    def create_llm_service(self) -> 'LLMService':
        """Create LLM service instance."""
        pass