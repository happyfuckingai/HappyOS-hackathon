# Agent Architecture Review - Strukturanalys

## Sammanfattning

Jag har granskat alla tre agentsystem (Agent Svea, Felicia's Finance och MeetMind) och identifierat både styrkor och inkonsistenser i hur de använder `backend/core` och `backend/services`.

## Nuvarande Status

### ✅ Agent Svea - BRA STRUKTUR
**Fil**: `backend/agents/agent_svea/agent_svea_mcp_server.py`

**Styrkor**:
- ✅ Använder **ENDAST** `happyos_sdk` imports (inga `backend.*` imports)
- ✅ Använder `create_service_facades()` för backend-åtkomst
- ✅ Har circuit breakers för alla service-typer
- ✅ Implementerar standardiserad MCP-struktur
- ✅ Har self-building integration
- ✅ Metrics collection via `AgentMetricsCollector`

**Struktur**:
```python
from happyos_sdk import (
    create_mcp_client, AgentType, MCPHeaders, MCPResponse, MCPTool,
    create_service_facades, get_circuit_breaker, CircuitBreakerConfig,
    setup_logging, get_error_handler, UnifiedErrorCode
)

# Service facades skapas via SDK
self.services = create_service_facades(self.mcp_client.a2a_client)

# Används som:
await self.services["database"].store_data(...)
```

### ✅ Felicia's Finance - BRA STRUKTUR
**Fil**: `backend/agents/felicias_finance/felicias_finance_mcp_server.py`

**Styrkor**:
- ✅ Använder **ENDAST** `happyos_sdk` imports (inga `backend.*` imports)
- ✅ Implementerar `StandardizedMCPServer` interface
- ✅ Använder `create_service_facades()` för backend-åtkomst
- ✅ Har A2A message handlers för cross-agent communication
- ✅ AWS-native implementation (migrerad från GCP)
- ✅ Self-building integration
- ✅ Metrics collection

**Struktur**:
```python
from happyos_sdk import (
    create_mcp_client, create_a2a_client, create_service_facades,
    MCPClient, MCPHeaders, MCPResponse, MCPTool, AgentType,
    A2AClient, DatabaseFacade, StorageFacade, ComputeFacade,
    CircuitBreaker, get_circuit_breaker, HappyOSSDKError,
    setup_logging, get_logger, create_log_context
)

# Service facades
self.service_facades = create_service_facades(self.a2a_client)

# Används som:
compute_service = self.service_facades["compute"]
database_service = self.service_facades["database"]
```

### ⚠️ MeetMind - BLANDAD STRUKTUR (BEHÖVER STANDARDISERING)
**Fil**: `backend/agents/meetmind/meetmind_mcp_server.py`

**Problem**:
- ❌ Använder **INTE** `happyos_sdk` - har egen implementation
- ❌ Använder **INTE** `create_service_facades()` pattern
- ❌ Har **INTE** standardiserad MCP client struktur
- ❌ Saknar circuit breakers för services
- ⚠️ Har egen `BedrockMeetingClient` istället för att använda shared services
- ⚠️ Har egen `MeetingMemoryService` istället för att använda database facade

**Nuvarande struktur**:
```python
# Använder egna imports istället för happyos_sdk
from .core.bedrock_client import BedrockMeetingClient, get_bedrock_client
from .managers.meeting_memory import MeetingMemoryService, meeting_memory_service

# Ingen service facade pattern
# Direkt användning av Bedrock client
client = _require_bedrock()
structured = await client.generate_structured_json(...)
```

## Identifierade Inkonsistenser

### 1. Import-strategi
- **Agent Svea & Felicia's Finance**: Använder `happyos_sdk` ✅
- **MeetMind**: Använder direkta imports från egna moduler ❌

### 2. Service Access Pattern
- **Agent Svea & Felicia's Finance**: `create_service_facades()` ✅
- **MeetMind**: Direkta service instanser ❌

### 3. Circuit Breaker Implementation
- **Agent Svea**: Har circuit breakers för alla service-typer ✅
- **Felicia's Finance**: Använder circuit breakers via SDK ✅
- **MeetMind**: Saknar circuit breakers ❌

### 4. A2A Communication
- **Agent Svea**: Använder MCP client med A2A ✅
- **Felicia's Finance**: Har både MCP och A2A clients ✅
- **MeetMind**: Saknar A2A integration ❌

### 5. Registry Integration
- **Alla agenter**: Har `registry.py` men olika implementationer ⚠️
- **Problem**: Inkonsistent användning av `backend.core.registry.agents`

## Rekommendationer

### 🎯 Prioritet 1: Standardisera MeetMind

MeetMind behöver refaktoreras för att matcha Agent Svea och Felicia's Finance:

```python
# FÖRE (nuvarande)
from .core.bedrock_client import BedrockMeetingClient
client = get_bedrock_client()
result = await client.generate_structured_json(...)

# EFTER (standardiserad)
from happyos_sdk import create_service_facades, create_mcp_client

self.services = create_service_facades(self.a2a_client)
llm_service = self.services["llm"]
result = await llm_service.generate_completion(
    prompt=prompt,
    agent_id="meetmind",
    tenant_id=tenant_id,
    model="bedrock/claude-3",
    response_format="json"
)
```

### 🎯 Prioritet 2: Unified Service Facade

Alla agenter ska använda samma service facade pattern:

```python
# Standard pattern för ALLA agenter
class StandardizedMCPServer:
    def __init__(self, agent_type: AgentType):
        self.agent_type = agent_type
        self.mcp_client = None
        self.a2a_client = None
        self.services = {}
    
    async def initialize(self):
        # 1. Skapa A2A client
        self.a2a_client = create_a2a_client(
            agent_id=self.agent_id,
            transport_type="inprocess",
            tenant_id=self.tenant_id
        )
        
        # 2. Skapa MCP client
        self.mcp_client = create_mcp_client(
            agent_id=self.agent_id,
            agent_type=self.agent_type,
            transport_type="inprocess"
        )
        
        # 3. Skapa service facades
        self.services = create_service_facades(self.a2a_client)
        
        # Nu tillgängliga:
        # - self.services["database"]
        # - self.services["storage"]
        # - self.services["compute"]
        # - self.services["cache"]
        # - self.services["search"]
        # - self.services["llm"]
```

### 🎯 Prioritet 3: Circuit Breaker Pattern

Alla agenter ska ha circuit breakers:

```python
from happyos_sdk import get_circuit_breaker, CircuitBreakerConfig

# I initialize()
self.circuit_breakers = {}
for service_type in ["llm", "database", "storage", "compute"]:
    self.circuit_breakers[service_type] = get_circuit_breaker(
        service_name=f"{self.agent_id}_{service_type}",
        config=CircuitBreakerConfig(
            failure_threshold=3,
            recovery_timeout=60
        )
    )

# Användning
async def call_llm_with_protection(self, prompt: str):
    circuit_breaker = self.circuit_breakers["llm"]
    
    async def llm_call():
        return await self.services["llm"].generate_completion(prompt=prompt)
    
    return await circuit_breaker.execute(llm_call)
```

### 🎯 Priorit 4: Shared Core Services

Alla agenter ska använda `backend/core` för:

1. **LLM Service** (`backend/core/llm/llm_service.py`)
   - Unified LLM interface
   - Multi-provider support (Bedrock, OpenAI, Anthropic)
   - Caching och cost tracking
   - Metrics collection

2. **Circuit Breaker** (`backend/core/circuit_breaker/`)
   - Standardiserad resilience
   - Health monitoring
   - Fallback management

3. **A2A Protocol** (`backend/core/a2a/`)
   - Agent-to-agent messaging
   - Discovery service
   - Orchestration

4. **Registry** (`backend/core/registry/`)
   - Agent registration
   - Capability discovery
   - Health checks

### 🎯 Prioritet 5: Branschspecifik Kod

Endast branschspecifik logik ska vara unik per agent:

**Agent Svea** (Swedish compliance):
- BAS account validation
- Swedish tax authority integration
- ERPNext synchronization
- GDPR compliance checks

**Felicia's Finance** (Financial services):
- Crypto trading logic
- Portfolio optimization
- Risk assessment
- Banking transactions

**MeetMind** (Meeting intelligence):
- Meeting summarization
- Action item extraction
- Persona-based views
- Email generation

## Föreslagen Mappstruktur

```
backend/agents/
├── shared/                          # Delad kod mellan agenter
│   ├── __init__.py
│   ├── base_mcp_server.py          # Bas-klass för alla MCP servers
│   ├── self_building_discovery.py  # ✅ Finns redan
│   ├── metrics_collector.py        # ✅ Finns redan
│   └── improvement_coordinator.py  # ✅ Finns redan
│
├── agent_svea/
│   ├── agent_svea_mcp_server.py    # ✅ Bra struktur
│   ├── services/                    # Branschspecifik logik
│   │   ├── bas_validator.py
│   │   ├── erp_sync.py
│   │   └── compliance_checker.py
│   └── registry.py
│
├── felicias_finance/
│   ├── felicias_finance_mcp_server.py  # ✅ Bra struktur
│   ├── services/                        # Branschspecifik logik
│   │   ├── crypto_trading.py
│   │   ├── portfolio_optimizer.py
│   │   └── risk_analyzer.py
│   └── registry.py
│
└── meetmind/
    ├── meetmind_mcp_server.py      # ⚠️ Behöver refaktorering
    ├── services/                    # Branschspecifik logik
    │   ├── meeting_summarizer.py
    │   ├── action_extractor.py
    │   └── persona_generator.py
    └── registry.py
```

## Implementationsplan

### Fas 1: Skapa Base Class (1-2 timmar)
```python
# backend/agents/shared/base_mcp_server.py
from happyos_sdk import *

class BaseMCPServer:
    """Base class för alla HappyOS MCP servers."""
    
    def __init__(self, agent_id: str, agent_type: AgentType):
        self.agent_id = agent_id
        self.agent_type = agent_type
        self.mcp_client = None
        self.a2a_client = None
        self.services = {}
        self.circuit_breakers = {}
    
    async def initialize(self):
        """Standard initialization för alla agenter."""
        # A2A client
        self.a2a_client = create_a2a_client(...)
        
        # MCP client
        self.mcp_client = create_mcp_client(...)
        
        # Service facades
        self.services = create_service_facades(self.a2a_client)
        
        # Circuit breakers
        await self._initialize_circuit_breakers()
        
        # Self-building discovery
        await self._initialize_self_building()
    
    async def _initialize_circuit_breakers(self):
        """Initialize circuit breakers för alla services."""
        pass
    
    async def _initialize_self_building(self):
        """Initialize self-building integration."""
        pass
```

### Fas 2: Refaktorera MeetMind (3-4 timmar)
1. Ersätt `BedrockMeetingClient` med `self.services["llm"]`
2. Ersätt `MeetingMemoryService` med `self.services["database"]`
3. Lägg till circuit breakers
4. Lägg till A2A message handlers
5. Implementera `BaseMCPServer`

### Fas 3: Uppdatera Agent Svea & Felicia's Finance (1-2 timmar)
1. Ärv från `BaseMCPServer`
2. Ta bort duplicerad initialization kod
3. Behåll endast branschspecifik logik

### Fas 4: Tester (2-3 timmar)
1. Testa varje agent individuellt
2. Testa A2A communication mellan agenter
3. Testa circuit breaker failover
4. Testa self-building integration

## Sammanfattning

**Nuvarande status**:
- ✅ Agent Svea: Bra struktur, använder happyos_sdk korrekt
- ✅ Felicia's Finance: Bra struktur, använder happyos_sdk korrekt
- ❌ MeetMind: Behöver refaktorering för att matcha standard

**Rekommendation**:
1. Skapa `BaseMCPServer` i `backend/agents/shared/`
2. Refaktorera MeetMind att använda happyos_sdk och service facades
3. Uppdatera alla agenter att ärva från `BaseMCPServer`
4. Flytta branschspecifik logik till `services/` subdirectories
5. Säkerställ att alla använder samma patterns för:
   - Service access (facades)
   - Circuit breakers
   - A2A communication
   - Self-building integration
   - Metrics collection

**Resultat**:
- Konsistent arkitektur över alla agenter
- Enklare underhåll och testning
- Bättre resilience genom standardiserade circuit breakers
- Tydlig separation mellan infrastruktur och branschlogik
