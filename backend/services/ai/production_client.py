"""
Production AI Client System

Real AI client implementation with robust error handling, cost tracking,
quota enforcement, circuit breaker pattern, and JSON schema validation.
"""

import asyncio
import json
import logging
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Union, Callable
from enum import Enum
from dataclasses import dataclass, field
from contextlib import asynccontextmanager
import hashlib
import uuid

# Third-party imports
import httpx
from pydantic import BaseModel, ValidationError
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

# Try to import AI libraries
try:
    from openai import AsyncOpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    AsyncOpenAI = None

try:
    import google.generativeai as genai
    GOOGLE_AI_AVAILABLE = True
except ImportError:
    GOOGLE_AI_AVAILABLE = False
    genai = None

try:
    import boto3
    BEDROCK_AVAILABLE = True
except ImportError:
    BEDROCK_AVAILABLE = False
    boto3 = None

logger = logging.getLogger(__name__)


class AIProvider(str, Enum):
    """Supported AI providers"""
    OPENAI = "openai"
    GOOGLE = "google"
    BEDROCK = "bedrock"


class CircuitBreakerState(str, Enum):
    """Circuit breaker states"""
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class AIOperationType(str, Enum):
    """Types of AI operations"""
    SUMMARIZE = "summarize"
    DETECT_TOPICS = "detect_topics"
    EXTRACT_ACTIONS = "extract_actions"
    ANALYZE_PERSONAS = "analyze_personas"
    DETECT_PHASE = "detect_phase"
    GENERATE_EMBEDDINGS = "generate_embeddings"


@dataclass
class UsageStats:
    """AI usage statistics"""
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    total_tokens: int = 0
    total_cost: float = 0.0
    avg_response_time: float = 0.0
    last_request_time: Optional[datetime] = None


@dataclass
class CircuitBreaker:
    """Circuit breaker for AI service failures"""
    failure_threshold: int = 5
    timeout_seconds: int = 60
    half_open_max_calls: int = 3
    
    failure_count: int = field(default=0)
    last_failure_time: Optional[datetime] = field(default=None)
    state: CircuitBreakerState = field(default=CircuitBreakerState.CLOSED)
    half_open_calls: int = field(default=0)

    def can_execute(self) -> bool:
        """Check if request can be executed based on circuit breaker state"""
        if self.state == CircuitBreakerState.CLOSED:
            return True
        elif self.state == CircuitBreakerState.OPEN:
            if self.last_failure_time and \
               (datetime.now() - self.last_failure_time).total_seconds() > self.timeout_seconds:
                self.state = CircuitBreakerState.HALF_OPEN
                self.half_open_calls = 0
                return True
            return False
        elif self.state == CircuitBreakerState.HALF_OPEN:
            return self.half_open_calls < self.half_open_max_calls
        return False

    def record_success(self):
        """Record successful request"""
        if self.state == CircuitBreakerState.HALF_OPEN:
            self.half_open_calls += 1
            if self.half_open_calls >= self.half_open_max_calls:
                self.state = CircuitBreakerState.CLOSED
                self.failure_count = 0

    def record_failure(self):
        """Record failed request"""
        self.failure_count += 1
        self.last_failure_time = datetime.now()
        
        if self.state == CircuitBreakerState.HALF_OPEN:
            self.state = CircuitBreakerState.OPEN
        elif self.failure_count >= self.failure_threshold:
            self.state = CircuitBreakerState.OPEN


class AIClientError(Exception):
    """Base exception for AI client errors"""
    pass


class QuotaExceededError(AIClientError):
    """Raised when user quota is exceeded"""
    pass


class CircuitBreakerOpenError(AIClientError):
    """Raised when circuit breaker is open"""
    pass


class ValidationError(AIClientError):
    """Raised when response validation fails"""
    pass


# JSON Schemas for response validation
SUMMARIZE_SCHEMA = {
    "type": "object",
    "properties": {
        "summary": {"type": "string", "minLength": 10},
        "key_points": {"type": "array", "items": {"type": "string"}},
        "confidence": {"type": "number", "minimum": 0, "maximum": 1}
    },
    "required": ["summary", "key_points", "confidence"]
}

TOPICS_SCHEMA = {
    "type": "object",
    "properties": {
        "topics": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                    "keywords": {"type": "array", "items": {"type": "string"}}
                },
                "required": ["name", "confidence"]
            }
        }
    },
    "required": ["topics"]
}

