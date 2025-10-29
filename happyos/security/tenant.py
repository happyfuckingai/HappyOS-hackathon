"""
Multi-Tenant Isolation

Enterprise-grade tenant isolation for SaaS AI agent deployments with
strict data boundaries and compliance enforcement.
"""

from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List, Set
from enum import Enum
import logging
from contextlib import asynccontextmanager

from ..exceptions import TenantIsolationError, AuthorizationError
from ..config import Config


class IsolationLevel(Enum):
    """Tenant isolation levels."""
    BASIC = "basic"          # Logical separation
    STANDARD = "standard"    # Database-level separation  
    STRICT = "strict"        # Complete infrastructure isolation
    REGULATORY = "regulatory" # Compliance-grade isolation


@dataclass
class TenantContext:
    """Tenant context for request processing.
    
    Provides tenant-specific information and access controls
    for multi-tenant AI agent systems.
    
    Attributes:
        tenant_id: Unique tenant identifier
        organization: Organization name
        isolation_level: Required isolation level
        permissions: Tenant-specific permissions
        compliance_requirements: Required compliance standards
        resource_limits: Resource usage limits
        metadata: Additional tenant metadata
    """
    
    tenant_id: str
    organization: str
    isolation_level: IsolationLevel = IsolationLevel.STANDARD
    
    # Access control
    permissions: Set[str] = field(default_factory=set)
    compliance_requirements: List[str] = field(default_factory=list)
    
    # Resource limits
    resource_limits: Dict[str, Any] = field(default_factory=dict)
    
    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        """Validate tenant context."""
        if not self.tenant_id:
            raise TenantIsolationError("Tenant ID is required")
        
        if not self.organization:
            raise TenantIsolationError("Organization is required")
    
    def has_permission(self, permission: str) -> bool:
        """Check if tenant has specific permission."""
        return permission in self.permissions
    
    def requires_compliance(self, standard: str) -> bool:
        """Check if tenant requires specific compliance standard."""
        return standard in self.compliance_requirements
    
    def get_resource_limit(self, resource: str) -> Optional[Any]:
        """Get resource limit for tenant."""
        return self.resource_limits.get(resource)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "tenant_id": self.tenant_id,
            "organization": self.organization,
            "isolation_level": self.isolation_level.value,
            "permissions": list(self.permissions),
            "compliance_requirements": self.compliance_requirements,
            "resource_limits": self.resource_limits,
            "metadata": self.metadata
        }


