# LLM Service API Documentation

## Overview

The LLM Service provides a centralized, resilient interface for all AI agents in HappyOS to access Large Language Models. It follows the same architectural patterns as other core services (AgentCoreService, SearchService) and provides automatic failover, caching, and usage tracking.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    HappyOS Agents                            │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │  MeetMind    │  │ Agent Svea   │  │  Felicia's   │      │
│  │    Team      │  │    Team      │  │   Finance    │      │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘      │
│         │                  │                  │              │
│         └──────────────────┼──────────────────┘              │
│                            │                                 │
│                    ┌───────▼────────┐                        │
│                    │  LLMService    │                        │
│                    │   Interface    │                        │
│                    └───────┬────────┘                        │
│                            │                                 │
│         ┌──────────────────┼──────────────────┐             │
│         │                  │                  │             │
│  ┌──────▼──────┐   ┌──────▼──────┐   ┌──────▼──────┐      │
│  │AWS Bedrock  │   │   OpenAI    │   │Google GenAI │      │
│  │  Provider   │   │  Provider   │   │  Provider   │      │
│  └─────────────┘   └─────────────┘   └─────────────┘      │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐  │
│  │         Circuit Breaker & Failover Logic             │  │
│  └──────────────────────────────────────────────────────┘  │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐  │
│  │    ElastiCache (AWS) / In-Memory (Local) Caching    │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

## LLMService Interface

### Core Methods

#### `generate_completion()`

Generate a text completion from an LLM.

**Signature:**
```python
async def generate_completion(
    self,
    prompt: str,
    agent_id: str,
    tenant_id: str,
    model: str = "gpt-4",
    temperature: float = 0.3,
    max_tokens: int = 500,
    response_format: str = "json"
) -> Dict[str, Any]
```

**Parameters:**
- `prompt` (str): The input prompt for the LLM
- `agent_id` (str): Identifier of the calling agent (e.g., "meetmind.coordinator")
- `tenant_id` (str): Tenant identifier for multi-tenant isolation
- `model` (str, optional): Model to use. Defaults to "gpt-4"
  - OpenAI: "gpt-4", "gpt-4-turbo", "gpt-3.5-turbo"
  - AWS Bedrock: "claude-3-sonnet", "claude-3-haiku", "claude-3-opus"
  - Google GenAI: "gemini-1.5-pro", "gemini-1.5-flash"
- `temperature` (float, optional): Sampling temperature (0.0-1.0). Defaults to 0.3
  - 0.0-0.3: Factual, deterministic responses
  - 0.4-0.7: Balanced creativity
  - 0.8-1.0: High creativity
- `max_tokens` (int, optional): Maximum tokens in response. Defaults to 500
- `response_format` (str, optional): Expected format ("json" or "text"). Defaults to "json"

**Returns:**
```python
{
    "content": str,           # The generated text
    "model": str,             # Model that generated the response
    "provider": str,          # Provider used (openai, bedrock, genai)
    "tokens": int,            # Total tokens used
    "cached": bool,           # Whether response was from cache
    "cost": float,            # Estimated cost in USD
    "latency_ms": int        # Response time in milliseconds
}
```

**Raises:**
- `APIKeyError`: Missing or invalid API key
- `RateLimitError`: Rate limit exceeded
- `TimeoutError`: Request timeout
- `LLMServiceError`: General LLM service error

**Example:**
```python
from backend.core.interfaces import LLMService

llm_service: LLMService = services.get("llm_service")

response = await llm_service.generate_completion(
    prompt="Analyze this meeting transcript and extract action items: ...",
    agent_id="meetmind.implementation",
    tenant_id="tenant_123",
    model="gpt-4",
    temperature=0.2,
    max_tokens=800,
    response_format="json"
)

print(f"Response: {response['content']}")
print(f"Cost: ${response['cost']:.4f}")
print(f"Cached: {response['cached']}")
```

#### `generate_streaming_completion()`

Generate a streaming text completion from an LLM.

**Signature:**
```python
async def generate_streaming_completion(
    self,
    prompt: str,
    agent_id: str,
    tenant_id: str,
    model: str = "gpt-4",
    temperature: float = 0.3,
    max_tokens: int = 500
) -> AsyncIterator[str]
```

**Parameters:** Same as `generate_completion()` except `response_format` (streaming always returns text)

**Returns:** AsyncIterator yielding text chunks

**Example:**
```python
async for chunk in llm_service.generate_streaming_completion(
    prompt="Write a detailed analysis of...",
    agent_id="meetmind.architect",
    tenant_id="tenant_123",
    model="gpt-4"
):
    print(chunk, end="", flush=True)
```

