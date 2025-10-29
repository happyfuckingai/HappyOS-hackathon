# Multi-User Agent Management Backend

A FastAPI-based backend server for managing multi-user LiveKit agents, meetings, and MCP integration with Supabase database.

> 📚 **Full documentation available in [docs/](docs/README.md)**

## Features

- **Authentication**: JWT-based user authentication with Supabase
- **Agent Management**: Start, stop, and monitor AI agents across multiple users
- **Meeting Management**: Create and manage multi-user video/audio meetings
- **LiveKit Integration**: Real-time communication infrastructure
- **MCP Integration**: AI summarization and tool interfaces
- **Memory Management**: Mem0-powered persistent memory across sessions
- **Multi-User Support**: Full multi-user architecture with participant management

## Architecture Overview

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Frontend      │    │   FastAPI        │    │   Supabase      │
│   (React)       │◄──►│   Backend        │◄──►│   Database      │
│                 │    │                  │    │                 │
│ - Auth UI       │    │ - Auth Routes    │    │ - Users         │
│ - Agent Manager │    │ - Agent Routes   │    │ - Meetings      │
│ - Meeting UI    │    │ - Meeting Routes │    │ - Agents        │
│ - MCP Tools     │    │ - MCP Routes     │    │ - Memories      │
└─────────────────┘    └──────────────────┘    └─────────────────┘
```

## API Structure

The backend provides RESTful APIs organized into the following modules:

### Authentication (`/auth`)
- `POST /auth/login` - User login
- `POST /auth/register` - User registration
- `POST /auth/logout` - User logout
- `POST /auth/refresh` - Refresh JWT token
- `GET /auth/profile` - Get user profile

### Agent Management (`/api/agents`)
- `GET /api/agents` - List all agents
- `POST /api/agents` - Create new agent
- `GET /api/agents/{agent_id}` - Get agent details
- `PUT /api/agents/{agent_id}/status` - Update agent status
- `DELETE /api/agents/{agent_id}` - Delete agent

### Meeting Management (`/api/meetings`)
- `GET /api/meetings` - List user's meetings
- `POST /api/meetings` - Create new meeting
- `GET /api/meetings/{meeting_id}` - Get meeting details
- `PUT /api/meetings/{meeting_id}` - Update meeting
- `DELETE /api/meetings/{meeting_id}` - Delete meeting

### MCP Integration (`/api/mcp`)
- `POST /api/mcp/tools` - Execute MCP tools
- `GET /api/mcp/summarize` - Get meeting summaries
- `POST /api/mcp/context` - Update context

### Memory Management (`/api/mem0`)
- `GET /api/mem0/memories` - Retrieve memories
- `POST /api/mem0/memories` - Save new memory
- `PUT /api/mem0/memories/{memory_id}` - Update memory
- `DELETE /api/mem0/memories/{memory_id}` - Delete memory

## Frontend-Backend Integration

### Connection Pattern

The frontend connects to the backend through dedicated API service modules:

```
frontend/src/services/api/
├── authApi.js      → /auth/*     (Authentication)
├── agentApi.js     → /api/*      (Agent management)
├── meetingApi.js   → /api/*      (Meeting management)
├── mcpApi.js       → /api/*      (MCP tools)
└── mem0Api.js      → /api/*      (Memory management)
```

### Authentication Flow

1. **Frontend** sends login credentials to `/auth/login`
2. **Backend** validates with Supabase and returns JWT token
3. **Frontend** stores token in localStorage
4. **Backend** automatically includes token in subsequent requests via axios interceptor
5. **Supabase** validates tokens for protected operations

### Real-time Communication

```
┌─────────────┐    WebSocket    ┌─────────────┐
│   Frontend  │◄──────────────►│   Backend   │
│  Components │                 │   Server    │
└─────────────┘                 └─────────────┘
                                      │
                                      ▼
┌─────────────┐    LiveKit RTC   ┌─────────────┐
│   LiveKit   │◄──────────────►│   Agents    │
│   Client    │                 │   Server    │
└─────────────┘                 └─────────────┘
```

## Getting Started

### Prerequisites

- Python 3.10 or higher
- Virtual environment (recommended)
- Supabase account and project
- LiveKit server credentials

### Installation

1. **Navigate to backend directory:**
   ```bash
   cd backend
   ```

2. **Create and activate virtual environment:**
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies:**
   ```bash
   pip install -r ../config/requirements.txt
   ```

4. **Configure environment:**
   ```bash
   cp .env.example .env
   ```

   Edit `.env` with your credentials:
   ```env
   # Supabase Configuration
   SUPABASE_URL=https://your-project.supabase.co
   SUPABASE_ANON_KEY=your-anon-key
   SUPABASE_SERVICE_ROLE_KEY=your-service-role-key

   # LiveKit Configuration
   LIVEKIT_URL=wss://your-livekit-server.livekit.cloud
   LIVEKIT_API_KEY=your-livekit-api-key
   LIVEKIT_API_SECRET=your-livekit-api-secret
   ```

5. **Start the server:**
   ```bash
   python3 main.py
   ```

The API will be available at `http://localhost:8000`

### Development Mode

For development with auto-reload:
```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

## Project Structure

```
backend/
├── main.py                     # FastAPI application entry point
├── core/                      # Core application modules
│   ├── __init__.py
│   ├── config.py              # Application configuration
│   ├── database.py            # Database connection management
│   └── models.py              # Pydantic data models
├── modules/                   # Business logic modules
│   ├── __init__.py
│   ├── auth.py               # Authentication utilities
│   ├── config.py             # Module-specific configuration
│   └── database.py           # Database operations
├── routes/                    # API route handlers
│   ├── __init__.py
│   ├── agent_routes.py       # Agent management endpoints
│   ├── auth_routes.py        # Authentication endpoints
│   ├── mcp_routes.py         # MCP integration endpoints
│   ├── meeting_routes.py     # Meeting management endpoints
│   └── mem0_routes.py        # Memory management endpoints
├── services/                  # Business logic services
│   ├── __init__.py
│   ├── mcp_integration_service.py
│   ├── startup_coordinator.py
│   ├── summarizer_client.py
│   └── summarizer_service.py
├── summarizer/               # AI summarization system
│   ├── __init__.py
│   ├── ai_clients.py         # AI provider integrations
│   ├── config.py            # Summarizer configuration
│   ├── summarizer_agent.py  # Main summarizer agent
│   ├── ARCHITECTURE.md      # Summarizer architecture docs
│   ├── COMPREHENSIVE_DOCUMENTATION.md
│   ├── a2a_protocol/        # Agent-to-Agent protocol
│   │   ├── README.md
│   │   └── core/
│   ├── core/               # Core summarizer components
│   │   ├── __init__.py
│   │   ├── ai_summarization.py
│   │   └── summarizer_skill.py
│   ├── database/           # Database components
│   │   ├── __init__.py
│   │   └── database.py
│   ├── managers/           # Manager components
│   │   ├── __init__.py
│   │   ├── topic_manager.py
│   │   └── ui_state_manager.py
│   └── utils/              # Utility functions
│       ├── __init__.py
│       ├── mcp_tools.py
│       ├── search_handlers.py
│       ├── vector_search.py
│       └── voice_commands.py
├── utils/                     # General utilities
│   ├── __init__.py
│   ├── supabase_config.py    # Supabase client configuration
│   ├── supabase_mem0_service.py
│   ├── supabase_service.py   # Supabase database operations
│   └── test_main.py
├── requirements.txt          # Python dependencies
├── .env                      # Environment variables
├── pytest.ini              # Test configuration
└── README.md                # This file
```

## Configuration

### Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `SUPABASE_URL` | Your Supabase project URL | Yes |
| `SUPABASE_ANON_KEY` | Supabase anonymous key | Yes |
| `SUPABASE_SERVICE_ROLE_KEY` | Supabase service role key | Yes |
| `LIVEKIT_URL` | LiveKit server WebSocket URL | Yes |
| `LIVEKIT_API_KEY` | LiveKit API key | Yes |
| `LIVEKIT_API_SECRET` | LiveKit API secret | Yes |

### CORS Configuration

The backend is configured to accept requests from any origin in development:
```python
allow_origins=["*"]  # Configure for production
```

## Database Schema

The application uses Supabase with the following main tables:
- `users` - User accounts and profiles
- `meetings` - Meeting information and metadata
- `agents` - AI agent configurations and status
- `memories` - Persistent memory storage
- `participants` - Meeting participant management

## API Response Format

### Success Response
```json
{
  "success": true,
  "data": {
    // Response data
  }
}
```

### Error Response
```json
{
  "success": false,
  "error": {
    "code": "ERROR_CODE",
    "message": "Error description"
  }
}
```

## Development Workflow

### 1. Start Backend Server
```bash
cd backend
python3 main.py
```

### 2. Start Frontend (in another terminal)
```bash
cd frontend
npm start
```

### 3. Access Application
- **Frontend:** http://localhost:3000
- **Backend API:** http://localhost:8000
- **API Documentation:** http://localhost:8000/docs

### 4. Testing Integration
The backend includes automatic JWT token validation and Supabase integration testing.

## Deployment

### Production Deployment

1. **Update CORS settings in `main.py`:**
   ```python
   allow_origins=["https://yourdomain.com"]  # Replace with your domain
   ```

2. **Set production environment variables**

3. **Use production WSGI server:**
   ```bash
   uvicorn main:app --host 0.0.0.0 --port 8000 --workers 4
   ```

### Docker Deployment

The backend includes a Dockerfile for containerized deployment:
```bash
docker build -t meetmind-backend .
docker run -p 8000:8000 meetmind-backend
```

## Troubleshooting

### Common Issues

1. **Import Errors:** Ensure you're running from the correct directory (`backend/`)

2. **Environment Variables:** Verify `.env` file exists in `backend/` directory

3. **Supabase Connection:** Check Supabase credentials in `.env` file

4. **CORS Issues:** Update `allow_origins` in `main.py` for your frontend domain

### Debug Mode

Enable debug logging by setting:
```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

## Contributing

1. Follow the existing code structure
2. Add appropriate error handling
3. Update tests when adding new features
4. Document new API endpoints
5. Ensure CORS compatibility

## 📚 Documentation

All documentation has been organized in the `docs/` directory:

- **[docs/README.md](docs/README.md)** - Documentation index
- **[docs/guides/QUICK_GUIDE.md](docs/guides/QUICK_GUIDE.md)** - Quick start guide for new structure
- **[docs/guides/QUICKSTART.md](docs/guides/QUICKSTART.md)** - Getting started
- **[docs/refactoring/](docs/refactoring/)** - Refactoring documentation
- **[docs/status/](docs/status/)** - Project status reports

### Quick Links:
- 🚀 [Quick Start Guide](docs/guides/QUICKSTART.md)
- 📖 [Import Guide](docs/guides/QUICK_GUIDE.md)
- 🔧 [Troubleshooting](docs/guides/STARTUP_TROUBLESHOOTING.md)
- ✅ [Refactoring Complete](docs/refactoring/REFACTORING_COMPLETE.md)

## License

This project is part of the MeetMind multi-user agent management system.