# Design Document

## Overview

The self-building MCP integration transforms the existing autonomous improvement system into a first-class HappyOS agent that communicates via MCP protocol and leverages CloudWatch telemetry for data-driven self-optimization. The design maintains the existing two-tier orchestration (SBO1 for core mechanics, SBO2 for decision-making) while adding MCP server capabilities, CloudWatch streaming, and real LLM integration.

### Key Design Principles

1. **MCP-First Communication**: All inter-agent communication uses MCP protocol with one-way calls and reply-to semantics
2. **Circuit Breaker Resilience**: CloudWatch integration uses circuit breaker pattern with local fallbacks
3. **Non-Invasive Integration**: Existing self-building code remains largely intact; new capabilities are added via composition
4. **Tenant Isolation**: All telemetry analysis and improvements respect tenant boundaries
5. **Gradual Rollout**: Improvements deploy incrementally with automatic rollback on degradation

## Architecture

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    HappyOS Agent Ecosystem                       │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────────┐   │
│  │MeetMind  │  │Agent Svea│  │Felicia's │  │Communication │   │
│  │  Agent   │  │  Agent   │  │ Finance  │  │    Agent     │   │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └──────┬───────┘   │
│       │             │              │                │            │
│       └─────────────┴──────────────┴────────────────┘            │
│                          │ MCP Protocol                          │
│                          ▼                                        │
│       ┌──────────────────────────────────────────┐              │
│       │   Self-Building MCP Server (Port 8004)   │              │
│       │  ┌────────────────────────────────────┐  │              │
│       │  │  FastMCP Server + Authentication   │  │              │
│       │  └────────────────────────────────────┘  │              │
│       │  ┌────────────────────────────────────┐  │              │
│       │  │  MCP Tools:                        │  │              │
│       │  │  - trigger_improvement_cycle       │  │              │
│       │  │  - generate_component              │  │              │
│       │  │  - get_system_status               │  │              │
│       │  │  - query_telemetry_insights        │  │              │
│       │  └────────────────────────────────────┘  │              │
│       └──────────────┬───────────────────────────┘              │
│                      │                                           │
└──────────────────────┼───────────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────────┐
│              Self-Building System (SBO2)                         │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  Ultimate Self-Building System (ultimate_self_building.py)│  │
│  │  - Decision making & approval                             │  │
│  │  - Recursive improvement coordination                     │  │
│  │  - Meta-orchestration                                     │  │
│  └──────────────────┬───────────────────────────────────────┘  │
│                     │                                            │
│                     ▼                                            │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  Core Orchestrator (self_building_orchestrator.py)       │  │
│  │  - Component discovery & registration                     │  │
│  │  - Auto-generation pipeline                               │  │
│  │  - Hot reload management                                  │  │
│  └──────────────────┬───────────────────────────────────────┘  │
│                     │                                            │
│       ┌─────────────┼─────────────┐                             │
│       │             │             │                             │
│       ▼             ▼             ▼                             │
│  ┌─────────┐  ┌─────────┐  ┌──────────────┐                   │
│  │Learning │  │  Code   │  │  Integration │                   │
│  │ Engine  │  │Generator│  │   Manager    │                   │
│  └────┬────┘  └────┬────┘  └──────┬───────┘                   │
│       │            │               │                            │
└───────┼────────────┼───────────────┼────────────────────────────┘
        │            │               │
        ▼            ▼               ▼
┌─────────────────────────────────────────────────────────────────┐
│                    External Services                             │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐ │
│  │  CloudWatch  │  │  LLM Service │  │  Agent Registry      │ │
│  │  - Metrics   │  │  - Bedrock   │  │  - Component Catalog │ │
│  │  - Logs      │  │  - OpenAI    │  │  - Health Status     │ │
│  │  - Events    │  │  - GenAI     │  │                      │ │
│  └──────────────┘  └──────────────┘  └──────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

### Component Interaction Flow

```
User/Agent Request → MCP Server → SBO2 Decision → SBO1 Execution → LLM Generation → Validation → Deployment
                                      ↑                                                              │
                                      │                                                              │
                                      └──────────────── Telemetry Feedback ─────────────────────────┘
                                                        (CloudWatch)
```

## Components and Interfaces