#### `get_usage_stats()`

Get LLM usage statistics for monitoring and cost tracking.

**Signature:**
```python
async def get_usage_stats(
    self,
    agent_id: Optional[str] = None,
    tenant_id: Optional[str] = None,
    time_range: str = "24h"
) -> Dict[str, Any]
```

**Parameters:**
- `agent_id` (str, optional): Filter by specific agent
- `tenant_id` (str, optional): Filter by specific tenant
- `time_range` (str, optional): Time range ("1h", "24h", "7d", "30d"). Defaults to "24h"

**Returns:**
```python
{
    "total_requests": int,
    "cached_requests": int,
    "failed_requests": int,
    "total_tokens": int,
    "total_cost": float,
    "average_latency_ms": float,
    "cache_hit_rate": float,
    "provider_breakdown": {
        "openai": int,
        "bedrock": int,
        "genai": int
    },
    "agent_breakdown": {
        "meetmind.coordinator": {...},
        "svea.product_manager": {...}
    }
}
```

**Example:**
```python
stats = await llm_service.get_usage_stats(
    tenant_id="tenant_123",
    time_range="24h"
)

print(f"Total requests: {stats['total_requests']}")
print(f"Total cost: ${stats['total_cost']:.2f}")
print(f"Cache hit rate: {stats['cache_hit_rate']:.1%}")
```

## Provider Configuration

### OpenAI Provider

**Configuration:**
```python
# Environment variables
OPENAI_API_KEY=sk-...
OPENAI_ORG_ID=org-...  # Optional
```

**Supported Models:**
- `gpt-4` - Most capable, highest cost
- `gpt-4-turbo` - Faster, lower cost than GPT-4
- `gpt-3.5-turbo` - Fast, cost-effective for simple tasks

**Pricing (as of 2024):**
- GPT-4: $0.03/1K input tokens, $0.06/1K output tokens
- GPT-4 Turbo: $0.01/1K input tokens, $0.03/1K output tokens
- GPT-3.5 Turbo: $0.0005/1K input tokens, $0.0015/1K output tokens

### AWS Bedrock Provider

**Configuration:**
```python
# Environment variables
AWS_REGION=us-east-1
AWS_ACCESS_KEY_ID=...
AWS_SECRET_ACCESS_KEY=...

# Or use IAM role (recommended for production)
```

**Supported Models:**
- `claude-3-opus` - Most capable Claude model
- `claude-3-sonnet` - Balanced performance and cost
- `claude-3-haiku` - Fastest, most cost-effective

**Pricing (as of 2024):**
- Claude 3 Opus: $0.015/1K input tokens, $0.075/1K output tokens
- Claude 3 Sonnet: $0.003/1K input tokens, $0.015/1K output tokens
- Claude 3 Haiku: $0.00025/1K input tokens, $0.00125/1K output tokens

### Google GenAI Provider

**Configuration:**
```python
# Environment variables
GOOGLE_API_KEY=...
```

**Supported Models:**
- `gemini-1.5-pro` - Most capable Gemini model
- `gemini-1.5-flash` - Fast, cost-effective

**Pricing (as of 2024):**
- Gemini 1.5 Pro: $0.00125/1K input tokens, $0.005/1K output tokens
- Gemini 1.5 Flash: $0.000125/1K input tokens, $0.0005/1K output tokens

## Cache Configuration

### AWS ElastiCache (Production)

**Configuration:**
```python
ELASTICACHE_CLUSTER=happyos-llm-cache.abc123.0001.use1.cache.amazonaws.com:6379
ELASTICACHE_TTL=3600  # Default TTL in seconds
```

**Cache Strategy:**
- Cache key: SHA256 hash of (prompt + model + temperature + max_tokens)
- Default TTL: 1 hour
- Tenant isolation: Keys prefixed with tenant_id
- Eviction policy: LRU (Least Recently Used)

### Local In-Memory Cache (Development)

**Configuration:**
```python
# No configuration needed - automatic fallback
```

**Cache Strategy:**
- Simple Python dict
- No persistence
- Cleared on service restart

## Usage Tracking

### DynamoDB Table (Production)

**Table Name:** `happyos-llm-usage`

**Schema:**
```python
{
    "request_id": str,        # Partition key (UUID)
    "timestamp": str,         # Sort key (ISO 8601)
    "agent_id": str,
    "tenant_id": str,
    "model": str,
    "provider": str,
    "prompt_tokens": int,
    "completion_tokens": int,
    "total_tokens": int,
    "cost": float,
    "latency_ms": int,
    "cached": bool,
    "error": str | None
}
```

