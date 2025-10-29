"""
Service Facades - Abstraction layer for HappyOS core services

Provides service facades that agents can use to interact with core platform
services (database, storage, compute, etc.) without direct backend imports.
"""

import asyncio
import logging
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List, Union
from datetime import datetime

try:
    from ..a2a_client import A2AClient
    from ..circuit_breaker import CircuitBreaker, CircuitBreakerConfig, get_circuit_breaker
    from ..exceptions import ServiceUnavailableError
    from ..unified_observability import get_observability_manager, ObservabilityContext
except ImportError:
    from happyos_sdk.a2a_client import A2AClient
    from happyos_sdk.circuit_breaker import CircuitBreaker, CircuitBreakerConfig, get_circuit_breaker
    from happyos_sdk.exceptions import ServiceUnavailableError
    from happyos_sdk.unified_observability import get_observability_manager, ObservabilityContext

logger = logging.getLogger(__name__)


class ServiceFacade(ABC):
    """Base class for all service facades."""
    
    def __init__(self, a2a_client: A2AClient, service_name: str):
        """
        Initialize service facade.
        
        Args:
            a2a_client: A2A client for communication
            service_name: Name of the core service
        """
        self.a2a_client = a2a_client
        self.service_name = service_name
        self.tenant_id = a2a_client.tenant_id
    
    async def _call_service(self, action: str, data: Dict[str, Any], trace_id: str = None) -> Dict[str, Any]:
        """Call core service via A2A protocol with circuit breaker protection and observability."""
        circuit_breaker = get_circuit_breaker(f"{self.service_name}_service")
        observability = get_observability_manager("service_facade")
        
        # Create observability context
        context = ObservabilityContext(
            trace_id=trace_id,
            tenant_id=self.tenant_id,
            component="service_facade",
            operation=action,
            protocol="a2a",
            service_name=self.service_name,
            action=action
        )
        
        async def service_call():
            response = await self.a2a_client.send_request(
                recipient_id=f"core_{self.service_name}",
                action=action,
                data=data
            )
            
            if not response.get("success", True):
                raise ServiceUnavailableError(
                    f"{self.service_name} service error: {response.get('error', 'Unknown error')}"
                )
            
            return response
        
        try:
            # Execute with observability and circuit breaker protection
            return await observability.execute_with_observability(
                lambda: circuit_breaker.execute(service_call),
                context,
                f"{self.service_name}_{action}"
            )
        except Exception as e:
            # Log circuit breaker events
            await observability.log_circuit_breaker_event(
                service_name=self.service_name,
                event_type="failed",
                trace_id=trace_id,
                tenant_id=self.tenant_id,
                details={"action": action, "error": str(e)}
            )
            
            logger.error(f"Service call failed for {self.service_name}.{action}: {e}")
            raise ServiceUnavailableError(f"{self.service_name} service unavailable: {e}")