### 1. Self-Building MCP Server

**Location**: `backend/agents/self_building/self_building_mcp_server.py` (new file)

**Purpose**: Expose self-building capabilities as MCP tools for other agents

**Interface**:
```python
from fastapi import FastAPI, Header, HTTPException
from fastmcp import FastMCP
import structlog

app = FastAPI(title="Self-Building MCP Server")
mcp = FastMCP("Self-Building Agent")

@mcp.tool()
async def trigger_improvement_cycle(
    analysis_window_hours: int = 24,
    max_improvements: int = 3,
    tenant_id: str = None
) -> dict:
    """
    Trigger an autonomous improvement cycle.
    
    Args:
        analysis_window_hours: Hours of telemetry to analyze
        max_improvements: Maximum concurrent improvements
        tenant_id: Optional tenant scope
        
    Returns:
        Improvement cycle results with deployed changes
    """
    pass

@mcp.tool()
async def generate_component(
    component_type: str,
    requirements: dict,
    context: dict = None
) -> dict:
    """
    Generate a new system component.
    
    Args:
        component_type: Type of component (skill, agent, service)
        requirements: Component requirements and specifications
        context: Additional context for generation
        
    Returns:
        Generated component details and registration info
    """
    pass

@mcp.tool()
async def get_system_status() -> dict:
    """
    Get comprehensive self-building system status.
    
    Returns:
        System health, active improvements, evolution level
    """
    pass

@mcp.tool()
async def query_telemetry_insights(
    metric_name: str = None,
    time_range_hours: int = 1,
    tenant_id: str = None
) -> dict:
    """
    Query analyzed telemetry insights.
    
    Args:
        metric_name: Specific metric to query
        time_range_hours: Time range for analysis
        tenant_id: Optional tenant filter
        
    Returns:
        Telemetry insights and recommendations
    """
    pass

# Mount MCP at /mcp endpoint
app.mount("/mcp", mcp.get_app())

# Health check
@app.get("/health")
async def health_check():
    return {"status": "healthy", "agent": "self-building"}
```

**Dependencies**:
- FastAPI for HTTP server
- FastMCP for MCP protocol
- SBO2 (ultimate_self_building_system) for orchestration
- Authentication middleware for API key validation

### 2. CloudWatch Telemetry Streamer

**Location**: `backend/core/self_building/intelligence/cloudwatch_streamer.py` (✅ exists)

**Purpose**: Stream CloudWatch metrics, logs, and events into LearningEngine

**Interface**:
```python
from typing import AsyncIterator, Dict, Any, List
import boto3
import asyncio
from datetime import datetime, timedelta
from backend.core.circuit_breaker.circuit_breaker import CircuitBreaker

class CloudWatchTelemetryStreamer:
    """
    Streams CloudWatch telemetry data into the LearningEngine.
    Uses circuit breaker for resilience with local fallback.
    """
    
    def __init__(self, learning_engine):
        self.learning_engine = learning_engine
        self.cloudwatch_client = None
        self.logs_client = None
        self.events_client = None
        self.circuit_breaker = CircuitBreaker(
            failure_threshold=3,
            recovery_timeout=60,
            expected_exception=Exception
        )
        self._initialize_clients()
    
    def _initialize_clients(self):
        """Initialize AWS clients with circuit breaker protection."""
        pass
    
    async def stream_metrics(
        self,
        namespace: str = "MeetMind/MCPUIHub",
        metric_names: List[str] = None,
        dimensions: Dict[str, str] = None,
        period_seconds: int = 300
    ) -> AsyncIterator[Dict[str, Any]]:
        """
        Stream CloudWatch metrics in real-time.
        
        Yields metric data points as they become available.
        Falls back to local metrics if CloudWatch unavailable.
        """
        pass
    
    async def stream_logs(
        self,
        log_group_pattern: str = "/aws/lambda/happyos-*",
        filter_pattern: str = None,
        start_time: datetime = None
    ) -> AsyncIterator[Dict[str, Any]]:
        """
        Stream CloudWatch Logs using Logs Insights.
        
        Yields log events with parsed fields and context.
        Falls back to local log files if CloudWatch unavailable.
        """
        pass
    
    async def subscribe_to_events(
        self,
        event_pattern: Dict[str, Any] = None
    ) -> AsyncIterator[Dict[str, Any]]:
        """
        Subscribe to CloudWatch Events via EventBridge.
        
        Yields events matching the pattern (alarms, Lambda completions, etc).
        Falls back to polling if EventBridge unavailable.
        """
        pass
    
    async def get_alarm_state(
        self,
        alarm_names: List[str] = None
    ) -> Dict[str, str]:
        """
        Get current state of CloudWatch alarms.
        
        Returns alarm states (OK, ALARM, INSUFFICIENT_DATA).
        """
        pass
    
    async def start_streaming(self):
        """Start all telemetry streams and feed into LearningEngine."""
        pass
    
    async def stop_streaming(self):
        """Stop all telemetry streams gracefully."""
        pass
```