**Indexes:**
- GSI1: tenant_id + timestamp (for tenant queries)
- GSI2: agent_id + timestamp (for agent queries)

### Local File Logging (Development)

**Log File:** `logs/llm_usage.log`

**Format:** JSON lines
```json
{"timestamp": "2024-01-15T10:30:00Z", "agent_id": "meetmind.coordinator", "tokens": 450, "cost": 0.027}
```

## Code Examples by Agent Type

### MeetMind Coordinator Agent

```python
from backend.core.interfaces import LLMService
import json

class CoordinatorAgent:
    def __init__(self, llm_service: LLMService):
        self.llm_service = llm_service
        self.agent_id = "meetmind.coordinator"
    
    async def coordinate_meeting_analysis(
        self,
        meeting_data: Dict[str, Any],
        tenant_id: str
    ) -> Dict[str, Any]:
        prompt = f"""
        Analyze this meeting data and create a coordination plan:
        
        Meeting Data: {json.dumps(meeting_data)}
        
        Provide a JSON response with:
        {{
            "workflow_id": "unique_id",
            "analysis_tasks": ["task1", "task2"],
            "priority": "high|medium|low",
            "estimated_duration": "time estimate"
        }}
        """
        
        try:
            response = await self.llm_service.generate_completion(
                prompt=prompt,
                agent_id=self.agent_id,
                tenant_id=tenant_id,
                model="gpt-4",
                temperature=0.3,
                max_tokens=800,
                response_format="json"
            )
            
            coordination_plan = json.loads(response["content"])
            
            return {
                "agent": "coordinator",
                "status": "workflow_started",
                "plan": coordination_plan,
                "cost": response["cost"],
                "cached": response["cached"]
            }
            
        except Exception as e:
            self.logger.error(f"LLM call failed: {e}")
            # Fallback to rule-based logic
            return self._fallback_coordination(meeting_data)
```

### Agent Svea Product Manager (Swedish Language)

```python
from backend.core.interfaces import LLMService
import json

class ProductManagerAgent:
    def __init__(self, llm_service: LLMService):
        self.llm_service = llm_service
        self.agent_id = "svea.product_manager"
    
    async def analyze_regulatory_requirements(
        self,
        regulation_type: str,
        tenant_id: str
    ) -> Dict[str, Any]:
        prompt = f"""
        Analysera svenska regulatoriska krav för {regulation_type}.
        
        Ge svar på svenska i JSON-format:
        {{
            "mandatory_requirements": ["krav1", "krav2"],
            "optional_requirements": ["krav3"],
            "compliance_deadline": "datum",
            "impact_assessment": "beskrivning"
        }}
        """
        
        try:
            response = await self.llm_service.generate_completion(
                prompt=prompt,
                agent_id=self.agent_id,
                tenant_id=tenant_id,
                model="gpt-4",  # GPT-4 has good Swedish support
                temperature=0.2,  # Low for factual responses
                max_tokens=600,
                response_format="json"
            )
            
            return json.loads(response["content"])
            
        except Exception as e:
            self.logger.error(f"LLM call failed: {e}")
            # Fallback to existing rule-based logic
            return self._fallback_analysis(regulation_type)
```

### Felicia's Finance Architect Agent

```python
from backend.core.interfaces import LLMService
import json

class ArchitectAgent:
    def __init__(self, llm_service: LLMService):
        self.llm_service = llm_service
        self.agent_id = "felicia.architect"
    
    async def design_trading_strategy(
        self,
        market_data: Dict[str, Any],
        tenant_id: str
    ) -> Dict[str, Any]:
        prompt = f"""
        Design a trading strategy based on this market data:
        
        Market Data: {json.dumps(market_data)}
        
        Provide a JSON response with:
        {{
            "strategy_type": "momentum|mean_reversion|arbitrage",
            "entry_conditions": ["condition1", "condition2"],
            "exit_conditions": ["condition1", "condition2"],
            "risk_parameters": {{"stop_loss": 0.02, "position_size": 0.1}},
            "expected_return": 0.05
        }}
        """
        
        try:
            response = await self.llm_service.generate_completion(
                prompt=prompt,
                agent_id=self.agent_id,
                tenant_id=tenant_id,
                model="gpt-4-turbo",
                temperature=0.4,  # Balanced for strategy design
                max_tokens=1000,
                response_format="json"
            )
            
            strategy = json.loads(response["content"])
            
            return {
                "agent": "architect",
                "strategy": strategy,
                "model_used": response["model"],
                "cost": response["cost"]
            }
            
        except Exception as e:
            self.logger.error(f"LLM call failed: {e}")
            # Fallback to rule-based strategy
            return self._fallback_strategy(market_data)
```

