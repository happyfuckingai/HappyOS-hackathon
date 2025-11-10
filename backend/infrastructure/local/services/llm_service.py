"""
Local LLM service implementation as fallback for AWS LLM Adapter.
Provides OpenAI-only LLM access with in-memory caching for development.
"""

import asyncio
import hashlib
import json
import logging
import os
import time
from typing import Any, Dict, Optional, AsyncIterator
from datetime import datetime
from pathlib import Path
import threading

from openai import AsyncOpenAI

from ....core.interfaces import LLMService
from ....core.settings import get_settings


logger = logging.getLogger(__name__)


class LocalLLMService(LLMService):
    """
    Local LLM service that provides LLM functionality using OpenAI only.
    Supports in-memory caching and basic usage logging for development.
    """
    
    def __init__(self):
        """Initialize local LLM service with OpenAI client and in-memory cache."""
        self.settings = get_settings()
        
        # Initialize OpenAI client
        api_key = os.getenv('OPENAI_API_KEY')
        if not api_key:
            logger.warning("OPENAI_API_KEY not found in environment variables")
            self.openai_client = None
        else:
            self.openai_client = AsyncOpenAI(api_key=api_key)
            logger.info("OpenAI client initialized successfully")
        
        # In-memory cache (simple dict)
        self.cache: Dict[str, Dict[str, Any]] = {}
        
        # Thread safety
        self._lock = threading.RLock()
        
        # Usage tracking
        self.usage_log: list = []
        
        # Data directory for usage logs
        self.data_directory = Path(self.settings.local.data_directory)
        self.data_directory.mkdir(parents=True, exist_ok=True)
        self.usage_log_file = self.data_directory / "llm_usage.jsonl"
        
        logger.info("Local LLM service initialized")
    
    def _generate_cache_key(self, prompt: str, model: str, temperature: float, max_tokens: int) -> str:
        """Generate cache key from prompt and parameters."""
        cache_string = f"{prompt}:{model}:{temperature}:{max_tokens}"
        return hashlib.sha256(cache_string.encode()).hexdigest()
    
    def _get_tenant_cache_key(self, cache_key: str, tenant_id: str) -> str:
        """Generate tenant-isolated cache key."""
        return f"{tenant_id}:{cache_key}"
    
    async def generate_completion(
        self,
        prompt: str,
        agent_id: str,
        tenant_id: str,
        model: str = "gpt-4",
        temperature: float = 0.3,
        max_tokens: int = 500,
        response_format: str = "json"
    ) -> Dict[str, Any]:
        """Generate LLM completion using OpenAI.
        
        Args:
            prompt: The prompt to send to the LLM
            agent_id: Identifier of the agent making the request
            tenant_id: Tenant identifier for isolation
            model: Model to use (e.g., "gpt-4", "gpt-3.5-turbo")
            temperature: Sampling temperature (0.0-1.0)
            max_tokens: Maximum tokens in response
            response_format: Expected response format ("json" or "text")
            
        Returns:
            Dict containing:
                - content: The generated text
                - model: Model used
                - tokens: Token count
                - cached: Whether response was cached
        """
        start_time = time.time()
        
        # Check if OpenAI client is available
        if not self.openai_client:
            logger.error("OpenAI client not initialized - missing API key")
            raise ValueError("OpenAI API key not configured")
        
        # Generate cache key
        cache_key = self._generate_cache_key(prompt, model, temperature, max_tokens)
        tenant_cache_key = self._get_tenant_cache_key(cache_key, tenant_id)
        
        # Try cache lookup
        with self._lock:
            if tenant_cache_key in self.cache:
                cached_entry = self.cache[tenant_cache_key]
                
                # Check if cache entry is still valid (1 hour TTL)
                if time.time() - cached_entry['timestamp'] < 3600:
                    logger.debug(f"Cache hit for agent {agent_id}")
                    
                    # Log cache hit
                    await self._log_usage(
                        agent_id=agent_id,
                        tenant_id=tenant_id,
                        model=model,
                        prompt_length=len(prompt),
                        tokens_used=cached_entry['tokens'],
                        latency_ms=int((time.time() - start_time) * 1000),
                        cached=True,
                        success=True
                    )
                    
                    return {
                        "content": cached_entry['content'],
                        "model": cached_entry['model'],
                        "tokens": cached_entry['tokens'],
                        "cached": True
                    }
                else:
                    # Cache expired, remove it
                    del self.cache[tenant_cache_key]
        
        # Cache miss - call OpenAI
        try:
            logger.debug(f"Calling OpenAI for agent {agent_id} with model {model}")
            
            # Prepare messages
            messages = [{"role": "user", "content": prompt}]
            
            # Prepare request parameters
            request_params = {
                "model": model,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens
            }
            
            # Add response format if JSON is requested
            if response_format == "json":
                request_params["response_format"] = {"type": "json_object"}
            
            # Call OpenAI
            response = await self.openai_client.chat.completions.create(**request_params)
            
            # Extract response data
            content = response.choices[0].message.content
            tokens_used = response.usage.total_tokens
            model_used = response.model
            
            latency_ms = int((time.time() - start_time) * 1000)
            
            # Store in cache
            with self._lock:
                self.cache[tenant_cache_key] = {
                    'content': content,
                    'model': model_used,
                    'tokens': tokens_used,
                    'timestamp': time.time()
                }
            
            # Log usage
            await self._log_usage(
                agent_id=agent_id,
                tenant_id=tenant_id,
                model=model_used,
                prompt_length=len(prompt),
                tokens_used=tokens_used,
                latency_ms=latency_ms,
                cached=False,
                success=True
            )
            
            logger.info(f"OpenAI call successful for agent {agent_id}: {tokens_used} tokens, {latency_ms}ms")
            
            return {
                "content": content,
                "model": model_used,
                "tokens": tokens_used,
                "cached": False
            }
            
        except Exception as e:
            latency_ms = int((time.time() - start_time) * 1000)
            
            # Log failed usage
            await self._log_usage(
                agent_id=agent_id,
                tenant_id=tenant_id,
                model=model,
                prompt_length=len(prompt),
                tokens_used=0,
                latency_ms=latency_ms,
                cached=False,
                success=False,
                error=str(e)
            )
            
            logger.error(f"OpenAI call failed for agent {agent_id}: {e}")
            raise
    
    async def generate_streaming_completion(
        self,
        prompt: str,
        agent_id: str,
        tenant_id: str,
        model: str = "gpt-4",
        temperature: float = 0.3,
        max_tokens: int = 500
    ) -> AsyncIterator[str]:
        """Generate streaming LLM completion using OpenAI.
        
        Args:
            prompt: The prompt to send to the LLM
            agent_id: Identifier of the agent making the request
            tenant_id: Tenant identifier for isolation
            model: Model to use
            temperature: Sampling temperature (0.0-1.0)
            max_tokens: Maximum tokens in response
            
        Yields:
            Chunks of generated text as they arrive
        """
        # Check if OpenAI client is available
        if not self.openai_client:
            logger.error("OpenAI client not initialized - missing API key")
            raise ValueError("OpenAI API key not configured")
        
        try:
            logger.debug(f"Starting streaming call for agent {agent_id} with model {model}")
            
            # Prepare messages
            messages = [{"role": "user", "content": prompt}]
            
            # Call OpenAI with streaming
            stream = await self.openai_client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                stream=True
            )
            
            # Stream chunks
            async for chunk in stream:
                if chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
            
            logger.info(f"Streaming call completed for agent {agent_id}")
            
        except Exception as e:
            logger.error(f"Streaming call failed for agent {agent_id}: {e}")
            raise
    
    async def get_usage_stats(
        self,
        agent_id: Optional[str] = None,
        tenant_id: Optional[str] = None,
        time_range: str = "24h"
    ) -> Dict[str, Any]:
        """Get LLM usage statistics.
        
        Args:
            agent_id: Optional agent ID to filter stats
            tenant_id: Optional tenant ID to filter stats
            time_range: Time range for stats (e.g., "1h", "24h", "7d")
            
        Returns:
            Dict containing usage statistics
        """
        # Parse time range
        time_range_seconds = self._parse_time_range(time_range)
        cutoff_time = time.time() - time_range_seconds
        
        # Filter usage log
        filtered_logs = []
        with self._lock:
            for log_entry in self.usage_log:
                # Filter by time
                if log_entry['timestamp'] < cutoff_time:
                    continue
                
                # Filter by agent_id if specified
                if agent_id and log_entry['agent_id'] != agent_id:
                    continue
                
                # Filter by tenant_id if specified
                if tenant_id and log_entry['tenant_id'] != tenant_id:
                    continue
                
                filtered_logs.append(log_entry)
        
        # Calculate statistics
        total_requests = len(filtered_logs)
        successful_requests = sum(1 for log in filtered_logs if log['success'])
        failed_requests = total_requests - successful_requests
        cached_requests = sum(1 for log in filtered_logs if log['cached'])
        
        total_tokens = sum(log['tokens_used'] for log in filtered_logs)
        total_latency = sum(log['latency_ms'] for log in filtered_logs)
        average_latency = total_latency / total_requests if total_requests > 0 else 0
        
        # Calculate cost (approximate)
        estimated_cost = self._calculate_cost(filtered_logs)
        
        # Model breakdown
        model_breakdown = {}
        for log in filtered_logs:
            model = log['model']
            model_breakdown[model] = model_breakdown.get(model, 0) + 1
        
        return {
            "time_range": time_range,
            "total_requests": total_requests,
            "successful_requests": successful_requests,
            "failed_requests": failed_requests,
            "cached_requests": cached_requests,
            "cache_hit_rate": cached_requests / total_requests if total_requests > 0 else 0,
            "total_tokens": total_tokens,
            "average_latency_ms": average_latency,
            "estimated_cost_usd": estimated_cost,
            "model_breakdown": model_breakdown
        }
    
    def _parse_time_range(self, time_range: str) -> int:
        """Parse time range string to seconds."""
        if time_range.endswith('h'):
            hours = int(time_range[:-1])
            return hours * 3600
        elif time_range.endswith('d'):
            days = int(time_range[:-1])
            return days * 86400
        else:
            # Default to 24 hours
            return 86400
    
    def _calculate_cost(self, logs: list) -> float:
        """Calculate estimated cost from usage logs."""
        # Approximate pricing (as of 2024)
        pricing = {
            "gpt-4": 0.03 / 1000,  # $0.03 per 1K tokens (input)
            "gpt-4-turbo": 0.01 / 1000,
            "gpt-3.5-turbo": 0.0015 / 1000,
        }
        
        total_cost = 0.0
        for log in logs:
            model = log['model']
            tokens = log['tokens_used']
            
            # Find matching pricing
            cost_per_token = 0.01 / 1000  # Default
            for model_prefix, price in pricing.items():
                if model.startswith(model_prefix):
                    cost_per_token = price
                    break
            
            total_cost += tokens * cost_per_token
        
        return round(total_cost, 4)
    
    async def _log_usage(
        self,
        agent_id: str,
        tenant_id: str,
        model: str,
        prompt_length: int,
        tokens_used: int,
        latency_ms: int,
        cached: bool,
        success: bool,
        error: Optional[str] = None
    ):
        """Log LLM usage to in-memory log and file."""
        log_entry = {
            "timestamp": time.time(),
            "datetime": datetime.utcnow().isoformat(),
            "agent_id": agent_id,
            "tenant_id": tenant_id,
            "model": model,
            "prompt_length": prompt_length,
            "tokens_used": tokens_used,
            "latency_ms": latency_ms,
            "cached": cached,
            "success": success,
            "error": error
        }
        
        # Add to in-memory log
        with self._lock:
            self.usage_log.append(log_entry)
            
            # Keep only last 10000 entries in memory
            if len(self.usage_log) > 10000:
                self.usage_log = self.usage_log[-10000:]
        
        # Write to file (append mode)
        try:
            with open(self.usage_log_file, 'a') as f:
                f.write(json.dumps(log_entry) + '\n')
        except Exception as e:
            logger.error(f"Error writing usage log to file: {e}")
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        with self._lock:
            total_entries = len(self.cache)
            
            # Calculate cache size (approximate)
            cache_size_bytes = 0
            for entry in self.cache.values():
                cache_size_bytes += len(entry['content'])
            
            return {
                "total_cache_entries": total_entries,
                "cache_size_bytes": cache_size_bytes,
                "cache_size_kb": cache_size_bytes / 1024
            }
    
    async def clear_cache(self, tenant_id: Optional[str] = None):
        """Clear cache entries, optionally for a specific tenant."""
        with self._lock:
            if tenant_id:
                # Clear only entries for specific tenant
                keys_to_delete = [k for k in self.cache.keys() if k.startswith(f"{tenant_id}:")]
                for key in keys_to_delete:
                    del self.cache[key]
                logger.info(f"Cleared {len(keys_to_delete)} cache entries for tenant {tenant_id}")
            else:
                # Clear all cache
                entry_count = len(self.cache)
                self.cache.clear()
                logger.info(f"Cleared all {entry_count} cache entries")