ACTIONS_SCHEMA = {
    "type": "object",
    "properties": {
        "actions": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "action": {"type": "string"},
                    "assignee": {"type": "string"},
                    "deadline": {"type": "string"},
                    "priority": {"type": "string", "enum": ["low", "medium", "high"]},
                    "confidence": {"type": "number", "minimum": 0, "maximum": 1}
                },
                "required": ["action", "confidence"]
            }
        }
    },
    "required": ["actions"]
}

PERSONAS_SCHEMA = {
    "type": "object",
    "properties": {
        "personas": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "speaker": {"type": "string"},
                    "role": {"type": "string"},
                    "engagement_level": {"type": "string", "enum": ["low", "medium", "high"]},
                    "sentiment": {"type": "string", "enum": ["positive", "neutral", "negative"]},
                    "key_contributions": {"type": "array", "items": {"type": "string"}}
                },
                "required": ["speaker", "role", "engagement_level", "sentiment"]
            }
        }
    },
    "required": ["personas"]
}

PHASE_SCHEMA = {
    "type": "object",
    "properties": {
        "phase": {"type": "string", "enum": ["scoping", "planning", "deciding", "executing", "reviewing"]},
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
        "indicators": {"type": "array", "items": {"type": "string"}},
        "progress": {"type": "number", "minimum": 0, "maximum": 1}
    },
    "required": ["phase", "confidence"]
}


