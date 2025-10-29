# Project Structure

## Root Directory Organization

```
happy-os/
├── backend/                    # FastAPI backend application
├── frontend/                   # React frontend application
├── agent_core/                 # Core agent framework
├── old/                        # Legacy code (avoid modifying)
├── .kiro/                      # Kiro IDE configuration
├── .specify/                   # Specification templates
├── docker-compose.prod.yml     # Production deployment
├── Dockerfile.backend          # Backend container definition
├── Makefile                    # Infrastructure commands
└── requirements.txt            # Root Python dependencies
```

## Backend Structure (`backend/`) - MCP Architecture

### Core Architecture
- `main.py` - FastAPI application entry point
- `modules/` - Business logic modules (auth, config, database, models, observability)
- `routes/` - API endpoint definitions
- `services/platform/` - MCP UI Hub and platform services
- `infrastructure/` - AWS and local service adapters with circuit breakers
- `tests/` - Comprehensive test suite (unit, integration, performance)

### Key Directories - MCP Isolation
- `agents/` - **DEPRECATED**: Agent implementations being migrated to standalone MCP servers
- `core/a2a/` - **Legacy internal A2A implementation** used only for backend-internal event routing (e.g. monitoring, UI Hub). All agent-to-agent communication now uses the **MCP-based A2A Protocol** implemented in each standalone MCP server
- `core/` - Core system components (circuit breakers, tenants, authentication)
- `communication_agent/` - Communications Agent for MCP workflow orchestration
- `middleware/` - Request/response middleware
- `utils/` - Utility functions and helpers
- `docs/` - Documentation and guides

### Standalone MCP Servers (Outside Backend)
- `agent_svea/svea_mcp_server.py` - Swedish ERP & compliance MCP server
- `felicias_finance/finance_mcp_server.py` - Financial services MCP server  
- `meetmind/summarizer_mcp_server.py` - Meeting intelligence MCP server with fan-in logic
- `meetmind/livekit_agent/` - LiveKit meeting listener (separate process)

## Frontend Structure (`frontend/`)

### React Application
- `src/components/` - Reusable UI components
- `src/contexts/` - React Context providers
- `src/pages/` - Route-based page components
- `src/lib/` - API clients and utilities
- `src/types/` - TypeScript type definitions

### Design System
- Glassmorphism styling with `bg-white/5 backdrop-blur-md`
- Tailwind CSS with custom theme
- Brand colors: Blue (#0A2540) and Orange (#FF6A3D)
- Mobile-first responsive design

## Agent Core (`communication_agent/`) - **DEPRECATED**

### MCP Integration - **MIGRATED TO STANDALONE SERVERS**
- `mcp_client/` - **DEPRECATED**: Use standalone MCP servers instead
- `agent.py` - **DEPRECATED**: Each agent now operates as standalone MCP server
- `tools.py` - **MIGRATED**: Tools now implemented as MCP tools in standalone servers
- `prompts.py` - **MIGRATED**: Prompts now part of individual MCP server implementations

### New MCP Architecture
Each agent is now a **completely isolated MCP server** with zero dependencies on agent_core or backend.*

## Configuration Files

### Environment Configuration
- `.env` - Local development environment
- `.env.production` - Production environment template
- `backend/.env` - Backend-specific configuration

### Build Configuration
- `frontend/package.json` - Frontend dependencies and scripts
- `backend/requirements.txt` - Backend Python dependencies
- `frontend/tailwind.config.js` - Tailwind CSS configuration
- `frontend/tsconfig.json` - TypeScript configuration

## Naming Conventions

### Files and Directories
- Use snake_case for Python files and directories
- Use kebab-case for frontend files and directories
- Use PascalCase for React components
- Use UPPER_CASE for constants and environment variables

### Code Organization
- Group related functionality in modules
- Separate concerns (routes, services, models)
- Use dependency injection for services
- Follow FastAPI and React best practices

## Import Patterns - MCP Architecture

### Backend Imports (Internal Only)
```python
# Backend internal imports (for backend services only)
from backend.modules.auth import get_current_user
from backend.services.platform.mcp_ui_hub_service import MCPUIHub
from backend.core.a2a import A2AProtocol  # Internal backend communication only

# Use try/except for flexible imports
try:
    from backend.modules.config import settings
except ImportError:
    from modules.config import settings
```

### MCP Server Imports (Standalone Agents)
```python
# MCP servers MUST NOT import from backend.*
# ❌ FORBIDDEN: from backend.anything import anything

# ✅ ALLOWED: Only MCP protocol and standard libraries
from mcp import MCPServer, MCPTool
import asyncio
import httpx
import os

# ✅ ALLOWED: Direct AWS SDK usage with circuit breakers
import boto3
from botocore.exceptions import ClientError
```

### **CRITICAL RULE**: Agent modules MUST be completely isolated
- **NO backend.* imports** in agent MCP servers
- **NO shared dependencies** except MCP protocol implementation
- **NO direct database access** - use MCP tools for data operations

### **A2A Protocol Clarification**
- **Global A2A Protocol**: The real Agent-to-Agent protocol between MeetMind, Agent Svea, Felicia's Finance, and Communications Agent via MCP with reply-to semantics
- **Backend Core A2A**: Legacy internal backend communication in `backend/core/a2a/` - only for backend-internal services, NOT for agent-to-agent communication

### **Adding New Agents**
Follow the standardized process documented in `.kiro/steering/new_agent_process.md`:
1. Create CDK stack in `infra/agents/<agent_name>/`
2. Register in Agent Registry with MCP tools and capabilities
3. Implement as isolated MCP server with NO backend.* imports
4. Configure reply-to semantics pointing to `meetmind/ingest_result`
5. Add CI/CD, monitoring, and smoke tests

### Frontend Imports
```typescript
// Use absolute imports from src
import { AuthContext } from '@/contexts/AuthContext'
import { Button } from '@/components/ui/button'
```

## Testing Structure

### Backend Tests (`backend/tests/`)
- `unit/` - Unit tests for individual components
- `integration/` - Integration tests for service interactions
- `performance/` - Load and performance tests
- `demo/` - Demo scenario tests

### Frontend Tests (`frontend/src/__tests__/`)
- Component tests with React Testing Library
- Integration tests for user flows
- Accessibility tests with jest-axe

## Documentation Location

- API documentation auto-generated at `/docs`
- Architecture docs in `backend/docs/`
- Setup guides in component README files
- Deployment guides in `backend/docs/DEPLOYMENT_GUIDE.md`