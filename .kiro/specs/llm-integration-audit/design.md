# Design Document: LLM Integration för Multiagent Teams

## Overview

Detta dokument beskriver den tekniska designen för att integrera LLM-kapacitet i alla multiagent-team i HappyOS. Designen fokuserar på att ge MeetMind och Agent Svea samma LLM-kapacitet som Felicia's Finance redan har, samtidigt som vi skapar en centraliserad Agent Core-tjänst för enhetlig LLM-åtkomst.

### Current State Analysis (UPPDATERAD)

**Felicia's Finance** (✅ Refaktorerad till LLMService):
- Coordinator, Architect, PM, Implementation, QA: Använder centraliserad LLMService
- Banking Agent: Använder LLMService med Gemini-modell
- **Centraliserad LLM-tjänst** via `backend/core/llm`
- Strukturerade prompts med JSON-svar
- Fallback-funktionalitet implementerad
- **STATUS**: ✅ KORREKT - Använder centraliserad infrastruktur

**MeetMind** (❌ ANVÄNDER FORTFARANDE DIREKT AsyncOpenAI):
- **PROBLEM**: Coordinator och andra agenter använder direkt `AsyncOpenAI` import
- **MÅSTE ÄNDRAS**: Ska använda centraliserad `LLMService` från `backend/core/llm`
- Har LLM-integration men INTE via centraliserad tjänst
- **STATUS**: ❌ FEL ARKITEKTUR - Behöver refaktorering

**Agent Svea** (✅ Korrekt LLMService-integration):
- Coordinator, Architect, PM, Implementation, QA: Använder centraliserad LLMService
- **Centraliserad LLM-tjänst** via dependency injection
- Svenska prompts för compliance och ERP
- Fallback till MCP-server-funktionalitet
- **STATUS**: ✅ KORREKT - Använder centraliserad infrastruktur

### Design Goals

1. **Enhetlighet**: Alla team ska använda samma LLM-tjänst via core-infrastrukturen
2. **Centralisering**: Använd `LLMService` i `backend/core/llm` (liknande `AgentCoreService`)
3. **Resiliens**: Circuit breaker och fallback till regelbaserad logik
4. **Kostnadseffektivitet**: Centraliserad caching och smart routing
5. **Säkerhet**: GDPR-compliant hantering av känslig data
6. **Framtidssäker**: Enkel att lägga till nya LLM-providers
7. **Monitoring**: Centraliserad logging och metrics för alla LLM-anrop

### ❌ FEL Pattern vs ✅ RÄTT Pattern

**❌ FEL - Direkt AsyncOpenAI (MeetMind gör detta nu):**
```python
# ANVÄND INTE DETTA PATTERN!
from openai import AsyncOpenAI
import os

class CoordinatorAgent:
    def __init__(self, services=None):
        # FEL: Direkt AsyncOpenAI-klient
        self.llm_client = AsyncOpenAI(api_key=os.getenv('OPENAI_API_KEY'))
    
    async def some_method(self):
        # FEL: Direkt API-anrop
        response = await self.llm_client.chat.completions.create(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt}]
        )
```

