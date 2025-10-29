"""
Cache Manager Module

Handles Redis caching for memory insights with fallback to in-memory caching.
"""

import json
import logging
from datetime import datetime
from typing import Dict, Any, Optional

from backend.modules.config.settings import settings

logger = logging.getLogger(__name__)


class CacheManager:
    """Manages caching for memory insights"""
    
    def __init__(self, cache_ttl: int = 3600):
        self.redis_client = None
        self.cache_ttl = cache_ttl
        self._memory_cache: Dict[str, Dict] = {}
    
    async def initialize(self) -> bool:
        """Initialize Redis client"""
        try:
            if settings.REDIS_URL:
                import redis.asyncio as redis
                self.redis_client = redis.from_url(
                    settings.REDIS_URL,
                    db=settings.REDIS_DB,
                    decode_responses=True
                )
                # Test connection
                await self.redis_client.ping()
                logger.info("Redis client initialized for memory insights caching")
                return True
            else:
                logger.info("Redis not configured, using in-memory caching")
                return True
        except Exception as e:
            logger.warning(f"Failed to initialize Redis client: {e}, using in-memory caching")
            self.redis_client = None
            return True
    
    async def get(self, cache_key: str) -> Optional[Dict[str, Any]]:
        """Get cached data"""
        try:
            if self.redis_client:
                cached_data = await self.redis_client.get(cache_key)
                if cached_data:
                    return json.loads(cached_data)
            else:
                # In-memory cache
                if cache_key in self._memory_cache:
                    cached = self._memory_cache[cache_key]
                    if (datetime.now() - cached["timestamp"]).total_seconds() < self.cache_ttl:
                        return cached["data"]
                    else:
                        del self._memory_cache[cache_key]
        except Exception as e:
            logger.error(f"Failed to get cached data: {e}")
        
        return None
    
    async def set(self, cache_key: str, data: Dict[str, Any]) -> bool:
        """Set cached data"""
        try:
            if self.redis_client:
                await self.redis_client.setex(
                    cache_key,
                    self.cache_ttl,
                    json.dumps(data, default=str)
                )
                return True
            else:
                # In-memory cache
                self._memory_cache[cache_key] = {
                    "data": data,
                    "timestamp": datetime.now()
                }
                
                # Clean old cache entries
                if len(self._memory_cache) > 100:
                    oldest_key = min(self._memory_cache.keys(),
                                   key=lambda k: self._memory_cache[k]["timestamp"])
                    del self._memory_cache[oldest_key]
                
                return True
        
        except Exception as e:
            logger.error(f"Failed to cache data: {e}")
            return False
    
    async def delete(self, cache_key: str) -> bool:
        """Delete cached data"""
        try:
            if self.redis_client:
                await self.redis_client.delete(cache_key)
            else:
                if cache_key in self._memory_cache:
                    del self._memory_cache[cache_key]
            return True
        except Exception as e:
            logger.error(f"Failed to delete cached data: {e}")
            return False
    
    async def clear_user_cache(self, user_id: str) -> bool:
        """Clear all cached data for a user"""
        try:
            if self.redis_client:
                # Get all keys for user
                pattern = f"insights:{user_id}:*"
                keys = await self.redis_client.keys(pattern)
                if keys:
                    await self.redis_client.delete(*keys)
            else:
                # Clear from memory cache
                keys_to_delete = [
                    key for key in self._memory_cache.keys()
                    if key.startswith(f"insights:{user_id}:")
                ]
                for key in keys_to_delete:
                    del self._memory_cache[key]
            
            return True
        except Exception as e:
            logger.error(f"Failed to clear user cache: {e}")
            return False
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        stats = {
            "redis_available": self.redis_client is not None,
            "memory_cache_size": len(self._memory_cache),
            "cache_ttl": self.cache_ttl
        }
        
        return stats