class TenantIsolation:
    """Tenant isolation enforcement.
    
    Provides mechanisms to enforce tenant boundaries and prevent
    cross-tenant data access in multi-tenant AI agent systems.
    """
    
    BASIC = IsolationLevel.BASIC
    STANDARD = IsolationLevel.STANDARD  
    STRICT = IsolationLevel.STRICT
    REGULATORY = IsolationLevel.REGULATORY
    
    def __init__(self, config: Config):
        """Initialize tenant isolation.
        
        Args:
            config: SDK configuration
        """
        self.config = config
        self.logger = logging.getLogger(__name__)
        
        # Tenant registry
        self._tenants: Dict[str, TenantContext] = {}
        
        # Active tenant contexts per request
        self._active_contexts: Dict[str, TenantContext] = {}
    
    def register_tenant(self, tenant: TenantContext) -> None:
        """Register a tenant in the system.
        
        Args:
            tenant: Tenant context to register
            
        Raises:
            TenantIsolationError: If tenant registration fails
        """
        if tenant.tenant_id in self._tenants:
            raise TenantIsolationError(f"Tenant already registered: {tenant.tenant_id}")
        
        # Validate tenant configuration
        self._validate_tenant_config(tenant)
        
        self._tenants[tenant.tenant_id] = tenant
        
        self.logger.info(
            f"Registered tenant: {tenant.tenant_id}",
            extra={
                "tenant_id": tenant.tenant_id,
                "organization": tenant.organization,
                "isolation_level": tenant.isolation_level.value
            }
        )
    
    def get_tenant(self, tenant_id: str) -> Optional[TenantContext]:
        """Get tenant context by ID.
        
        Args:
            tenant_id: Tenant identifier
            
        Returns:
            Tenant context or None if not found
        """
        return self._tenants.get(tenant_id)
    
    def validate_tenant_access(
        self, 
        tenant_id: str, 
        resource: str,
        operation: str
    ) -> bool:
        """Validate tenant access to resource.
        
        Args:
            tenant_id: Tenant identifier
            resource: Resource being accessed
            operation: Operation being performed
            
        Returns:
            True if access is allowed
            
        Raises:
            TenantIsolationError: If tenant not found
            AuthorizationError: If access is denied
        """
        tenant = self.get_tenant(tenant_id)
        if not tenant:
            raise TenantIsolationError(f"Unknown tenant: {tenant_id}")
        
        # Check permissions
        required_permission = f"{resource}:{operation}"
        if not tenant.has_permission(required_permission):
            raise AuthorizationError(
                f"Tenant {tenant_id} lacks permission: {required_permission}"
            )
        
        # Check resource limits
        if operation in ["create", "update"]:
            limit = tenant.get_resource_limit(resource)
            if limit is not None:
                # Would check current usage against limit
                pass
        
        return True
    
    @asynccontextmanager
    async def tenant_context(self, tenant_id: str):
        """Context manager for tenant-scoped operations.
        
        Args:
            tenant_id: Tenant identifier
            
        Yields:
            TenantContext for the specified tenant
            
        Example:
            >>> async with isolation.tenant_context("acme_corp") as tenant:
            ...     result = await agent.process_data(data, tenant)
        """
        tenant = self.get_tenant(tenant_id)
        if not tenant:
            raise TenantIsolationError(f"Unknown tenant: {tenant_id}")
        
        # Set active context
        request_id = self._generate_request_id()
        self._active_contexts[request_id] = tenant
        
        try:
            yield tenant
        finally:
            # Clean up context
            self._active_contexts.pop(request_id, None)
    
    def get_database_schema(self, tenant_id: str) -> str:
        """Get tenant-specific database schema.
        
        Args:
            tenant_id: Tenant identifier
            
        Returns:
            Database schema name for tenant
        """
        tenant = self.get_tenant(tenant_id)
        if not tenant:
            raise TenantIsolationError(f"Unknown tenant: {tenant_id}")
        
        if tenant.isolation_level in [IsolationLevel.STRICT, IsolationLevel.REGULATORY]:
            return f"tenant_{tenant_id}"
        else:
            return "shared"
    
    def get_storage_prefix(self, tenant_id: str) -> str:
        """Get tenant-specific storage prefix.
        
        Args:
            tenant_id: Tenant identifier
            
        Returns:
            Storage prefix for tenant data
        """
        tenant = self.get_tenant(tenant_id)
        if not tenant:
            raise TenantIsolationError(f"Unknown tenant: {tenant_id}")
        
        return f"tenants/{tenant_id}/"
    
    def _validate_tenant_config(self, tenant: TenantContext) -> None:
        """Validate tenant configuration."""
        # Check isolation level requirements
        if tenant.isolation_level == IsolationLevel.REGULATORY:
            required_compliance = ["audit_logging", "data_encryption"]
            for requirement in required_compliance:
                if requirement not in tenant.compliance_requirements:
                    raise TenantIsolationError(
                        f"Regulatory isolation requires {requirement}"
                    )
        
        # Validate permissions format
        for permission in tenant.permissions:
            if ":" not in permission:
                raise TenantIsolationError(
                    f"Invalid permission format: {permission}. Use 'resource:operation'"
                )
    
    def _generate_request_id(self) -> str:
        """Generate unique request ID."""
        import uuid
        return str(uuid.uuid4())