**Key Features**:
- Async streaming using `AsyncIterator` for efficient data flow
- Circuit breaker protection with automatic fallback
- Tenant-aware filtering using dimensions
- Configurable sampling for high-volume logs
- Event deduplication to prevent redundant processing

### 3. Enhanced LearningEngine

**Location**: `backend/core/self_building/intelligence/learning_engine.py` (✅ implemented in Task 4)

**Purpose**: Analyze telemetry data and generate improvement insights

**Interface**:
```python
from typing import Dict, Any, List
from dataclasses import dataclass
from datetime import datetime

@dataclass
class TelemetryInsight:
    """Represents an analyzed insight from telemetry data."""
    insight_type: str  # performance_degradation, error_pattern, optimization_opportunity
    severity: str  # low, medium, high, critical
    affected_component: str
    affected_tenants: List[str]
    metrics: Dict[str, float]
    description: str
    recommended_action: str
    confidence_score: float
    timestamp: datetime

@dataclass
class ImprovementOpportunity:
    """Represents a potential system improvement."""
    opportunity_id: str
    title: str
    description: str
    impact_score: float  # 0-100
    effort_estimate: str  # low, medium, high
    affected_components: List[str]
    telemetry_evidence: List[TelemetryInsight]
    proposed_changes: Dict[str, Any]
    risk_level: str  # low, medium, high

class LearningEngine:
    """
    Analyzes telemetry data and generates improvement insights.
    Uses ML models and heuristics to identify optimization opportunities.
    """
    
    def __init__(self):
        self.telemetry_buffer = []
        self.insights_cache = []
        self.ml_models = {}
        self._initialize_models()
    
    def _initialize_models(self):
        """Initialize ML models for pattern recognition."""
        # Placeholder for future ML model integration
        pass
    
    async def ingest_telemetry(
        self,
        telemetry_data: Dict[str, Any],
        source: str  # metrics, logs, events
    ):
        """
        Ingest telemetry data for analysis.
        
        Buffers data and triggers analysis when thresholds met.
        """
        pass
    
    async def analyze_performance_trends(
        self,
        time_window_hours: int = 24,
        tenant_id: str = None
    ) -> List[TelemetryInsight]:
        """
        Analyze performance trends from metrics.
        
        Identifies degradation patterns, anomalies, and optimization opportunities.
        """
        pass
    
    async def analyze_error_patterns(
        self,
        time_window_hours: int = 24,
        tenant_id: str = None
    ) -> List[TelemetryInsight]:
        """
        Analyze error patterns from logs.
        
        Identifies recurring errors, root causes, and fix opportunities.
        """
        pass
    
    async def identify_improvement_opportunities(
        self,
        insights: List[TelemetryInsight]
    ) -> List[ImprovementOpportunity]:
        """
        Convert telemetry insights into actionable improvement opportunities.
        
        Prioritizes by impact score and filters by risk tolerance.
        """
        pass
    
    async def get_insights_summary(
        self,
        time_range_hours: int = 1,
        tenant_id: str = None
    ) -> Dict[str, Any]:
        """
        Get summary of recent insights.
        
        Returns aggregated insights by type and severity.
        """
        pass
```

**Analysis Algorithms**:
1. **Performance Degradation Detection**: Moving average with standard deviation thresholds
2. **Error Pattern Recognition**: Frequency analysis with clustering
3. **Anomaly Detection**: Statistical outlier detection using Z-scores
4. **Impact Scoring**: `impact_score = (performance_gain × affected_users × frequency) / 100`

