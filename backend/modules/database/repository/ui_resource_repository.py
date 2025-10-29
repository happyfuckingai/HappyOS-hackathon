"""
UI Resource Repository - High-level data access layer
"""

import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any, Tuple

import jsonpatch

from ..dynamodb import DynamoDBClient, DynamoDBOperations, dynamodb_client
from ..dynamodb.secure_operations import SecureDynamoDBOperations, create_secure_dynamodb_operations
from ..dynamodb.performance_optimizations import PerformanceOptimizedOperations
from ..s3 import S3Client, SnapshotManager, AuditLogManager, s3_client
from ...models.ui_resource import (
    UIResource, UIResourceCreate, UIResourceQuery,
    ui_resource_validator
)
from .exceptions import (
    UIResourceRepositoryError,
    ResourceNotFoundError,
    ResourceConflictError
)
from ...auth.tenant_isolation import TenantIsolationError, DynamoDBTenantIsolation
from ...auth.jwt_service import JWTClaims

logger = logging.getLogger(__name__)


class UIResourceRepository:
    """
    High-level data access layer for UI resources
    
    Provides:
    - CRUD operations with proper error handling
    - Batch operations for efficiency
    - Query optimization for common access patterns
    - Tenant isolation enforcement
    - Revision management and conflict resolution
    - Idempotency key handling
    """
    
    def __init__(
        self, 
        dynamodb_client: DynamoDBClient = None,
        s3_client: S3Client = None
    ):
        self.db_client = dynamodb_client or dynamodb_client
        self.s3_client = s3_client or s3_client
        self.db_ops = DynamoDBOperations(self.db_client)
        self.optimized_db_ops = PerformanceOptimizedOperations(self.db_client)
        self.secure_db_ops = create_secure_dynamodb_operations(self.db_client)
        self.snapshot_manager = None
        self.audit_manager = None
        self._revision_counters: Dict[str, int] = {}
    
    async def initialize(self):
        """Initialize the repository and underlying clients"""
        await self.db_client.initialize()
        await self.s3_client.initialize()
        
        # Initialize S3 managers
        self.snapshot_manager = SnapshotManager(self.s3_client.s3)
        self.audit_manager = AuditLogManager(self.s3_client.s3)
        
        logger.info("UI Resource Repository initialized")
    
    def _get_next_revision(self, resource_id: str) -> int:
        """Get next revision number for a resource"""
        current = self._revision_counters.get(resource_id, 0)
        next_revision = current + 1
        self._revision_counters[resource_id] = next_revision
        return next_revision
    
    def _validate_tenant_access(self, resource: UIResource, tenant_id: str) -> None:
        """Validate that the resource belongs to the specified tenant"""
        if resource.tenantId != tenant_id:
            raise TenantIsolationError(
                f"Resource {resource.id} belongs to tenant {resource.tenantId}, "
                f"not {tenant_id}",
                resource.tenantId,
                "repository"
            )
    
    async def create_resource(
        self,
        resource_create: UIResourceCreate,
        tenant_id: str,
        claims: JWTClaims,
        idempotency_check: bool = True
    ) -> UIResource:
        """Create a new UI resource with validation and idempotency checking"""
        try:
            # Validate tenant access
            if resource_create.tenantId != tenant_id:
                raise TenantIsolationError(
                    f"Cannot create resource for tenant {resource_create.tenantId} "
                    f"when authenticated as {tenant_id}",
                    resource_create.tenantId,
                    "repository"
                )
            
            # Convert to full UIResource
            resource = resource_create.to_ui_resource()
            
            # Set revision
            resource.revision = self._get_next_revision(resource.id)
            
            # Set timestamps
            now = datetime.now(timezone.utc).isoformat()
            resource.createdAt = now
            resource.updatedAt = now
            
            # Comprehensive JSON schema validation
            resource_data = resource.model_dump()
            ui_resource_validator.validate(resource_data, resource.version)
            
            # Additional payload validation by type
            ui_resource_validator.validate_payload_by_type(
                resource_data['payload'], 
                resource.type, 
                resource.version
            )
            
            # Store in database with tenant validation
            stored_resource = await self.secure_db_ops.put_resource(
                resource, 
                claims,
                audit_context={"idempotency_check": idempotency_check}
            )
            
            logger.info(f"Created resource: {resource.id} (revision {resource.revision})")
            return stored_resource
            
        except TenantIsolationError:
            raise
        except Exception as e:
            logger.error(f"Failed to create resource: {e}")
            raise UIResourceRepositoryError(f"Resource creation failed: {str(e)}")
    
    async def get_resource(
        self,
        resource_id: str,
        tenant_id: str,
        session_id: str,
        claims: JWTClaims,
        include_expired: bool = False
    ) -> Optional[UIResource]:
        """Get a UI resource by ID with tenant isolation"""
        try:
            # Use secure operations with tenant validation
            resource = await self.secure_db_ops.get_resource(
                tenant_id, session_id, resource_id, claims
            )
            
            if not resource:
                return None
            
            # Check expiry
            if not include_expired and resource.is_expired():
                logger.debug(f"Resource {resource_id} has expired")
                return None
            
            return resource
            
        except TenantIsolationError:
            raise
        except Exception as e:
            logger.error(f"Failed to get resource {resource_id}: {e}")
            raise UIResourceRepositoryError(f"Resource retrieval failed: {str(e)}")
    
    async def update_resource(
        self,
        resource_id: str,
        updated_resource: UIResource,
        tenant_id: str,
        claims: JWTClaims,
        expected_revision: Optional[int] = None
    ) -> UIResource:
        """Update an existing UI resource with comprehensive validation"""
        try:
            # Validate tenant access
            if updated_resource.tenantId != tenant_id:
                raise TenantIsolationError(
                    f"Cannot update resource for tenant {updated_resource.tenantId} "
                    f"when authenticated as {tenant_id}",
                    updated_resource.tenantId,
                    "repository"
                )
            
            # Validate resource ID matches
            if updated_resource.id != resource_id:
                raise ResourceConflictError(f"Resource ID mismatch: {resource_id} != {updated_resource.id}")
            
            # Comprehensive JSON schema validation
            resource_data = updated_resource.model_dump()
            ui_resource_validator.validate(resource_data, updated_resource.version)
            
            # Additional payload validation by type
            ui_resource_validator.validate_payload_by_type(
                resource_data['payload'], 
                updated_resource.type, 
                updated_resource.version
            )
            
            # Update revision
            updated_resource.revision = self._get_next_revision(resource_id)
            updated_resource.updatedAt = datetime.now(timezone.utc).isoformat()
            
            # Store updated resource with tenant validation
            stored_resource = await self.secure_db_ops.put_resource(
                updated_resource, 
                claims,
                audit_context={
                    "operation": "update",
                    "expected_revision": expected_revision,
                    "new_revision": updated_resource.revision
                }
            )
            
            logger.info(f"Updated resource: {resource_id} (revision {updated_resource.revision})")
            return stored_resource
            
        except TenantIsolationError:
            raise
        except Exception as e:
            logger.error(f"Failed to update resource {resource_id}: {e}")
            raise UIResourceRepositoryError(f"Resource update failed: {str(e)}")
    
    async def patch_resource(
        self,
        resource_id: str,
        patch_operations: List[Dict[str, Any]],
        tenant_id: str,
        session_id: str,
        claims: JWTClaims,
        expected_revision: Optional[int] = None
    ) -> UIResource:
        """Apply JSON Patch operations to a resource with validation"""
        try:
            # Get existing resource
            existing_resource = await self.get_resource(
                resource_id, tenant_id, session_id, claims, include_expired=False
            )
            
            if not existing_resource:
                raise ResourceNotFoundError(f"Resource not found: {resource_id}")
            
            # Validate patch operations
            self._validate_patch_operations(patch_operations, existing_resource)
            
            # Apply patch operations
            import jsonpatch
            resource_dict = existing_resource.model_dump()
            
            try:
                patch_obj = jsonpatch.JsonPatch(patch_operations)
                patched_dict = patch_obj.apply(resource_dict)
            except jsonpatch.JsonPatchException as e:
                raise ResourceConflictError(f"Invalid patch operation: {e}")
            
            # Preserve protected fields
            patched_dict['id'] = existing_resource.id
            patched_dict['tenantId'] = existing_resource.tenantId
            patched_dict['sessionId'] = existing_resource.sessionId
            patched_dict['agentId'] = existing_resource.agentId
            patched_dict['createdAt'] = existing_resource.createdAt
            
            # Create updated resource
            try:
                updated_resource = UIResource(**patched_dict)
            except Exception as e:
                raise ResourceConflictError(f"Invalid resource after patch: {e}")
            
            # Update using the update method (which includes validation)
            return await self.update_resource(
                resource_id, updated_resource, tenant_id, claims, expected_revision
            )
            
        except (TenantIsolationError, ResourceNotFoundError, ResourceConflictError):
            raise
        except Exception as e:
            logger.error(f"Failed to patch resource {resource_id}: {e}")
            raise UIResourceRepositoryError(f"Resource patch failed: {str(e)}")
    
    def _validate_patch_operations(
        self, 
        patch_operations: List[Dict[str, Any]], 
        current_resource: UIResource
    ) -> None:
        """Validate JSON Patch operations"""
        valid_operations = ['add', 'remove', 'replace', 'move', 'copy', 'test']
        protected_paths = ['/id', '/tenantId', '/sessionId', '/agentId', '/createdAt', '/version']
        
        for i, op in enumerate(patch_operations):
            if not isinstance(op, dict):
                raise ResourceConflictError(f"Patch operation {i} must be a dictionary")
            
            if 'op' not in op:
                raise ResourceConflictError(f"Patch operation {i} missing 'op' field")
            
            if 'path' not in op:
                raise ResourceConflictError(f"Patch operation {i} missing 'path' field")
            
            if op['op'] not in valid_operations:
                raise ResourceConflictError(
                    f"Patch operation {i} has invalid operation '{op['op']}'. "
                    f"Valid operations: {valid_operations}"
                )
            
            path = op['path']
            if not isinstance(path, str) or not path.startswith('/'):
                raise ResourceConflictError(
                    f"Patch operation {i} path must be a string starting with '/'"
                )
            
            # Check for protected field modifications
            for protected_path in protected_paths:
                if path.startswith(protected_path):
                    raise ResourceConflictError(
                        f"Patch operation {i} attempts to modify protected field: {path}"
                    )
        
        # Test apply patch to validate it won't break the resource
        import jsonpatch
        resource_dict = current_resource.model_dump()
        try:
            patch_obj = jsonpatch.JsonPatch(patch_operations)
            patched_dict = patch_obj.apply(resource_dict)
            
            # Validate the patched resource would be valid
            ui_resource_validator.validate(patched_dict, current_resource.version)
            
        except jsonpatch.JsonPatchException as e:
            raise ResourceConflictError(f"Invalid patch operation: {e}")
        except Exception as e:
            raise ResourceConflictError(f"Patch would result in invalid resource: {e}")

    async def query_resources(
        self,
        query: UIResourceQuery,
        tenant_id: str,
        claims: JWTClaims
    ) -> List[UIResource]:
        """Query UI resources with filtering and tenant isolation"""
        try:
            # Validate tenant access
            if query.tenantId and query.tenantId != tenant_id:
                raise TenantIsolationError(
                    f"Cannot query tenant {query.tenantId} when authenticated as {tenant_id}",
                    query.tenantId,
                    "repository"
                )
            
            # Ensure tenant ID is set
            if not query.tenantId:
                query.tenantId = tenant_id
            
            # Execute query with secure operations
            validated_resources = await self.secure_db_ops.query_resources(query, claims)
            
            logger.debug(f"Query returned {len(validated_resources)} resources for tenant {tenant_id}")
            return validated_resources
            
        except TenantIsolationError:
            raise
        except Exception as e:
            logger.error(f"Failed to query resources: {e}")
            raise UIResourceRepositoryError(f"Resource query failed: {str(e)}")
    
    async def create_snapshot(
        self,
        tenant_id: str,
        session_id: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """Create a snapshot of all resources for a session"""
        try:
            # Get all resources for the session
            query = UIResourceQuery(
                tenantId=tenant_id,
                sessionId=session_id,
                includeExpired=False
            )
            resources = await self.query_resources(query, tenant_id)
            
            # Create snapshot
            if self.snapshot_manager:
                return await self.snapshot_manager.create_snapshot(
                    tenant_id, session_id, resources, metadata
                )
            else:
                raise UIResourceRepositoryError("Snapshot manager not initialized")
                
        except Exception as e:
            logger.error(f"Failed to create snapshot: {e}")
            raise UIResourceRepositoryError(f"Snapshot creation failed: {str(e)}")
    
    async def write_audit_log(
        self,
        tenant_id: str,
        log_entries: List[Dict[str, Any]],
        log_type: str = "general"
    ) -> str:
        """Write audit log entries"""
        try:
            if self.audit_manager:
                return await self.audit_manager.write_audit_log(
                    tenant_id, log_entries, log_type
                )
            else:
                raise UIResourceRepositoryError("Audit manager not initialized")
                
        except Exception as e:
            logger.error(f"Failed to write audit log: {e}")
            raise UIResourceRepositoryError(f"Audit log writing failed: {str(e)}")
    
    async def close(self):
        """Close repository and underlying connections"""
        await self.db_client.close()
        await self.s3_client.close()
        self._revision_counters.clear()
        logger.info("UI Resource Repository closed")


# Global repository instance
ui_resource_repository = UIResourceRepository()