**✅ RÄTT - Centraliserad LLMService (Agent Svea och Felicia's Finance):**
```python
# ANVÄND DETTA PATTERN!
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from backend.core.interfaces import LLMService

class CoordinatorAgent:
    def __init__(self, services=None):
        self.services = services or {}
        # RÄTT: LLMService via dependency injection
        self.llm_service = self.services.get("llm_service")
        if not self.llm_service:
            self.logger.warning("No LLM service provided")
    
    async def some_method(self):
        if not self.llm_service:
            return self._fallback_logic()
        
        # RÄTT: Använd centraliserad service
        response = await self.llm_service.generate_completion(
            prompt=prompt,
            agent_id=self.agent_id,
            tenant_id=tenant_id,
            model="gpt-4",
            temperature=0.3,
            max_tokens=500,
            response_format="json"
        )
        return json.loads(response["content"])
```

**Fördelar med RÄTT pattern:**
- ✅ Centraliserad caching (ElastiCache)
- ✅ Circuit breaker och automatic failover
- ✅ Multi-provider support (OpenAI, Bedrock, GenAI)
- ✅ Centraliserad monitoring och cost tracking
- ✅ Tenant isolation
- ✅ Följer HappyOS arkitektur-standard

## Architecture

### High-Level Architecture (Current State)

```
┌─────────────────────────────────────────────────────────────────┐
│                    HappyOS Platform                              │
│                                                                   │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │  MeetMind    │  │ Agent Svea   │  │  Felicia's   │          │
│  │    Team      │  │    Team      │  │   Finance    │          │
│  │              │  │              │  │    Team      │          │
│  │ ┌──────────┐ │  │ ┌──────────┐ │  │ ┌──────────┐ │          │
│  │ │Coordinator│ │  │ │Coordinator│ │  │ │Coordinator│ │          │
│  │ │  ❌ No LLM│ │  │ │  ❌ No LLM│ │  │ │✅AsyncOpenAI│          │
│  │ │Architect  │ │  │ │Architect  │ │  │ │Architect  │ │          │
│  │ │  ❌ No LLM│ │  │ │  ❌ No LLM│ │  │ │✅AsyncOpenAI│          │
│  │ │PM         │ │  │ │PM         │ │  │ │PM         │ │          │
│  │ │  ❌ No LLM│ │  │ │  ❌ No LLM│ │  │ │✅AsyncOpenAI│          │
│  │ │Implement  │ │  │ │Implement  │ │  │ │Implement  │ │          │
│  │ │  ❌ No LLM│ │  │ │  ❌ No LLM│ │  │ │✅AsyncOpenAI│          │
│  │ │QA         │ │  │ │QA         │ │  │ │QA         │ │          │
│  │ │  ❌ No LLM│ │  │ │  ❌ No LLM│ │  │ │✅AsyncOpenAI│          │
│  │ └───────────┘ │  │ └───────────┘ │  │ │Banking    │ │          │
│  │               │  │               │  │ │✅GenAI    │ │          │
│  │               │  │               │  │ └─────┬─────┘ │          │
│  └───────────────┘  └───────────────┘  └───────┼───────┘          │
│                                                 │                  │
│                                                 │                  │
│                              Environment Variables                │
│                              ┌─────────────────┐                  │
│                              │ OPENAI_API_KEY  │                  │
│                              │GOOGLE_API_KEY   │                  │
│                              └────────┬────────┘                  │
│                                       │                            │
│          ┌────────────────────────────┼────────────────┐          │
│          │                            │                │          │
│    ┌─────▼─────┐              ┌──────▼──────┐  ┌─────▼─────┐    │
│    │  OpenAI   │              │Google GenAI │  │AWS Bedrock│    │
│    │   GPT-4   │              │  Gemini     │  │ (unused)  │    │
│    │           │              │             │  │           │    │
│    │ Used by:  │              │ Used by:    │  │           │    │
│    │ - Felicia │              │ - Banking   │  │           │    │
│    │   Finance │              │   Agent     │  │           │    │
│    └───────────┘              └─────────────┘  └───────────┘    │
└─────────────────────────────────────────────────────────────────┘

**Key Points (UPPDATERAD STATUS):**
- ❌ MeetMind: HAR LLM men använder DIREKT AsyncOpenAI (FEL ARKITEKTUR!)
  - Måste refaktoreras till centraliserad LLMService
  - Använder `from openai import AsyncOpenAI` direkt i agenter
  - Ska använda `backend/core/llm` LLMService istället
- ✅ Agent Svea: KORREKT - Använder centraliserad LLMService via dependency injection
- ✅ Felicia's Finance: KORREKT - Refaktorerad till centraliserad LLMService
- ⚠️ PROBLEM: MeetMind följer inte HappyOS arkitektur-standard
- ✅ LÖSNING: Refaktorera MeetMind till samma pattern som Agent Svea och Felicia's Finance
```

### Component Design

#### 1. Core LLM Service (New Infrastructure Component)

**Location**: `backend/core/llm/llm_service.py`

**Interface Definition** (följer samma mönster som AgentCoreService):
```python
# backend/core/interfaces.py

class LLMService(ABC):
    """Interface for LLM operations with tenant isolation."""
    
    @abstractmethod
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
        """Generate LLM completion."""
        pass
    
    @abstractmethod
    async def generate_streaming_completion(
        self,
        prompt: str,
        agent_id: str,
        tenant_id: str,
        model: str = "gpt-4"
    ) -> AsyncIterator[str]:
        """Generate streaming LLM completion."""
        pass
    
    @abstractmethod
    async def get_usage_stats(
        self,
        agent_id: Optional[str] = None,
        tenant_id: Optional[str] = None,
        time_range: str = "24h"
    ) -> Dict[str, Any]:
        """Get LLM usage statistics."""
        pass
```

**AWS Implementation** (`backend/infrastructure/aws/services/llm_adapter.py`):
```python
class AWSLLMAdapter(LLMService):
    """AWS implementation using Bedrock + OpenAI fallback."""
    
    def __init__(self, region_name: str = "us-east-1"):
        self.bedrock_client = boto3.client('bedrock-runtime', region_name=region_name)
        self.openai_client = AsyncOpenAI(api_key=os.getenv('OPENAI_API_KEY'))
        self.cache_service = AWSElastiCacheAdapter(region_name)
        self.circuit_breaker = CircuitBreaker("llm_service")
    
    async def generate_completion(self, prompt: str, agent_id: str, tenant_id: str, **kwargs):
        # Try cache first
        cache_key = self._generate_cache_key(prompt, kwargs)
        cached = await self.cache_service.get(cache_key, tenant_id)
        if cached:
            return cached
        
        # Try AWS Bedrock with circuit breaker
        try:
            result = await self.circuit_breaker.call(
                self._call_bedrock, prompt, **kwargs
            )
        except CircuitBreakerOpenError:
            # Fallback to OpenAI
            result = await self._call_openai(prompt, **kwargs)
        
        # Cache result
        await self.cache_service.set(cache_key, result, tenant_id, ttl=3600)
        
        # Log usage
        await self._log_usage(agent_id, tenant_id, result)
        
        return result
```

**Local Implementation** (`backend/infrastructure/local/services/llm_service.py`):
```python
class LocalLLMService(LLMService):
    """Local implementation using OpenAI only."""
    
    def __init__(self):
        self.openai_client = AsyncOpenAI(api_key=os.getenv('OPENAI_API_KEY'))
        self.cache = {}  # Simple in-memory cache
    
    async def generate_completion(self, prompt: str, agent_id: str, tenant_id: str, **kwargs):
        # Simple implementation without AWS dependencies
        response = await self.openai_client.chat.completions.create(
            model=kwargs.get('model', 'gpt-4'),
            messages=[{"role": "user", "content": prompt}],
            temperature=kwargs.get('temperature', 0.3),
            max_tokens=kwargs.get('max_tokens', 500)
        )
        
        return {
            "content": response.choices[0].message.content,
            "model": response.model,
            "tokens": response.usage.total_tokens
        }
```

**Why This Approach?**:
- ✅ Följer core-infrastrukturens mönster (AgentCoreService, SearchService, etc.)
- ✅ Centraliserad monitoring och caching
- ✅ Circuit breaker för resiliens
- ✅ Tenant isolation (multi-tenant support)
- ✅ Enkel att lägga till nya providers
- ✅ Framtidssäker arkitektur
- ⚠️ Mer arbete initialt (4-5 veckor)
- ⚠️ Måste refaktorera Felicia's Finance

#### 2. MeetMind Team LLM Integration

**Pattern**: Använd centraliserad LLMService (samma som Agent Svea och Felicia's Finance)

**⚠️ VIKTIGT**: MeetMind ska INTE använda direkt AsyncOpenAI. Alla agenter ska använda centraliserad `backend/core/llm` LLMService.

**Implementation för varje agent**:
```python
# RÄTT PATTERN - Använd LLMService från core
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from backend.core.interfaces import LLMService

class CoordinatorAgent:
    def __init__(self, services: Optional[Dict[str, Any]] = None):
        self.services = services or {}
        self.logger = logging.getLogger(__name__)
        
        # Initialize LLM service via dependency injection (samma som Agent Svea)
        self.llm_service = self.services.get("llm_service")
        if not self.llm_service:
            self.logger.warning("No LLM service provided - running with fallback logic only")
        
        self.agent_id = "meetmind.coordinator"
        self.active_workflows = {}
        
    async def coordinate_meeting_analysis(
        self,
        meeting_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        # Use LLM for intelligent coordination
        prompt = f"""
        Analyze this meeting data and create a coordination plan:
        
        Meeting Data: {meeting_data}
        
        Provide a JSON response with:
        {{
            "workflow_id": "unique_id",
            "analysis_tasks": ["task1", "task2"],
            "priority": "high|medium|low",
            "estimated_duration": "time estimate"
        }}
        """
        
        try:
            # Use centralized LLM service (NOT direct AsyncOpenAI)
            response = await self.llm_service.generate_completion(
                prompt=prompt,
                agent_id=self.agent_id,
                tenant_id=meeting_data.get("tenant_id", "default"),
                model="gpt-4",
                temperature=0.3,
                max_tokens=800,
                response_format="json"
            )
            
            # Parse LLM response
            coordination_plan = json.loads(response["content"])
            
            return {
                "agent": "coordinator",
                "status": "workflow_started",
                "plan": coordination_plan,
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"LLM call failed: {e}")
            # Fallback to rule-based logic
            return self._fallback_coordination(meeting_data)
```

**Specific LLM Use Cases per Agent**:

- **Coordinator**: Workflow orchestration, task prioritization
- **Architect**: Analysis framework design, data pipeline architecture
- **Product Manager**: Requirements analysis, feature prioritization
- **Implementation**: Algorithm implementation, code generation
- **Quality Assurance**: Quality validation, test case generation

#### 3. Agent Svea Team LLM Integration

**Pattern**: Använd centraliserad LLMService med svensk språkfokus

**✅ KORREKT IMPLEMENTATION**: Agent Svea använder redan LLMService från core (bra exempel!)

**Swedish Language Considerations**:
```python
# RÄTT PATTERN - Agent Svea använder redan LLMService
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from backend.core.interfaces import LLMService

class ProductManagerAgent:
    def __init__(self, services=None):
        self.services = services or {}
        self.logger = logging.getLogger(__name__)
        
        # Initialize LLM service via dependency injection (RÄTT!)
        self.llm_service = self.services.get("llm_service")
        if not self.llm_service:
            self.logger.warning("No LLM service provided - running with fallback logic only")
        
        self.agent_id = "svea.product_manager"
    
    async def analyze_regulatory_requirements(
        self,
        regulation_type: str
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
            # Use centralized LLM service (RÄTT!)
            response = await self.llm_service.generate_completion(
                prompt=prompt,
                agent_id=self.agent_id,
                tenant_id="default",  # eller från request context
                model="gpt-4",  # GPT-4 har bra svenskstöd
                temperature=0.2,  # Låg för faktabaserade svar
                max_tokens=600,
                response_format="json"
            )
            
            return json.loads(response["content"])
            
        except Exception as e:
            self.logger.error(f"LLM call failed: {e}")
            # Fallback to existing rule-based logic
            return self._fallback_analysis(regulation_type)
```

**Specific LLM Use Cases per Agent**:

- **Coordinator**: Svenska compliance-workflows, ERP-integration
- **Architect**: ERPNext-arkitektur, svensk systemdesign
- **Product Manager**: Regulatorisk kravanalys, svensk affärslogik
- **Implementation**: ERP-anpassningar, svensk bokföringslogik
- **Quality Assurance**: Compliance-validering, svensk regelverkstest

#### 4. Configuration Management

**Environment Variables** (följer 12-factor app principles):
```bash
# .env file or system environment

# OpenAI (used by MeetMind, Agent Svea, Felicia's Finance)
OPENAI_API_KEY=sk-...

# Google GenAI (used by Banking Agent)
GOOGLE_API_KEY=...

# Optional: AWS Bedrock (for future use)
AWS_REGION=us-east-1
AWS_ACCESS_KEY_ID=...
AWS_SECRET_ACCESS_KEY=...
```

**No ADK Config Changes Needed**:
- Felicia's Finance fungerar redan med miljövariabler
- MeetMind och Agent Svea ska följa samma mönster
- Ingen config-fil behöver uppdateras

#### 5. Error Handling and Fallbacks

**Simple Try-Catch Pattern** (följer Felicia's Finance):
```python
async def some_llm_operation(self, data: Dict[str, Any]) -> Dict[str, Any]:
    try:
        # Try LLM call
        response = await self.llm_client.chat.completions.create(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=500
        )
        
        return self._parse_llm_response(response)
        
    except Exception as e:
        self.logger.error(f"LLM call failed: {e}")
        # Fall back to rule-based logic
        return self._fallback_logic(data)
```

**Fallback Strategy**:
1. Primary: OpenAI GPT-4 (via miljövariabel)
2. Fallback: Befintlig regelbaserad logik (redan implementerad)

**No Complex Circuit Breakers Needed**:
- Enkel try-catch räcker (samma som Felicia's Finance)
- AsyncOpenAI har inbyggd retry-logik
- Fallback till regelbaserad logik vid fel

#### 6. Logging (Simple Approach)

**Basic Logging** (följer befintligt mönster):
```python
self.logger.info(f"LLM call for {self.agent_id}")
self.logger.error(f"LLM call failed: {error}")
self.logger.warning(f"Using fallback logic for {operation}")
```

**No Complex Monitoring Initially**:
- Använd befintlig logging-infrastruktur
- Kan lägga till Prometheus metrics senare om behövs
- Fokus på att få LLM-integration att fungera först

## Data Models

### LLM Request Model
```python
@dataclass
class LLMRequest:
    agent_id: str
    team: str
    prompt: str
    model: str
    temperature: float
    max_tokens: int
    response_format: str
    metadata: Dict[str, Any]
    timestamp: datetime
```

### LLM Response Model
```python
@dataclass
class LLMResponse:
    request_id: str
    agent_id: str
    content: str
    model: str
    provider: str
    tokens_used: int
    estimated_cost: float
    latency_ms: int
    cached: bool
    timestamp: datetime
```

### Usage Statistics Model
```python
@dataclass
class LLMUsageStats:
    agent_id: str
    team: str
    time_range: str
    total_requests: int
    cached_requests: int
    failed_requests: int
    total_tokens: int
    total_cost: float
    average_latency_ms: float
    provider_breakdown: Dict[str, int]
```

## Error Handling

### Error Types and Handling

**1. API Key Missing/Invalid**:
```python
try:
    response = await llm_service.generate_completion(...)
except APIKeyError as e:
    logger.warning(f"LLM API key error: {e}")
    # Fall back to rule-based logic
    return self._fallback_response()
```

**2. Rate Limit Exceeded**:
```python
try:
    response = await llm_service.generate_completion(...)
except RateLimitError as e:
    logger.warning(f"LLM rate limit exceeded: {e}")
    # Wait and retry with exponential backoff
    await asyncio.sleep(retry_delay)
    return await self._retry_with_backoff()
```

**3. Timeout**:
```python
try:
    response = await asyncio.wait_for(
        llm_service.generate_completion(...),
        timeout=30.0
    )
except asyncio.TimeoutError:
    logger.error("LLM request timeout")
    # Try fallback provider
    return await self._try_fallback_provider()
```

**4. Invalid Response Format**:
```python
try:
    parsed_response = json.loads(llm_response.content)
except json.JSONDecodeError:
    logger.error("Invalid JSON response from LLM")
    # Retry with more explicit instructions
    return await self._retry_with_explicit_format()
```

## Testing Strategy

### Unit Tests
- Mock LLM responses för snabba tester
- Testa fallback-logik
- Testa error handling
- Testa cache-funktionalitet

### Integration Tests
- Testa mot riktiga LLM-API:er (med test-nycklar)
- Testa circuit breaker-beteende
- Testa provider failover
- Testa cost tracking

### Performance Tests
- Mät latens för LLM-anrop
- Testa cache-effektivitet
- Testa concurrent requests
- Testa rate limiting

### Example Test
```python
@pytest.mark.asyncio
async def test_meetmind_coordinator_llm_integration():
    # Arrange
    coordinator = CoordinatorAgent()
    meeting_data = {"meeting_id": "test123", "participants": 5}
    
    # Act
    result = await coordinator.coordinate_meeting_analysis(meeting_data)
    
    # Assert
    assert result["status"] == "workflow_started"
    assert "workflow_id" in result
    assert result["agent"] == "coordinator"
    
    # Verify LLM was called
    assert coordinator.llm_service.total_requests > 0
```

## Security Considerations

### Data Privacy
- **PII Masking**: Maskera personuppgifter innan LLM-anrop
- **Data Residency**: Använd EU-baserade LLM-providers för GDPR-compliance
- **Audit Logging**: Logga alla LLM-anrop för compliance

### API Key Management
- Lagra nycklar i AWS Secrets Manager
- Rotera nycklar regelbundet
- Använd olika nycklar per miljö (dev, staging, prod)

### Rate Limiting
- Implementera per-agent rate limits
- Implementera per-team rate limits
- Implementera global rate limits

## Performance Optimization

### Caching Strategy
- Cache vanliga prompts (1 hour TTL)
- Cache regelverksanalyser (24 hour TTL)
- Cache dokumentation (7 days TTL)

### Prompt Optimization
- Använd kortare prompts när möjligt
- Använd few-shot learning istället för långa instruktioner
- Batch multiple questions i en prompt

### Model Selection
- Använd GPT-3.5-turbo för enkla uppgifter
- Använd GPT-4 för komplexa analyser
- Använd Gemini Flash för snabba svar

## Migration Plan (Simplified)

### Phase 1: MeetMind Integration (Week 1)
1. Lägg till AsyncOpenAI import i alla 5 agenter
2. Initiera llm_client i __init__ (samma som Felicia's Finance)
3. Implementera LLM-anrop i key methods
4. Implementera fallback-logik
5. Testa med OPENAI_API_KEY miljövariabel

### Phase 2: Agent Svea Integration (Week 2)
1. Lägg till AsyncOpenAI import i alla 5 agenter
2. Initiera llm_client i __init__ (samma som Felicia's Finance)
3. Implementera LLM-anrop med svenskfokus
4. Implementera fallback-logik
5. Testa med OPENAI_API_KEY miljövariabel

### Phase 3: Testing and Documentation (Week 3)
1. Integration testing för alla agenter
2. Testa fallback-funktionalitet
3. Dokumentera LLM-användning
4. Uppdatera README med miljövariabel-krav
5. Production deployment

**Total tid: 3 veckor** (istället för 4 veckor med Agent Core)

## Success Metrics

- **Coverage**: 100% av agenter har LLM-integration
- **Availability**: 99.9% uptime för Agent Core LLM Service
- **Latency**: < 2 sekunder median svarstid
- **Cost**: < $100/dag för alla LLM-anrop
- **Cache Hit Rate**: > 30% för vanliga queries
- **Error Rate**: < 1% för LLM-anrop
