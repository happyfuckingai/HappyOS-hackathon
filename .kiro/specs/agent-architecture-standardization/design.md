# Design Document

## Overview

This design document outlines the standardization of the HappyOS agent architecture through the creation of a BaseMCPServer class and refactoring of all agents (Agent Svea, Felicia's Finance, and MeetMind) to use consistent patterns. The design eliminates architectural inconsistencies while preserving domain-specific functionality.

## Architecture

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    HappyOS Agent System                      │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │ Agent Svea   │  │  Felicia's   │  │  MeetMind    │      │
│  │              │  │   Finance    │  │              │      │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘      │
│         │                  │                  │              │
│         └──────────────────┴──────────────────┘              │
│                            │                                 │
│                   ┌────────▼────────┐                        │
│                   │ BaseMCPServer   │                        │
│                   │  (Base Class)   │                        │
│                   └────────┬────────┘                        │
│                            │                                 │
│         ┌──────────────────┼──────────────────┐             │
│         │                  │                  │             │
│    ┌────▼────┐      ┌─────▼─────┐     ┌─────▼─────┐       │
│    │   MCP   │      │    A2A    │     │  Service  │       │
│    │  Client │      │  Client   │     │  Facades  │       │
│    └────┬────┘      └─────┬─────┘     └─────┬─────┘       │
│         │                  │                  │             │
│         └──────────────────┴──────────────────┘             │
│                            │                                 │
│                   ┌────────▼────────┐                        │
│                   │  HappyOS SDK    │                        │
│                   └─────────────────┘                        │
└─────────────────────────────────────────────────────────────┘
```

### Component Hierarchy

```
backend/agents/
├── shared/
│   ├── base_mcp_server.py          # BaseMCPServer class
│   ├── self_building_discovery.py  # Existing
│   ├── metrics_collector.py        # Existing
│   └── improvement_coordinator.py  # Existing
│
├── agent_svea/
│   ├── agent_svea_mcp_server.py    # Inherits BaseMCPServer
│   └── services/                    # Domain-specific logic
│       ├── bas_validator.py
│       ├── erp_sync.py
│       └── compliance_checker.py
│
├── felicias_finance/
│   ├── felicias_finance_mcp_server.py  # Inherits BaseMCPServer
│   └── services/                        # Domain-specific logic
│       ├── crypto_trading.py
│       ├── portfolio_optimizer.py
│       └── risk_analyzer.py
│
└── meetmind/
    ├── meetmind_mcp_server.py      # Refactored to inherit BaseMCPServer
    └── services/                    # Domain-specific logic
        ├── meeting_summarizer.py
        ├── action_extractor.py
        └── persona_generator.py
```

## Components and Interfaces

### 1. BaseMCPServer Class

**Location:** `backend/agents/shared/base_mcp_server.py`

**Purpose:** Provides standardized initialization, service access, circuit breakers, and A2A communication for all agents.

**Key Responsibilities:**
- Initialize MCP and A2A clients
- Create service facades for backend access
- Configure circuit breakers for resilience
- Integrate with self-building agent
- Provide standardized health status
- Handle MCP tool registration
- Manage A2A message handlers

**Interface:**

```python
class BaseMCPServer:
    """Base class for all HappyOS MCP servers."""
    
    def __init__(
        self,
        agent_id: str,
        agent_type: AgentType,
        config: Optional[Dict[str, Any]] = None
    ):
        """Initialize base MCP server."""
        pass
    
    async def initialize(self) -> bool:
        """Initialize all components."""
        pass
    
    async def _initialize_mcp_client(self) -> None:
        """Initialize MCP client for agent-to-agent communication."""
        pass
    
    async def _initialize_a2a_client(self) -> None:
        """Initialize A2A client for messaging."""
        pass
    
    async def _initialize_service_facades(self) -> None:
        """Create service facades for backend access."""
        pass
    
    async def _initialize_circuit_breakers(self) -> None:
        """Configure circuit breakers for all services."""
        pass
    
    async def _initialize_self_building(self) -> None:
        """Initialize self-building agent integration."""
        pass
    
    async def register_mcp_tool(
        self,
        tool: MCPTool,
        handler: Callable
    ) -> None:
        """Register an MCP tool with its handler."""
        pass
    
    async def register_a2a_handler(
        self,
        message_type: str,
        handler: Callable
    ) -> None:
        """Register an A2A message handler."""
        pass
    
    async def call_service_with_circuit_breaker(
        self,
        service_type: str,
        operation: Callable,
        *args,
        **kwargs
    ) -> Any:
        """Execute service call with circuit breaker protection."""
        pass
    
    async def get_health_status(self) -> Dict[str, Any]:
        """Get standardized health status."""
        pass
    
    async def shutdown(self) -> None:
        """Gracefully shutdown the server."""
        pass
```

### 2. Service Facade Pattern

**Purpose:** Provide unified access to backend services through standardized interfaces.

**Service Types:**
- **Database Service** (`self.services["database"]`)
  - `store_data(data, data_type, trace_id)`
  - `query_data(query, limit)`
  - `update_data(data_id, updates)`
  - `delete_data(data_id)`

- **Storage Service** (`self.services["storage"]`)
  - `store_file(file_key, file_data, metadata)`
  - `retrieve_file(file_key)`
  - `delete_file(file_key)`
  - `list_files(prefix)`

- **Compute Service** (`self.services["compute"]`)
  - `invoke_function(function_name, payload)`
  - `schedule_job(job_config)`
  - `get_job_status(job_id)`

- **Cache Service** (`self.services["cache"]`)
  - `get(key)`
  - `set(key, value, ttl)`
  - `delete(key)`
  - `exists(key)`

- **Search Service** (`self.services["search"]`)
  - `index_document(doc_id, document)`
  - `search(query, filters, limit)`
  - `delete_document(doc_id)`

- **LLM Service** (`self.services["llm"]`)
  - `generate_completion(prompt, model, parameters)`
  - `generate_structured_json(prompt, schema, model)`
  - `embed_text(text, model)`

### 3. Circuit Breaker Configuration

**Purpose:** Provide resilience through failure detection and recovery.

**Configuration Strategy:**

| Service Type | Failure Threshold | Recovery Timeout | Rationale |
|-------------|------------------|------------------|-----------|
| Database | 3 | 60s | Critical service, moderate recovery |
| Storage | 5 | 90s | Less critical, longer recovery |
| Compute | 3 | 120s | Complex operations, longer recovery |
| Cache | 5 | 30s | Non-critical, fast recovery |
| Search | 4 | 45s | Moderate criticality |
| LLM | 2 | 120s | Expensive operations, careful recovery |

**Circuit Breaker States:**
- **Closed:** Normal operation, requests pass through
- **Open:** Failures detected, requests fail immediately
- **Half-Open:** Testing recovery, limited requests allowed

### 4. Agent-Specific Implementations

#### Agent Svea

**Domain-Specific Services:**
- `BASValidator`: Validates Swedish BAS account structure
- `ERPSyncService`: Synchronizes with ERPNext
- `ComplianceChecker`: Validates Swedish regulatory compliance

**MCP Tools:**
- `check_swedish_compliance`
- `validate_bas_account`
- `sync_erp_document`
- `generate_sie_export`
- `validate_invoice`

#### Felicia's Finance

**Domain-Specific Services:**
- `CryptoTradingService`: Executes cryptocurrency trades
- `PortfolioOptimizer`: Optimizes investment portfolios
- `RiskAnalyzer`: Analyzes financial risk

**MCP Tools:**
- `analyze_financial_risk`
- `execute_crypto_trade`
- `process_banking_transaction`
- `optimize_portfolio`
- `get_market_analysis`

#### MeetMind

**Domain-Specific Services:**
- `MeetingSummarizer`: Generates meeting summaries
- `ActionExtractor`: Extracts action items
- `PersonaGenerator`: Creates persona-specific views

**MCP Tools:**
- `generate_meeting_summary`
- `extract_action_items`
- `generate_persona_view`
- `generate_stakeholder_email`
- `analyze_meeting_sentiment`

## Data Models

### BaseMCPServer Configuration

```python
@dataclass
class BaseMCPServerConfig:
    """Configuration for BaseMCPServer."""
    agent_id: str
    agent_type: AgentType
    tenant_id: str = "default"
    transport_type: str = "inprocess"
    enable_metrics: bool = True
    enable_self_building: bool = True
    circuit_breaker_configs: Dict[str, CircuitBreakerConfig] = field(default_factory=dict)
```

### Service Facade Registry

```python
@dataclass
class ServiceFacadeRegistry:
    """Registry of available service facades."""
    database: DatabaseFacade
    storage: StorageFacade
    compute: ComputeFacade
    cache: CacheFacade
    search: SearchFacade
    llm: LLMFacade
```

### Circuit Breaker State

```python
@dataclass
class CircuitBreakerState:
    """State of a circuit breaker."""
    service_name: str
    state: str  # "closed", "open", "half_open"
    failure_count: int
    last_failure_time: Optional[datetime]
    last_success_time: Optional[datetime]
    is_healthy: bool
```

### Health Status Response

```python
@dataclass
class AgentHealthStatus:
    """Standardized health status response."""
    agent_id: str
    agent_type: str
    status: str  # "healthy", "degraded", "unhealthy"
    timestamp: datetime
    components: Dict[str, ComponentHealth]
    circuit_breakers: Dict[str, CircuitBreakerState]
    self_building_status: Optional[SelfBuildingStatus]
    metrics: Optional[AgentMetrics]
```

## Error Handling

### Error Hierarchy

```
HappyOSError
├── MCPError
│   ├── MCPClientError
│   ├── MCPToolError
│   └── MCPTransportError
├── A2AError
│   ├── A2AMessageError
│   ├── A2ARoutingError
│   └── A2ATimeoutError
├── ServiceError
│   ├── DatabaseError
│   ├── StorageError
│   ├── ComputeError
│   ├── CacheError
│   ├── SearchError
│   └── LLMError
└── CircuitBreakerError
    ├── CircuitOpenError
    └── CircuitBreakerConfigError
```

### Error Handling Strategy

1. **Service-Level Errors:**
   - Caught by circuit breakers
   - Logged with trace_id
   - Metrics recorded
   - Fallback responses provided

2. **Circuit Breaker Errors:**
   - Immediate failure response
   - No retry attempts
   - Health status updated
   - Alerts triggered

3. **MCP Tool Errors:**
   - Wrapped in MCPResponse
   - Error details included
   - Async callback sent
   - Client notified

4. **A2A Communication Errors:**
   - Retry with exponential backoff
   - Dead letter queue for failed messages
   - Timeout handling
   - Circuit breaker protection

## Testing Strategy

### Unit Tests

**BaseMCPServer Tests:**
- Test initialization of all components
- Test service facade creation
- Test circuit breaker configuration
- Test health status generation
- Test error handling

**Service Facade Tests:**
- Test each service type independently
- Mock backend services
- Verify correct method calls
- Test error propagation

**Circuit Breaker Tests:**
- Test state transitions
- Test failure detection
- Test recovery behavior
- Test timeout handling

### Integration Tests

**Agent Integration Tests:**
- Test complete agent initialization
- Test MCP tool registration
- Test A2A message handling
- Test service facade usage
- Test circuit breaker integration

**Cross-Agent Tests:**
- Test A2A communication between agents
- Test MCP tool invocation
- Test reply-to semantics
- Test error propagation

### End-to-End Tests

**System Tests:**
- Test complete workflows
- Test failure scenarios
- Test recovery behavior
- Test self-building integration
- Test metrics collection

## Migration Strategy

### Phase 1: Create BaseMCPServer (No Breaking Changes)

1. Create `backend/agents/shared/base_mcp_server.py`
2. Implement all base functionality
3. Add comprehensive unit tests
4. Document API and usage patterns

### Phase 2: Refactor Agent Svea (Validation)

1. Update Agent Svea to inherit from BaseMCPServer
2. Remove duplicated initialization code
3. Verify all existing functionality works
4. Run integration tests
5. Deploy and monitor

### Phase 3: Refactor Felicia's Finance (Validation)

1. Update Felicia's Finance to inherit from BaseMCPServer
2. Remove duplicated initialization code
3. Verify all existing functionality works
4. Run integration tests
5. Deploy and monitor

### Phase 4: Refactor MeetMind (Major Changes)

1. Create domain-specific services:
   - `MeetingSummarizer` (replaces BedrockMeetingClient usage)
   - `ActionExtractor`
   - `PersonaGenerator`
2. Update MeetMind to inherit from BaseMCPServer
3. Replace BedrockMeetingClient with `self.services["llm"]`
4. Replace MeetingMemoryService with `self.services["database"]`
5. Add circuit breakers for all service calls
6. Add A2A message handlers
7. Run comprehensive tests
8. Deploy and monitor

### Phase 5: Cleanup and Documentation

1. Remove deprecated code
2. Update documentation
3. Create migration guide
4. Update deployment scripts
5. Final system tests

## Performance Considerations

### Initialization Performance

- **Target:** < 2 seconds for complete agent initialization
- **Strategy:** Parallel initialization of independent components
- **Monitoring:** Track initialization time metrics

### Service Call Performance

- **Target:** < 100ms overhead for circuit breaker checks
- **Strategy:** In-memory circuit breaker state
- **Monitoring:** Track service call latency

### Memory Usage

- **Target:** < 50MB base memory per agent
- **Strategy:** Lazy initialization of heavy components
- **Monitoring:** Track memory usage metrics

### Scalability

- **Target:** Support 100+ concurrent MCP tool calls per agent
- **Strategy:** Async/await throughout, connection pooling
- **Monitoring:** Track concurrent request metrics

## Security Considerations

### Authentication

- MCP API key validation for all endpoints
- SSE token generation and validation
- Tenant isolation enforcement

### Authorization

- Tool-level access control
- Service-level permissions
- Tenant-scoped data access

### Data Protection

- Encryption in transit (TLS)
- Encryption at rest (AWS KMS)
- PII handling compliance
- Audit logging

### Circuit Breaker Security

- Prevent denial of service through rate limiting
- Protect against cascading failures
- Secure circuit breaker state storage

## Monitoring and Observability

### Metrics Collection

**Agent Metrics:**
- Request count by tool
- Request latency by tool
- Error rate by tool
- Circuit breaker state changes

**Service Metrics:**
- Service call count by type
- Service call latency by type
- Service error rate by type
- Circuit breaker trips by service

**System Metrics:**
- Active agent count
- Total request throughput
- System error rate
- Resource utilization

### Logging Strategy

**Structured Logging:**
- JSON format
- Trace ID propagation
- Tenant ID inclusion
- Error context capture

**Log Levels:**
- DEBUG: Detailed execution flow
- INFO: Normal operations
- WARNING: Degraded performance
- ERROR: Operation failures
- CRITICAL: System failures

### Tracing

- Distributed tracing with trace IDs
- Span creation for service calls
- Cross-agent trace propagation
- Performance bottleneck identification

## Deployment Considerations

### Backward Compatibility

- Maintain existing MCP tool interfaces
- Preserve A2A message formats
- Support gradual rollout
- Enable feature flags

### Rollback Strategy

- Keep previous agent versions deployed
- Blue-green deployment support
- Quick rollback capability
- Health check validation

### Configuration Management

- Environment-based configuration
- Secret management (AWS Secrets Manager)
- Dynamic configuration updates
- Configuration validation

## Success Criteria

1. **Code Consistency:** All agents inherit from BaseMCPServer
2. **Import Compliance:** Zero `backend.*` imports in agent code
3. **Test Coverage:** > 80% code coverage for BaseMCPServer
4. **Performance:** No degradation in agent response times
5. **Reliability:** Circuit breakers prevent cascading failures
6. **Maintainability:** 50% reduction in duplicated code
7. **Documentation:** Complete API documentation and migration guide
