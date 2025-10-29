"""
Tenant Isolation Controls

Implements comprehensive tenant isolation with row-level security,
cross-tenant access prevention, and audit logging.

Requirements: 6.1, 6.2, 6.3, 6.5
"""

import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional, Set
from uuid import uuid4

from pydantic import BaseModel, Field

from .jwt_service import JWTClaims, JWTService
from ..config.settings import settings

logger = logging.getLogger(__name__)


class TenantAccessAttempt(BaseModel):
    """Record of tenant access attempt"""
    attempt_id: str = Field(default_factory=lambda: str(uuid4()))
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    user_id: str
    requested_tenant: str
    user_tenant: str
    operation: str
    resource_id: Optional[str] = None
    allowed: bool
    reason: str
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None


class TenantIsolationError(Exception):
    """Raised when tenant isolation is violated"""
    def __init__(self, message: str, tenant_id: str, user_id: str):
        super().__init__(message)
        self.tenant_id = tenant_id
        self.user_id = user_id


class CrossTenantAccessError(TenantIsolationError):
    """Raised when cross-tenant access is attempted"""
    def __init__(self, user_tenant: str, requested_tenant: str, user_id: str):
        message = f"Cross-tenant access denied: user from {user_tenant} attempted to access {requested_tenant}"
        super().__init__(message, requested_tenant, user_id)
        self.user_tenant = user_tenant


