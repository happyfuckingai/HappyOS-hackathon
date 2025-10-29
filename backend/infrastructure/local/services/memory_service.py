"""
Local memory service implementation as fallback for AWS Agent Core.
Provides in-memory storage with persistence options and session management.
"""

import asyncio
import json
import pickle
import time
import logging
from typing import Any, Dict, Optional, List
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from pathlib import Path
import threading

from ....core.interfaces import AgentCoreService, AgentSession
from ....core.settings import get_settings


logger = logging.getLogger(__name__)


@dataclass
class MemoryEntry:
    """Entry in the local memory store."""
    key: str
    value: Any
    tenant_id: str
    user_id: str
    created_at: datetime
    updated_at: datetime
    expires_at: Optional[datetime] = None
    access_count: int = 0
    last_accessed: Optional[datetime] = None
    
    def is_expired(self) -> bool:
        """Check if the memory entry has expired."""
        if self.expires_at is None:
            return False
        return datetime.now() > self.expires_at
    
    def access(self):
        """Mark the entry as accessed."""
        self.access_count += 1
        self.last_accessed = datetime.now()


class LocalMemoryService(AgentCoreService):
    """
    Local memory service that provides Agent Core functionality using local storage.
    Supports session management, memory storage with TTL, and persistence.
    """
    
    def __init__(self):
        self.settings = get_settings()
        
        # In-memory storage
        self.memory_store: Dict[str, MemoryEntry] = {}
        self.sessions: Dict[str, AgentSession] = {}
        
        # Persistence settings
        self.data_directory = Path(self.settings.local.data_directory)
        self.data_directory.mkdir(parents=True, exist_ok=True)
        
        self.memory_file = self.data_directory / "memory_store.json"
        self.sessions_file = self.data_directory / "sessions.json"
        
        # Configuration
        self.max_memory_mb = self.settings.local.max_memory_mb
        self.default_ttl_hours = 24
        self.cleanup_interval = 300  # 5 minutes
        
        # Thread safety
        self._lock = threading.RLock()
        
        # Background tasks
        self._cleanup_task: Optional[asyncio.Task] = None
        self._persistence_task: Optional[asyncio.Task] = None
        
        # Load persisted data
        self._load_persisted_data()
        
        # Start background tasks
        asyncio.create_task(self._start_background_tasks())
        
        logger.info("Local memory service initialized")
    
    async def _start_background_tasks(self):
        """Start background cleanup and persistence tasks."""
        self._cleanup_task = asyncio.create_task(self._cleanup_expired_entries())
        self._persistence_task = asyncio.create_task(self._periodic_persistence())
    
    def _generate_memory_key(self, user_id: str, key: str, tenant_id: str) -> str:
        """Generate a unique key for memory storage."""
        return f"{tenant_id}:{user_id}:{key}"
    
    def _generate_session_key(self, session_id: str, tenant_id: str) -> str:
        """Generate a unique key for session storage."""
        return f"{tenant_id}:{session_id}"
    
    async def put_memory(self, user_id: str, key: str, value: Any, tenant_id: str, ttl_hours: Optional[int] = None) -> bool:
        """Store memory data for a user within a tenant context."""
        try:
            with self._lock:
                memory_key = self._generate_memory_key(user_id, key, tenant_id)
                
                # Calculate expiration time
                expires_at = None
                if ttl_hours is not None:
                    expires_at = datetime.now() + timedelta(hours=ttl_hours)
                elif self.default_ttl_hours > 0:
                    expires_at = datetime.now() + timedelta(hours=self.default_ttl_hours)
                
                # Create or update memory entry
                if memory_key in self.memory_store:
                    entry = self.memory_store[memory_key]
                    entry.value = value
                    entry.updated_at = datetime.now()
                    entry.expires_at = expires_at
                else:
                    entry = MemoryEntry(
                        key=key,
                        value=value,
                        tenant_id=tenant_id,
                        user_id=user_id,
                        created_at=datetime.now(),
                        updated_at=datetime.now(),
                        expires_at=expires_at
                    )
                    self.memory_store[memory_key] = entry
                
                logger.debug(f"Stored memory: {memory_key}")
                return True
                
        except Exception as e:
            logger.error(f"Error storing memory {user_id}:{key} for tenant {tenant_id}: {e}")
            return False
    
    async def get_memory(self, user_id: str, key: str, tenant_id: str) -> Any:
        """Retrieve memory data for a user within a tenant context."""
        try:
            with self._lock:
                memory_key = self._generate_memory_key(user_id, key, tenant_id)
                
                if memory_key not in self.memory_store:
                    return None
                
                entry = self.memory_store[memory_key]
                
                # Check if expired
                if entry.is_expired():
                    del self.memory_store[memory_key]
                    logger.debug(f"Removed expired memory: {memory_key}")
                    return None
                
                # Mark as accessed
                entry.access()
                
                logger.debug(f"Retrieved memory: {memory_key}")
                return entry.value
                
        except Exception as e:
            logger.error(f"Error retrieving memory {user_id}:{key} for tenant {tenant_id}: {e}")
            return None
    
    async def create_session(self, tenant_id: str, agent_id: str, user_id: str, config: Dict[str, Any]) -> str:
        """Create a new agent session."""
        try:
            with self._lock:
                # Generate unique session ID
                session_id = f"{agent_id}_{user_id}_{int(time.time())}"
                session_key = self._generate_session_key(session_id, tenant_id)
                
                # Create session
                session = AgentSession(
                    session_id=session_id,
                    tenant_id=tenant_id,
                    agent_id=agent_id,
                    user_id=user_id,
                    created_at=datetime.now(),
                    last_activity=datetime.now(),
                    status="active",
                    memory_context={},
                    configuration=config
                )
                
                self.sessions[session_key] = session
                
                logger.info(f"Created session: {session_id} for tenant {tenant_id}")
                return session_id
                
        except Exception as e:
            logger.error(f"Error creating session for tenant {tenant_id}: {e}")
            raise
    
    async def get_session(self, session_id: str, tenant_id: str) -> Optional[AgentSession]:
        """Retrieve an agent session."""
        try:
            with self._lock:
                session_key = self._generate_session_key(session_id, tenant_id)
                
                if session_key not in self.sessions:
                    return None
                
                session = self.sessions[session_key]
                
                # Update last activity
                session.last_activity = datetime.now()
                
                logger.debug(f"Retrieved session: {session_id}")
                return session
                
        except Exception as e:
            logger.error(f"Error retrieving session {session_id} for tenant {tenant_id}: {e}")
            return None
    
    async def update_session(self, session_id: str, tenant_id: str, updates: Dict[str, Any]) -> bool:
        """Update an agent session."""
        try:
            with self._lock:
                session_key = self._generate_session_key(session_id, tenant_id)
                
                if session_key not in self.sessions:
                    return False
                
                session = self.sessions[session_key]
                
                # Update session fields
                for field, value in updates.items():
                    if hasattr(session, field):
                        setattr(session, field, value)
                
                session.last_activity = datetime.now()
                
                logger.debug(f"Updated session: {session_id}")
                return True
                
        except Exception as e:
            logger.error(f"Error updating session {session_id} for tenant {tenant_id}: {e}")
            return False
    
    async def delete_session(self, session_id: str, tenant_id: str) -> bool:
        """Delete an agent session."""
        try:
            with self._lock:
                session_key = self._generate_session_key(session_id, tenant_id)
                
                if session_key in self.sessions:
                    del self.sessions[session_key]
                    logger.info(f"Deleted session: {session_id}")
                    return True
                
                return False
                
        except Exception as e:
            logger.error(f"Error deleting session {session_id} for tenant {tenant_id}: {e}")
            return False
    
    async def list_user_sessions(self, user_id: str, tenant_id: str) -> List[AgentSession]:
        """List all sessions for a user in a tenant."""
        try:
            with self._lock:
                user_sessions = []
                
                for session_key, session in self.sessions.items():
                    if session.user_id == user_id and session.tenant_id == tenant_id:
                        user_sessions.append(session)
                
                return user_sessions
                
        except Exception as e:
            logger.error(f"Error listing sessions for user {user_id} in tenant {tenant_id}: {e}")
            return []
    
    async def cleanup_expired_sessions(self, max_idle_hours: int = 24) -> int:
        """Clean up expired sessions based on last activity."""
        try:
            with self._lock:
                cutoff_time = datetime.now() - timedelta(hours=max_idle_hours)
                expired_sessions = []
                
                for session_key, session in self.sessions.items():
                    if session.last_activity < cutoff_time:
                        expired_sessions.append(session_key)
                
                # Remove expired sessions
                for session_key in expired_sessions:
                    del self.sessions[session_key]
                
                if expired_sessions:
                    logger.info(f"Cleaned up {len(expired_sessions)} expired sessions")
                
                return len(expired_sessions)
                
        except Exception as e:
            logger.error(f"Error cleaning up expired sessions: {e}")
            return 0
    
    async def _cleanup_expired_entries(self):
        """Background task to clean up expired memory entries and sessions."""
        while True:
            try:
                await asyncio.sleep(self.cleanup_interval)
                
                # Clean up expired memory entries
                with self._lock:
                    expired_keys = []
                    for key, entry in self.memory_store.items():
                        if entry.is_expired():
                            expired_keys.append(key)
                    
                    for key in expired_keys:
                        del self.memory_store[key]
                    
                    if expired_keys:
                        logger.debug(f"Cleaned up {len(expired_keys)} expired memory entries")
                
                # Clean up expired sessions
                await self.cleanup_expired_sessions()
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in cleanup task: {e}")
    
    def _load_persisted_data(self):
        """Load persisted memory and session data from disk."""
        try:
            # Load memory store
            if self.memory_file.exists():
                with open(self.memory_file, 'r') as f:
                    data = json.load(f)
                    
                    for key, entry_data in data.items():
                        # Convert datetime strings back to datetime objects
                        entry_data['created_at'] = datetime.fromisoformat(entry_data['created_at'])
                        entry_data['updated_at'] = datetime.fromisoformat(entry_data['updated_at'])
                        
                        if entry_data.get('expires_at'):
                            entry_data['expires_at'] = datetime.fromisoformat(entry_data['expires_at'])
                        
                        if entry_data.get('last_accessed'):
                            entry_data['last_accessed'] = datetime.fromisoformat(entry_data['last_accessed'])
                        
                        entry = MemoryEntry(**entry_data)
                        
                        # Only load non-expired entries
                        if not entry.is_expired():
                            self.memory_store[key] = entry
                
                logger.info(f"Loaded {len(self.memory_store)} memory entries from persistence")
            
            # Load sessions
            if self.sessions_file.exists():
                with open(self.sessions_file, 'r') as f:
                    data = json.load(f)
                    
                    for key, session_data in data.items():
                        # Convert datetime strings back to datetime objects
                        session_data['created_at'] = datetime.fromisoformat(session_data['created_at'])
                        session_data['last_activity'] = datetime.fromisoformat(session_data['last_activity'])
                        
                        session = AgentSession(**session_data)
                        self.sessions[key] = session
                
                logger.info(f"Loaded {len(self.sessions)} sessions from persistence")
                
        except Exception as e:
            logger.error(f"Error loading persisted data: {e}")
    
    async def _periodic_persistence(self):
        """Background task to periodically persist data to disk."""
        persistence_interval = 300  # 5 minutes
        
        while True:
            try:
                await asyncio.sleep(persistence_interval)
                await self.persist_data()
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in persistence task: {e}")
    
    async def persist_data(self):
        """Persist current memory and session data to disk."""
        try:
            with self._lock:
                # Persist memory store
                memory_data = {}
                for key, entry in self.memory_store.items():
                    if not entry.is_expired():
                        entry_dict = asdict(entry)
                        # Convert datetime objects to ISO strings
                        entry_dict['created_at'] = entry.created_at.isoformat()
                        entry_dict['updated_at'] = entry.updated_at.isoformat()
                        
                        if entry.expires_at:
                            entry_dict['expires_at'] = entry.expires_at.isoformat()
                        
                        if entry.last_accessed:
                            entry_dict['last_accessed'] = entry.last_accessed.isoformat()
                        
                        memory_data[key] = entry_dict
                
                with open(self.memory_file, 'w') as f:
                    json.dump(memory_data, f, indent=2)
                
                # Persist sessions
                session_data = {}
                for key, session in self.sessions.items():
                    session_dict = asdict(session)
                    # Convert datetime objects to ISO strings
                    session_dict['created_at'] = session.created_at.isoformat()
                    session_dict['last_activity'] = session.last_activity.isoformat()
                    
                    session_data[key] = session_dict
                
                with open(self.sessions_file, 'w') as f:
                    json.dump(session_data, f, indent=2)
                
                logger.debug("Persisted memory and session data to disk")
                
        except Exception as e:
            logger.error(f"Error persisting data: {e}")
    
    def get_memory_stats(self) -> Dict[str, Any]:
        """Get memory service statistics."""
        with self._lock:
            total_entries = len(self.memory_store)
            total_sessions = len(self.sessions)
            
            # Calculate memory usage (approximate)
            memory_usage_bytes = 0
            for entry in self.memory_store.values():
                try:
                    memory_usage_bytes += len(pickle.dumps(entry.value))
                except:
                    memory_usage_bytes += 1024  # Estimate
            
            return {
                "total_memory_entries": total_entries,
                "total_sessions": total_sessions,
                "memory_usage_bytes": memory_usage_bytes,
                "memory_usage_mb": memory_usage_bytes / (1024 * 1024),
                "max_memory_mb": self.max_memory_mb,
                "memory_utilization_percent": (memory_usage_bytes / (1024 * 1024)) / self.max_memory_mb * 100
            }
    
    async def shutdown(self):
        """Shutdown the memory service and persist data."""
        logger.info("Shutting down local memory service")
        
        # Cancel background tasks
        if self._cleanup_task:
            self._cleanup_task.cancel()
        if self._persistence_task:
            self._persistence_task.cancel()
        
        # Wait for tasks to complete
        if self._cleanup_task or self._persistence_task:
            tasks = [t for t in [self._cleanup_task, self._persistence_task] if t]
            await asyncio.gather(*tasks, return_exceptions=True)
        
        # Final persistence
        await self.persist_data()
        
        logger.info("Local memory service shutdown complete")

