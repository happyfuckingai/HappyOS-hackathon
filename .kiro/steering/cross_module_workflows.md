# Agent System Isolation and MCP Communication

## Core Focus: Agent Isolation + A2A Protocol + AWS Native

### MCP Communication Flow (KEEP SIMPLE)
```
Communications Agent (LiveKit + Google Realtime)
        ↓ (MCP calls with reply-to)
Agent Svea MCP Server (isolated)
Felicia's Finance MCP Server (isolated)  
        ↓ (ACK + async callback)
MeetMind MCP Server (fan-in logic)
        ↓ (Results to UI Hub)
MCP UI Hub → Frontend
```

### Required MCP Headers (MINIMAL)
```json
{
  "tenant-id": "multi-tenant isolation",
  "trace-id": "unique per workflow", 
  "reply-to": "mcp://meetmind/ingest_result",
  "caller": "communications_agent"
}
```

### Simple Payloads (NO OVERENGINEERING)
```json
// Basic MCP tool call
{
  "tool": "analyze_financial_data",
  "args": { "meeting_id": "123", "data": {...} }
}

// Basic callback result  
{
  "source": "agent_svea",
  "trace_id": "abc123",
  "result": { "status": "ok", "data": {...} }
}
```

### Simple MCP Workflow (NO COMPLEX ORCHESTRATION)

1. **Communications Agent** makes MCP call with reply-to
2. **Agent** returns ACK immediately  
3. **Agent** processes and sends result to MeetMind
4. **MeetMind** shows result in MCP UI Hub
5. **Done** - Keep it simple!

### Key Principles (FOCUS ON THESE)
- **Complete Isolation**: No backend.* imports in agents
- **MCP Only**: All communication via MCP protocol
- **AWS Native**: Use AWS services throughout
- **Simple Callbacks**: Basic reply-to semantics
- **UI Hub Results**: Show everything in MCP UI Hub

### What NOT to Build
- ❌ Complex workflow orchestration
- ❌ Compensation patterns
- ❌ Complex state machines  
- ❌ Advanced error handling
- ❌ Multi-step workflows

### What TO Focus On
- ✅ Agent isolation validation
- ✅ MCP protocol implementation
- ✅ AWS service integration
- ✅ Basic A2A communication
- ✅ Results in MCP UI Hub

### Repo Layout - Komplett Isolation
```
happyos/
├── backend/                      # ENDAST interna services
│   ├── core/a2a/                 # intern kö/event för retrys (EJ agent-to-agent)
│   ├── services/platform/        # MCP UI Hub + MCP-klient wrapper
│   ├── routes/mcp_ui_routes.py   # flows till UI
│   └── communication_agent/      # orchestrerar MCP workflows
├── meetmind/                     # ISOLERAD MCP server
│   ├── summarizer_mcp_server.py  # tar emot ingest_result + pratar till UI-hub
│   └── livekit_agent/            # lyssnar i rummet (separat process)
├── agent_svea/                   # ISOLERAD MCP server
│   └── svea_mcp_server.py        # ACK + callback till meetmind
└── felicias_finance/             # ISOLERAD MCP server
    └── finance_mcp_server.py     # ACK + callback till meetmind

# KRITISK REGEL: Inga backend.* imports i agent_svea/, felicias_finance/, meetmind/
# ENDAST MCP protocol communication mellan agents
```

### Deployment Isolation
```bash
# Varje MCP server kan deployas oberoende
docker run -p 8001:8001 agent-svea-mcp-server
docker run -p 8002:8002 finance-mcp-server  
docker run -p 8003:8003 meetmind-mcp-server

# Backend services (intern kommunikation)
docker run -p 8000:8000 happy-os-backend
```