class TenantIsolationService:
    """Service for enforcing tenant isolation controls"""
    
    def __init__(self):
        # In-memory storage for demo - in production use database
        self._access_attempts: List[TenantAccessAttempt] = []
        self._blocked_users: Set[str] = set()
        self._tenant_configs = {
            "meetmind": {
                "name": "MeetMind",
                "domain": "meetmind.se",
                "allowed_agents": ["meetmind-summarizer"],
                "isolation_level": "strict"
            },
            "agentsvea": {
                "name": "Agent Svea",
                "domain": "agentsvea.se",
                "allowed_agents": ["agent-svea"],
                "isolation_level": "strict"
            },
            "feliciasfi": {
                "name": "Felicia's Finance",
                "domain": "feliciasfi.com",
                "allowed_agents": ["felicia-core"],
                "isolation_level": "strict"
            }
        }
    
    def validate_tenant_access(
        self,
        claims: JWTClaims,
        requested_tenant: str,
        session_id: str,
        operation: str = "read",
        resource_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> bool:
        """
        Validate tenant access with comprehensive logging
        
        Args:
            claims: JWT claims
            requested_tenant: Tenant being accessed
            session_id: Session identifier
            operation: Operation type (read/write)
            resource_id: Optional resource identifier
            ip_address: Client IP address
            user_agent: Client user agent
            
        Returns:
            True if access is allowed
            
        Raises:
            CrossTenantAccessError: If cross-tenant access is attempted
            TenantIsolationError: If access is denied for other reasons
        """
        user_id = claims.sub
        
        # Check if user is blocked
        if user_id in self._blocked_users:
            self._log_access_attempt(
                user_id, requested_tenant, claims.tenantId or "unknown",
                operation, resource_id, False, "User is blocked",
                ip_address, user_agent
            )
            raise TenantIsolationError("User is blocked", requested_tenant, user_id)
        
        # Validate tenant exists
        if requested_tenant not in self._tenant_configs:
            self._log_access_attempt(
                user_id, requested_tenant, claims.tenantId or "unknown",
                operation, resource_id, False, "Unknown tenant",
                ip_address, user_agent
            )
            raise TenantIsolationError(f"Unknown tenant: {requested_tenant}", requested_tenant, user_id)
        
        # Check JWT tenant claim
        if claims.tenantId and claims.tenantId != requested_tenant:
            self._log_access_attempt(
                user_id, requested_tenant, claims.tenantId,
                operation, resource_id, False, "Cross-tenant access attempt",
                ip_address, user_agent
            )
            raise CrossTenantAccessError(claims.tenantId, requested_tenant, user_id)
        
        # Validate scopes
        required_scope = f"ui:{operation}:{requested_tenant}:{session_id}"
        if not JWTService.verify_scope(claims.scopes, required_scope):
            self._log_access_attempt(
                user_id, requested_tenant, claims.tenantId or "unknown",
                operation, resource_id, False, f"Missing scope: {required_scope}",
                ip_address, user_agent
            )
            raise TenantIsolationError(f"Missing scope: {required_scope}", requested_tenant, user_id)
        
        # Log successful access
        self._log_access_attempt(
            user_id, requested_tenant, claims.tenantId or requested_tenant,
            operation, resource_id, True, "Access granted",
            ip_address, user_agent
        )
        
        return True
    
    def validate_resource_tenant(
        self,
        claims: JWTClaims,
        resource_tenant: str,
        resource_session: str,
        operation: str = "read"
    ) -> bool:
        """
        Validate access to a specific resource's tenant
        
        Args:
            claims: JWT claims
            resource_tenant: Resource's tenant ID
            resource_session: Resource's session ID
            operation: Operation type
            
        Returns:
            True if access is allowed
        """
        return self.validate_tenant_access(
            claims, resource_tenant, resource_session, operation
        )
    
    def get_accessible_tenants(self, claims: JWTClaims) -> List[str]:
        """
        Get list of tenants accessible by the user
        
        Args:
            claims: JWT claims
            
        Returns:
            List of accessible tenant IDs
        """
        accessible_tenants = set()
        
        for scope in claims.scopes:
            parts = scope.split(":")
            if len(parts) >= 3 and parts[0] == "ui":
                tenant_id = parts[2]
                if tenant_id != "*" and tenant_id in self._tenant_configs:
                    accessible_tenants.add(tenant_id)
        
        return list(accessible_tenants)
    
    def check_agent_tenant_access(
        self,
        agent_id: str,
        tenant_id: str
    ) -> bool:
        """
        Check if agent is allowed for tenant
        
        Args:
            agent_id: Agent identifier
            tenant_id: Tenant identifier
            
        Returns:
            True if agent is allowed
        """
        if tenant_id not in self._tenant_configs:
            return False
        
        allowed_agents = self._tenant_configs[tenant_id]["allowed_agents"]
        return agent_id in allowed_agents
    
    def block_user(self, user_id: str, reason: str) -> bool:
        """
        Block user from accessing any tenant
        
        Args:
            user_id: User identifier
            reason: Reason for blocking
            
        Returns:
            True if user was blocked
        """
        self._blocked_users.add(user_id)
        logger.warning(f"Blocked user {user_id}: {reason}")
        return True
    
    def unblock_user(self, user_id: str) -> bool:
        """
        Unblock user
        
        Args:
            user_id: User identifier
            
        Returns:
            True if user was unblocked
        """
        if user_id in self._blocked_users:
            self._blocked_users.remove(user_id)
            logger.info(f"Unblocked user {user_id}")
            return True
        return False
    
    def get_access_attempts(
        self,
        tenant_id: Optional[str] = None,
        user_id: Optional[str] = None,
        failed_only: bool = False,
        limit: int = 100
    ) -> List[TenantAccessAttempt]:
        """
        Get access attempts with filtering
        
        Args:
            tenant_id: Filter by tenant
            user_id: Filter by user
            failed_only: Only return failed attempts
            limit: Maximum number of results
            
        Returns:
            List of access attempts
        """
        attempts = self._access_attempts
        
        # Apply filters
        if tenant_id:
            attempts = [a for a in attempts if a.requested_tenant == tenant_id]
        
        if user_id:
            attempts = [a for a in attempts if a.user_id == user_id]
        
        if failed_only:
            attempts = [a for a in attempts if not a.allowed]
        
        # Sort by timestamp (newest first) and limit
        attempts.sort(key=lambda a: a.timestamp, reverse=True)
        return attempts[:limit]
    
    def get_cross_tenant_attempts(self, limit: int = 50) -> List[TenantAccessAttempt]:
        """
        Get cross-tenant access attempts
        
        Args:
            limit: Maximum number of results
            
        Returns:
            List of cross-tenant access attempts
        """
        cross_tenant_attempts = [
            a for a in self._access_attempts
            if not a.allowed and "cross-tenant" in a.reason.lower()
        ]
        
        cross_tenant_attempts.sort(key=lambda a: a.timestamp, reverse=True)
        return cross_tenant_attempts[:limit]
    
    def get_tenant_stats(self, tenant_id: str) -> Dict:
        """
        Get statistics for a tenant
        
        Args:
            tenant_id: Tenant identifier
            
        Returns:
            Dictionary with tenant statistics
        """
        tenant_attempts = [a for a in self._access_attempts if a.requested_tenant == tenant_id]
        
        return {
            "tenant_id": tenant_id,
            "total_attempts": len(tenant_attempts),
            "successful_attempts": len([a for a in tenant_attempts if a.allowed]),
            "failed_attempts": len([a for a in tenant_attempts if not a.allowed]),
            "unique_users": len(set(a.user_id for a in tenant_attempts)),
            "cross_tenant_attempts": len([
                a for a in tenant_attempts
                if not a.allowed and "cross-tenant" in a.reason.lower()
            ])
        }
    
    def _log_access_attempt(
        self,
        user_id: str,
        requested_tenant: str,
        user_tenant: str,
        operation: str,
        resource_id: Optional[str],
        allowed: bool,
        reason: str,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ):
        """Log access attempt for audit trail"""
        attempt = TenantAccessAttempt(
            user_id=user_id,
            requested_tenant=requested_tenant,
            user_tenant=user_tenant,
            operation=operation,
            resource_id=resource_id,
            allowed=allowed,
            reason=reason,
            ip_address=ip_address,
            user_agent=user_agent
        )
        
        self._access_attempts.append(attempt)
        
        # Keep only recent attempts (last 10000)
        if len(self._access_attempts) > 10000:
            self._access_attempts = self._access_attempts[-10000:]
        
        # Log security events
        if not allowed:
            logger.warning(
                f"Tenant access denied: user={user_id}, tenant={requested_tenant}, "
                f"operation={operation}, reason={reason}, ip={ip_address}"
            )
        else:
            logger.debug(
                f"Tenant access granted: user={user_id}, tenant={requested_tenant}, "
                f"operation={operation}, resource={resource_id}"
            )


class DynamoDBTenantIsolation:
    """DynamoDB-specific tenant isolation utilities"""
    
    @staticmethod
    def build_partition_key(tenant_id: str, session_id: str) -> str:
        """
        Build partition key with tenant isolation
        
        Args:
            tenant_id: Tenant identifier
            session_id: Session identifier
            
        Returns:
            Partition key string
        """
        return f"{tenant_id}#{session_id}"
    
    @staticmethod
    def validate_partition_key(partition_key: str, allowed_tenant: str) -> bool:
        """
        Validate partition key matches allowed tenant
        
        Args:
            partition_key: DynamoDB partition key
            allowed_tenant: Allowed tenant ID
            
        Returns:
            True if partition key is valid for tenant
        """
        if not partition_key or "#" not in partition_key:
            return False
        
        tenant_part = partition_key.split("#")[0]
        return tenant_part == allowed_tenant
    
    @staticmethod
    def extract_tenant_from_partition_key(partition_key: str) -> Optional[str]:
        """
        Extract tenant ID from partition key
        
        Args:
            partition_key: DynamoDB partition key
            
        Returns:
            Tenant ID if found, None otherwise
        """
        if not partition_key or "#" not in partition_key:
            return None
        
        return partition_key.split("#")[0]


class AuditLogger:
    """Audit logger for tenant operations"""
    
    def __init__(self):
        self._audit_logs: List[Dict] = []
    
    def log_tenant_operation(
        self,
        operation: str,
        tenant_id: str,
        user_id: str,
        resource_id: Optional[str] = None,
        details: Optional[Dict] = None,
        success: bool = True
    ):
        """
        Log tenant operation for audit trail
        
        Args:
            operation: Operation type
            tenant_id: Tenant identifier
            user_id: User identifier
            resource_id: Optional resource identifier
            details: Additional details
            success: Whether operation was successful
        """
        audit_entry = {
            "id": str(uuid4()),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "operation": operation,
            "tenant_id": tenant_id,
            "user_id": user_id,
            "resource_id": resource_id,
            "success": success,
            "details": details or {}
        }
        
        self._audit_logs.append(audit_entry)
        
        # Keep only recent logs (last 5000)
        if len(self._audit_logs) > 5000:
            self._audit_logs = self._audit_logs[-5000:]
        
        # Log to system logger
        log_level = logging.INFO if success else logging.WARNING
        logger.log(
            log_level,
            f"Tenant operation: {operation} on {tenant_id} by {user_id} "
            f"{'succeeded' if success else 'failed'}"
        )
    
    def get_audit_logs(
        self,
        tenant_id: Optional[str] = None,
        user_id: Optional[str] = None,
        operation: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict]:
        """
        Get audit logs with filtering
        
        Args:
            tenant_id: Filter by tenant
            user_id: Filter by user
            operation: Filter by operation
            limit: Maximum number of results
            
        Returns:
            List of audit log entries
        """
        logs = self._audit_logs
        
        # Apply filters
        if tenant_id:
            logs = [log for log in logs if log["tenant_id"] == tenant_id]
        
        if user_id:
            logs = [log for log in logs if log["user_id"] == user_id]
        
        if operation:
            logs = [log for log in logs if log["operation"] == operation]
        
        # Sort by timestamp (newest first) and limit
        logs.sort(key=lambda log: log["timestamp"], reverse=True)
        return logs[:limit]


# Global services
tenant_isolation_service = TenantIsolationService()
audit_logger = AuditLogger()