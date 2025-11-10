# Technology Stack

## Backend

**Framework**: FastAPI with uvicorn ASGI server
**Language**: Python 3.10+
**MCP Integration**: FastMCP for Model Context Protocol server implementation

### Core Dependencies

- `fastapi` - Web framework with async support
- `uvicorn[standard]` - ASGI server
- `pydantic` & `pydantic-settings` - Data validation and settings management
- `supabase` & `postgrest` - Database and authentication
- `python-jose[cryptography]` - JWT token handling
- `boto3` & `aioboto3` - AWS SDK (async and sync)
- `redis[asyncio]` & `aioredis` - Caching and rate limiting
- `livekit` & `livekit-agents` - Real-time video/audio
- `sse-starlette` - Server-Sent Events for real-time updates
- `httpx` & `requests` - HTTP clients
- `structlog` - Structured logging
- `prometheus-client` - Metrics collection
- `sentry-sdk[fastapi]` - Error tracking

### Testing

- `pytest` & `pytest-asyncio` - Test framework
- `pytest-cov` - Coverage reporting

## Frontend

**Framework**: React 18 with TypeScript
**Build Tool**: Create React App (react-scripts 5.0.1)
**Styling**: Tailwind CSS with custom glassmorphism design system

### Core Dependencies

- `react` & `react-dom` (v18.2.0)
- `react-router-dom` (v6.20.0) - Client-side routing
- `axios` (v1.6.0) - HTTP client
- `@livekit/components-react` & `livekit-client` - Video/audio components
- `@radix-ui/*` - Accessible UI primitives (dialog, tabs, scroll-area, switch)
- `lucide-react` - Icon library
- `jwt-decode` - JWT token parsing
- `clsx` & `tailwind-merge` - Utility class management
- `class-variance-authority` - Component variant management
- `ajv` - JSON schema validation

### Testing & Accessibility

- `@testing-library/react` & `@testing-library/jest-dom`
- `@axe-core/react` & `jest-axe` - Accessibility testing

## AWS Services

- **Amazon Bedrock** - LLM inference with local fallback
- **Amazon SageMaker** - Model training and deployment
- **AWS Lambda** - Serverless agent deployment
- **Amazon DynamoDB** - Multi-tenant data storage
- **Amazon OpenSearch** - Vector search and analytics
- **Amazon ElastiCache** - Redis caching layer
- **Amazon S3** - Object storage for snapshots and audit logs
- **AWS Secrets Manager** - Secrets and key management
- **Amazon CloudWatch** - Monitoring and logging
- **AWS API Gateway** - MCP protocol routing

## Infrastructure as Code

**Tool**: AWS CDK (Python)
**Location**: `backend/infrastructure/aws/iac/`

## Common Commands

### Backend Development

```bash
# Start backend server
cd backend && python main.py

# Development mode with auto-reload
uvicorn main:app --reload --host 0.0.0.0 --port 8000

# Run tests
python -m pytest tests/ -v

# Install dependencies
pip install -r requirements.txt
```

### Frontend Development

```bash
# Start development server
cd frontend && npm start

# Build for production
npm run build

# Run tests
npm test

# Install dependencies
npm install
```

### Docker & Deployment

```bash
# Build all Docker images
make docker-build

# Start complete system
make demo

# Deploy to AWS
make aws-deploy ENV=prod REGION=us-east-1

# Check system health
make health
```

### MCP Agent Management

```bash
# Start all agents
make agents

# Start individual agents
make agent-svea        # Port 8001
make agent-finance     # Port 8002
make agent-meetmind    # Port 8003
```

## Development Workflow

1. Backend runs on `http://localhost:8000`
2. Frontend runs on `http://localhost:3000`
3. MCP agents run on ports 8001-8003
4. API documentation available at `/docs` (FastAPI auto-generated)
5. Health checks at `/health` endpoints

## Environment Variables

Backend requires `.env` file with:
- `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_ROLE_KEY`
- `LIVEKIT_URL`, `LIVEKIT_API_KEY`, `LIVEKIT_API_SECRET`
- `AWS_REGION`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`
- `BEDROCK_MODEL_ID`, `OPENSEARCH_ENDPOINT`, `ELASTICACHE_CLUSTER`
- `MCP_API_KEY` - For MCP server authentication

Frontend requires `.env` with:
- `REACT_APP_API_URL` - Backend API URL (default: http://localhost:8000)
