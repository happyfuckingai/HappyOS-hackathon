"""
Base LLM service implementation with provider routing and error handling.
"""

import logging
import asyncio
from typing import Any, Dict, Optional, AsyncIterator, List
from datetime import datetime
from abc import ABC, abstractmethod

from backend.core.interfaces import LLMService

logger = logging.getLogger(__name__)


class BaseLLMService(LLMService, ABC):
    """
    Base implementation of LLM service with common functionality.
    
    This class provides:
    - Provider routing logic
    - Cache key generation
    - Usage logging
    - Error handling and retry logic
    """
    
    def __init__(
        self,
        cache_manager=None,
        circuit_breaker=None,
        max_retries: int = 3,
        retry_delay: float = 1.0
    ):
        """
        Initialize base LLM service.
        
        Args:
            cache_manager: Optional cache manager for response caching
            circuit_breaker: Optional circuit breaker for resilience
            max_retries: Maximum number of retry attempts
            retry_delay: Initial delay between retries in seconds
        """
        self.cache_manager = cache_manager
        self.circuit_breaker = circuit_breaker
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.logger = logger
        self.providers: List[str] = []  # List of available providers
    
    def _generate_cache_key(
        self,
        prompt: str,
        model: str,
        temperature: float,
        max_tokens: int,
        tenant_id: str
    ) -> str:
        """
        Generate cache key for LLM request.
        
        Args:
            prompt: The prompt text
            model: Model identifier
            temperature: Temperature setting
            max_tokens: Max tokens setting
            tenant_id: Tenant identifier
            
        Returns:
            Cache key string
        """
        import hashlib
        
        # Create a deterministic hash of the request parameters
        key_components = f"{tenant_id}:{model}:{temperature}:{max_tokens}:{prompt}"
        hash_digest = hashlib.sha256(key_components.encode()).hexdigest()
        
        return f"llm_cache:{tenant_id}:{model}:{hash_digest[:16]}"
    
    async def _log_usage(
        self,
        agent_id: str,
        tenant_id: str,
        model: str,
        provider: str,
        tokens_used: int,
        latency_ms: int,
        cached: bool,
        success: bool
    ) -> None:
        """
        Log LLM usage for monitoring and cost tracking.
        
        Args:
            agent_id: Agent making the request
            tenant_id: Tenant identifier
            model: Model used
            provider: Provider used (openai, bedrock, genai)
            tokens_used: Number of tokens consumed
            latency_ms: Request latency in milliseconds
            cached: Whether response was cached
            success: Whether request succeeded
        """
        log_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "agent_id": agent_id,
            "tenant_id": tenant_id,
            "model": model,
            "provider": provider,
            "tokens_used": tokens_used,
            "latency_ms": latency_ms,
            "cached": cached,
            "success": success
        }
        
        self.logger.info(f"LLM usage: {log_entry}")
    
    async def _handle_llm_error(
        self,
        error: Exception,
        agent_id: str,
        operation: str
    ) -> None:
        """
        Handle LLM errors with appropriate logging.
        
        Args:
            error: The exception that occurred
            agent_id: Agent that encountered the error
            operation: Operation being performed
        """
        error_type = type(error).__name__
        self.logger.error(
            f"LLM error in {operation} for agent {agent_id}: "
            f"{error_type} - {str(error)}"
        )
    
    async def _retry_with_backoff(
        self,
        func,
        *args,
        **kwargs
    ) -> Any:
        """
        Retry a function with exponential backoff.
        
        Args:
            func: Async function to retry
            *args: Positional arguments for func
            **kwargs: Keyword arguments for func
            
        Returns:
            Result from successful function call
            
        Raises:
            Last exception if all retries fail
        """
        last_exception = None
        
        for attempt in range(self.max_retries):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                last_exception = e
                
                if attempt < self.max_retries - 1:
                    # Exponential backoff
                    delay = self.retry_delay * (2 ** attempt)
                    self.logger.warning(
                        f"Retry attempt {attempt + 1}/{self.max_retries} "
                        f"after {delay}s delay. Error: {e}"
                    )
                    await asyncio.sleep(delay)
                else:
                    self.logger.error(
                        f"All {self.max_retries} retry attempts failed"
                    )
        
        raise last_exception
    
    @abstractmethod
    async def _call_provider(
        self,
        provider: str,
        prompt: str,
        model: str,
        temperature: float,
        max_tokens: int,
        response_format: str
    ) -> Dict[str, Any]:
        """
        Call a specific LLM provider.
        
        This method must be implemented by concrete service classes.
        
        Args:
            provider: Provider name (e.g., "openai", "bedrock", "genai")
            prompt: The prompt text
            model: Model identifier
            temperature: Temperature setting
            max_tokens: Max tokens setting
            response_format: Expected response format
            
        Returns:
            Dict containing response data
        """
        pass
    
    async def _route_to_provider(
        self,
        prompt: str,
        model: str,
        temperature: float,
        max_tokens: int,
        response_format: str
    ) -> Dict[str, Any]:
        """
        Route request to appropriate provider with fallback logic.
        
        Args:
            prompt: The prompt text
            model: Model identifier
            temperature: Temperature setting
            max_tokens: Max tokens setting
            response_format: Expected response format
            
        Returns:
            Dict containing response data
            
        Raises:
            Exception if all providers fail
        """
        last_exception = None
        
        for provider in self.providers:
            try:
                self.logger.debug(f"Attempting provider: {provider}")
                
                if self.circuit_breaker:
                    # Use circuit breaker if available
                    result = await self.circuit_breaker.call_with_circuit_breaker(
                        f"llm_{provider}",
                        self._call_provider,
                        provider,
                        prompt,
                        model,
                        temperature,
                        max_tokens,
                        response_format
                    )
                else:
                    # Direct call without circuit breaker
                    result = await self._call_provider(
                        provider,
                        prompt,
                        model,
                        temperature,
                        max_tokens,
                        response_format
                    )
                
                # Add provider info to result
                result["provider"] = provider
                return result
                
            except Exception as e:
                last_exception = e
                self.logger.warning(
                    f"Provider {provider} failed: {e}. "
                    f"Trying next provider..."
                )
                continue
        
        # All providers failed
        error_msg = f"All LLM providers failed. Last error: {last_exception}"
        self.logger.error(error_msg)
        raise Exception(error_msg)