class ProductionAIClient:
    """Production-ready AI client with robust error handling and monitoring"""

    def __init__(self, 
                 openai_api_key: Optional[str] = None,
                 google_api_key: Optional[str] = None,
                 bedrock_region: str = "us-east-1",
                 default_timeout: int = 30,
                 max_retries: int = 3,
                 circuit_breaker_config: Optional[Dict] = None):
        """
        Initialize production AI client
        
        Args:
            openai_api_key: OpenAI API key
            google_api_key: Google AI API key
            bedrock_region: AWS Bedrock region
            default_timeout: Default request timeout in seconds
            max_retries: Maximum retry attempts
            circuit_breaker_config: Circuit breaker configuration
        """
        self.openai_client = None
        self.google_client = None
        self.bedrock_client = None
        
        self.default_timeout = default_timeout
        self.max_retries = max_retries
        
        # Initialize clients
        self._init_openai_client(openai_api_key)
        self._init_google_client(google_api_key)
        self._init_bedrock_client(bedrock_region)
        
        # Circuit breakers for each provider
        cb_config = circuit_breaker_config or {}
        self.circuit_breakers = {
            AIProvider.OPENAI: CircuitBreaker(**cb_config),
            AIProvider.GOOGLE: CircuitBreaker(**cb_config),
            AIProvider.BEDROCK: CircuitBreaker(**cb_config)
        }
        
        # Usage statistics
        self.usage_stats = {
            AIProvider.OPENAI: UsageStats(),
            AIProvider.GOOGLE: UsageStats(),
            AIProvider.BEDROCK: UsageStats()
        }
        
        # Cost tracking (tokens to cost conversion rates)
        self.cost_rates = {
            AIProvider.OPENAI: {"input": 0.0015, "output": 0.002},  # per 1K tokens
            AIProvider.GOOGLE: {"input": 0.00025, "output": 0.0005},
            AIProvider.BEDROCK: {"input": 0.0008, "output": 0.0024}
        }
        
        # User quotas (tokens per day)
        self.user_quotas: Dict[str, Dict] = {}
        self.daily_usage: Dict[str, Dict] = {}
        
        # Response cache
        self.response_cache: Dict[str, Dict] = {}
        self.cache_ttl = 3600  # 1 hour
        
        # Thread safety
        self._lock = asyncio.Lock()
        
        logger.info("ProductionAIClient initialized with available providers: %s", 
                   self._get_available_providers())

    def _init_openai_client(self, api_key: Optional[str]):
        """Initialize OpenAI client"""
        if OPENAI_AVAILABLE and api_key:
            try:
                self.openai_client = AsyncOpenAI(
                    api_key=api_key,
                    timeout=self.default_timeout
                )
                logger.info("OpenAI client initialized")
            except Exception as e:
                logger.error("Failed to initialize OpenAI client: %s", e)

    def _init_google_client(self, api_key: Optional[str]):
        """Initialize Google AI client"""
        if GOOGLE_AI_AVAILABLE and api_key:
            try:
                genai.configure(api_key=api_key)
                self.google_client = genai.GenerativeModel('gemini-pro')
                logger.info("Google AI client initialized")
            except Exception as e:
                logger.error("Failed to initialize Google AI client: %s", e)

    def _init_bedrock_client(self, region: str):
        """Initialize AWS Bedrock client"""
        if BEDROCK_AVAILABLE:
            try:
                self.bedrock_client = boto3.client(
                    'bedrock-runtime',
                    region_name=region
                )
                logger.info("AWS Bedrock client initialized")
            except Exception as e:
                logger.error("Failed to initialize Bedrock client: %s", e)

    def _get_available_providers(self) -> List[AIProvider]:
        """Get list of available AI providers"""
        providers = []
        if self.openai_client:
            providers.append(AIProvider.OPENAI)
        if self.google_client:
            providers.append(AIProvider.GOOGLE)
        if self.bedrock_client:
            providers.append(AIProvider.BEDROCK)
        return providers

    def _select_provider(self, preferred: Optional[AIProvider] = None) -> Optional[AIProvider]:
        """Select best available provider based on circuit breaker state and performance"""
        available = self._get_available_providers()
        
        if not available:
            return None
        
        # If preferred provider is specified and available, try it first
        if preferred and preferred in available:
            if self.circuit_breakers[preferred].can_execute():
                return preferred
        
        # Select provider with best performance and available circuit breaker
        best_provider = None
        best_score = float('inf')
        
        for provider in available:
            if not self.circuit_breakers[provider].can_execute():
                continue
                
            stats = self.usage_stats[provider]
            # Score based on error rate and response time
            error_rate = stats.failed_requests / max(stats.total_requests, 1)
            score = error_rate * 100 + stats.avg_response_time
            
            if score < best_score:
                best_score = score
                best_provider = provider
        
        return best_provider

    async def _check_quota(self, user_id: str, estimated_tokens: int) -> bool:
        """Check if user has sufficient quota for the request"""
        if not user_id:
            return True  # No quota check for anonymous requests
        
        today = datetime.now().date().isoformat()
        
        # Initialize user quota if not exists
        if user_id not in self.user_quotas:
            self.user_quotas[user_id] = {"daily_limit": 100000, "monthly_limit": 1000000}
        
        # Initialize daily usage if not exists
        if user_id not in self.daily_usage:
            self.daily_usage[user_id] = {}
        
        if today not in self.daily_usage[user_id]:
            self.daily_usage[user_id][today] = {"tokens": 0, "cost": 0.0}
        
        current_usage = self.daily_usage[user_id][today]["tokens"]
        daily_limit = self.user_quotas[user_id]["daily_limit"]
        
        return (current_usage + estimated_tokens) <= daily_limit

    async def _track_usage(self, user_id: str, provider: AIProvider, 
                          tokens_used: int, cost: float, response_time: float, success: bool):
        """Track usage statistics and costs"""
        async with self._lock:
            # Update provider stats
            stats = self.usage_stats[provider]
            stats.total_requests += 1
            stats.last_request_time = datetime.now()
            
            if success:
                stats.successful_requests += 1
                stats.total_tokens += tokens_used
                stats.total_cost += cost
                
                # Update average response time
                if stats.successful_requests > 1:
                    stats.avg_response_time = (
                        (stats.avg_response_time * (stats.successful_requests - 1) + response_time) /
                        stats.successful_requests
                    )
                else:
                    stats.avg_response_time = response_time
            else:
                stats.failed_requests += 1
            
            # Update user usage
            if user_id:
                today = datetime.now().date().isoformat()
                if user_id not in self.daily_usage:
                    self.daily_usage[user_id] = {}
                if today not in self.daily_usage[user_id]:
                    self.daily_usage[user_id][today] = {"tokens": 0, "cost": 0.0}
                
                self.daily_usage[user_id][today]["tokens"] += tokens_used
                self.daily_usage[user_id][today]["cost"] += cost

    def _get_cache_key(self, operation: AIOperationType, content: str, 
                      provider: AIProvider, **kwargs) -> str:
        """Generate cache key for request"""
        key_data = f"{operation}:{provider}:{content}:{json.dumps(kwargs, sort_keys=True)}"
        return hashlib.md5(key_data.encode()).hexdigest()

    def _get_cached_response(self, cache_key: str) -> Optional[Dict]:
        """Get cached response if available and not expired"""
        if cache_key in self.response_cache:
            cached = self.response_cache[cache_key]
            if (datetime.now() - cached["timestamp"]).total_seconds() < self.cache_ttl:
                return cached["response"]
            else:
                del self.response_cache[cache_key]
        return None

    def _cache_response(self, cache_key: str, response: Dict):
        """Cache response"""
        self.response_cache[cache_key] = {
            "response": response,
            "timestamp": datetime.now()
        }
        
        # Clean old cache entries if cache gets too large
        if len(self.response_cache) > 1000:
            oldest_key = min(self.response_cache.keys(),
                           key=lambda k: self.response_cache[k]["timestamp"])
            del self.response_cache[oldest_key]

    def _validate_response(self, response: Dict, schema: Dict) -> bool:
        """Validate AI response against JSON schema"""
        try:
            import jsonschema
            jsonschema.validate(response, schema)
            return True
        except Exception as e:
            logger.error("Response validation failed: %s", e)
            return False

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry=retry_if_exception_type((httpx.TimeoutException, httpx.ConnectError))
    )
    async def _call_openai(self, messages: List[Dict], model: str = "gpt-3.5-turbo",
                          max_tokens: int = 1000, temperature: float = 0.7) -> Dict:
        """Call OpenAI API with retry logic"""
        if not self.openai_client:
            raise AIClientError("OpenAI client not available")
        
        response = await self.openai_client.chat.completions.create(
            model=model,
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature
        )
        
        return {
            "content": response.choices[0].message.content,
            "tokens_used": response.usage.total_tokens,
            "model": model
        }

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry=retry_if_exception_type((Exception,))
    )
    async def _call_google(self, prompt: str, max_tokens: int = 1000, 
                          temperature: float = 0.7) -> Dict:
        """Call Google AI API with retry logic"""
        if not self.google_client:
            raise AIClientError("Google AI client not available")
        
        generation_config = genai.types.GenerationConfig(
            max_output_tokens=max_tokens,
            temperature=temperature
        )
        
        response = await self.google_client.generate_content_async(
            prompt,
            generation_config=generation_config
        )
        
        # Estimate tokens (Google doesn't provide exact count)
        estimated_tokens = len(prompt.split()) + len(response.text.split())
        
        return {
            "content": response.text,
            "tokens_used": estimated_tokens,
            "model": "gemini-pro"
        }

    async def _call_bedrock(self, prompt: str, model_id: str = "anthropic.claude-v2",
                           max_tokens: int = 1000, temperature: float = 0.7) -> Dict:
        """Call AWS Bedrock API"""
        if not self.bedrock_client:
            raise AIClientError("Bedrock client not available")
        
        body = json.dumps({
            "prompt": f"\n\nHuman: {prompt}\n\nAssistant:",
            "max_tokens_to_sample": max_tokens,
            "temperature": temperature
        })
        
        response = self.bedrock_client.invoke_model(
            body=body,
            modelId=model_id,
            accept="application/json",
            contentType="application/json"
        )
        
        response_body = json.loads(response.get('body').read())
        
        return {
            "content": response_body.get('completion', ''),
            "tokens_used": len(prompt.split()) + len(response_body.get('completion', '').split()),
            "model": model_id
        }

    async def _execute_with_circuit_breaker(self, provider: AIProvider, 
                                          operation: Callable, *args, **kwargs) -> Dict:
        """Execute operation with circuit breaker protection"""
        circuit_breaker = self.circuit_breakers[provider]
        
        if not circuit_breaker.can_execute():
            raise CircuitBreakerOpenError(f"Circuit breaker open for {provider}")
        
        start_time = time.time()
        try:
            result = await operation(*args, **kwargs)
            response_time = time.time() - start_time
            
            circuit_breaker.record_success()
            return {**result, "response_time": response_time}
            
        except Exception as e:
            circuit_breaker.record_failure()
            raise e

    async def summarize(self, content: str, user_id: Optional[str] = None,
                       preferred_provider: Optional[AIProvider] = None,
                       style: str = "detailed") -> Dict[str, Any]:
        """
        Summarize content using AI
        
        Args:
            content: Text content to summarize
            user_id: User ID for quota tracking
            preferred_provider: Preferred AI provider
            style: Summary style (brief, detailed, bullet_points)
            
        Returns:
            Dict with summary, key_points, and metadata
        """
        # Check cache first
        cache_key = self._get_cache_key(AIOperationType.SUMMARIZE, content, 
                                       preferred_provider or AIProvider.OPENAI, style=style)
        cached = self._get_cached_response(cache_key)
        if cached:
            logger.debug("Cache hit for summarization request")
            return cached
        
        # Estimate tokens and check quota
        estimated_tokens = len(content.split()) * 1.5  # Rough estimate
        if not await self._check_quota(user_id, int(estimated_tokens)):
            raise QuotaExceededError("Daily quota exceeded")
        
        # Select provider
        provider = self._select_provider(preferred_provider)
        if not provider:
            raise AIClientError("No AI providers available")
        
        # Create prompt based on style
        style_prompts = {
            "brief": "Provide a brief 2-3 sentence summary of the following content:",
            "detailed": "Provide a detailed summary with key points of the following content:",
            "bullet_points": "Summarize the following content as bullet points:"
        }
        
        prompt = f"{style_prompts.get(style, style_prompts['detailed'])}\n\n{content}\n\nProvide response in JSON format with 'summary', 'key_points' (array), and 'confidence' (0-1) fields."
        
        try:
            # Execute with circuit breaker
            if provider == AIProvider.OPENAI:
                messages = [{"role": "user", "content": prompt}]
                result = await self._execute_with_circuit_breaker(
                    provider, self._call_openai, messages
                )
            elif provider == AIProvider.GOOGLE:
                result = await self._execute_with_circuit_breaker(
                    provider, self._call_google, prompt
                )
            elif provider == AIProvider.BEDROCK:
                result = await self._execute_with_circuit_breaker(
                    provider, self._call_bedrock, prompt
                )
            
            # Parse JSON response
            try:
                parsed_response = json.loads(result["content"])
            except json.JSONDecodeError:
                # Fallback: extract summary from text response
                parsed_response = {
                    "summary": result["content"][:500],
                    "key_points": [result["content"][:200]],
                    "confidence": 0.7
                }
            
            # Validate response
            if not self._validate_response(parsed_response, SUMMARIZE_SCHEMA):
                raise ValidationError("Response validation failed")
            
            # Calculate cost
            cost = (result["tokens_used"] / 1000) * self.cost_rates[provider]["input"]
            
            # Track usage
            await self._track_usage(user_id, provider, result["tokens_used"], 
                                  cost, result["response_time"], True)
            
            # Add metadata
            response = {
                **parsed_response,
                "provider": provider,
                "model": result["model"],
                "tokens_used": result["tokens_used"],
                "cost": cost,
                "response_time": result["response_time"]
            }
            
            # Cache response
            self._cache_response(cache_key, response)
            
            return response
            
        except Exception as e:
            # Track failed usage
            await self._track_usage(user_id, provider, 0, 0.0, 0.0, False)
            logger.error("Summarization failed with provider %s: %s", provider, e)
            raise AIClientError(f"Summarization failed: {str(e)}")

    async def detect_topics(self, content: str, user_id: Optional[str] = None,
                           preferred_provider: Optional[AIProvider] = None,
                           max_topics: int = 5) -> Dict[str, Any]:
        """Detect topics in content"""
        # Implementation similar to summarize but with topic detection prompt
        cache_key = self._get_cache_key(AIOperationType.DETECT_TOPICS, content,
                                       preferred_provider or AIProvider.OPENAI, max_topics=max_topics)
        cached = self._get_cached_response(cache_key)
        if cached:
            return cached
        
        estimated_tokens = len(content.split()) * 1.2
        if not await self._check_quota(user_id, int(estimated_tokens)):
            raise QuotaExceededError("Daily quota exceeded")
        
        provider = self._select_provider(preferred_provider)
        if not provider:
            raise AIClientError("No AI providers available")
        
        prompt = f"""Analyze the following content and identify up to {max_topics} main topics.
        
Content: {content}

Provide response in JSON format with 'topics' array, where each topic has 'name', 'confidence' (0-1), and optional 'keywords' array."""
        
        try:
            if provider == AIProvider.OPENAI:
                messages = [{"role": "user", "content": prompt}]
                result = await self._execute_with_circuit_breaker(
                    provider, self._call_openai, messages
                )
            elif provider == AIProvider.GOOGLE:
                result = await self._execute_with_circuit_breaker(
                    provider, self._call_google, prompt
                )
            elif provider == AIProvider.BEDROCK:
                result = await self._execute_with_circuit_breaker(
                    provider, self._call_bedrock, prompt
                )
            
            try:
                parsed_response = json.loads(result["content"])
            except json.JSONDecodeError:
                # Fallback: simple topic extraction
                words = content.split()
                topics = [{"name": word, "confidence": 0.5} for word in words[:max_topics] if len(word) > 5]
                parsed_response = {"topics": topics}
            
            if not self._validate_response(parsed_response, TOPICS_SCHEMA):
                raise ValidationError("Response validation failed")
            
            cost = (result["tokens_used"] / 1000) * self.cost_rates[provider]["input"]
            await self._track_usage(user_id, provider, result["tokens_used"], 
                                  cost, result["response_time"], True)
            
            response = {
                **parsed_response,
                "provider": provider,
                "model": result["model"],
                "tokens_used": result["tokens_used"],
                "cost": cost,
                "response_time": result["response_time"]
            }
            
            self._cache_response(cache_key, response)
            return response
            
        except Exception as e:
            await self._track_usage(user_id, provider, 0, 0.0, 0.0, False)
            logger.error("Topic detection failed with provider %s: %s", provider, e)
            raise AIClientError(f"Topic detection failed: {str(e)}")

    async def get_usage_stats(self, user_id: Optional[str] = None) -> Dict[str, Any]:
        """Get usage statistics"""
        stats = {
            "providers": {
                provider.value: {
                    "total_requests": self.usage_stats[provider].total_requests,
                    "successful_requests": self.usage_stats[provider].successful_requests,
                    "failed_requests": self.usage_stats[provider].failed_requests,
                    "total_tokens": self.usage_stats[provider].total_tokens,
                    "total_cost": self.usage_stats[provider].total_cost,
                    "avg_response_time": self.usage_stats[provider].avg_response_time,
                    "circuit_breaker_state": self.circuit_breakers[provider].state.value
                }
                for provider in AIProvider
            },
            "cache_size": len(self.response_cache)
        }
        
        if user_id and user_id in self.daily_usage:
            today = datetime.now().date().isoformat()
            stats["user_usage"] = {
                "today": self.daily_usage[user_id].get(today, {"tokens": 0, "cost": 0.0}),
                "quota": self.user_quotas.get(user_id, {"daily_limit": 100000})
            }
        
        return stats

    async def set_user_quota(self, user_id: str, daily_limit: int, monthly_limit: int):
        """Set user quota limits"""
        self.user_quotas[user_id] = {
            "daily_limit": daily_limit,
            "monthly_limit": monthly_limit
        }

    async def health_check(self) -> Dict[str, Any]:
        """Perform health check on all providers"""
        health_status = {}
        
        for provider in self._get_available_providers():
            try:
                # Simple test request
                test_content = "Test health check"
                if provider == AIProvider.OPENAI and self.openai_client:
                    messages = [{"role": "user", "content": "Say 'OK'"}]
                    await asyncio.wait_for(self._call_openai(messages, max_tokens=10), timeout=5)
                    health_status[provider.value] = "healthy"
                elif provider == AIProvider.GOOGLE and self.google_client:
                    await asyncio.wait_for(self._call_google("Say 'OK'", max_tokens=10), timeout=5)
                    health_status[provider.value] = "healthy"
                elif provider == AIProvider.BEDROCK and self.bedrock_client:
                    await asyncio.wait_for(self._call_bedrock("Say 'OK'", max_tokens=10), timeout=5)
                    health_status[provider.value] = "healthy"
                    
            except Exception as e:
                health_status[provider.value] = f"unhealthy: {str(e)}"
        
        return {
            "status": "healthy" if all("healthy" in status for status in health_status.values()) else "degraded",
            "providers": health_status,
            "timestamp": datetime.now().isoformat()
        }

    async def close(self):
        """Close all client connections"""
        if self.openai_client:
            await self.openai_client.close()
        # Google and Bedrock clients don't need explicit closing
        logger.info("ProductionAIClient closed")