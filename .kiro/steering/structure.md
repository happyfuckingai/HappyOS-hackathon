# Project Structure

## Root Organization

```
HappyOS-hackathon/
├── backend/                    # FastAPI backend with MCP UI Hub
├── frontend/                   # React frontend with real-time dashboard
├── hackathon_demo_scripts/     # Demo scripts and documentation
├── hackathon_submissions/      # Hackathon submission materials
├── Makefile                    # Development and deployment commands
└── README.md                   # Main project documentation
```

## Backend Structure (`backend/`)

### Core Application

- `main.py` - FastAPI application entry point with lifespan management, middleware setup, and route registration
- `requirements.txt` - Python dependencies

### Module Organization

**`agents/`** - Domain-specific MCP agent implementations
- `agent_svea/` - Swedish compliance agent with ERPNext integration
- `felicias_finance/` - Financial services and crypto trading agent
- `meetmind/` - Meeting intelligence agent with Bedrock integration
- Each agent contains:
  - `*_mcp_server.py` - Standalone MCP server
  - `adk_agents/` - Agent Development Kit implementations
  - `services/` - Domain-specific services
  - `registry.py` - Agent capability registration

**`core/`** - Core system components
- `a2a/` - Agent-to-Agent protocol implementation (messaging, discovery, orchestration)
- `circuit_breaker/` - Circuit breaker pattern for resilience
- `mcp/` - MCP routing and UI Hub service
- `registry/` - Agent registry and initialization
- `tenants/` - Multi-tenant isolation
- `interfaces.py` - Shared interfaces and contracts
- `settings.py` - Configuration management system

**`infrastructure/`** - Infrastructure adapters and services
- `aws/` - AWS service adapters (Lambda, DynamoDB, OpenSearch, ElastiCache, S3, Secrets Manager)
  - `iac/` - AWS CDK infrastructure as code
  - `services/` - Service-specific adapters
- `local/` - Local fallback services (memory, search, storage, job runner)
- `database/` - Unified database service abstraction
- `migration/` - GCP to AWS migration tools
- `service_facade.py` - Unified service interface

**`modules/`** - Business logic modules
- `auth/` - Authentication, JWT, tenant isolation, MCP security
- `config/` - Configuration and health checks
- `database/` - Database connections and repositories
  - `dynamodb/` - DynamoDB client and operations
  - `s3/` - S3 client and bucket management
  - `repository/` - Data access layer
- `models/` - Pydantic data models
- `observability/` - Logging, metrics, tracing, audit

**`routes/`** - API route handlers
- `auth_routes.py` - Authentication endpoints
- `meeting_routes.py` - Meeting management
- `mcp_ui_routes.py` - MCP UI Hub endpoints
- `mcp_adapter_routes.py` - MCP adapter integration
- `agent_registry.py` - Agent discovery and health
- `observability_routes.py` - Metrics and health checks
- `security_routes.py` - Security management
- `rate_limit_routes.py` - Rate limiting configuration

**`services/`** - Business services
- `agents/` - Agent orchestration and process management
- `ai/` - AI client management and detection
- `integration/` - External service integrations (MCP, summarizer)
- `observability/` - Observability decorators and middleware
- `platform/` - MCP agent SDK and UI Hub service
- `websocket_manager.py` - WebSocket connection management

**`middleware/`** - Request/response middleware
- `security_middleware.py` - Security headers and validation
- `json_schema_validation_middleware.py` - Request validation
- `tenant_isolation_middleware.py` - Multi-tenant isolation

**`communication_agent/`** - LiveKit and Google Realtime orchestration
- `agent.py` - Main communication agent
- `mcp_client/` - MCP client implementation
- `tools.py` - Agent tools and capabilities

## Frontend Structure (`frontend/`)

### Source Organization (`src/`)

**`components/`** - React components
- `auth/` - Authentication guards and flows
- `common/` - Shared components (ErrorBoundary, AccessibilityProvider, NetworkErrorHandler)
- `layout/` - Layout components (AppShell, Header)
- `meeting/` - Meeting UI (VideoGrid, AISidebar, FabMenu)
  - `tabs/` - Sidebar tabs (AI, Chat, Settings, ShareRecording)
- `ui/` - Reusable UI primitives (button, card, input, tabs, themed components)
- `ui-resources/` - Dynamic UI resource rendering system
  - `renderers/` - Specific renderers (Card, Chart, Form, List)

**`contexts/`** - React Context providers
- `AuthContext.tsx` - Authentication state
- `MeetingContext.tsx` - Meeting state management
- `SSEContext.tsx` - Server-Sent Events connection
- `WebSocketContext.tsx` - WebSocket connection
- `UIResourceContext.tsx` - Dynamic UI resources
- `TenantContext.tsx` - Multi-tenant configuration

**`pages/`** - Route pages
- `Landing.tsx` - Landing page
- `Auth.tsx` - Authentication page
- `Lobby.tsx` - Meeting lobby
- `Meeting.tsx` - Meeting room
- `UIResourceDemo.tsx` - UI resource demonstration

**`lib/`** - Utility libraries
- `api.ts` - API client configuration
- `tenant-config.ts` - Tenant-specific configuration
- `ui-resource-api.ts` - UI resource API client
- `utils.ts` - Shared utilities

**`types/`** - TypeScript type definitions
- `index.ts` - Core types
- `ui-resources.ts` - UI resource types

**`styles/`** - Global styles
- `mobile-optimizations.css` - Mobile-specific styles

### Configuration Files

- `tailwind.config.js` - Tailwind CSS configuration with custom theme
- `tsconfig.json` - TypeScript configuration
- `package.json` - Dependencies and scripts
- `components.json` - shadcn/ui configuration

## Key Patterns

### Import Conventions

**Backend**: Use relative imports within modules, absolute imports across modules
```python
# Within same module
from .services import MyService

# Across modules
from backend.core.settings import settings
```

**Frontend**: Use absolute imports from `src/`
```typescript
import { useAuth } from 'contexts/AuthContext';
import { Button } from 'components/ui/button';
```

### MCP Server Pattern

Each agent follows this structure:
1. FastAPI app with CORS middleware
2. FastMCP instance mounted at `/mcp`
3. MCP tools decorated with `@mcp.tool()`
4. SSE endpoints for real-time updates
5. Health check endpoint at `/health`
6. API key authentication via Bearer token

### Service Facade Pattern

Infrastructure services use a facade pattern:
- Abstract interface in `core/interfaces.py`
- AWS implementation in `infrastructure/aws/services/`
- Local fallback in `infrastructure/local/services/`
- Circuit breaker wraps service calls
- Automatic failover on AWS service failure

### Multi-Tenant Isolation

Tenant isolation enforced at multiple layers:
1. Middleware validates tenant_id in requests
2. Database queries scoped to tenant_id
3. Agent registries per tenant
4. UI resources namespaced by tenant
5. Security policies per tenant

### Observability Pattern

All services instrumented with:
- Structured logging via `structlog`
- Prometheus metrics via decorators
- Distributed tracing with trace IDs
- Health checks at `/health` endpoints
- Audit logging for security events
