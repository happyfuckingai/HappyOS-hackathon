# HappyOS SDK Unified Error Handling and Logging

## Overview

The HappyOS SDK now provides unified error handling and logging that works seamlessly across both MCP (Model Context Protocol) and Backend Core A2A protocols. This implementation ensures consistent observability patterns across all HappyOS agent systems while maintaining protocol-specific optimizations.

## Key Components

### 1. Unified Error Handling (`error_handling.py`)

**Enhanced Features:**
- **Standardized Error Codes**: 30+ error codes covering MCP, A2A, circuit breaker, tool execution, and compliance scenarios
- **Protocol Translation**: Automatic translation between MCP and A2A error formats
- **Recovery Strategies**: Built-in recovery patterns with exponential backoff
- **Backend Integration**: Seamless integration with existing backend observability systems

**New Error Codes Added:**
```python
# Tool Execution Errors
TOOL_EXECUTION_FAILED = "TOOL_EXEC_001"
TOOL_NOT_FOUND = "TOOL_NOT_FOUND_001"
TOOL_TIMEOUT = "TOOL_TIMEOUT_001"

# Compliance and Business Logic Errors
COMPLIANCE_VIOLATION = "COMPLIANCE_001"
BUSINESS_RULE_VIOLATION = "BUSINESS_RULE_001"
WORKFLOW_ERROR = "WORKFLOW_ERROR_001"
```

**Key Methods:**
- `handle_mcp_error()`: MCP-specific error handling with trace correlation
- `handle_a2a_error()`: A2A-specific error handling with service context
- `handle_tool_error()`: MCP tool execution error handling
- `handle_compliance_error()`: Business rule and compliance violation handling
- `attempt_recovery()`: Automatic error recovery with configurable strategies

### 2. Unified Logging (`logging.py`)

**Enhanced Features:**
- **Structured Logging**: JSON-formatted logs with consistent schema
- **Trace Correlation**: Automatic trace-id and conversation-id propagation
- **Protocol-Aware**: Different log formats for MCP vs A2A operations
- **Backend Integration**: Seamless integration with existing backend logging infrastructure

**Key Components:**
```python
@dataclass
class LogContext:
    trace_id: Optional[str] = None
    conversation_id: Optional[str] = None
    tenant_id: Optional[str] = None
    agent_type: Optional[str] = None
    component: Optional[str] = None
    operation: Optional[str] = None
    user_id: Optional[str] = None
    session_id: Optional[str] = None
```

**Specialized Logging Methods:**
- `log_mcp_call()`: MCP tool calls with target agent and tool name
- `log_mcp_callback()`: MCP async callbacks with reply-to semantics
- `log_a2a_call()`: A2A service calls with service name and action
- `log_circuit_breaker_event()`: Circuit breaker state changes
- `log_unified_error()`: Standardized error logging across protocols

### 3. Unified Observability Manager (`unified_observability.py`)

**New Component Features:**
- **Full Observability Integration**: Combines error handling, logging, metrics, and tracing
- **Protocol Translation**: Seamless translation between MCP and A2A observability patterns
- **Backend Integration**: Automatic integration with CloudWatch, X-Ray, and audit logging
- **Decorator Support**: Automatic instrumentation via decorators

**Key Features:**
```python
class UnifiedObservabilityManager:
    async def execute_with_observability(operation, context, operation_name)
    async def log_mcp_operation(operation_type, target_agent, tool_name, ...)
    async def log_a2a_operation(operation_type, service_name, action, ...)
    async def log_circuit_breaker_event(service_name, event_type, ...)
```

**Observability Decorators:**
```python
@with_mcp_observability(target_agent="agent_svea", tool_name="check_compliance")
async def mcp_function(trace_id=None, conversation_id=None, tenant_id=None):
    # Automatic MCP observability instrumentation
    pass

@with_a2a_observability(service_name="database", action="store_data")
async def a2a_function(trace_id=None, tenant_id=None):
    # Automatic A2A observability instrumentation
    pass
```

## Integration with Existing Systems

### Backend Observability Integration

The unified observability system seamlessly integrates with existing backend components:

```python
# Automatic integration with backend systems when available
try:
    from backend.modules.observability.audit_logger import get_audit_logger
    from backend.modules.observability.cloudwatch import get_cloudwatch_monitor
    from backend.modules.observability.xray_tracing import get_xray_tracer
    BACKEND_OBSERVABILITY_AVAILABLE = True
except ImportError:
    BACKEND_OBSERVABILITY_AVAILABLE = False
```

**Integration Points:**
- **Audit Logging**: Automatic audit trail for security events and compliance violations
- **CloudWatch Metrics**: Protocol-specific metrics with proper dimensions
- **X-Ray Tracing**: Distributed tracing across MCP and A2A calls
- **Structured Logging**: Integration with existing backend logging infrastructure

### MCP Client Integration

The MCP client now includes full observability integration:

```python
# Enhanced MCP client with observability
async def call_tool(self, target_agent, tool_name, arguments, headers, timeout=30.0):
    observability = get_observability_manager("mcp_client", self.agent_type.value)
    
    # Automatic observability instrumentation
    await observability.log_mcp_operation(
        operation_type="tool_call",
        target_agent=target_agent,
        tool_name=tool_name,
        trace_id=headers.trace_id,
        conversation_id=headers.conversation_id,
        tenant_id=headers.tenant_id,
        success=True,
        duration_ms=duration_ms
    )
```

### Service Facade Integration

Service facades now include unified observability:

```python
# Enhanced service facade with observability
async def _call_service(self, action, data, trace_id=None):
    observability = get_observability_manager("service_facade")
    
    context = ObservabilityContext(
        trace_id=trace_id,
        tenant_id=self.tenant_id,
        protocol="a2a",
        service_name=self.service_name,
        action=action
    )
    
    return await observability.execute_with_observability(
        lambda: circuit_breaker.execute(service_call),
        context,
        f"{self.service_name}_{action}"
    )
```

