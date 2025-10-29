# New Agent Addition Process

## Övergripande mål

Alla nya agenter ska köras som frånkopplade MCP-servrar med endast Global A2A Protocol via MCP. Backend (MCP UI Hub) ska inte ändras för själva agentlogiken, utan enbart för registrering och routing. Infrastructure as Code ska ske med AWS CDK (Python).

## Standardiserad process för nya agenter

### 1. Skapa CDK-stack för agenten

```bash
# Skapa agent-specifik infrastruktur
mkdir -p infra/agents/<agent_namn>/
```

**Generera stackfil i Python:**
```python
# infra/agents/<agent_namn>/stack.py
from aws_cdk import (
    Stack,
    aws_lambda as _lambda,
    aws_apigateway as apigateway,
    aws_iam as iam,
    Duration
)

class AgentMCPStack(Stack):
    def __init__(self, scope, construct_id, **kwargs):
        super().__init__(scope, construct_id, **kwargs)
        
        # Lambda för MCP-servern
        mcp_server = _lambda.Function(
            self, f"{agent_namn}MCPServer",
            runtime=_lambda.Runtime.PYTHON_3_10,
            handler="mcp_server.handler",
            code=_lambda.Code.from_asset(f"../agents/{agent_namn}/"),
            timeout=Duration.seconds(30),
            environment={
                "AGENT_NAME": agent_namn,
                "REPLY_TO_ENDPOINT": "mcp://meetmind/ingest_result"
            }
        )
        
        # IAM-roller - endast nödvändiga AWS-tjänster
        mcp_server.add_to_role_policy(
            iam.PolicyStatement(
                actions=["dynamodb:GetItem", "dynamodb:PutItem"],
                resources=[f"arn:aws:dynamodb:*:*:table/{agent_namn}-*"]
            )
        )
```

### 2. API Gateway-route (om publikt exponerad)

```python
# Lägg till i platformens API Gateway-setup
api_gateway.add_resource(f"mcp/{agent_namn}")
    .add_method("POST", _lambda.LambdaIntegration(mcp_server))
```

### 3. Registrera agenten i Agent Registry

```python
# backend/services/platform/agent_registry.py
AGENT_REGISTRY = {
    "agent_namn": {
        "id": "agent_namn",
        "capabilities": ["tool1", "tool2", "tool3"],
        "healthcheck_endpoint": f"https://api.happyos.com/mcp/{agent_namn}/health",
        "reply_to_address": "mcp://meetmind/ingest_result",
        "auth_method": "signed_headers",
        "mcp_tools": [
            {
                "name": "tool1",
                "description": "Tool description",
                "input_schema": {...},
                "output_schema": {...}
            }
        ],
        "heartbeat_interval": 30,
        "timeout": 10
    }
}
```

### 4. Uppdatera dokumentation

**Structure.md:**
```markdown
### Standalone MCP Servers (Outside Backend)
- `agent_namn/agent_namn_mcp_server.py` - Agent description MCP server
```

**Tech.md:**
```markdown
### MCP Server Development
```bash
# Start Agent Namn MCP Server
cd agent_namn && python agent_namn_mcp_server.py
```

**Deployment docs:**
```markdown
### CDK Stacks
- `infra/agents/agent_namn/` - Agent Namn infrastructure stack
```

### 5. CI/CD-workflows

```yaml
# .github/workflows/agent_namn_deploy.yml
name: Deploy Agent Namn MCP Server

on:
  push:
    paths:
      - 'agents/agent_namn/**'
      - 'infra/agents/agent_namn/**'

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Setup Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.10'
          
      - name: Install dependencies
        run: |
          cd agents/agent_namn
          pip install -r requirements.txt
          
      - name: Run tests
        run: |
          cd agents/agent_namn
          python -m pytest tests/
          
      - name: Deploy CDK stack
        run: |
          cd infra/agents/agent_namn
          cdk deploy --require-approval never
```

### 6. Övervakning och larm

```python
# infra/agents/<agent_namn>/monitoring.py
import aws_cdk.aws_cloudwatch as cloudwatch

# CloudWatch Dashboard
dashboard = cloudwatch.Dashboard(
    self, f"{agent_namn}Dashboard",
    dashboard_name=f"{agent_namn}-mcp-server"
)

# Larm för fel
error_alarm = cloudwatch.Alarm(
    self, f"{agent_namn}ErrorAlarm",
    metric=mcp_server.metric_errors(),
    threshold=5,
    evaluation_periods=2
)