cla
ss LocalCacheService:
    """Local cache service using in-memory storage."""
    
    def __init__(self):
        """Initialize local cache service."""
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.RLock()
    
    def _get_cache_key(self, key: str, tenant_id: str) -> str:
        """Generate tenant-isolated cache key."""
        return f"{tenant_id}:{key}"
    
    async def get(self, key: str, tenant_id: str) -> Optional[Any]:
        """Get value from cache."""
        try:
            with self._lock:
                cache_key = self._get_cache_key(key, tenant_id)
                entry = self._cache.get(cache_key)
                
                if entry:
                    # Check TTL
                    if entry.get('expires_at') and time.time() > entry['expires_at']:
                        del self._cache[cache_key]
                        return None
                    
                    return entry['value']
                
                return None
                
        except Exception as e:
            logger.error(f"Error getting cache value: {e}")
            return None
    
    async def set(self, key: str, value: Any, tenant_id: str, ttl: int = None) -> bool:
        """Set value in cache with optional TTL."""
        try:
            with self._lock:
                cache_key = self._get_cache_key(key, tenant_id)
                
                entry = {
                    'value': value,
                    'created_at': time.time()
                }
                
                if ttl:
                    entry['expires_at'] = time.time() + ttl
                
                self._cache[cache_key] = entry
                return True
                
        except Exception as e:
            logger.error(f"Error setting cache value: {e}")
            return False
    
    async def delete(self, key: str, tenant_id: str) -> bool:
        """Delete value from cache."""
        try:
            with self._lock:
                cache_key = self._get_cache_key(key, tenant_id)
                if cache_key in self._cache:
                    del self._cache[cache_key]
                return True
                
        except Exception as e:
            logger.error(f"Error deleting cache value: {e}")
            return False
    
    async def exists(self, key: str, tenant_id: str) -> bool:
        """Check if key exists in cache."""
        try:
            with self._lock:
                cache_key = self._get_cache_key(key, tenant_id)
                entry = self._cache.get(cache_key)
                
                if entry:
                    # Check TTL
                    if entry.get('expires_at') and time.time() > entry['expires_at']:
                        del self._cache[cache_key]
                        return False
                    
                    return True
                
                return False
                
        except Exception as e:
            logger.error(f"Error checking cache key existence: {e}")
            return False