### 4. LLM-Integrated Code Generator

**Location**: `backend/core/self_building/generators/llm_code_generator.py` (new file)

**Purpose**: Generate production-ready code using real LLM services

**Interface**:
```python
from backend.core.llm.llm_service import LLMService
from backend.core.circuit_breaker.llm_circuit_breaker import LLMCircuitBreaker
from typing import Dict, Any, List

class LLMCodeGenerator:
    """
    Generates code using LLM services with circuit breaker protection.
    Replaces mock code generation with real LLM integration.
    """
    
    def __init__(self):
        self.llm_service = LLMService()
        self.circuit_breaker = LLMCircuitBreaker()
    
    async def generate_component_code(
        self,
        component_type: str,
        requirements: Dict[str, Any],
        context: Dict[str, Any],
        telemetry_insights: List[TelemetryInsight] = None
    ) -> Dict[str, str]:
        """
        Generate component code using LLM.
        
        Args:
            component_type: Type of component to generate
            requirements: Component requirements
            context: System context and patterns
            telemetry_insights: Optional telemetry insights for optimization
            
        Returns:
            Dictionary mapping file paths to generated code
        """
        # Build comprehensive prompt
        prompt = self._build_generation_prompt(
            component_type,
            requirements,
            context,
            telemetry_insights
        )
        
        # Generate with circuit breaker protection
        response = await self.circuit_breaker.call_with_protection(
            self.llm_service.generate_text,
            prompt=prompt,
            max_tokens=4000,
            temperature=0.1
        )
        
        # Parse and validate generated code
        code_files = self._parse_generated_code(response)
        validation_result = await self._validate_code(code_files)
        
        if not validation_result.success:
            raise CodeGenerationError(validation_result.errors)
        
        return code_files
    
    def _build_generation_prompt(
        self,
        component_type: str,
        requirements: Dict[str, Any],
        context: Dict[str, Any],
        telemetry_insights: List[TelemetryInsight]
    ) -> str:
        """
        Build comprehensive prompt for LLM code generation.
        
        Includes:
        - System architecture overview
        - Existing code patterns
        - Component requirements
        - Telemetry insights and optimization goals
        - Code quality standards
        """
        pass
    
    async def generate_improvement_code(
        self,
        opportunity: ImprovementOpportunity,
        existing_code: str
    ) -> Dict[str, str]:
        """
        Generate code improvements for existing components.
        
        Uses diff-based generation to minimize changes.
        """
        pass
    
    async def _validate_code(
        self,
        code_files: Dict[str, str]
    ) -> ValidationResult:
        """
        Validate generated code.
        
        Checks:
        - Syntax correctness
        - Import resolution
        - Type checking
        - Security vulnerabilities
        - Code quality metrics
        """
        pass
```

**Prompt Engineering Strategy**:
- Include system architecture diagrams in prompt
- Provide 3-5 examples of existing code patterns
- Specify quality requirements (test coverage, complexity limits)
- Include telemetry insights as optimization constraints
- Use chain-of-thought prompting for complex components

### 5. Agent Registry Integration

**Location**: `backend/core/registry/agents.py` (modify existing)

**Purpose**: Register self-building agent and enable discovery

**Modifications**:
```python
# Add to existing AgentRegistry class

async def register_self_building_agent(self):
    """Register the self-building agent in the registry."""
    agent_info = {
        "agent_id": "self-building",
        "name": "Self-Building Agent",
        "type": "system",
        "mcp_endpoint": "http://localhost:8004/mcp",
        "capabilities": [
            "autonomous_improvement",
            "code_generation",
            "system_optimization",
            "telemetry_analysis",
            "component_generation"
        ],
        "health_endpoint": "http://localhost:8004/health",
        "version": "1.0.0",
        "status": "active"
    }
    
    await self.register_agent(agent_info)
    logger.info("Self-building agent registered successfully")
```

## Data Models

### Telemetry Data Model

