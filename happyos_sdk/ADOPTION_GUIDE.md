# HappyOS SDK Adoption Guide

## Quick Start (2 minutes)

### 1. Replace Backend Imports
```python
# ❌ OLD (violates isolation)
from backend.core.a2a.client import A2AClient
from backend.infrastructure.service_facade import DatabaseService

# ✅ NEW (SDK only)
from happyos_sdk import create_mcp_client, AgentType, create_service_facades
```

### 2. Initialize MCP Server
```python
from happyos_sdk import create_mcp_client, AgentType, setup_logging

class MyAgentMCPServer:
    def __init__(self):
        # Setup logging with trace-id correlation
        self.logger = setup_logging("INFO", "json", "my_agent", "my_agent")
        
        # Create MCP client for agent-to-agent communication
        self.mcp_client = create_mcp_client("my_agent", AgentType.AGENT_SVEA)
        
        # Service facades for backend access
        self.services = None
    
    async def initialize(self):
        await self.mcp_client.initialize()
        self.services = create_service_facades(self.mcp_client.a2a_client)
        
        # Register MCP tools
        await self.mcp_client.register_tool(my_tool_definition, self.handle_my_tool)
```

### 3. Implement MCP Tools with Reply-To
```python
async def handle_my_tool(self, arguments: Dict[str, Any], headers: MCPHeaders) -> Dict[str, Any]:
    """Handle MCP tool call with reply-to semantics."""
    
    # 1. Return immediate ACK
    # (MCP client handles this automatically)
    
    # 2. Process asynchronously
    try:
        # Use service facades for backend access
        result = await self.services["database"].store_data(arguments["data"])
        
        # 3. Send callback to reply-to endpoint
        await self.mcp_client.send_callback(
            reply_to=headers.reply_to,
            result={
                "status": "success",
                "data": result,
                "tool_name": "my_tool"
            },
            headers=headers
        )
        
    except Exception as e:
        # Send error callback
        await self.mcp_client.send_callback(
            reply_to=headers.reply_to,
            result={
                "status": "error",
                "error": str(e),
                "tool_name": "my_tool"
            },
            headers=headers
        )
```

## Service Access Patterns

### Database Operations
```python
# Store data with tenant isolation
data_id = await self.services["database"].store_data(
    data={"key": "value"}, 
    data_type="document"
)

# Query with filters
results = await self.services["database"].query_data(
    query={"type": "document"}, 
    limit=10
)
```

### Storage Operations
```python
# Store file with metadata
success = await self.services["storage"].store_file(
    file_key="documents/file.pdf",
    file_data=file_bytes,
    metadata={"type": "pdf", "size": len(file_bytes)}
)
```

### Compute Operations
```python
# Invoke serverless function
result = await self.services["compute"].invoke_function(
    function_name="process_document",
    payload={"document_id": doc_id},
    async_mode=True
)
```

## Error Handling
```python
from happyos_sdk import get_error_handler, UnifiedErrorCode

error_handler = get_error_handler("my_agent", "agent_svea")

try:
    result = await risky_operation()
except Exception as e:
    # Create unified error
    error = error_handler.handle_mcp_error(e, context={
        "trace_id": headers.trace_id,
        "tenant_id": headers.tenant_id
    })
    
    # Log with correlation
    error_handler.log_error(error)
    
    # Attempt recovery
    if await error_handler.attempt_recovery(error):
        result = await risky_operation()  # Retry
```

## Circuit Breaker Usage
```python
from happyos_sdk import get_circuit_breaker, CircuitBreakerConfig

# Get circuit breaker for service
cb = get_circuit_breaker("my_service", CircuitBreakerConfig(
    failure_threshold=3,
    recovery_timeout=30
))

# Execute with protection
result = await cb.execute(lambda: call_external_service())
```

## Validation Checklist

### ✅ Before Deployment
- [ ] Zero `from backend.*` imports: `rg 'from\s+backend\.' my_agent/`
- [ ] MCP server starts successfully
- [ ] Tools respond with immediate ACK
- [ ] Reply-to callbacks work
- [ ] Service facades access backend correctly
- [ ] Circuit breakers trigger on failures
- [ ] Logs show trace-id correlation
- [ ] Health endpoint returns standardized format

### 🧪 Testing
```python
# Test MCP tool call
headers = MCPHeaders(
    tenant_id="test",
    trace_id="test-123",
    conversation_id="conv-123",
    reply_to="mcp://test/callback",
    auth_sig="test-sig",
    caller="test"
)

response = await mcp_client.call_tool(
    target_agent="my_agent",
    tool_name="my_tool",
    arguments={"test": "data"},
    headers=headers
)

assert response.status == "ack"
```

## Common Patterns

### Fan-In Logic (MeetMind)
```python
async def handle_ingest_result(self, arguments: Dict, headers: MCPHeaders):
    """Collect partial results from other agents."""
    trace_id = headers.trace_id
    
    # Store partial result
    self.partial_results[trace_id] = arguments
    
    # Check if all results received
    if self.all_results_received(trace_id):
        combined = self.combine_results(trace_id)
        
        # Send to MCP UI Hub
        await self.send_to_ui_hub(combined, headers)
```

### Cross-Agent Workflow
```python
# Communications Agent initiates workflow
headers = self.mcp_client.create_mcp_headers(
    tenant_id="tenant123",
    reply_to="mcp://meetmind/ingest_result"
)

# Call multiple agents in parallel
await asyncio.gather(
    self.mcp_client.call_tool("agent_svea", "check_compliance", data, headers),
    self.mcp_client.call_tool("felicias_finance", "analyze_risk", data, headers)
)

# Results will be sent to MeetMind via reply-to callbacks
```

That's it! The SDK handles all the complexity - you just focus on your business logic.