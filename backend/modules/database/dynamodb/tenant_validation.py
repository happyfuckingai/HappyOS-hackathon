"""
DynamoDB Tenant Validation Module

Provides comprehensive tenant validation for all DynamoDB operations
to ensure complete row-level security and prevent cross-tenant data access.

Requirements: 6.1, 6.2, 6.3
"""

import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, timezone

from ..auth.jwt_service import JWTClaims
from ..auth.tenant_isolation import (
    TenantIsolationError, CrossTenantAccessError, 
    DynamoDBTenantIsolation, tenant_isolation_service
)

logger = logging.getLogger(__name__)


class DynamoDBTenantValidator:
    """
    Validates all DynamoDB operations for tenant isolation
    
    Ensures that:
    - All partition keys contain valid tenant IDs
    - Users can only access their authorized tenants
    - Cross-tenant queries are blocked
    - Audit logs are generated for all access attempts
    """
    
    def __init__(self):
        self._validation_enabled = True
    
    def validate_put_operation(
        self,
        item: Dict[str, Any],
        claims: JWTClaims,
        operation_context: str = "put_item"
    ) -> bool:
        """
        Validate PUT operation for tenant isolation
        
        Args:
            item: DynamoDB item being stored
            claims: JWT claims for authorization
            operation_context: Context for audit logging
            
        Returns:
            True if operation is allowed
            
        Raises:
            TenantIsolationError: If tenant validation fails
        """
        if not self._validation_enabled:
            return True
        
        # Extract partition key
        partition_key = item.get("PK")
        if not partition_key:
            raise TenantIsolationError(
                "Missing partition key in DynamoDB item",
                "unknown",
                claims.sub
            )
        
        # Extract tenant from partition key
        tenant_id = DynamoDBTenantIsolation.extract_tenant_from_partition_key(partition_key)
        if not tenant_id:
            raise TenantIsolationError(
                f"Invalid partition key format: {partition_key}",
                "unknown",
                claims.sub
            )
        
        # Validate tenant access
        try:
            tenant_isolation_service.validate_tenant_access(
                claims=claims,
                requested_tenant=tenant_id,
                session_id="*",  # Session is embedded in partition key
                operation="write",
                resource_id=item.get("SK"),
                ip_address=None,
                user_agent=None
            )
            
            logger.debug(f"DynamoDB PUT validated for tenant {tenant_id} by user {claims.sub}")
            return True
            
        except (TenantIsolationError, CrossTenantAccessError) as e:
            logger.warning(
                f"DynamoDB PUT blocked for user {claims.sub}: {e} "
                f"(partition_key: {partition_key})"
            )
            raise
    
    def validate_get_operation(
        self,
        partition_key: str,
        sort_key: Optional[str],
        claims: JWTClaims,
        operation_context: str = "get_item"
    ) -> bool:
        """
        Validate GET operation for tenant isolation
        
        Args:
            partition_key: DynamoDB partition key
            sort_key: DynamoDB sort key (optional)
            claims: JWT claims for authorization
            operation_context: Context for audit logging
            
        Returns:
            True if operation is allowed
            
        Raises:
            TenantIsolationError: If tenant validation fails
        """
        if not self._validation_enabled:
            return True
        
        # Extract tenant from partition key
        tenant_id = DynamoDBTenantIsolation.extract_tenant_from_partition_key(partition_key)
        if not tenant_id:
            raise TenantIsolationError(
                f"Invalid partition key format: {partition_key}",
                "unknown",
                claims.sub
            )
        
        # Validate tenant access
        try:
            tenant_isolation_service.validate_tenant_access(
                claims=claims,
                requested_tenant=tenant_id,
                session_id="*",  # Session is embedded in partition key
                operation="read",
                resource_id=sort_key,
                ip_address=None,
                user_agent=None
            )
            
            logger.debug(f"DynamoDB GET validated for tenant {tenant_id} by user {claims.sub}")
            return True
            
        except (TenantIsolationError, CrossTenantAccessError) as e:
            logger.warning(
                f"DynamoDB GET blocked for user {claims.sub}: {e} "
                f"(partition_key: {partition_key})"
            )
            raise
    
    def validate_query_operation(
        self,
        key_condition_expression: str,
        filter_expression: Optional[str],
        claims: JWTClaims,
        operation_context: str = "query"
    ) -> bool:
        """
        Validate QUERY operation for tenant isolation
        
        Args:
            key_condition_expression: DynamoDB key condition
            filter_expression: Optional filter expression
            claims: JWT claims for authorization
            operation_context: Context for audit logging
            
        Returns:
            True if operation is allowed
            
        Raises:
            TenantIsolationError: If tenant validation fails
        """
        if not self._validation_enabled:
            return True
        
        # Extract tenant from key condition (simplified parsing)
        # In production, use proper DynamoDB expression parser
        tenant_id = self._extract_tenant_from_key_condition(key_condition_expression)
        
        if not tenant_id:
            raise TenantIsolationError(
                f"Cannot determine tenant from key condition: {key_condition_expression}",
                "unknown",
                claims.sub
            )
        
        # Validate tenant access
        try:
            tenant_isolation_service.validate_tenant_access(
                claims=claims,
                requested_tenant=tenant_id,
                session_id="*",
                operation="read",
                resource_id=None,
                ip_address=None,
                user_agent=None
            )
            
            logger.debug(f"DynamoDB QUERY validated for tenant {tenant_id} by user {claims.sub}")
            return True
            
        except (TenantIsolationError, CrossTenantAccessError) as e:
            logger.warning(
                f"DynamoDB QUERY blocked for user {claims.sub}: {e} "
                f"(key_condition: {key_condition_expression})"
            )
            raise
    
    def validate_scan_operation(
        self,
        filter_expression: Optional[str],
        claims: JWTClaims,
        operation_context: str = "scan"
    ) -> Dict[str, Any]:
        """
        Validate SCAN operation and add tenant filter
        
        SCAN operations are restricted and must include tenant filtering
        
        Args:
            filter_expression: Optional existing filter expression
            claims: JWT claims for authorization
            operation_context: Context for audit logging
            
        Returns:
            Dictionary with required filter expression components
            
        Raises:
            TenantIsolationError: If scan is not allowed
        """
        if not self._validation_enabled:
            return {}
        
        # Get accessible tenants for user
        accessible_tenants = tenant_isolation_service.get_accessible_tenants(claims)
        
        if not accessible_tenants:
            raise TenantIsolationError(
                "No accessible tenants for scan operation",
                "unknown",
                claims.sub
            )
        
        # Build tenant filter expression
        if len(accessible_tenants) == 1:
            tenant_id = accessible_tenants[0]
            tenant_filter = {
                "FilterExpression": "begins_with(PK, :tenant_prefix)",
                "ExpressionAttributeValues": {
                    ":tenant_prefix": f"{tenant_id}#"
                }
            }
        else:
            # Multiple tenants - build OR condition
            filter_conditions = []
            expression_values = {}
            
            for i, tenant_id in enumerate(accessible_tenants):
                filter_conditions.append(f"begins_with(PK, :tenant_prefix_{i})")
                expression_values[f":tenant_prefix_{i}"] = f"{tenant_id}#"
            
            tenant_filter = {
                "FilterExpression": " OR ".join(filter_conditions),
                "ExpressionAttributeValues": expression_values
            }
        
        # Combine with existing filter if present
        if filter_expression:
            tenant_filter["FilterExpression"] = f"({tenant_filter['FilterExpression']}) AND ({filter_expression})"
        
        logger.info(
            f"DynamoDB SCAN validated with tenant filter for user {claims.sub} "
            f"(accessible_tenants: {accessible_tenants})"
        )
        
        return tenant_filter
    
    def validate_delete_operation(
        self,
        partition_key: str,
        sort_key: Optional[str],
        claims: JWTClaims,
        operation_context: str = "delete_item"
    ) -> bool:
        """
        Validate DELETE operation for tenant isolation
        
        Args:
            partition_key: DynamoDB partition key
            sort_key: DynamoDB sort key (optional)
            claims: JWT claims for authorization
            operation_context: Context for audit logging
            
        Returns:
            True if operation is allowed
            
        Raises:
            TenantIsolationError: If tenant validation fails
        """
        if not self._validation_enabled:
            return True
        
        # Extract tenant from partition key
        tenant_id = DynamoDBTenantIsolation.extract_tenant_from_partition_key(partition_key)
        if not tenant_id:
            raise TenantIsolationError(
                f"Invalid partition key format: {partition_key}",
                "unknown",
                claims.sub
            )
        
        # Validate tenant access
        try:
            tenant_isolation_service.validate_tenant_access(
                claims=claims,
                requested_tenant=tenant_id,
                session_id="*",
                operation="write",
                resource_id=sort_key,
                ip_address=None,
                user_agent=None
            )
            
            logger.debug(f"DynamoDB DELETE validated for tenant {tenant_id} by user {claims.sub}")
            return True
            
        except (TenantIsolationError, CrossTenantAccessError) as e:
            logger.warning(
                f"DynamoDB DELETE blocked for user {claims.sub}: {e} "
                f"(partition_key: {partition_key})"
            )
            raise
    
    def validate_batch_operation(
        self,
        items: List[Dict[str, Any]],
        claims: JWTClaims,
        operation_type: str = "batch_write"
    ) -> bool:
        """
        Validate batch operation for tenant isolation
        
        Args:
            items: List of DynamoDB items
            claims: JWT claims for authorization
            operation_type: Type of batch operation
            
        Returns:
            True if all items are allowed
            
        Raises:
            TenantIsolationError: If any item violates tenant isolation
        """
        if not self._validation_enabled:
            return True
        
        for i, item in enumerate(items):
            try:
                if operation_type == "batch_write":
                    self.validate_put_operation(item, claims, f"batch_write_item_{i}")
                elif operation_type == "batch_get":
                    partition_key = item.get("PK")
                    sort_key = item.get("SK")
                    self.validate_get_operation(partition_key, sort_key, claims, f"batch_get_item_{i}")
                else:
                    raise TenantIsolationError(
                        f"Unknown batch operation type: {operation_type}",
                        "unknown",
                        claims.sub
                    )
            except (TenantIsolationError, CrossTenantAccessError) as e:
                logger.error(f"Batch operation item {i} failed validation: {e}")
                raise TenantIsolationError(
                    f"Batch operation failed at item {i}: {str(e)}",
                    getattr(e, 'tenant_id', 'unknown'),
                    claims.sub
                )
        
        logger.debug(f"DynamoDB batch operation validated for user {claims.sub} ({len(items)} items)")
        return True
    
    def _extract_tenant_from_key_condition(self, key_condition: str) -> Optional[str]:
        """
        Extract tenant ID from DynamoDB key condition expression
        
        This is a simplified implementation. In production, use a proper
        DynamoDB expression parser.
        
        Args:
            key_condition: Key condition expression
            
        Returns:
            Tenant ID if found, None otherwise
        """
        import re
        
        # Look for patterns like: PK = :pk_value or PK = 'tenant#session'
        patterns = [
            r"PK\s*=\s*['\"]([^#]+)#",  # Direct string value
            r"PK\s*=\s*:(\w+)",         # Parameter reference
        ]
        
        for pattern in patterns:
            match = re.search(pattern, key_condition, re.IGNORECASE)
            if match:
                value = match.group(1)
                # If it's a parameter reference, we can't extract the tenant here
                # In production, this would need access to expression attribute values
                if not value.startswith(':'):
                    return value
        
        return None
    
    def enable_validation(self):
        """Enable tenant validation"""
        self._validation_enabled = True
        logger.info("DynamoDB tenant validation enabled")
    
    def disable_validation(self):
        """Disable tenant validation (for testing only)"""
        self._validation_enabled = False
        logger.warning("DynamoDB tenant validation DISABLED")
    
    def is_validation_enabled(self) -> bool:
        """Check if validation is enabled"""
        return self._validation_enabled


# Global validator instance
dynamodb_tenant_validator = DynamoDBTenantValidator()