### Streaming Example (Real-time Analysis)

```python
from backend.core.interfaces import LLMService

class ImplementationAgent:
    def __init__(self, llm_service: LLMService):
        self.llm_service = llm_service
        self.agent_id = "meetmind.implementation"
    
    async def stream_transcript_analysis(
        self,
        transcript: str,
        tenant_id: str,
        callback: Callable[[str], None]
    ):
        prompt = f"""
        Analyze this meeting transcript and provide insights:
        
        Transcript: {transcript}
        
        Provide:
        1. Key discussion points
        2. Action items
        3. Decisions made
        4. Follow-up needed
        """
        
        try:
            async for chunk in self.llm_service.generate_streaming_completion(
                prompt=prompt,
                agent_id=self.agent_id,
                tenant_id=tenant_id,
                model="gpt-4",
                temperature=0.3,
                max_tokens=1500
            ):
                # Send chunk to client via SSE or WebSocket
                callback(chunk)
                
        except Exception as e:
            self.logger.error(f"Streaming failed: {e}")
            callback(f"Error: {str(e)}")
```

## Error Handling Best Practices

### 1. Always Use Try-Except

```python
try:
    response = await llm_service.generate_completion(...)
    return self._process_response(response)
except APIKeyError as e:
    logger.warning(f"API key error: {e}")
    return self._fallback_response()
except RateLimitError as e:
    logger.warning(f"Rate limit exceeded: {e}")
    await asyncio.sleep(60)  # Wait before retry
    return await self._retry_with_backoff()
except TimeoutError as e:
    logger.error(f"Request timeout: {e}")
    return self._fallback_response()
except Exception as e:
    logger.error(f"Unexpected error: {e}")
    return self._fallback_response()
```

### 2. Implement Fallback Logic

Every agent should have rule-based fallback logic:

```python
def _fallback_response(self, data: Dict[str, Any]) -> Dict[str, Any]:
    """Rule-based fallback when LLM is unavailable."""
    return {
        "status": "fallback_mode",
        "result": self._rule_based_analysis(data),
        "warning": "LLM unavailable, using rule-based logic"
    }
```

### 3. Validate LLM Responses

```python
try:
    response = await llm_service.generate_completion(...)
    parsed = json.loads(response["content"])
    
    # Validate required fields
    required_fields = ["workflow_id", "tasks", "priority"]
    if not all(field in parsed for field in required_fields):
        raise ValueError("Missing required fields in LLM response")
    
    return parsed
    
except json.JSONDecodeError:
    logger.error("Invalid JSON from LLM")
    # Retry with more explicit instructions
    return await self._retry_with_explicit_format()
```

## Performance Optimization

### 1. Use Appropriate Models

```python
# Simple tasks: Use GPT-3.5 Turbo or Gemini Flash
response = await llm_service.generate_completion(
    prompt="Extract action items from: ...",
    model="gpt-3.5-turbo",  # 10x cheaper than GPT-4
    ...
)

# Complex analysis: Use GPT-4 or Claude 3 Sonnet
response = await llm_service.generate_completion(
    prompt="Analyze complex regulatory requirements...",
    model="gpt-4",  # Better reasoning
    ...
)
```

### 2. Optimize Prompts

```python
# Bad: Verbose prompt
prompt = """
Please analyze the following meeting transcript and provide a detailed 
analysis including all the key points discussed, action items that were 
mentioned, decisions that were made, and any follow-up items that need 
to be addressed. Here is the transcript: ...
"""

# Good: Concise prompt
prompt = """
Analyze this meeting transcript:

{transcript}

Provide JSON with:
- key_points: [list]
- action_items: [list]
- decisions: [list]
- follow_ups: [list]
"""
```

### 3. Leverage Caching

```python
# Identical prompts are automatically cached
# This call will hit cache if made within TTL
response1 = await llm_service.generate_completion(
    prompt="Analyze GDPR requirements",
    model="gpt-4",
    ...
)

# Same prompt = cache hit (no API call, no cost)
response2 = await llm_service.generate_completion(
    prompt="Analyze GDPR requirements",
    model="gpt-4",
    ...
)

print(response2["cached"])  # True
```

## Monitoring and Observability

### Prometheus Metrics

The LLM service exposes these metrics:

