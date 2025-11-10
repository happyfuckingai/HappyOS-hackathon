# Self-Building MCP Agent

The Self-Building MCP Agent provides autonomous system improvement and code generation capabilities through the Model Context Protocol (MCP).

## Overview

This agent exposes the HappyOS self-building system as an MCP server, allowing other agents and external systems to:
- Trigger autonomous improvement cycles
- Generate new system components
- Query system status and health
- Access telemetry insights

## Architecture

```
Self-Building MCP Server (Port 8004)
├── FastAPI Application
│   ├── CORS Middleware
│   ├── Bearer Token Authentication
│   └── Health Check Endpoint
├── FastMCP Integration
│   └── MCP Tools
│       ├── trigger_improvement_cycle
│       ├── generate_component
│       ├── get_system_status
│       └── query_telemetry_insights
└── Ultimate Self-Building System (SBO2)
    └── Core Self-Building Orchestrator (SBO1)
```

## Files

- `self_building_mcp_server.py` - Main MCP server with FastAPI and tool definitions
- `config.py` - Configuration settings and feature flags
- `registry.py` - Agent registration with HappyOS agent registry
- `__init__.py` - Package initialization

## Configuration

Configuration is managed through environment variables with the `SELF_BUILDING_` prefix:

### Server Configuration
- `SELF_BUILDING_MCP_HOST` - Server host (default: 0.0.0.0)
- `SELF_BUILDING_MCP_PORT` - Server port (default: 8004)
- `SELF_BUILDING_MCP_API_KEY` - API key for authentication

### Feature Flags
- `SELF_BUILDING_ENABLE_SELF_BUILDING` - Enable self-building system (default: true)
- `SELF_BUILDING_ENABLE_AUTONOMOUS_IMPROVEMENTS` - Enable autonomous cycles (default: false)
- `SELF_BUILDING_ENABLE_COMPONENT_GENERATION` - Enable component generation (default: true)
- `SELF_BUILDING_ENABLE_CLOUDWATCH_STREAMING` - Enable CloudWatch telemetry (default: true)
- `SELF_BUILDING_ENABLE_IMPROVEMENT_ROLLBACK` - Enable automatic rollback (default: true)

### Improvement Cycle Configuration
- `SELF_BUILDING_IMPROVEMENT_CYCLE_INTERVAL_HOURS` - Hours between cycles (default: 24)
- `SELF_BUILDING_MAX_CONCURRENT_IMPROVEMENTS` - Max concurrent improvements (default: 3)
- `SELF_BUILDING_MONITORING_DURATION_SECONDS` - Monitoring duration (default: 3600)
- `SELF_BUILDING_ROLLBACK_DEGRADATION_THRESHOLD` - Rollback threshold (default: 0.10)

## MCP Tools

### trigger_improvement_cycle

Triggers an autonomous improvement cycle that analyzes telemetry, identifies opportunities, generates code, and deploys changes.

**Parameters:**
- `analysis_window_hours` (int, default: 24) - Hours of telemetry to analyze
- `max_improvements` (int, default: 3) - Maximum concurrent improvements
- `tenant_id` (str, optional) - Tenant scope for multi-tenant isolation

**Returns:**
```json
{
  "success": true,
  "data": {
    "cycle_id": "uuid",
    "status": "initiated",
    "analysis_window_hours": 24,
    "max_improvements": 3,
    "tenant_id": "system"
  }
}
```

### generate_component

Generates a new system component (skill, agent, service) based on requirements.

**Parameters:**
- `component_type` (str) - Type: "skill", "agent", "service", "plugin"
- `requirements` (dict) - Component requirements and specifications
- `context` (dict, optional) - Additional context for generation

**Returns:**
```json
{
  "success": true,
  "data": {
    "component_id": "uuid",
    "component_type": "skill",
    "component_name": "web_scraper",
    "file_path": "/path/to/component",
    "status": "registered"
  }
}
```

### get_system_status

Returns comprehensive system status including health, evolution level, and component statistics.

**Parameters:** None

**Returns:**
```json
{
  "success": true,
  "data": {
    "system": {
      "initialized": true,
      "running": true,
      "evolution_level": 1.5
    },
    "components": {...},
    "configuration": {...}
  }
}
```

### query_telemetry_insights

Queries analyzed telemetry insights from the LearningEngine.

**Parameters:**
- `metric_name` (str, optional) - Specific metric to query
- `time_range_hours` (int, default: 1) - Time range for analysis
- `tenant_id` (str, optional) - Tenant filter

**Returns:**
```json
{
  "success": true,
  "data": {
    "insights": [...],
    "recommendations": [...]
  }
}
```

## Authentication

All endpoints require Bearer token authentication:

```bash
curl -H "Authorization: Bearer YOUR_API_KEY" \
  http://localhost:8004/health
```

## Health Check

```bash
GET /health
```

Returns:
```json
{
  "status": "ok",
  "agent": "self-building",
  "version": "1.0.0",
  "system_ready": true,
  "system_running": true,
  "features": {
    "autonomous_improvements": false,
    "component_generation": true,
    "cloudwatch_streaming": true,
    "improvement_rollback": true
  }
}
```

## Running the Server

### Standalone Mode

```bash
python backend/agents/self_building/self_building_mcp_server.py
```

### As Part of HappyOS

The server will be started automatically when integrated with `backend/main.py` (see task 2.2).

## Integration with HappyOS

The self-building agent registers itself with the HappyOS agent registry:

```python
from backend.agents.self_building.registry import register_self_building_agent

# During startup
await register_self_building_agent(agent_registry)
```

## Development Status

### ✅ Completed (Task 1)
- FastAPI application with MCP endpoint mounting
- Bearer token authentication middleware
- Health check endpoint
- CORS configuration
- All 4 MCP tools implemented:
  - trigger_improvement_cycle
  - generate_component
  - get_system_status
  - query_telemetry_insights

### 🚧 Pending Implementation
- CloudWatch telemetry streaming (Task 3)
- LearningEngine integration (Task 4)
- LLM code generation (Task 5)
- Autonomous improvement cycles (Task 7)
- Multi-tenant isolation (Task 9)
- Integration tests (Task 13)

## Next Steps

1. **Task 2**: Integrate with agent registry and main.py
2. **Task 3**: Implement CloudWatch telemetry streamer
3. **Task 4**: Create enhanced LearningEngine
4. **Task 5**: Implement LLM-integrated code generator

## License

Part of the HappyOS project.