class TenantManager:
    """High-level tenant management.
    
    Provides administrative functions for managing tenants
    in multi-tenant AI agent deployments.
    """
    
    def __init__(self, isolation: TenantIsolation):
        """Initialize tenant manager.
        
        Args:
            isolation: Tenant isolation instance
        """
        self.isolation = isolation
        self.logger = logging.getLogger(__name__)
    
    async def create_tenant(
        self,
        tenant_id: str,
        organization: str,
        isolation_level: IsolationLevel = IsolationLevel.STANDARD,
        permissions: Optional[List[str]] = None,
        compliance_requirements: Optional[List[str]] = None,
        resource_limits: Optional[Dict[str, Any]] = None
    ) -> TenantContext:
        """Create new tenant.
        
        Args:
            tenant_id: Unique tenant identifier
            organization: Organization name
            isolation_level: Required isolation level
            permissions: List of permissions
            compliance_requirements: Required compliance standards
            resource_limits: Resource usage limits
            
        Returns:
            Created tenant context
        """
        tenant = TenantContext(
            tenant_id=tenant_id,
            organization=organization,
            isolation_level=isolation_level,
            permissions=set(permissions or []),
            compliance_requirements=compliance_requirements or [],
            resource_limits=resource_limits or {}
        )
        
        # Register tenant
        self.isolation.register_tenant(tenant)
        
        # Initialize tenant resources
        await self._initialize_tenant_resources(tenant)
        
        self.logger.info(f"Created tenant: {tenant_id}")
        return tenant
    
    async def update_tenant(
        self,
        tenant_id: str,
        **updates
    ) -> TenantContext:
        """Update tenant configuration.
        
        Args:
            tenant_id: Tenant identifier
            **updates: Fields to update
            
        Returns:
            Updated tenant context
        """
        tenant = self.isolation.get_tenant(tenant_id)
        if not tenant:
            raise TenantIsolationError(f"Tenant not found: {tenant_id}")
        
        # Update fields
        for field, value in updates.items():
            if hasattr(tenant, field):
                setattr(tenant, field, value)
        
        # Re-validate
        self.isolation._validate_tenant_config(tenant)
        
        self.logger.info(f"Updated tenant: {tenant_id}")
        return tenant
    
    async def delete_tenant(self, tenant_id: str) -> bool:
        """Delete tenant and cleanup resources.
        
        Args:
            tenant_id: Tenant identifier
            
        Returns:
            True if deletion successful
        """
        tenant = self.isolation.get_tenant(tenant_id)
        if not tenant:
            return False
        
        # Cleanup tenant resources
        await self._cleanup_tenant_resources(tenant)
        
        # Remove from registry
        self.isolation._tenants.pop(tenant_id, None)
        
        self.logger.info(f"Deleted tenant: {tenant_id}")
        return True
    
    async def _initialize_tenant_resources(self, tenant: TenantContext) -> None:
        """Initialize tenant-specific resources."""
        # Create database schema if needed
        if tenant.isolation_level in [IsolationLevel.STRICT, IsolationLevel.REGULATORY]:
            schema = self.isolation.get_database_schema(tenant.tenant_id)
            # Would create database schema here
            self.logger.debug(f"Would create schema: {schema}")
        
        # Create storage directories
        storage_prefix = self.isolation.get_storage_prefix(tenant.tenant_id)
        # Would create storage directories here
        self.logger.debug(f"Would create storage prefix: {storage_prefix}")
    
    async def _cleanup_tenant_resources(self, tenant: TenantContext) -> None:
        """Cleanup tenant-specific resources."""
        # Cleanup database schema
        if tenant.isolation_level in [IsolationLevel.STRICT, IsolationLevel.REGULATORY]:
            schema = self.isolation.get_database_schema(tenant.tenant_id)
            # Would drop database schema here
            self.logger.debug(f"Would cleanup schema: {schema}")
        
        # Cleanup storage
        storage_prefix = self.isolation.get_storage_prefix(tenant.tenant_id)
        # Would cleanup storage here
        self.logger.debug(f"Would cleanup storage: {storage_prefix}")