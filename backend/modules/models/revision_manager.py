"""
Revision Management System

Handles monotonic revision numbering, conflict detection, and idempotency
for UI resources in the multi-tenant MCP UI Hub platform.

Requirements: 2.3, 2.4, 4.5
"""

import asyncio
import time
from datetime import datetime, timezone, timedelta
from typing import Dict, Optional, Set, Tuple
from uuid import uuid4

from pydantic import BaseModel


class RevisionInfo(BaseModel):
    """Revision information for a resource"""
    resourceId: str
    currentRevision: int
    lastUpdated: str
    lastUpdatedBy: Optional[str] = None
    conflictCount: int = 0


class IdempotencyRecord(BaseModel):
    """Idempotency key record"""
    key: str
    resourceId: str
    tenantId: str
    sessionId: str
    createdAt: str
    expiresAt: str
    
    def is_expired(self) -> bool:
        """Check if idempotency record has expired"""
        try:
            expires_dt = datetime.fromisoformat(self.expiresAt.replace('Z', '+00:00'))
            return datetime.now(timezone.utc) > expires_dt
        except Exception:
            return True


class RevisionConflictError(Exception):
    """Raised when a revision conflict is detected"""
    def __init__(self, resource_id: str, expected_revision: int, current_revision: int):
        self.resource_id = resource_id
        self.expected_revision = expected_revision
        self.current_revision = current_revision
        super().__init__(
            f"Revision conflict for {resource_id}: expected {expected_revision}, "
            f"current {current_revision}"
        )


class IdempotencyConflictError(Exception):
    """Raised when an idempotency key conflict is detected"""
    def __init__(self, key: str, existing_resource_id: str):
        self.key = key
        self.existing_resource_id = existing_resource_id
        super().__init__(
            f"Idempotency key '{key}' already used for resource {existing_resource_id}"
        )