class DatabaseFacade(ServiceFacade):
    """Facade for database operations."""
    
    def __init__(self, a2a_client: A2AClient):
        super().__init__(a2a_client, "database")
    
    async def store_data(self, 
                        data: Dict[str, Any], 
                        data_type: Optional[str] = None,
                        trace_id: str = None) -> str:
        """
        Store data in the database.
        
        Args:
            data: Data to store
            data_type: Optional data type classification
            trace_id: Trace ID for observability
            
        Returns:
            Data ID
        """
        request_data = {
            "operation": "store",
            "data": data,
            "data_type": data_type,
            "tenant_id": self.tenant_id,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        response = await self._call_service("store_data", request_data, trace_id)
        return response.get("data_id")
    
    async def get_data(self, data_id: str, trace_id: str = None) -> Optional[Dict[str, Any]]:
        """
        Retrieve data by ID.
        
        Args:
            data_id: Data identifier
            trace_id: Trace ID for observability
            
        Returns:
            Data or None if not found
        """
        request_data = {
            "operation": "get",
            "data_id": data_id,
            "tenant_id": self.tenant_id
        }
        
        response = await self._call_service("get_data", request_data, trace_id)
        return response.get("data")
    
    async def query_data(self, 
                        query: Dict[str, Any], 
                        limit: int = 100,
                        trace_id: str = None) -> List[Dict[str, Any]]:
        """
        Query data with filters.
        
        Args:
            query: Query parameters and filters
            limit: Maximum number of results
            trace_id: Trace ID for observability
            
        Returns:
            List of matching data items
        """
        request_data = {
            "operation": "query",
            "query": query,
            "limit": limit,
            "tenant_id": self.tenant_id
        }
        
        response = await self._call_service("query_data", request_data, trace_id)
        return response.get("results", [])
    
    async def update_data(self, data_id: str, updates: Dict[str, Any]) -> bool:
        """
        Update existing data.
        
        Args:
            data_id: Data identifier
            updates: Fields to update
            
        Returns:
            Success status
        """
        request_data = {
            "operation": "update",
            "data_id": data_id,
            "updates": updates,
            "tenant_id": self.tenant_id,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        response = await self._call_service("update_data", request_data)
        return response.get("success", False)
    
    async def delete_data(self, data_id: str) -> bool:
        """
        Delete data by ID.
        
        Args:
            data_id: Data identifier
            
        Returns:
            Success status
        """
        request_data = {
            "operation": "delete",
            "data_id": data_id,
            "tenant_id": self.tenant_id
        }
        
        response = await self._call_service("delete_data", request_data)
        return response.get("success", False)


class StorageFacade(ServiceFacade):
    """Facade for file storage operations."""
    
    def __init__(self, a2a_client: A2AClient):
        super().__init__(a2a_client, "storage")
    
    async def store_file(self, 
                        file_key: str, 
                        file_data: bytes, 
                        metadata: Optional[Dict[str, str]] = None) -> bool:
        """
        Store a file.
        
        Args:
            file_key: File identifier/path
            file_data: File content as bytes
            metadata: Optional file metadata
            
        Returns:
            Success status
        """
        # For large files, we might need to chunk or use presigned URLs
        # For now, encode as base64 for A2A transport
        import base64
        
        request_data = {
            "operation": "store_file",
            "file_key": file_key,
            "file_data": base64.b64encode(file_data).decode('utf-8'),
            "metadata": metadata or {},
            "tenant_id": self.tenant_id,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        response = await self._call_service("store_file", request_data)
        return response.get("success", False)
    
    async def get_file(self, file_key: str) -> Optional[bytes]:
        """
        Retrieve a file.
        
        Args:
            file_key: File identifier/path
            
        Returns:
            File content as bytes or None if not found
        """
        request_data = {
            "operation": "get_file",
            "file_key": file_key,
            "tenant_id": self.tenant_id
        }
        
        response = await self._call_service("get_file", request_data)
        file_data = response.get("file_data")
        
        if file_data:
            import base64
            return base64.b64decode(file_data)
        
        return None
    
    async def list_files(self, prefix: str = "") -> List[str]:
        """
        List files with optional prefix filter.
        
        Args:
            prefix: File key prefix to filter by
            
        Returns:
            List of file keys
        """
        request_data = {
            "operation": "list_files",
            "prefix": prefix,
            "tenant_id": self.tenant_id
        }
        
        response = await self._call_service("list_files", request_data)
        return response.get("files", [])
    
    async def delete_file(self, file_key: str) -> bool:
        """
        Delete a file.
        
        Args:
            file_key: File identifier/path
            
        Returns:
            Success status
        """
        request_data = {
            "operation": "delete_file",
            "file_key": file_key,
            "tenant_id": self.tenant_id
        }
        
        response = await self._call_service("delete_file", request_data)
        return response.get("success", False)


class ComputeFacade(ServiceFacade):
    """Facade for compute/job operations."""
    
    def __init__(self, a2a_client: A2AClient):
        super().__init__(a2a_client, "compute")
    
    async def invoke_function(self, 
                             function_name: str, 
                             payload: Dict[str, Any],
                             async_mode: bool = False) -> Dict[str, Any]:
        """
        Invoke a compute function.
        
        Args:
            function_name: Name of the function to invoke
            payload: Function payload
            async_mode: Whether to invoke asynchronously
            
        Returns:
            Function result
        """
        request_data = {
            "operation": "invoke_function",
            "function_name": function_name,
            "payload": payload,
            "async_mode": async_mode,
            "tenant_id": self.tenant_id,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        response = await self._call_service("invoke_function", request_data)
        return response.get("result", {})
    
    async def schedule_job(self, 
                          job_config: Dict[str, Any]) -> str:
        """
        Schedule a background job.
        
        Args:
            job_config: Job configuration
            
        Returns:
            Job ID
        """
        request_data = {
            "operation": "schedule_job",
            "job_config": job_config,
            "tenant_id": self.tenant_id,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        response = await self._call_service("schedule_job", request_data)
        return response.get("job_id")
    
    async def get_job_status(self, job_id: str) -> Dict[str, Any]:
        """
        Get job status.
        
        Args:
            job_id: Job identifier
            
        Returns:
            Job status information
        """
        request_data = {
            "operation": "get_job_status",
            "job_id": job_id,
            "tenant_id": self.tenant_id
        }
        
        response = await self._call_service("get_job_status", request_data)
        return response.get("job_status", {})


class SearchFacade(ServiceFacade):
    """Facade for search operations."""
    
    def __init__(self, a2a_client: A2AClient):
        super().__init__(a2a_client, "search")
    
    async def index_document(self, 
                           document: Dict[str, Any], 
                           index_name: Optional[str] = None) -> str:
        """
        Index a document for search.
        
        Args:
            document: Document to index
            index_name: Optional index name
            
        Returns:
            Document ID
        """
        request_data = {
            "operation": "index_document",
            "document": document,
            "index_name": index_name,
            "tenant_id": self.tenant_id,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        response = await self._call_service("index_document", request_data)
        return response.get("document_id")
    
    async def search(self, 
                    query: str, 
                    filters: Optional[Dict[str, Any]] = None,
                    limit: int = 100) -> List[Dict[str, Any]]:
        """
        Search for documents.
        
        Args:
            query: Search query
            filters: Optional filters
            limit: Maximum number of results
            
        Returns:
            List of matching documents
        """
        request_data = {
            "operation": "search",
            "query": query,
            "filters": filters or {},
            "limit": limit,
            "tenant_id": self.tenant_id
        }
        
        response = await self._call_service("search", request_data)
        return response.get("results", [])
    
    async def hybrid_search(self, 
                           query: str, 
                           vector: List[float],
                           filters: Optional[Dict[str, Any]] = None,
                           limit: int = 100) -> List[Dict[str, Any]]:
        """
        Perform hybrid text + vector search.
        
        Args:
            query: Text query
            vector: Query vector
            filters: Optional filters
            limit: Maximum number of results
            
        Returns:
            List of matching documents with scores
        """
        request_data = {
            "operation": "hybrid_search",
            "query": query,
            "vector": vector,
            "filters": filters or {},
            "limit": limit,
            "tenant_id": self.tenant_id
        }
        
        response = await self._call_service("hybrid_search", request_data)
        return response.get("results", [])


class SecretsFacade(ServiceFacade):
    """Facade for secrets management."""
    
    def __init__(self, a2a_client: A2AClient):
        super().__init__(a2a_client, "secrets")
    
    async def get_secret(self, secret_name: str) -> Optional[str]:
        """
        Retrieve a secret value.
        
        Args:
            secret_name: Name of the secret
            
        Returns:
            Secret value or None if not found
        """
        request_data = {
            "operation": "get_secret",
            "secret_name": secret_name,
            "tenant_id": self.tenant_id
        }
        
        response = await self._call_service("get_secret", request_data)
        return response.get("secret_value")
    
    async def store_secret(self, secret_name: str, secret_value: str) -> bool:
        """
        Store a secret value.
        
        Args:
            secret_name: Name of the secret
            secret_value: Secret value
            
        Returns:
            Success status
        """
        request_data = {
            "operation": "store_secret",
            "secret_name": secret_name,
            "secret_value": secret_value,
            "tenant_id": self.tenant_id,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        response = await self._call_service("store_secret", request_data)
        return response.get("success", False)


class CacheFacade(ServiceFacade):
    """Facade for caching operations."""
    
    def __init__(self, a2a_client: A2AClient):
        super().__init__(a2a_client, "cache")
    
    async def get(self, key: str) -> Optional[Any]:
        """
        Get value from cache.
        
        Args:
            key: Cache key
            
        Returns:
            Cached value or None if not found
        """
        request_data = {
            "operation": "get",
            "key": key,
            "tenant_id": self.tenant_id
        }
        
        response = await self._call_service("get", request_data)
        return response.get("value")
    
    async def set(self, 
                 key: str, 
                 value: Any, 
                 ttl: Optional[int] = None) -> bool:
        """
        Set value in cache.
        
        Args:
            key: Cache key
            value: Value to cache
            ttl: Time to live in seconds
            
        Returns:
            Success status
        """
        request_data = {
            "operation": "set",
            "key": key,
            "value": value,
            "ttl": ttl,
            "tenant_id": self.tenant_id,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        response = await self._call_service("set", request_data)
        return response.get("success", False)
    
    async def delete(self, key: str) -> bool:
        """
        Delete value from cache.
        
        Args:
            key: Cache key
            
        Returns:
            Success status
        """
        request_data = {
            "operation": "delete",
            "key": key,
            "tenant_id": self.tenant_id
        }
        
        response = await self._call_service("delete", request_data)
        return response.get("success", False)


# Factory functions for creating service facades
def create_service_facades(a2a_client: A2AClient) -> Dict[str, ServiceFacade]:
    """
    Create all service facades for an agent.
    
    Args:
        a2a_client: A2A client instance
        
    Returns:
        Dictionary of service facades
    """
    return {
        "database": DatabaseFacade(a2a_client),
        "storage": StorageFacade(a2a_client),
        "compute": ComputeFacade(a2a_client),
        "search": SearchFacade(a2a_client),
        "secrets": SecretsFacade(a2a_client),
        "cache": CacheFacade(a2a_client)
    }