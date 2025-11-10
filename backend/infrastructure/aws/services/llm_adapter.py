"""
AWS LLM service adapter with Bedrock + OpenAI fallback.

This adapter provides LLM operations using AWS Bedrock as primary provider
with automatic fallback to OpenAI when Bedrock is unavailable.
Includes ElastiCache caching and circuit breaker integration.
"""

import logging
import os
import json
import hashlib
from typing import Any, Dict, Optional, AsyncIterator
from datetime import datetime
import boto3
from botocore.exceptions import ClientError

from backend.core.interfaces import LLMService
from backend.core.llm.providers.bedrock_provider import BedrockProvider
from backend.core.llm.providers.openai_provider import OpenAIProvider
from backend.core.llm.cost_calculator import LLMCostCalculator
from backend.infrastructure.aws.services.elasticache_adapter import AWSElastiCacheAdapter
from backend.core.circuit_breaker.circuit_breaker import CircuitBreaker, CircuitBreakerOpenError

logger = logging.getLogger(__name__)


class AWSLLMAdapter(LLMService):
    """
    AWS implementation of LLM service using Bedrock with OpenAI fallback.
    
    Features:
    - Primary: AWS Bedrock (Claude models)
    - Fallback: OpenAI (GPT models)
    - Caching: ElastiCache for response caching
    - Resilience: Circuit breaker for automatic failover
    - Monitoring: Usage logging to DynamoDB
    - Tenant isolation: Cache keys scoped by tenant
    """
    
    def __init__(
        self,
        region_name: str = "us-east-1",
        elasticache_endpoint: Optional[str] = None,
        dynamodb_table_name: str = "llm_usage_logs"
    ):
        """
        Initialize AWS LLM adapter.
        
        Args:
            region_name: AWS region for Bedrock and DynamoDB
            elasticache_endpoint: ElastiCache cluster endpoint for caching
            dynamodb_table_name: DynamoDB table name for usage logs
        """
        self.region_name = region_name
        self.dynamodb_table_name = dynamodb_table_name
        self.logger = logger
        
        # Initialize providers
        self.bedrock_provider = BedrockProvider(region_name=region_name)
        self.openai_provider = OpenAIProvider()
        
        # Initialize cache service
        if elasticache_endpoint:
            try:
                self.cache_service = AWSElastiCacheAdapter(
                    cluster_endpoint=elasticache_endpoint,
                    region_name=region_name
                )
                self.logger.info(f"ElastiCache initialized: {elasticache_endpoint}")
            except Exception as e:
                self.logger.warning(f"Failed to initialize ElastiCache: {e}. Caching disabled.")
                self.cache_service = None
        else:
            self.logger.info("No ElastiCache endpoint provided. Caching disabled.")
            self.cache_service = None
        
        # Initialize circuit breakers
        self.bedrock_circuit_breaker = CircuitBreaker(
            service_name="bedrock_llm",
            failure_threshold=3,
            timeout_seconds=30,
            half_open_max_calls=2
        )
        
        self.openai_circuit_breaker = CircuitBreaker(
            service_name="openai_llm",
            failure_threshold=5,
            timeout_seconds=30,
            half_open_max_calls=3
        )
        
        # Initialize DynamoDB client for usage logging
        try:
            self.dynamodb_client = boto3.client('dynamodb', region_name=region_name)
            self.logger.info(f"DynamoDB client initialized for table: {dynamodb_table_name}")
        except Exception as e:
            self.logger.warning(f"Failed to initialize DynamoDB client: {e}. Usage logging disabled.")
            self.dynamodb_client = None
        
        self.logger.info("AWS LLM Adapter initialized successfully")
    
    def _generate_cache_key(
        self,
        prompt: str,
        model: str,
        temperature: float,
        max_tokens: int,
        tenant_id: str
    ) -> str:
        """
        Generate tenant-isolated cache key for LLM request.
        
        Args:
            prompt: The prompt text
            model: Model identifier
            temperature: Temperature setting
            max_tokens: Max tokens setting
            tenant_id: Tenant identifier
            
        Returns:
            Cache key string with tenant isolation
        """
        # Create deterministic hash of request parameters
        key_components = f"{model}:{temperature}:{max_tokens}:{prompt}"
        hash_digest = hashlib.sha256(key_components.encode()).hexdigest()
        
        # Include tenant_id for isolation
        return f"llm_cache:{tenant_id}:{model}:{hash_digest[:16]}"
    
    async def _get_from_cache(
        self,
        cache_key: str,
        tenant_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get cached LLM response.
        
        Args:
            cache_key: Cache key
            tenant_id: Tenant identifier
            
        Returns:
            Cached response or None
        """
        if not self.cache_service:
            return None
        
        try:
            cached_data = await self.cache_service.get(cache_key, tenant_id)
            if cached_data:
                self.logger.debug(f"Cache hit for key: {cache_key}")
                return cached_data
            else:
                self.logger.debug(f"Cache miss for key: {cache_key}")
                return None
        except Exception as e:
            self.logger.warning(f"Cache lookup failed: {e}")
            return None
    
    async def _store_in_cache(
        self,
        cache_key: str,
        response: Dict[str, Any],
        tenant_id: str,
        ttl: int = 3600
    ) -> bool:
        """
        Store LLM response in cache.
        
        Args:
            cache_key: Cache key
            response: Response to cache
            tenant_id: Tenant identifier
            ttl: Time to live in seconds (default: 1 hour)
            
        Returns:
            True if successful, False otherwise
        """
        if not self.cache_service:
            return False
        
        try:
            success = await self.cache_service.set(cache_key, response, tenant_id, ttl=ttl)
            if success:
                self.logger.debug(f"Cached response for key: {cache_key}")
            return success
        except Exception as e:
            self.logger.warning(f"Cache storage failed: {e}")
            return False
    
    async def _call_bedrock(
        self,
        prompt: str,
        model: str,
        temperature: float,
        max_tokens: int,
        response_format: str
    ) -> Dict[str, Any]:
        """
        Call AWS Bedrock with circuit breaker protection.
        
        Args:
            prompt: The prompt text
            model: Model identifier
            temperature: Temperature setting
            max_tokens: Max tokens setting
            response_format: Expected response format
            
        Returns:
            Response from Bedrock
            
        Raises:
            Exception: If Bedrock call fails
        """
        self.logger.debug(f"Calling Bedrock with model: {model}")
        
        result = await self.bedrock_circuit_breaker.call(
            self.bedrock_provider.generate_completion,
            prompt=prompt,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            response_format=response_format
        )
        
        result["provider"] = "bedrock"
        return result
    
    async def _call_openai(
        self,
        prompt: str,
        model: str,
        temperature: float,
        max_tokens: int,
        response_format: str
    ) -> Dict[str, Any]:
        """
        Call OpenAI with circuit breaker protection.
        
        Args:
            prompt: The prompt text
            model: Model identifier
            temperature: Temperature setting
            max_tokens: Max tokens setting
            response_format: Expected response format
            
        Returns:
            Response from OpenAI
            
        Raises:
            Exception: If OpenAI call fails
        """
        self.logger.debug(f"Calling OpenAI with model: {model}")
        
        result = await self.openai_circuit_breaker.call(
            self.openai_provider.generate_completion,
            prompt=prompt,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            response_format=response_format
        )
        
        result["provider"] = "openai"
        return result
    
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
        """
        Generate LLM completion with caching and fallback.
        
        Implementation strategy:
        1. Check cache for existing response
        2. Try AWS Bedrock (primary)
        3. Fallback to OpenAI if Bedrock fails
        4. Cache successful response
        5. Log usage to DynamoDB
        
        Args:
            prompt: The prompt to send to the LLM
            agent_id: Identifier of the agent making the request
            tenant_id: Tenant identifier for isolation
            model: Model to use
            temperature: Sampling temperature (0.0-1.0)
            max_tokens: Maximum tokens in response
            response_format: Expected response format ("json" or "text")
            
        Returns:
            Dict containing:
                - content: The generated text
                - model: Model used
                - tokens: Token count
                - provider: Provider used ("bedrock" or "openai")
                - cached: Whether response was cached
                
        Raises:
            Exception: If all providers fail
        """
        start_time = datetime.utcnow()
        
        # Generate cache key
        cache_key = self._generate_cache_key(
            prompt, model, temperature, max_tokens, tenant_id
        )
        
        # Try cache first
        cached_response = await self._get_from_cache(cache_key, tenant_id)
        if cached_response:
            cached_response["cached"] = True
            self.logger.info(f"Returning cached response for agent: {agent_id}")
            return cached_response
        
        # Try Bedrock first
        response = None
        provider_used = None
        error_occurred = None
        
        try:
            response = await self._call_bedrock(
                prompt, model, temperature, max_tokens, response_format
            )
            provider_used = "bedrock"
            self.logger.info(f"Bedrock call successful for agent: {agent_id}")
            
        except CircuitBreakerOpenError as e:
            self.logger.warning(f"Bedrock circuit breaker open: {e}. Trying OpenAI fallback.")
            error_occurred = str(e)
            
        except Exception as e:
            self.logger.warning(f"Bedrock call failed: {e}. Trying OpenAI fallback.")
            error_occurred = str(e)
        
        # Fallback to OpenAI if Bedrock failed
        if response is None:
            try:
                response = await self._call_openai(
                    prompt, model, temperature, max_tokens, response_format
                )
                provider_used = "openai"
                self.logger.info(f"OpenAI fallback successful for agent: {agent_id}")
                
            except Exception as e:
                self.logger.error(f"OpenAI fallback also failed: {e}")
                raise Exception(
                    f"All LLM providers failed. Bedrock: {error_occurred}, OpenAI: {str(e)}"
                )
        
        # Add metadata
        response["cached"] = False
        response["provider"] = provider_used
        
        # Cache the successful response
        await self._store_in_cache(cache_key, response, tenant_id, ttl=3600)
        
        # Calculate latency
        latency_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)
        
        # Calculate cost
        prompt_tokens = response.get("prompt_tokens", 0)
        completion_tokens = response.get("completion_tokens", 0)
        total_tokens = response.get("tokens", 0)
        
        if prompt_tokens > 0 and completion_tokens > 0:
            estimated_cost = LLMCostCalculator.calculate_cost(
                model=response.get("model", model),
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens
            )
        else:
            # Fallback if token breakdown not available
            estimated_cost = LLMCostCalculator.calculate_cost_from_total_tokens(
                model=response.get("model", model),
                total_tokens=total_tokens
            )
        
        # Add cost to response
        response["estimated_cost"] = estimated_cost
        
        # Log usage (async, don't wait)
        await self._log_usage(
            agent_id=agent_id,
            tenant_id=tenant_id,
            model=response.get("model", model),
            provider=provider_used,
            tokens_used=total_tokens,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            estimated_cost=estimated_cost,
            latency_ms=latency_ms,
            cached=False,
            success=True
        )
        
        return response
    
    async def generate_streaming_completion(
        self,
        prompt: str,
        agent_id: str,
        tenant_id: str,
        model: str = "gpt-4",
        temperature: float = 0.3,
        max_tokens: int = 500
    ) -> AsyncIterator[str]:
        """
        Generate streaming LLM completion with fallback.
        
        Note: Streaming responses are not cached.
        
        Args:
            prompt: The prompt to send to the LLM
            agent_id: Identifier of the agent making the request
            tenant_id: Tenant identifier for isolation
            model: Model to use
            temperature: Sampling temperature (0.0-1.0)
            max_tokens: Maximum tokens in response
            
        Yields:
            Chunks of generated text as they arrive
            
        Raises:
            Exception: If all providers fail
        """
        self.logger.info(f"Starting streaming completion for agent: {agent_id}")
        
        # Try Bedrock streaming first (if implemented)
        try:
            async for chunk in self.bedrock_provider.generate_streaming_completion(
                prompt=prompt,
                model=model,
                temperature=temperature,
                max_tokens=max_tokens
            ):
                yield chunk
            
            self.logger.info(f"Bedrock streaming completed for agent: {agent_id}")
            return
            
        except NotImplementedError:
            self.logger.info("Bedrock streaming not implemented, falling back to OpenAI")
            
        except Exception as e:
            self.logger.warning(f"Bedrock streaming failed: {e}. Trying OpenAI fallback.")
        
        # Fallback to OpenAI streaming
        try:
            async for chunk in self.openai_provider.generate_streaming_completion(
                prompt=prompt,
                model=model,
                temperature=temperature,
                max_tokens=max_tokens
            ):
                yield chunk
            
            self.logger.info(f"OpenAI streaming completed for agent: {agent_id}")
            
        except Exception as e:
            self.logger.error(f"OpenAI streaming also failed: {e}")
            raise Exception(f"All streaming providers failed: {str(e)}")
    
    async def _log_usage(
        self,
        agent_id: str,
        tenant_id: str,
        model: str,
        provider: str,
        tokens_used: int,
        prompt_tokens: int,
        completion_tokens: int,
        estimated_cost: float,
        latency_ms: int,
        cached: bool,
        success: bool
    ) -> None:
        """
        Log LLM usage to DynamoDB for monitoring and cost tracking.
        
        Args:
            agent_id: Agent making the request
            tenant_id: Tenant identifier
            model: Model used
            provider: Provider used (bedrock, openai)
            tokens_used: Total number of tokens consumed
            prompt_tokens: Number of input tokens
            completion_tokens: Number of output tokens
            estimated_cost: Estimated cost in USD
            latency_ms: Request latency in milliseconds
            cached: Whether response was cached
            success: Whether request succeeded
        """
        if not self.dynamodb_client:
            self.logger.debug("DynamoDB client not available, skipping usage logging")
            return
        
        try:
            timestamp = datetime.utcnow().isoformat()
            
            # Create usage log item
            item = {
                'log_id': {'S': f"{tenant_id}#{agent_id}#{timestamp}"},
                'tenant_id': {'S': tenant_id},
                'agent_id': {'S': agent_id},
                'timestamp': {'S': timestamp},
                'model': {'S': model},
                'provider': {'S': provider},
                'tokens_used': {'N': str(tokens_used)},
                'prompt_tokens': {'N': str(prompt_tokens)},
                'completion_tokens': {'N': str(completion_tokens)},
                'estimated_cost': {'N': str(estimated_cost)},
                'latency_ms': {'N': str(latency_ms)},
                'cached': {'BOOL': cached},
                'success': {'BOOL': success}
            }
            
            # Write to DynamoDB (async, fire and forget)
            self.dynamodb_client.put_item(
                TableName=self.dynamodb_table_name,
                Item=item
            )
            
            self.logger.debug(
                f"Usage logged for agent {agent_id}: {tokens_used} tokens, "
                f"cost: ${estimated_cost:.6f}"
            )
            
        except Exception as e:
            # Don't fail the request if logging fails
            self.logger.warning(f"Failed to log usage to DynamoDB: {e}")
    
    async def get_usage_stats(
        self,
        agent_id: Optional[str] = None,
        tenant_id: Optional[str] = None,
        time_range: str = "24h"
    ) -> Dict[str, Any]:
        """
        Get LLM usage statistics from DynamoDB.
        
        Args:
            agent_id: Optional agent ID to filter stats
            tenant_id: Optional tenant ID to filter stats
            time_range: Time range for stats (e.g., "1h", "24h", "7d")
            
        Returns:
            Dict containing usage statistics
        """
        if not self.dynamodb_client:
            return {
                "error": "DynamoDB client not available",
                "total_requests": 0,
                "total_tokens": 0
            }
        
        try:
            # Parse time range
            time_value = int(time_range[:-1])
            time_unit = time_range[-1]
            
            # Calculate start time
            from datetime import timedelta
            if time_unit == 'h':
                start_time = datetime.utcnow() - timedelta(hours=time_value)
            elif time_unit == 'd':
                start_time = datetime.utcnow() - timedelta(days=time_value)
            else:
                start_time = datetime.utcnow() - timedelta(hours=24)
            
            start_time_str = start_time.isoformat()
            
            # Query DynamoDB using appropriate index
            if tenant_id:
                # Query by tenant_id using GSI
                response = self.dynamodb_client.query(
                    TableName=self.dynamodb_table_name,
                    IndexName='tenant_id-timestamp-index',
                    KeyConditionExpression='tenant_id = :tenant_id AND #ts >= :start_time',
                    ExpressionAttributeNames={
                        '#ts': 'timestamp'
                    },
                    ExpressionAttributeValues={
                        ':tenant_id': {'S': tenant_id},
                        ':start_time': {'S': start_time_str}
                    }
                )
            elif agent_id:
                # Query by agent_id using GSI
                response = self.dynamodb_client.query(
                    TableName=self.dynamodb_table_name,
                    IndexName='agent_id-timestamp-index',
                    KeyConditionExpression='agent_id = :agent_id AND #ts >= :start_time',
                    ExpressionAttributeNames={
                        '#ts': 'timestamp'
                    },
                    ExpressionAttributeValues={
                        ':agent_id': {'S': agent_id},
                        ':start_time': {'S': start_time_str}
                    }
                )
            else:
                # No filter - scan (expensive, should be avoided in production)
                self.logger.warning("Scanning entire table - this is expensive!")
                response = self.dynamodb_client.scan(
                    TableName=self.dynamodb_table_name,
                    FilterExpression='#ts >= :start_time',
                    ExpressionAttributeNames={
                        '#ts': 'timestamp'
                    },
                    ExpressionAttributeValues={
                        ':start_time': {'S': start_time_str}
                    }
                )
            
            # Process results
            items = response.get('Items', [])
            
            total_requests = len(items)
            cached_requests = 0
            failed_requests = 0
            total_tokens = 0
            total_cost = 0.0
            total_latency = 0
            provider_breakdown = {}
            
            for item in items:
                # Parse item
                cached = item.get('cached', {}).get('BOOL', False)
                success = item.get('success', {}).get('BOOL', True)
                tokens = int(item.get('tokens_used', {}).get('N', '0'))
                cost = float(item.get('estimated_cost', {}).get('N', '0.0'))
                latency = int(item.get('latency_ms', {}).get('N', '0'))
                provider = item.get('provider', {}).get('S', 'unknown')
                
                # Aggregate stats
                if cached:
                    cached_requests += 1
                if not success:
                    failed_requests += 1
                
                total_tokens += tokens
                total_cost += cost
                total_latency += latency
                
                # Provider breakdown
                provider_breakdown[provider] = provider_breakdown.get(provider, 0) + 1
            
            # Calculate averages
            avg_latency = total_latency / total_requests if total_requests > 0 else 0.0
            
            return {
                "agent_id": agent_id,
                "tenant_id": tenant_id,
                "time_range": time_range,
                "start_time": start_time_str,
                "total_requests": total_requests,
                "cached_requests": cached_requests,
                "failed_requests": failed_requests,
                "success_rate": ((total_requests - failed_requests) / total_requests * 100) if total_requests > 0 else 100.0,
                "total_tokens": total_tokens,
                "total_cost": round(total_cost, 4),
                "average_latency_ms": round(avg_latency, 2),
                "average_tokens_per_request": round(total_tokens / total_requests, 2) if total_requests > 0 else 0.0,
                "average_cost_per_request": round(total_cost / total_requests, 6) if total_requests > 0 else 0.0,
                "cache_hit_rate": (cached_requests / total_requests * 100) if total_requests > 0 else 0.0,
                "provider_breakdown": provider_breakdown
            }
            
        except ClientError as e:
            self.logger.error(f"DynamoDB query failed: {e}")
            return {
                "error": f"DynamoDB error: {e.response['Error']['Code']}",
                "total_requests": 0,
                "total_tokens": 0
            }
        except Exception as e:
            self.logger.error(f"Failed to get usage stats: {e}")
            return {
                "error": str(e),
                "total_requests": 0,
                "total_tokens": 0
            }
    
    def is_available(self) -> bool:
        """
        Check if LLM service is available.
        
        Returns:
            True if at least one provider is available
        """
        bedrock_available = self.bedrock_provider.is_available()
        openai_available = self.openai_provider.is_available()
        
        return bedrock_available or openai_available
    
    def get_health_status(self) -> Dict[str, Any]:
        """
        Get health status of LLM service and its components.
        
        Returns:
            Dict containing health status information
        """
        return {
            "service": "aws_llm_adapter",
            "status": "healthy" if self.is_available() else "unhealthy",
            "providers": {
                "bedrock": {
                    "available": self.bedrock_provider.is_available(),
                    "circuit_breaker_state": self.bedrock_circuit_breaker.get_state().value
                },
                "openai": {
                    "available": self.openai_provider.is_available(),
                    "circuit_breaker_state": self.openai_circuit_breaker.get_state().value
                }
            },
            "cache": {
                "enabled": self.cache_service is not None
            },
            "usage_logging": {
                "enabled": self.dynamodb_client is not None
            }
        }
