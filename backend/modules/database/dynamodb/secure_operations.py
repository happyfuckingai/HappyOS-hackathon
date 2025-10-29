"""
Secure DynamoDB Operations with Tenant Isolation

Wraps all DynamoDB operations with mandatory tenant validation
to ensure complete row-level security and prevent cross-tenant data access.

Requirements: 6.1, 6.2, 6.3
"""

import logging
from typing import Dict, List, Optional, Any, Union
from datetime import datetime, timezone

from .client import DynamoDBClient
from .operations import DynamoDBOperations
from .tenant_validation import dynamodb_tenant_validator
from ..auth.jwt_service import JWTClaims
from ..auth.tenant_isolation import audit_logger, TenantIsolationError

logger = logging.getLogger(__name__)


class SecureDynamoDBOperations:
    """
    Secure wrapper for DynamoDB operations with mandatory tenant validation
    
    All operations are validated for tenant isolation before execution.
    Provides complete protection against cross-tenant data access.
    """
    
    def __init__(self, client: DynamoDBClient):
        self.client = client
        self.operations = DynamoDBOperations(client)
        self.validator = dynamodb_tenant_validator
    
    async def put_resource(
        self,
        resource: Any,  # UIResource
        claims: JWTClaims,
        audit_context: Optional[Dict[str, Any]] = None
    ) -> Any:
        """
        Securely store a UI resource with tenant validation
        
        Args:
            resource: UIResource to store
            claims: JWT claims for authorization
            audit_context: Additional audit context
            
        Returns:
            Stored resource
            
        Raises:
            TenantIsolationError: If tenant validation fails
        """
        try:
            # Convert resource to DynamoDB item format
            item = self.operations._resource_to_item(resource)
            
            # Validate tenant access
            self.validator.validate_put_operation(item, claims, "put_resource")
            
            # Execute operation
            result = await self.operations.put_resource(resource)
            
            # Log successful operation
            audit_logger.log_tenant_operation(
                operation="dynamodb_put_resource",
                tenant_id=resource.tenantId,
                user_id=claims.sub,
                resource_id=resource.id,
                details={
                    "operation_type": "put_resource",
                    "resource_type": resource.type,
                    "revision": resource.revision,
                    **(audit_context or {})
                },
                success=True
            )
            
            return result
            
        except TenantIsolationError:
            # Log failed operation
            audit_logger.log_tenant_operation(
                operation="dynamodb_put_resource_denied",
                tenant_id=getattr(resource, 'tenantId', 'unknown'),
                user_id=claims.sub,
                resource_id=getattr(resource, 'id', 'unknown'),
                details={
                    "operation_type": "put_resource",
                    "reason": "tenant_isolation_violation",
                    **(audit_context or {})
                },
                success=False
            )
            raise
        except Exception as e:
            # Log unexpected error
            audit_logger.log_tenant_operation(
                operation="dynamodb_put_resource_error",
                tenant_id=getattr(resource, 'tenantId', 'unknown'),
                user_id=claims.sub,
                resource_id=getattr(resource, 'id', 'unknown'),
                details={
                    "operation_type": "put_resource",
                    "error": str(e),
                    **(audit_context or {})
                },
                success=False
            )
            raise
    
    async def get_resource(
        self,
        tenant_id: str,
        session_id: str,
        resource_id: str,
        claims: JWTClaims,
        audit_context: Optional[Dict[str, Any]] = None
    ) -> Optional[Any]:
        """
        Securely retrieve a UI resource with tenant validation
        
        Args:
            tenant_id: Tenant identifier
            session_id: Session identifier
            resource_id: Resource identifier
            claims: JWT claims for authorization
            audit_context: Additional audit context
            
        Returns:
            Retrieved resource or None if not found
            
        Raises:
            TenantIsolationError: If tenant validation fails
        """
        try:
            # Build partition key
            partition_key = f"{tenant_id}#{session_id}"
            
            # Validate tenant access
            self.validator.validate_get_operation(partition_key, resource_id, claims, "get_resource")
            
            # Execute operation
            result = await self.operations.get_resource(tenant_id, session_id, resource_id)
            
            # Log successful operation
            audit_logger.log_tenant_operation(
                operation="dynamodb_get_resource",
                tenant_id=tenant_id,
                user_id=claims.sub,
                resource_id=resource_id,
                details={
                    "operation_type": "get_resource",
                    "found": result is not None,
                    **(audit_context or {})
                },
                success=True
            )
            
            return result
            
        except TenantIsolationError:
            # Log failed operation
            audit_logger.log_tenant_operation(
                operation="dynamodb_get_resource_denied",
                tenant_id=tenant_id,
                user_id=claims.sub,
                resource_id=resource_id,
                details={
                    "operation_type": "get_resource",
                    "reason": "tenant_isolation_violation",
                    **(audit_context or {})
                },
                success=False
            )
            raise
        except Exception as e:
            # Log unexpected error
            audit_logger.log_tenant_operation(
                operation="dynamodb_get_resource_error",
                tenant_id=tenant_id,
                user_id=claims.sub,
                resource_id=resource_id,
                details={
                    "operation_type": "get_resource",
                    "error": str(e),
                    **(audit_context or {})
                },
                success=False
            )
            raise
    
    async def query_resources(
        self,
        query: Any,  # UIResourceQuery
        claims: JWTClaims,
        audit_context: Optional[Dict[str, Any]] = None
    ) -> List[Any]:
        """
        Securely query UI resources with tenant validation
        
        Args:
            query: UIResourceQuery with filtering parameters
            claims: JWT claims for authorization
            audit_context: Additional audit context
            
        Returns:
            List of matching resources
            
        Raises:
            TenantIsolationError: If tenant validation fails
        """
        try:
            # Build key condition expression (simplified)
            key_condition = f"PK = :pk"
            partition_key = f"{query.tenantId}#{query.sessionId or '*'}"
            
            # Validate tenant access
            self.validator.validate_query_operation(key_condition, None, claims, "query_resources")
            
            # Execute operation
            result = await self.operations.query_resources(query)
            
            # Additional validation: ensure all returned resources belong to authorized tenant
            validated_results = []
            for resource in result:
                if resource.tenantId == query.tenantId:
                    validated_results.append(resource)
                else:
                    logger.warning(
                        f"Filtered out resource {resource.id} with mismatched tenant "
                        f"{resource.tenantId} (expected {query.tenantId})"
                    )
            
            # Log successful operation
            audit_logger.log_tenant_operation(
                operation="dynamodb_query_resources",
                tenant_id=query.tenantId,
                user_id=claims.sub,
                details={
                    "operation_type": "query_resources",
                    "session_id": query.sessionId,
                    "agent_id": query.agentId,
                    "resource_type": query.resourceType,
                    "result_count": len(validated_results),
                    "filtered_count": len(result) - len(validated_results),
                    **(audit_context or {})
                },
                success=True
            )
            
            return validated_results
            
        except TenantIsolationError:
            # Log failed operation
            audit_logger.log_tenant_operation(
                operation="dynamodb_query_resources_denied",
                tenant_id=getattr(query, 'tenantId', 'unknown'),
                user_id=claims.sub,
                details={
                    "operation_type": "query_resources",
                    "reason": "tenant_isolation_violation",
                    **(audit_context or {})
                },
                success=False
            )
            raise
        except Exception as e:
            # Log unexpected error
            audit_logger.log_tenant_operation(
                operation="dynamodb_query_resources_error",
                tenant_id=getattr(query, 'tenantId', 'unknown'),
                user_id=claims.sub,
                details={
                    "operation_type": "query_resources",
                    "error": str(e),
                    **(audit_context or {})
                },
                success=False
            )
            raise
    
    async def delete_resource(
        self,
        tenant_id: str,
        session_id: str,
        resource_id: str,
        claims: JWTClaims,
        audit_context: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Securely delete a UI resource with tenant validation
        
        Args:
            tenant_id: Tenant identifier
            session_id: Session identifier
            resource_id: Resource identifier
            claims: JWT claims for authorization
            audit_context: Additional audit context
            
        Returns:
            True if resource was deleted
            
        Raises:
            TenantIsolationError: If tenant validation fails
        """
        try:
            # Build partition key
            partition_key = f"{tenant_id}#{session_id}"
            
            # Validate tenant access
            self.validator.validate_delete_operation(partition_key, resource_id, claims, "delete_resource")
            
            # Execute operation
            result = await self.operations.delete_resource(tenant_id, session_id, resource_id)
            
            # Log successful operation
            audit_logger.log_tenant_operation(
                operation="dynamodb_delete_resource",
                tenant_id=tenant_id,
                user_id=claims.sub,
                resource_id=resource_id,
                details={
                    "operation_type": "delete_resource",
                    "deleted": result,
                    **(audit_context or {})
                },
                success=True
            )
            
            return result
            
        except TenantIsolationError:
            # Log failed operation
            audit_logger.log_tenant_operation(
                operation="dynamodb_delete_resource_denied",
                tenant_id=tenant_id,
                user_id=claims.sub,
                resource_id=resource_id,
                details={
                    "operation_type": "delete_resource",
                    "reason": "tenant_isolation_violation",
                    **(audit_context or {})
                },
                success=False
            )
            raise
        except Exception as e:
            # Log unexpected error
            audit_logger.log_tenant_operation(
                operation="dynamodb_delete_resource_error",
                tenant_id=tenant_id,
                user_id=claims.sub,
                resource_id=resource_id,
                details={
                    "operation_type": "delete_resource",
                    "error": str(e),
                    **(audit_context or {})
                },
                success=False
            )
            raise
    
    async def batch_get_resources(
        self,
        keys: List[Dict[str, str]],
        claims: JWTClaims,
        audit_context: Optional[Dict[str, Any]] = None
    ) -> List[Any]:
        """
        Securely batch get resources with tenant validation
        
        Args:
            keys: List of key dictionaries with PK and SK
            claims: JWT claims for authorization
            audit_context: Additional audit context
            
        Returns:
            List of retrieved resources
            
        Raises:
            TenantIsolationError: If any key violates tenant isolation
        """
        try:
            # Validate all keys
            self.validator.validate_batch_operation(keys, claims, "batch_get")
            
            # Execute operation
            result = await self.operations.batch_get_resources(keys)
            
            # Log successful operation
            audit_logger.log_tenant_operation(
                operation="dynamodb_batch_get_resources",
                tenant_id="multiple",  # Multiple tenants possible
                user_id=claims.sub,
                details={
                    "operation_type": "batch_get_resources",
                    "key_count": len(keys),
                    "result_count": len(result),
                    **(audit_context or {})
                },
                success=True
            )
            
            return result
            
        except TenantIsolationError:
            # Log failed operation
            audit_logger.log_tenant_operation(
                operation="dynamodb_batch_get_resources_denied",
                tenant_id="multiple",
                user_id=claims.sub,
                details={
                    "operation_type": "batch_get_resources",
                    "reason": "tenant_isolation_violation",
                    "key_count": len(keys),
                    **(audit_context or {})
                },
                success=False
            )
            raise
        except Exception as e:
            # Log unexpected error
            audit_logger.log_tenant_operation(
                operation="dynamodb_batch_get_resources_error",
                tenant_id="multiple",
                user_id=claims.sub,
                details={
                    "operation_type": "batch_get_resources",
                    "error": str(e),
                    "key_count": len(keys),
                    **(audit_context or {})
                },
                success=False
            )
            raise
    
    async def scan_resources_with_tenant_filter(
        self,
        claims: JWTClaims,
        additional_filter: Optional[str] = None,
        audit_context: Optional[Dict[str, Any]] = None
    ) -> List[Any]:
        """
        Securely scan resources with mandatory tenant filtering
        
        Args:
            claims: JWT claims for authorization
            additional_filter: Additional filter expression
            audit_context: Additional audit context
            
        Returns:
            List of resources accessible to the user
            
        Raises:
            TenantIsolationError: If scan is not allowed
        """
        try:
            # Get tenant filter from validator
            tenant_filter = self.validator.validate_scan_operation(
                additional_filter, claims, "scan_resources"
            )
            
            # Execute scan with tenant filter
            result = await self.operations.scan_resources_with_filter(
                filter_expression=tenant_filter.get("FilterExpression"),
                expression_attribute_values=tenant_filter.get("ExpressionAttributeValues", {})
            )
            
            # Log successful operation
            accessible_tenants = tenant_isolation_service.get_accessible_tenants(claims)
            audit_logger.log_tenant_operation(
                operation="dynamodb_scan_resources",
                tenant_id="multiple",
                user_id=claims.sub,
                details={
                    "operation_type": "scan_resources",
                    "accessible_tenants": accessible_tenants,
                    "result_count": len(result),
                    "has_additional_filter": additional_filter is not None,
                    **(audit_context or {})
                },
                success=True
            )
            
            return result
            
        except TenantIsolationError:
            # Log failed operation
            audit_logger.log_tenant_operation(
                operation="dynamodb_scan_resources_denied",
                tenant_id="multiple",
                user_id=claims.sub,
                details={
                    "operation_type": "scan_resources",
                    "reason": "tenant_isolation_violation",
                    **(audit_context or {})
                },
                success=False
            )
            raise
        except Exception as e:
            # Log unexpected error
            audit_logger.log_tenant_operation(
                operation="dynamodb_scan_resources_error",
                tenant_id="multiple",
                user_id=claims.sub,
                details={
                    "operation_type": "scan_resources",
                    "error": str(e),
                    **(audit_context or {})
                },
                success=False
            )
            raise
    
    def get_validator(self) -> Any:
        """Get the tenant validator instance"""
        return self.validator
    
    def enable_tenant_validation(self):
        """Enable tenant validation"""
        self.validator.enable_validation()
    
    def disable_tenant_validation(self):
        """Disable tenant validation (for testing only)"""
        self.validator.disable_validation()


# Factory function to create secure operations
def create_secure_dynamodb_operations(client: DynamoDBClient) -> SecureDynamoDBOperations:
    """Create secure DynamoDB operations with tenant validation"""
    return SecureDynamoDBOperations(client)