class RevisionManager:
    """
    Manages resource revisions, conflict detection, and idempotency
    
    In production, this would be backed by DynamoDB with atomic operations.
    For now, using in-memory storage with locks for thread safety.
    """
    
    def __init__(self):
        self._revisions: Dict[str, RevisionInfo] = {}
        self._idempotency_records: Dict[str, IdempotencyRecord] = {}
        self._locks: Dict[str, asyncio.Lock] = {}
        self._cleanup_interval = 3600  # 1 hour
        self._last_cleanup = time.time()
    
    async def _get_lock(self, resource_id: str) -> asyncio.Lock:
        """Get or create a lock for a resource"""
        if resource_id not in self._locks:
            self._locks[resource_id] = asyncio.Lock()
        return self._locks[resource_id]
    
    async def _cleanup_expired_records(self) -> None:
        """Clean up expired idempotency records"""
        current_time = time.time()
        if current_time - self._last_cleanup < self._cleanup_interval:
            return
        
        expired_keys = []
        for key, record in self._idempotency_records.items():
            if record.is_expired():
                expired_keys.append(key)
        
        for key in expired_keys:
            del self._idempotency_records[key]
        
        self._last_cleanup = current_time
    
    async def get_next_revision(self, resource_id: str, agent_id: Optional[str] = None) -> int:
        """
        Get the next revision number for a resource
        
        Args:
            resource_id: Unique resource identifier
            agent_id: Agent making the request (for audit)
            
        Returns:
            Next revision number
        """
        lock = await self._get_lock(resource_id)
        
        async with lock:
            if resource_id not in self._revisions:
                # First revision
                self._revisions[resource_id] = RevisionInfo(
                    resourceId=resource_id,
                    currentRevision=1,
                    lastUpdated=datetime.now(timezone.utc).isoformat(),
                    lastUpdatedBy=agent_id
                )
                return 1
            
            # Increment revision
            revision_info = self._revisions[resource_id]
            revision_info.currentRevision += 1
            revision_info.lastUpdated = datetime.now(timezone.utc).isoformat()
            revision_info.lastUpdatedBy = agent_id
            
            return revision_info.currentRevision
    
    async def get_current_revision(self, resource_id: str) -> int:
        """Get current revision number for a resource"""
        if resource_id not in self._revisions:
            return 0
        return self._revisions[resource_id].currentRevision
    
    async def validate_revision(self, resource_id: str, expected_revision: Optional[int]) -> None:
        """
        Validate that the expected revision matches current revision
        
        Args:
            resource_id: Unique resource identifier
            expected_revision: Expected revision number (None to skip check)
            
        Raises:
            RevisionConflictError: If revision doesn't match
        """
        if expected_revision is None:
            return
        
        current_revision = await self.get_current_revision(resource_id)
        
        if expected_revision != current_revision:
            # Record conflict
            if resource_id in self._revisions:
                self._revisions[resource_id].conflictCount += 1
            
            raise RevisionConflictError(resource_id, expected_revision, current_revision)
    
    async def check_idempotency(
        self, 
        idempotency_key: str, 
        tenant_id: str, 
        session_id: str,
        ttl_seconds: int = 3600
    ) -> Optional[str]:
        """
        Check if idempotency key has been used before
        
        Args:
            idempotency_key: Unique idempotency key
            tenant_id: Tenant ID for scoping
            session_id: Session ID for scoping
            ttl_seconds: TTL for idempotency record
            
        Returns:
            Existing resource ID if key was used, None otherwise
            
        Raises:
            IdempotencyConflictError: If key exists for different resource
        """
        await self._cleanup_expired_records()
        
        # Scope key to tenant and session
        scoped_key = f"{tenant_id}:{session_id}:{idempotency_key}"
        
        if scoped_key in self._idempotency_records:
            record = self._idempotency_records[scoped_key]
            
            if record.is_expired():
                # Clean up expired record
                del self._idempotency_records[scoped_key]
                return None
            
            return record.resourceId
        
        return None
    
    async def record_idempotency(
        self,
        idempotency_key: str,
        resource_id: str,
        tenant_id: str,
        session_id: str,
        ttl_seconds: int = 3600
    ) -> None:
        """
        Record idempotency key usage
        
        Args:
            idempotency_key: Unique idempotency key
            resource_id: Resource ID this key is associated with
            tenant_id: Tenant ID for scoping
            session_id: Session ID for scoping
            ttl_seconds: TTL for idempotency record
        """
        scoped_key = f"{tenant_id}:{session_id}:{idempotency_key}"
        
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=ttl_seconds)
        
        self._idempotency_records[scoped_key] = IdempotencyRecord(
            key=scoped_key,
            resourceId=resource_id,
            tenantId=tenant_id,
            sessionId=session_id,
            createdAt=datetime.now(timezone.utc).isoformat(),
            expiresAt=expires_at.isoformat()
        )
    
    async def delete_resource_revision(self, resource_id: str) -> None:
        """
        Delete revision information for a resource
        
        Args:
            resource_id: Resource to delete revision info for
        """
        lock = await self._get_lock(resource_id)
        
        async with lock:
            if resource_id in self._revisions:
                del self._revisions[resource_id]
            
            # Clean up lock if no longer needed
            if resource_id in self._locks:
                del self._locks[resource_id]
    
    async def get_revision_info(self, resource_id: str) -> Optional[RevisionInfo]:
        """Get detailed revision information for a resource"""
        if resource_id not in self._revisions:
            return None
        return self._revisions[resource_id].copy()
    
    async def get_conflict_stats(self) -> Dict[str, int]:
        """Get conflict statistics across all resources"""
        total_conflicts = sum(info.conflictCount for info in self._revisions.values())
        resources_with_conflicts = sum(1 for info in self._revisions.values() if info.conflictCount > 0)
        
        return {
            "total_resources": len(self._revisions),
            "total_conflicts": total_conflicts,
            "resources_with_conflicts": resources_with_conflicts,
            "active_idempotency_records": len(self._idempotency_records)
        }
    
    async def cleanup_tenant_data(self, tenant_id: str) -> int:
        """
        Clean up all revision data for a tenant
        
        Args:
            tenant_id: Tenant to clean up
            
        Returns:
            Number of records cleaned up
        """
        cleaned_count = 0
        
        # Clean up idempotency records
        expired_keys = []
        for key, record in self._idempotency_records.items():
            if record.tenantId == tenant_id:
                expired_keys.append(key)
        
        for key in expired_keys:
            del self._idempotency_records[key]
            cleaned_count += 1
        
        return cleaned_count