## Error Code Mapping

### MCP Protocol Errors
- `MCP_COMMUNICATION_ERROR`: General MCP communication failures
- `MCP_TOOL_NOT_FOUND`: Requested tool not available on target agent
- `MCP_CALLBACK_FAILED`: Async callback delivery failed
- `MCP_HEADER_INVALID`: Invalid or missing MCP headers
- `MCP_TIMEOUT`: MCP operation timeout

### A2A Protocol Errors
- `A2A_COMMUNICATION_ERROR`: General A2A communication failures
- `A2A_SERVICE_UNAVAILABLE`: Backend service unavailable
- `A2A_TIMEOUT`: A2A operation timeout
- `A2A_AUTHENTICATION_FAILED`: A2A authentication failure

### Circuit Breaker Errors
- `CIRCUIT_BREAKER_OPEN`: Circuit breaker is open, requests blocked
- `CIRCUIT_BREAKER_TIMEOUT`: Circuit breaker timeout
- `SERVICE_DEGRADED`: Service operating in degraded mode
- `FAILOVER_FAILED`: Failover to local implementation failed

### Tool and Business Logic Errors
- `TOOL_EXECUTION_FAILED`: MCP tool execution failed
- `TOOL_TIMEOUT`: MCP tool execution timeout
- `COMPLIANCE_VIOLATION`: Business rule or compliance violation
- `DATA_VALIDATION_ERROR`: Data validation failed

## Metrics and Monitoring

### MCP-Specific Metrics
- `MCPCallSuccess`: Successful MCP tool calls
- `MCPCallError`: Failed MCP tool calls
- `MCPCallDuration`: MCP call duration in milliseconds

**Dimensions:**
- `Component`: SDK component (mcp_client, mcp_server)
- `SourceAgent`: Agent making the call
- `TargetAgent`: Agent receiving the call
- `ToolName`: MCP tool being called
- `Protocol`: Always "mcp"

### A2A-Specific Metrics
- `A2ACallSuccess`: Successful A2A service calls
- `A2ACallError`: Failed A2A service calls
- `A2ACallDuration`: A2A call duration in milliseconds

**Dimensions:**
- `Component`: SDK component (service_facade, a2a_client)
- `AgentType`: Agent making the call
- `ServiceName`: Backend service being called
- `Action`: Service action being performed
- `Protocol`: Always "a2a"

### Circuit Breaker Metrics
- `CircuitBreakerEvent`: Circuit breaker state changes

**Dimensions:**
- `ServiceName`: Service with circuit breaker
- `EventType`: opened, closed, half_open, failed
- `AgentType`: Agent experiencing the event

## Usage Examples

### Basic Error Handling
```python
from happyos_sdk import get_error_handler, UnifiedErrorCode

error_handler = get_error_handler("mcp_client", "agent_svea")

try:
    # Some MCP operation
    result = await mcp_client.call_tool(...)
except Exception as e:
    unified_error = error_handler.handle_mcp_error(e, {
        "trace_id": "trace-123",
        "conversation_id": "conv-456",
        "tenant_id": "tenant-789"
    })
    
    # Log the error
    error_handler.log_error(unified_error)
    
    # Attempt recovery if possible
    if unified_error.recoverable:
        recovery_success = await error_handler.attempt_recovery(unified_error)
```

### Basic Logging
```python
from happyos_sdk import get_logger, create_log_context

logger = get_logger(component="mcp_client", agent_type="meetmind")

context = create_log_context(
    trace_id="trace-123",
    conversation_id="conv-456",
    tenant_id="tenant-789"
)

logger.log_mcp_call(
    target_agent="agent_svea",
    tool_name="check_compliance",
    trace_id="trace-123",
    success=True,
    duration_ms=150.5
)
```

### Full Observability Integration
```python
from happyos_sdk import get_observability_manager, ObservabilityContext

observability = get_observability_manager("service_facade", "felicias_finance")

context = ObservabilityContext(
    trace_id="trace-123",
    tenant_id="tenant-789",
    protocol="a2a",
    service_name="database",
    action="store_data"
)

async def database_operation():
    # Your database operation here
    return {"data_id": "stored-123"}

result = await observability.execute_with_observability(
    database_operation,
    context,
    "store_financial_data"
)
```

## Benefits

### 1. Consistency Across Protocols
- Same error codes and formats for MCP and A2A operations
- Unified logging schema with protocol-specific extensions
- Consistent recovery patterns and retry logic

### 2. Seamless Backend Integration
- Automatic integration with existing CloudWatch, X-Ray, and audit systems
- No changes required to existing backend observability infrastructure
- Graceful degradation when backend systems are unavailable

### 3. Developer Experience
- Simple, consistent APIs across all SDK components
- Automatic instrumentation via decorators
- Rich context propagation with trace correlation

### 4. Operational Excellence
- Comprehensive metrics for both protocols
- Detailed audit trails for compliance and security
- Circuit breaker integration for resilience

### 5. Agent Isolation
- Zero backend.* imports in agent code
- Complete isolation while maintaining observability
- Protocol translation layer handles backend integration

## Requirements Satisfied

This implementation satisfies the following requirements from the specification:

- **6.1, 6.2**: Consistent monitoring and observability across all agent systems
- **6.3, 6.4**: Unified dashboards and distributed tracing with correlation
- **14.1, 14.2**: Consistent error handling and recovery patterns across all agents

The unified observability system ensures that all HappyOS agent systems follow identical patterns for error handling and logging while maintaining the flexibility to optimize for specific protocols (MCP vs A2A).