```python
# Request metrics
llm_requests_total{agent="meetmind.coordinator", model="gpt-4", provider="openai"}
llm_request_duration_seconds{agent="meetmind.coordinator", model="gpt-4"}

# Token usage
llm_tokens_used_total{agent="meetmind.coordinator", model="gpt-4", type="input"}
llm_tokens_used_total{agent="meetmind.coordinator", model="gpt-4", type="output"}

# Cache metrics
llm_cache_hits_total{agent="meetmind.coordinator"}
llm_cache_misses_total{agent="meetmind.coordinator"}

# Error metrics
llm_errors_total{agent="meetmind.coordinator", error_type="rate_limit"}
llm_errors_total{agent="meetmind.coordinator", error_type="timeout"}

# Cost metrics
llm_cost_total{agent="meetmind.coordinator", model="gpt-4"}
```

### Grafana Dashboard

Access the LLM usage dashboard at:
```
http://localhost:3000/d/llm-usage
```

Panels include:
- Requests per agent (time series)
- Cost per team (pie chart)
- Latency distribution (histogram)
- Cache hit rate (gauge)
- Error rate per provider (time series)

### CloudWatch Logs (AWS)

```python
# Logs are automatically sent to CloudWatch
# Log group: /aws/happyos/llm-service
# Log stream: {agent_id}/{date}

# Example log entry:
{
    "timestamp": "2024-01-15T10:30:00Z",
    "agent_id": "meetmind.coordinator",
    "tenant_id": "tenant_123",
    "model": "gpt-4",
    "provider": "openai",
    "tokens": 450,
    "cost": 0.027,
    "latency_ms": 1250,
    "cached": false
}
```

## Security and Privacy

### 1. PII Handling

```python
# Always mask PII before sending to LLM
from backend.utils.pii_masker import mask_pii

transcript = "John Smith (john@example.com) discussed..."
masked_transcript = mask_pii(transcript)
# Result: "[NAME] ([EMAIL]) discussed..."

response = await llm_service.generate_completion(
    prompt=f"Analyze: {masked_transcript}",
    ...
)
```

### 2. GDPR Compliance

For Swedish/EU data:
```python
# Use EU-based providers or on-premise models
response = await llm_service.generate_completion(
    prompt=swedish_data,
    model="claude-3-sonnet",  # Bedrock in eu-west-1
    ...
)
```

### 3. API Key Security

```python
# Never hardcode API keys
# ❌ Bad
llm_service = LLMService(api_key="sk-...")

# ✅ Good - use environment variables
llm_service = LLMService(api_key=os.getenv("OPENAI_API_KEY"))

# ✅ Better - use AWS Secrets Manager
llm_service = LLMService(api_key=await secrets_manager.get_secret("openai-key"))
```

## Troubleshooting

### Issue: "API key not found"

**Solution:**
```bash
# Check environment variable
echo $OPENAI_API_KEY

# Set if missing
export OPENAI_API_KEY=sk-...

# Or add to .env file
echo "OPENAI_API_KEY=sk-..." >> .env
```

### Issue: "Rate limit exceeded"

**Solution:**
```python
# Implement exponential backoff
async def call_with_retry(self, prompt: str, max_retries: int = 3):
    for attempt in range(max_retries):
        try:
            return await self.llm_service.generate_completion(prompt, ...)
        except RateLimitError:
            if attempt == max_retries - 1:
                raise
            wait_time = 2 ** attempt  # 1s, 2s, 4s
            await asyncio.sleep(wait_time)
```

### Issue: "Circuit breaker open"

**Solution:**
```bash
# Check circuit breaker status
curl http://localhost:8000/health/llm

# Reset circuit breaker
curl -X POST http://localhost:8000/admin/circuit-breaker/reset

# Check AWS Bedrock status
aws bedrock list-foundation-models --region us-east-1
```

### Issue: "High latency"

**Solution:**
```python
# 1. Use faster models
model="gpt-3.5-turbo"  # Instead of gpt-4

# 2. Reduce max_tokens
max_tokens=300  # Instead of 1000

# 3. Check cache hit rate
stats = await llm_service.get_usage_stats()
print(f"Cache hit rate: {stats['cache_hit_rate']}")

# 4. Use streaming for long responses
async for chunk in llm_service.generate_streaming_completion(...):
    process(chunk)
```

## API Reference Summary

| Method | Purpose | Returns |
|--------|---------|---------|
| `generate_completion()` | Generate text completion | Dict with content, cost, tokens |
| `generate_streaming_completion()` | Stream text completion | AsyncIterator[str] |
| `get_usage_stats()` | Get usage statistics | Dict with metrics |

## Support

For issues or questions:
- GitHub Issues: https://github.com/happyos/issues
- Documentation: https://docs.happyos.ai/llm-service
- Slack: #llm-service channel