# Larm för latens
latency_alarm = cloudwatch.Alarm(
    self, f"{agent_namn}LatencyAlarm", 
    metric=mcp_server.metric_duration(),
    threshold=5000,  # 5 sekunder
    evaluation_periods=3
)
```

### 7. Smoke tests

```python
# backend/tests/integration/test_agent_namn_mcp.py
import pytest
from backend.services.platform.mcp_client import MCPClient

class TestAgentNamnMCP:
    async def test_agent_registration(self):
        """Test that agent is properly registered"""
        registry = await get_agent_registry()
        assert "agent_namn" in registry
        
    async def test_mcp_tool_call(self):
        """Test MCP tool call with reply-to"""
        client = MCPClient()
        response = await client.call_tool(
            agent="agent_namn",
            tool="tool1", 
            arguments={"test": "data"},
            headers={
                "reply-to": "mcp://meetmind/ingest_result",
                "trace-id": "test-trace-123",
                "tenant-id": "test-tenant"
            }
        )
        assert response.status == "ack"
        
    async def test_heartbeat(self):
        """Test agent heartbeat"""
        health = await check_agent_health("agent_namn")
        assert health.status == "healthy"
```

### 8. Verifiera MCP-isolering

```bash
# Kontrollera att ingen backend.* import finns
grep -r "from backend" agents/agent_namn/
# Ska returnera tomt resultat

# Kontrollera reply-to konfiguration
grep -r "reply_to.*meetmind" agents/agent_namn/
# Ska hitta korrekt konfiguration
```

### 9. Agent MCP Server Template

```python
# agents/agent_namn/agent_namn_mcp_server.py
import asyncio
import json
from mcp import MCPServer, MCPTool
from typing import Dict, Any

class AgentNamnMCPServer:
    def __init__(self):
        self.server = MCPServer("agent_namn")
        self.register_tools()
        
    def register_tools(self):
        @self.server.tool("tool1")
        async def tool1(arguments: Dict[str, Any]) -> Dict[str, Any]:
            """Tool description"""
            # Implementera tool-logik här
            # INGEN backend.* import!
            result = await self.process_tool1(arguments)
            
            # Skicka async callback till MeetMind
            await self.send_callback(result)
            
            return {"status": "ack", "message": "Processing started"}
            
    async def send_callback(self, result: Dict[str, Any]):
        """Skicka resultat till MeetMind via reply-to"""
        callback_data = {
            "source": "agent_namn",
            "trace_id": self.current_trace_id,
            "conversation_id": self.current_conversation_id,
            "kind": "tool1_result",
            "data": result
        }
        
        # Skicka till meetmind/ingest_result
        await self.mcp_client.call_tool(
            "meetmind", 
            "ingest_result", 
            callback_data
        )
        
    async def start(self):
        """Starta MCP server"""
        await self.server.start()
        
if __name__ == "__main__":
    server = AgentNamnMCPServer()
    asyncio.run(server.start())
```

### 10. Validering Checklist

- [ ] CDK-stack skapad i `infra/agents/<agent_namn>/`
- [ ] Agent registrerad i Agent Registry
- [ ] Dokumentation uppdaterad (structure.md, tech.md)
- [ ] CI/CD-workflow skapad
- [ ] CloudWatch monitoring konfigurerat
- [ ] Smoke tests implementerade
- [ ] Ingen `from backend.*` import i agent-kod
- [ ] `reply-to` korrekt konfigurerat mot `meetmind/ingest_result`
- [ ] Heartbeat implementerat
- [ ] IAM-roller begränsade till nödvändiga AWS-tjänster

## Exempel på komplett agent-struktur

```
agents/agent_namn/
├── agent_namn_mcp_server.py    # Huvudserver
├── tools/                      # MCP tools
│   ├── tool1.py
│   └── tool2.py
├── tests/                      # Tester
│   ├── test_tools.py
│   └── test_server.py
├── requirements.txt            # Dependencies (INGEN backend.*)
└── README.md                   # Agent-specifik dokumentation

infra/agents/agent_namn/
├── stack.py                    # CDK stack
├── monitoring.py               # CloudWatch setup
└── app.py                      # CDK app entry point
```

Denna process säkerställer att alla nya agenter följer MCP-arkitekturen med komplett isolation och standardiserad deployment.