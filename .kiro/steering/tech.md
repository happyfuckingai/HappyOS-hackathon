# Technology Stack - MCP Architecture

## Backend Stack (Internal Services Only)
- **Framework**: FastAPI with Python 3.10+
- **Database**: PostgreSQL with Supabase integration
- **Caching**: Redis for sessions, rate limiting, and MCP message queuing
- **Vector DB**: Qdrant for AI memory and search
- **Authentication**: JWT with Supabase Auth + HMAC/Ed25519 for MCP headers
- **Real-time**: WebSockets, Server-Sent Events (SSE)
- **AI Integration**: OpenAI, Google Gemini, Mem0 for memory
- **Communication**: LiveKit for video/audio RTC + MCP protocol for agent communication

## MCP Server Stack (Isolated Agents)
- **Protocol**: Model Context Protocol (MCP) implementing the **Global A2A Protocol** for all agent communication
- **Architecture**: Standalone servers with zero backend.* dependencies
- **Authentication**: Signed MCP headers with tenant isolation
- **Database Access**: Via MCP tools only (no direct database imports)
- **AWS Integration**: Direct AWS SDK usage with circuit breaker patterns
- **Communication Pattern**: One-way with reply-to semantics for async callbacks

## A2A Protocol Layers
- **Global A2A Protocol**: MCP-based communication between isolated agent servers (MeetMind ↔ Agent Svea ↔ Felicia's Finance ↔ Communications Agent)
- **Backend Internal A2A**: Legacy `backend/core/a2a/` for backend-internal services only (monitoring, UI Hub, configuration)

## Frontend Stack
- **Framework**: React 18 with TypeScript
- **Styling**: Tailwind CSS with glassmorphism design system
- **Routing**: React Router v6
- **State Management**: Context API
- **UI Components**: Radix UI primitives with shadcn/ui
- **Real-time**: LiveKit Components React
- **HTTP Client**: Axios with JWT interceptors

## Infrastructure & DevOps
- **Cloud**: AWS (Lambda, API Gateway, OpenSearch, ElastiCache)
- **IaC**: AWS CDK for infrastructure as code
- **Containers**: Docker with multi-stage builds
- **Orchestration**: Docker Compose for local/production
- **Monitoring**: Prometheus, Grafana, CloudWatch, Loki
- **Deployment**: Blue-green deployment strategy
- **Load Balancing**: Nginx reverse proxy

## Development Tools
- **Testing**: pytest (backend), Jest/React Testing Library (frontend)
- **Code Quality**: Black, flake8, ESLint, TypeScript
- **Security**: Bandit security scanning, JWT validation
- **Documentation**: OpenAPI/Swagger auto-generation

## Common Commands

### Backend Development (Internal Services)
```bash
# Start backend server (internal services only)
cd backend && python main.py

# Run tests
cd backend && python -m pytest tests/

# Install dependencies
pip install -r requirements.txt
```

### MCP Server Development (Isolated Agents)
```bash
# Start Agent Svea MCP Server
cd agent_svea && python svea_mcp_server.py

# Start Felicia's Finance MCP Server  
cd felicias_finance && python finance_mcp_server.py

# Start MeetMind MCP Server
cd meetmind && python summarizer_mcp_server.py

# Start Communications Agent
cd backend/communication_agent && python agent.py

# Test MCP server isolation (should have NO backend.* imports)
grep -r "from backend" agent_svea/ felicias_finance/ meetmind/
```

### MCP Workflow Testing
```bash
# Test cross-module MCP workflow
curl -X POST http://localhost:8000/mcp/workflow/compliance \
  -H "Content-Type: application/json" \
  -d '{"meeting_id": "test", "tenant_id": "demo"}'

# Monitor MCP message flow
tail -f backend/logs/mcp_*.log
```

### Adding New MCP Agents
Follow the standardized process in `.kiro/steering/new_agent_process.md`:
```bash
# Create new agent structure
mkdir -p agents/new_agent infra/agents/new_agent

# Deploy agent infrastructure
cd infra/agents/new_agent && cdk deploy

# Verify MCP isolation (should return empty)
grep -r "from backend" agents/new_agent/
```

### Frontend Development
```bash
# Start development server
cd frontend && npm start

# Build for production
npm run build

# Run tests
npm test
```

### Infrastructure
```bash
# Deploy infrastructure
make deploy ENV=dev

# Bootstrap CDK
make bootstrap

# View logs
make logs
```

### Docker Operations
```bash
# Build and run production
docker-compose -f docker-compose.prod.yml up -d

# Build backend image
docker build -t happy-os-backend -f Dockerfile.backend .
```

## Environment Configuration
- Use `.env` files for local development
- Environment-specific configs in `.env.production`
- AWS credentials via IAM roles in production
- Supabase keys for database and auth
- LiveKit credentials for real-time communication