# Global revision manager instance
revision_manager = RevisionManager()


class TTLManager:
    """
    Manages TTL (Time To Live) for UI resources
    
    Handles automatic expiry and cleanup of expired resources.
    In production, this would be handled by DynamoDB TTL.
    """
    
    def __init__(self):
        self._ttl_records: Dict[str, datetime] = {}
        self._cleanup_callbacks: Dict[str, callable] = {}
    
    def set_ttl(self, resource_id: str, ttl_seconds: int, cleanup_callback: callable = None) -> None:
        """
        Set TTL for a resource
        
        Args:
            resource_id: Resource identifier
            ttl_seconds: Seconds until expiry
            cleanup_callback: Function to call when resource expires
        """
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=ttl_seconds)
        self._ttl_records[resource_id] = expires_at
        
        if cleanup_callback:
            self._cleanup_callbacks[resource_id] = cleanup_callback
    
    def is_expired(self, resource_id: str) -> bool:
        """Check if a resource has expired"""
        if resource_id not in self._ttl_records:
            return False
        
        return datetime.now(timezone.utc) > self._ttl_records[resource_id]
    
    def get_time_to_expiry(self, resource_id: str) -> Optional[int]:
        """Get seconds until expiry, None if no TTL set"""
        if resource_id not in self._ttl_records:
            return None
        
        delta = self._ttl_records[resource_id] - datetime.now(timezone.utc)
        return max(0, int(delta.total_seconds()))
    
    async def cleanup_expired(self) -> int:
        """
        Clean up expired resources
        
        Returns:
            Number of resources cleaned up
        """
        expired_resources = []
        current_time = datetime.now(timezone.utc)
        
        for resource_id, expires_at in self._ttl_records.items():
            if current_time > expires_at:
                expired_resources.append(resource_id)
        
        cleaned_count = 0
        for resource_id in expired_resources:
            # Call cleanup callback if registered
            if resource_id in self._cleanup_callbacks:
                try:
                    callback = self._cleanup_callbacks[resource_id]
                    if asyncio.iscoroutinefunction(callback):
                        await callback(resource_id)
                    else:
                        callback(resource_id)
                except Exception as e:
                    # Log error but continue cleanup
                    print(f"Error in TTL cleanup callback for {resource_id}: {e}")
            
            # Remove TTL record
            del self._ttl_records[resource_id]
            if resource_id in self._cleanup_callbacks:
                del self._cleanup_callbacks[resource_id]
            
            cleaned_count += 1
        
        return cleaned_count
    
    def remove_ttl(self, resource_id: str) -> None:
        """Remove TTL for a resource"""
        if resource_id in self._ttl_records:
            del self._ttl_records[resource_id]
        if resource_id in self._cleanup_callbacks:
            del self._cleanup_callbacks[resource_id]
    
    def get_stats(self) -> Dict[str, int]:
        """Get TTL statistics"""
        current_time = datetime.now(timezone.utc)
        expired_count = sum(1 for expires_at in self._ttl_records.values() if current_time > expires_at)
        
        return {
            "total_ttl_records": len(self._ttl_records),
            "expired_records": expired_count,
            "active_records": len(self._ttl_records) - expired_count
        }


# Global TTL manager instance
ttl_manager = TTLManager()