```python
@dataclass
class MetricDataPoint:
    metric_name: str
    value: float
    unit: str
    dimensions: Dict[str, str]
    timestamp: datetime
    tenant_id: str

@dataclass
class LogEvent:
    log_group: str
    log_stream: str
    message: str
    timestamp: datetime
    fields: Dict[str, Any]
    tenant_id: str
    severity: str

@dataclass
class CloudWatchEvent:
    event_type: str  # alarm, lambda_completion, custom
    source: str
    detail: Dict[str, Any]
    timestamp: datetime
    tenant_id: str
```

### Improvement Tracking Model

```python
@dataclass
class ImprovementExecution:
    improvement_id: str
    opportunity: ImprovementOpportunity
    status: str  # pending, generating, validating, deploying, monitoring, completed, failed, rolled_back
    generated_code: Dict[str, str]
    deployment_time: datetime
    monitoring_metrics: Dict[str, List[float]]
    rollback_triggered: bool
    completion_time: datetime
    tenant_id: str
```

## Error Handling

### Circuit Breaker Strategy

```python
# CloudWatch circuit breaker configuration
cloudwatch_circuit_breaker = CircuitBreaker(
    failure_threshold=3,  # Open after 3 failures
    recovery_timeout=60,  # Try recovery after 60 seconds
    expected_exception=(ClientError, NoCredentialsError)
)

# Fallback behavior
async def get_metrics_with_fallback(metric_name, dimensions):
    try:
        return await cloudwatch_circuit_breaker.call_with_protection(
            cloudwatch_client.get_metric_statistics,
            Namespace="MeetMind/MCPUIHub",
            MetricName=metric_name,
            Dimensions=dimensions,
            StartTime=datetime.now() - timedelta(hours=1),
            EndTime=datetime.now(),
            Period=300,
            Statistics=['Average', 'Sum']
        )
    except CircuitBreakerOpen:
        # Fall back to local metrics
        return await local_metrics_service.get_metrics(metric_name, dimensions)
```

### LLM Generation Error Handling

```python
# Retry strategy for LLM generation
async def generate_with_retry(prompt, max_retries=3):
    for attempt in range(max_retries):
        try:
            return await llm_service.generate_text(prompt)
        except (RateLimitError, TimeoutError) as e:
            if attempt < max_retries - 1:
                wait_time = 2 ** attempt  # Exponential backoff
                await asyncio.sleep(wait_time)
                continue
            else:
                raise CodeGenerationError(f"Failed after {max_retries} attempts: {e}")
```

### Improvement Rollback Logic

```python
async def monitor_and_rollback_if_needed(improvement_id, monitoring_duration_seconds=3600):
    """
    Monitor improvement impact and rollback if metrics degrade.
    """
    baseline_metrics = await get_baseline_metrics(improvement_id)
    deployment_time = datetime.now()
    
    while (datetime.now() - deployment_time).total_seconds() < monitoring_duration_seconds:
        await asyncio.sleep(60)  # Check every minute
        
        current_metrics = await get_current_metrics(improvement_id)
        degradation = calculate_degradation(baseline_metrics, current_metrics)
        
        if degradation > 0.10:  # 10% degradation threshold
            logger.warning(f"Improvement {improvement_id} caused {degradation*100}% degradation - rolling back")
            await rollback_improvement(improvement_id)
            return {"rolled_back": True, "reason": "performance_degradation"}
    
    return {"rolled_back": False, "status": "stable"}
```

## Testing Strategy

### Unit Tests

1. **MCP Server Tests**: Test each MCP tool endpoint with mock SBO2
2. **CloudWatch Streamer Tests**: Test streaming with mock boto3 clients
3. **LearningEngine Tests**: Test analysis algorithms with synthetic telemetry
4. **Code Generator Tests**: Test LLM integration with mock responses
5. **Circuit Breaker Tests**: Test failover behavior

### Integration Tests

1. **End-to-End Improvement Cycle**: Trigger cycle, verify code generation, deployment, monitoring
2. **MCP Communication**: Test self-building agent calling other agents and vice versa
3. **CloudWatch Integration**: Test with real CloudWatch (or LocalStack)
4. **Multi-Tenant Isolation**: Verify tenant boundaries in telemetry and improvements

### Performance Tests

1. **Telemetry Throughput**: Measure max metrics/logs per second
2. **Analysis Latency**: Measure time from telemetry to insights
3. **Generation Speed**: Measure LLM code generation time
4. **Memory Usage**: Monitor memory during long-running improvement cycles

