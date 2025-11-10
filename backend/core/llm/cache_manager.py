"""
Cache manager for LLM responses.

Provides caching functionality to reduce costs and latency for repeated LLM requests.
"""

import logging
import hashlib
from typing import Any, Dict, Optional
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class CacheManager:
    """
    Manages caching of LLM responses with TTL-based invalidation.
    
    Features:
    - Prompt hashing for cache keys
    - TTL-based cache invalidation
    - Cache hit/miss metrics
    - Tenant isolation
    """
    
    def __init__(self, cache_service=None, default_ttl: int = 3600):
        """
        Initialize cache manager.
        
        Args:
            cache_service: Backend cache service (e.g., Redis, ElastiCache)
            default_ttl: Default TTL in seconds (default: 1 hour)
        """
        self.cache_service = cache_service
        self.default_ttl = default_ttl
        self.logger = logger
        
        # Metrics
        self.cache_hits = 0
        self.cache_misses = 0
    
    def generate_cache_key(
        self,
        prompt: str,
        model: str,
        temperature: float,
        max_tokens: int,
        tenant_id: str
    ) -> str:
        """
        Generate a deterministic cache key from request parameters.
        
        Args:
            prompt: The prompt text
            model: Model identifier
            temperature: Temperature setting
            max_tokens: Max tokens setting
            tenant_id: Tenant identifier
            
        Returns:
            Cache key string
        """
        # Create a string representation of all parameters
        key_components = f"{tenant_id}:{model}:{temperature}:{max_tokens}:{prompt}"
        
        # Hash the components for a fixed-length key
        hash_digest = hashlib.sha256(key_components.encode()).hexdigest()
        
        # Include tenant_id and model in the key for easier debugging
        return f"llm:{tenant_id}:{model}:{hash_digest[:16]}"
    
    async def get(
        self,
        cache_key: str,
        tenant_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Retrieve cached LLM response.
        
        Args:
            cache_key: Cache key to lookup
            tenant_id: Tenant identifier for isolation
            
        Returns:
            Cached response dict or None if not found
        """
        if not self.cache_service:
            return None
        
        try:
            cached_value = await self.cache_service.get(cache_key, tenant_id)
            
            if cached_value:
                self.cache_hits += 1
                self.logger.debug(f"Cache hit for key: {cache_key}")
                return cached_value
            else:
                self.cache_misses += 1
                self.logger.debug(f"Cache miss for key: {cache_key}")
                return None
                
        except Exception as e:
            self.logger.error(f"Cache get error: {e}")
            self.cache_misses += 1
            return None
    
    async def set(
        self,
        cache_key: str,
        value: Dict[str, Any],
        tenant_id: str,
        ttl: Optional[int] = None
    ) -> bool:
        """
        Store LLM response in cache.
        
        Args:
            cache_key: Cache key to store under
            value: Response data to cache
            tenant_id: Tenant identifier for isolation
            ttl: Time-to-live in seconds (uses default if not specified)
            
        Returns:
            True if successful, False otherwise
        """
        if not self.cache_service:
            return False
        
        try:
            ttl_value = ttl if ttl is not None else self.default_ttl
            
            success = await self.cache_service.set(
                cache_key,
                value,
                tenant_id,
                ttl=ttl_value
            )
            
            if success:
                self.logger.debug(
                    f"Cached response for key: {cache_key} (TTL: {ttl_value}s)"
                )
            
            return success
            
        except Exception as e:
            self.logger.error(f"Cache set error: {e}")
            return False
    
    async def invalidate(
        self,
        cache_key: str,
        tenant_id: str
    ) -> bool:
        """
        Invalidate a cached entry.
        
        Args:
            cache_key: Cache key to invalidate
            tenant_id: Tenant identifier for isolation
            
        Returns:
            True if successful, False otherwise
        """
        if not self.cache_service:
            return False
        
        try:
            success = await self.cache_service.delete(cache_key, tenant_id)
            
            if success:
                self.logger.debug(f"Invalidated cache key: {cache_key}")
            
            return success
            
        except Exception as e:
            self.logger.error(f"Cache invalidate error: {e}")
            return False
    
    def get_metrics(self) -> Dict[str, Any]:
        """
        Get cache performance metrics.
        
        Returns:
            Dict containing cache hit/miss statistics
        """
        total_requests = self.cache_hits + self.cache_misses
        hit_rate = (
            (self.cache_hits / total_requests * 100)
            if total_requests > 0
            else 0.0
        )
        
        return {
            "cache_hits": self.cache_hits,
            "cache_misses": self.cache_misses,
            "total_requests": total_requests,
            "hit_rate_percent": round(hit_rate, 2)
        }
    
    def reset_metrics(self) -> None:
        """Reset cache metrics counters."""
        self.cache_hits = 0
        self.cache_misses = 0
        self.logger.info("Cache metrics reset")