## Security Considerations

### Authentication

- MCP server requires Bearer token authentication
- CloudWatch access uses IAM roles with least-privilege permissions
- LLM service uses existing authentication from `backend/core/llm/`

### Authorization

- Tenant-scoped improvements require tenant_id validation
- System-wide improvements require meta-orchestrator approval
- Component generation requests validated against requester capabilities

### Audit Logging

- All improvement cycles logged with audit_logger
- Code generation requests logged with requester identity
- Deployment and rollback events logged with full context
- CloudWatch access logged for compliance

## Deployment Strategy

### Phase 1: MCP Server Setup (Week 1)

1. Create self-building MCP server
2. Register in agent registry
3. Implement basic MCP tools (status, health)
4. Test MCP communication with existing agents

### Phase 2: CloudWatch Integration (Week 2)

1. Implement CloudWatch telemetry streamer
2. Add circuit breaker protection
3. Integrate with LearningEngine
4. Test with real CloudWatch data

### Phase 3: LLM Integration (Week 3)

1. Replace mock code generation with LLM service
2. Implement prompt engineering
3. Add code validation pipeline
4. Test generation quality

### Phase 4: Autonomous Cycles (Week 4)

1. Implement full improvement cycle
2. Add monitoring and rollback logic
3. Test with synthetic improvements
4. Enable in production with monitoring

## Configuration

### Environment Variables

```bash
# Self-Building MCP Server
SELF_BUILDING_MCP_PORT=8004
SELF_BUILDING_MCP_API_KEY=<secret>

# CloudWatch Integration
AWS_REGION=us-east-1
CLOUDWATCH_NAMESPACE=MeetMind/MCPUIHub
CLOUDWATCH_METRICS_PERIOD=300
CLOUDWATCH_LOG_GROUP_PATTERN=/aws/lambda/happyos-*

# Improvement Cycle Configuration
IMPROVEMENT_CYCLE_INTERVAL_HOURS=24
MAX_CONCURRENT_IMPROVEMENTS=3
IMPROVEMENT_QUALITY_THRESHOLD=0.85
IMPROVEMENT_RISK_TOLERANCE=0.1
MONITORING_DURATION_SECONDS=3600
ROLLBACK_DEGRADATION_THRESHOLD=0.10

# LLM Configuration (uses existing backend/core/llm/llm_service.py)
LLM_PROVIDER=bedrock  # bedrock, openai, google_genai
LLM_MODEL=anthropic.claude-v2
LLM_TEMPERATURE=0.1
LLM_MAX_TOKENS=4000
```

### Feature Flags

```python
# backend/core/settings.py additions
class Settings(BaseSettings):
    # Existing settings...
    
    # Self-building feature flags
    enable_self_building: bool = True
    enable_cloudwatch_streaming: bool = True
    enable_autonomous_improvements: bool = False  # Start disabled
    enable_component_generation: bool = True
    enable_improvement_rollback: bool = True
```

## Monitoring and Observability

### Metrics to Track

1. **Improvement Cycle Metrics**:
   - `self_building.improvement_cycles_started`
   - `self_building.improvement_cycles_completed`
   - `self_building.improvements_deployed`
   - `self_building.improvements_rolled_back`

2. **Code Generation Metrics**:
   - `self_building.code_generation_requests`
   - `self_building.code_generation_success_rate`
   - `self_building.code_generation_duration_ms`
   - `self_building.llm_tokens_used`

3. **Telemetry Processing Metrics**:
   - `self_building.telemetry_events_processed`
   - `self_building.insights_generated`
   - `self_building.cloudwatch_api_calls`
   - `self_building.circuit_breaker_opens`

### Dashboards

Create CloudWatch dashboard for self-building system:
- Improvement cycle success rate over time
- Code generation latency distribution
- Telemetry processing throughput
- Circuit breaker state transitions
- Evolution level progression

### Alerts

1. **High Failure Rate**: Alert if improvement success rate < 70%
2. **Circuit Breaker Open**: Alert if CloudWatch circuit breaker stays open > 5 minutes
3. **Rollback Triggered**: Alert on any improvement rollback
4. **Generation Timeout**: Alert if code generation takes > 60 seconds
