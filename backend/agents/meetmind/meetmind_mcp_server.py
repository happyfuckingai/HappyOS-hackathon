#!/usr/bin/env python3
"""
Meetmind MCP Server

Provides Bedrock-backed meeting summarization tools, meeting memory publishing,
and secure SSE endpoints for MCP clients.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import secrets
import sys
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional
from uuid import uuid4

try:
    from dotenv import load_dotenv

    load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))
except ImportError:
    pass  # Environment variables can still be provided externally

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from mcp.server import FastMCP
from sse_starlette.sse import EventSourceResponse
from pydantic import BaseModel, Field, field_validator

try:
    from .managers.meeting_memory import MeetingMemoryService, meeting_memory_service
except ImportError:  # pragma: no cover - fallback for direct execution
    current_dir = os.path.dirname(os.path.abspath(__file__))
    parent_dir = os.path.dirname(current_dir)
    if parent_dir not in sys.path:
        sys.path.append(parent_dir)
    from managers.meeting_memory import MeetingMemoryService, meeting_memory_service  # type: ignore

try:
    from .core.bedrock_client import BedrockMeetingClient, get_bedrock_client
except ImportError:  # pragma: no cover - fallback for direct execution
    current_dir = os.path.dirname(os.path.abspath(__file__))
    parent_dir = os.path.dirname(current_dir)
    if parent_dir not in sys.path:
        sys.path.append(parent_dir)
    from core.bedrock_client import BedrockMeetingClient, get_bedrock_client  # type: ignore


# ---------------------------------------------------------------------------
# Logging configuration
# ---------------------------------------------------------------------------

LOG_LEVEL = os.getenv("MEETMIND_LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("meetmind_mcp_server")
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("botocore").setLevel(logging.WARNING)
logging.getLogger("boto3").setLevel(logging.WARNING)


# ---------------------------------------------------------------------------
# Core services and application setup
# ---------------------------------------------------------------------------

meeting_memory: MeetingMemoryService = meeting_memory_service

# Initialize enhanced MCP tools handler
try:
    from .utils.mcp_tools import MCPToolsHandler
    mcp_tools_handler = MCPToolsHandler()
    logger.info("Enhanced MCP Tools Handler initialized successfully")
except ImportError:
    # Fallback for direct execution
    try:
        from utils.mcp_tools import MCPToolsHandler
        mcp_tools_handler = MCPToolsHandler()
        logger.info("Enhanced MCP Tools Handler initialized successfully (fallback)")
    except Exception as e:
        logger.error(f"Failed to initialize MCP Tools Handler: {e}")
        mcp_tools_handler = None
except Exception as e:
    logger.error(f"Failed to initialize MCP Tools Handler: {e}")
    mcp_tools_handler = None

mcp = FastMCP(
    name="Meetmind MCP Server",
    host=os.getenv("MCP_HOST", "0.0.0.0"),
    port=int(os.getenv("MCP_PORT", "8150")),
    mount_path="/mcp",
    log_level=LOG_LEVEL,
)

app = FastAPI(title="Meetmind MCP Server", version="0.1.0")

allowed_origins_env = os.getenv("MCP_ALLOWED_ORIGINS", "*")
allowed_origins = [origin.strip() for origin in allowed_origins_env.split(",") if origin.strip()]
if not allowed_origins:
    allowed_origins = ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/mcp", mcp.sse_app(mount_path="/mcp"))

# API key security for HTTP/SSE access
API_KEY = os.getenv("MCP_API_KEY") or secrets.token_urlsafe(32)
if "MCP_API_KEY" not in os.environ:
    logger.warning("Generated ephemeral MCP API key: %s...", API_KEY[:8])

security = HTTPBearer(auto_error=False)

# Short-lived tokens for SSE authentication
SSE_TOKENS: Dict[str, Dict[str, Any]] = {}
SSE_TOKEN_EXPIRY_MINUTES = 30


async def verify_api_key(credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)) -> str:
    """Verify bearer token matches configured MCP API key."""
    if credentials is None or credentials.credentials != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid or missing API key")
    return credentials.credentials


def generate_sse_token(meeting_id: str, user_id: str = "anonymous") -> str:
    """Generate a short-lived token for SSE authentication."""
    token = secrets.token_urlsafe(32)
    expiry = datetime.now(timezone.utc) + timedelta(minutes=SSE_TOKEN_EXPIRY_MINUTES)

    SSE_TOKENS[token] = {
        "meeting_id": meeting_id,
        "user_id": user_id,
        "expiry": expiry,
        "created_at": datetime.now(timezone.utc),
    }

    logger.info(f"Generated SSE token for meeting {meeting_id}, expires at {expiry}")
    return token


def verify_sse_token(token: str, meeting_id: str) -> bool:
    """Verify SSE token is valid for the given meeting."""
    if token not in SSE_TOKENS:
        return False

    token_data = SSE_TOKENS[token]

    # Check if token has expired
    if datetime.now(timezone.utc) > token_data["expiry"]:
        del SSE_TOKENS[token]
        return False

    # Check if token is for the correct meeting
    if token_data["meeting_id"] != meeting_id:
        return False

    return True


class TranscriptChunk(BaseModel):
    """Incoming transcript chunk payload from real-time agents."""

    content: str = Field(..., min_length=1, description="Transcript text chunk")
    speaker: Optional[str] = Field(
        default=None, description="Identified speaker label or participant ID"
    )
    is_final: bool = Field(
        default=False, description="Indicates if the chunk is a final transcript segment"
    )
    sequence: Optional[int] = Field(
        default=None, ge=0, description="Monotonic sequence number for ordering"
    )
    start_time_ms: Optional[int] = Field(
        default=None, ge=0, description="Start timestamp in milliseconds since session start"
    )
    end_time_ms: Optional[int] = Field(
        default=None, ge=0, description="End timestamp in milliseconds since session start"
    )
    confidence: Optional[float] = Field(
        default=None, description="Confidence score between 0 and 1"
    )
    tenant_id: Optional[str] = Field(
        default=None, description="Tenant identifier for multi-tenant scenarios"
    )
    metadata: Optional[Dict[str, Any]] = Field(
        default=None, description="Arbitrary metadata forwarded from the agent"
    )

    @field_validator("confidence")
    @classmethod
    def _clamp_confidence(cls, value: Optional[float]) -> Optional[float]:
        if value is None:
            return value
        if value < 0:
            return 0.0
        if value > 1:
            return 1.0
        return value


@app.post("/meetmind/auth/sse-token")
async def create_sse_token(
    request: Dict[str, str],
    _: str = Depends(verify_api_key)
) -> Dict[str, Any]:
    """Create a short-lived token for SSE authentication."""
    meeting_id = request.get("meeting_id")
    user_id = request.get("user_id", "anonymous")

    if not meeting_id:
        raise HTTPException(status_code=400, detail="meeting_id is required")

    token = generate_sse_token(meeting_id, user_id)

    return {
        "token": token,
        "expires_in": SSE_TOKEN_EXPIRY_MINUTES * 60,
        "meeting_id": meeting_id,
        "user_id": user_id,
    }


@app.post("/meetmind/meetings/{meeting_id}/transcripts")
async def ingest_transcript_chunk(
    meeting_id: str,
    chunk: TranscriptChunk,
    _: str = Depends(verify_api_key),
) -> Dict[str, Any]:
    """Ingest a real-time transcript chunk and persist to meeting memory."""
    metadata = (chunk.metadata or {}).copy()

    metadata.update(
        {
            "speaker": chunk.speaker,
            "is_final": chunk.is_final,
            "sequence": chunk.sequence,
            "start_time_ms": chunk.start_time_ms,
            "end_time_ms": chunk.end_time_ms,
            "confidence": chunk.confidence,
            "tenant_id": metadata.get("tenant_id") or chunk.tenant_id or "default",
        }
    )

    # Remove keys with None values to keep storage clean
    metadata = {key: value for key, value in metadata.items() if value is not None}

    await meeting_memory.append_transcript(
        meeting_id,
        chunk.content,
        metadata,
    )

    await _broadcast(
        meeting_id,
        event="transcript_chunk",
        payload={
            "content": chunk.content,
            "metadata": metadata,
        },
    )

    logger.debug(
        "Transcript chunk stored for meeting %s (speaker=%s, final=%s, sequence=%s)",
        meeting_id,
        metadata.get("speaker"),
        metadata.get("is_final"),
        metadata.get("sequence"),
    )

    return {
        "status": "accepted",
        "meeting_id": meeting_id,
        "metadata": metadata,
    }


# ---------------------------------------------------------------------------
# Meeting update bus for SSE streaming
# ---------------------------------------------------------------------------


class MeetingUpdateBus:
    """Simple pub/sub queue per meeting for SSE streaming."""

    def __init__(self) -> None:
        self._queues: Dict[str, List[asyncio.Queue]] = {}
        self._lock = asyncio.Lock()

    async def subscribe(self, meeting_id: str) -> asyncio.Queue:
        queue: asyncio.Queue = asyncio.Queue()
        async with self._lock:
            self._queues.setdefault(meeting_id, []).append(queue)
        return queue

    async def unsubscribe(self, meeting_id: str, queue: asyncio.Queue) -> None:
        async with self._lock:
            queues = self._queues.get(meeting_id)
            if not queues:
                return
            if queue in queues:
                queues.remove(queue)
            if not queues:
                self._queues.pop(meeting_id, None)

    async def publish(self, meeting_id: str, event: str, payload: Dict[str, Any]) -> None:
        async with self._lock:
            queues = list(self._queues.get(meeting_id, []))

        if not queues:
            return

        message = {
            "event": event,
            "data": payload,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        for queue in queues:
            await queue.put(message)


update_bus = MeetingUpdateBus()


async def _broadcast(meeting_id: str, event: str, payload: Dict[str, Any]) -> None:
    """Send meeting updates to SSE subscribers."""
    try:
        await update_bus.publish(meeting_id, event, payload)
    except Exception as exc:  # pragma: no cover - best-effort telemetry
        logger.warning("Failed to publish update for meeting %s: %s", meeting_id, exc)


# ---------------------------------------------------------------------------
# Bedrock client wrapper
# ---------------------------------------------------------------------------


def _require_bedrock() -> BedrockMeetingClient:
    try:
        return get_bedrock_client()
    except Exception as exc:
        raise RuntimeError(
            "Bedrock client is not initialised. Ensure AWS credentials and BEDROCK_MODEL_ID are configured."
        ) from exc


def _bedrock_ready() -> bool:
    try:
        get_bedrock_client()
        return True
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Utility helpers
# ---------------------------------------------------------------------------


def _json_default(obj: Any) -> str:
    if isinstance(obj, datetime):
        return obj.isoformat()
    return str(obj)


def _format_tool_response(success: bool, data: Any = None, error: Optional[str] = None) -> str:
    payload: Dict[str, Any] = {
        "success": success,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    if success:
        payload["data"] = data
    else:
        payload["error"] = error or "Unknown error"
    return json.dumps(payload, default=_json_default)


def _format_preferences(preferences: Dict[str, Any]) -> str:
    if not preferences:
        return "No explicit persona preferences provided."
    try:
        return json.dumps(preferences, indent=2)
    except TypeError:
        return str(preferences)


SUMMARY_SYSTEM_PROMPT = (
    "You are Meetmind's meeting intelligence engine. "
    "Always respond with a single JSON object that matches the provided schema. "
    "Do not include markdown, commentary, or additional text outside of JSON."
)

ACTION_SYSTEM_PROMPT = (
    "You are Meetmind's action item synthesiser. "
    "Your output must be strict JSON containing actionable follow-ups with owners."
)

EMAIL_SYSTEM_PROMPT = (
    "You are Meetmind's meeting communication specialist. "
    "Craft concise stakeholder emails using only the JSON structure requested."
)

PERSONA_SYSTEM_PROMPT = (
    "You are Meetmind's persona lens generator. "
    "Transform the meeting context into a focus view tailored to the persona."
)


def _build_summary_prompt(
    meeting_id: str,
    transcript: str,
    summary_style: str,
    agenda: Optional[str],
    preferences: Dict[str, Any],
) -> str:
    agenda_block = f"\nAgenda:\n{agenda}\n" if agenda else ""
    return (
        "Produce a JSON object with this exact shape:\n"
        "{\n"
        '  "meeting_id": string,\n'
        '  "summary": string,\n'
        '  "highlights": [string, ...],\n'
        '  "risks": [string, ...],\n'
        '  "topics": [{"id": string, "title": string, "summary": string, "confidence": float}],\n'
        '  "action_items": [{"title": string, "owner": string, "due_date": string, "priority": string, "status": string, "context": string}],\n'
        '  "next_steps": [string, ...]\n'
        "}\n"
        "Rules:\n"
        "- The response must be valid JSON.\n"
        "- Use ISO8601 format for any dates you infer.\n"
        "- Confidence values must be between 0 and 1.\n"
        "- Owner fields must come from transcript context; if unknown use \"Unassigned\".\n"
        f"- Adopt the '{summary_style}' tone.\n"
        f"- Persona preferences:\n{_format_preferences(preferences)}\n"
        f"{agenda_block}"
        "Transcript:\n"
        f"\"\"\"\n{transcript}\n\"\"\"\n"
        f"Meeting ID: {meeting_id}\n"
    )


def _build_action_prompt(
    meeting_id: str,
    transcript: str,
    focus: Optional[str],
    preferences: Dict[str, Any],
) -> str:
    focus_block = f"\nPrioritise action items related to: {focus}.\n" if focus else ""
    return (
        "Return JSON with the structure:\n"
        "{\n"
        '  "meeting_id": string,\n'
        '  "action_items": [\n'
        '    {\n'
        '      "title": string,\n'
        '      "owner": string,\n'
        '      "owner_role": string,\n'
        '      "due_date": string | null,\n'
        '      "priority": "high" | "medium" | "low",\n'
        '      "status": "pending" | "blocked" | "complete",\n'
        '      "context": string\n'
        "    }\n"
        "  ]\n"
        "}\n"
        "Constraints:\n"
        "- Keep between 3 and 8 action items.\n"
        "- Due dates must be ISO8601 when inferred, otherwise null.\n"
        "- Owner names should align with transcript mentions; default to \"Unassigned\" when unclear.\n"
        "- Context should summarise the rationale in 1-2 sentences.\n"
        f"- Persona preferences:\n{_format_preferences(preferences)}\n"
        f"{focus_block}"
        "Transcript:\n"
        f"\"\"\"\n{transcript}\n\"\"\"\n"
        f"Meeting ID: {meeting_id}\n"
    )


def _build_email_prompt(
    meeting_id: str,
    summary: Dict[str, Any],
    action_items: List[Dict[str, Any]],
    recipient_role: str,
    tone: str,
    preferences: Dict[str, Any],
) -> str:
    return (
        "Return JSON with the structure:\n"
        "{\n"
        '  "meeting_id": string,\n'
        '  "subject": string,\n'
        '  "preview": string,\n'
        '  "body": string,\n'
        '  "bullet_points": [string, ...]\n'
        "}\n"
        "Guidelines:\n"
        f"- Tone must be {tone} and appropriate for a {recipient_role}.\n"
        "- Highlight the most important decisions and commitments.\n"
        "- If action items exist include a concise list in the body.\n"
        "- Bullet points should align with persona preferences.\n"
        f"- Persona preferences:\n{_format_preferences(preferences)}\n"
        f"Summary JSON:\n{json.dumps(summary, indent=2)}\n"
        f"Action items:\n{json.dumps(action_items, indent=2)}\n"
        f"Meeting ID: {meeting_id}\n"
    )


def _build_persona_view_prompt(
    meeting_id: str,
    persona_id: str,
    summary: Dict[str, Any],
    action_items: List[Dict[str, Any]],
    preferences: Dict[str, Any],
) -> str:
    return (
        "Return JSON with the structure:\n"
        "{\n"
        '  "meeting_id": string,\n'
        '  "persona_id": string,\n'
        '  "sections": [{"title": string, "content": [string, ...]}],\n'
        '  "focus_topics": [string, ...],\n'
        '  "key_metrics": [string, ...],\n'
        '  "next_steps": [string, ...]\n'
        "}\n"
        "Guidelines:\n"
        "- Tailor the content to the persona preferences.\n"
        "- Focus topics should reference meeting topics or decisions.\n"
        "- Key metrics should highlight progress, risks, or KPIs mentioned.\n"
        "- Use clear, concise sentences.\n"
        f"- Persona preferences:\n{_format_preferences(preferences)}\n"
        f"Summary JSON:\n{json.dumps(summary, indent=2)}\n"
        f"Action items:\n{json.dumps(action_items, indent=2)}\n"
        f"Meeting ID: {meeting_id}\n"
        f"Persona ID: {persona_id}\n"
    )


# ---------------------------------------------------------------------------
# SSE endpoints
# ---------------------------------------------------------------------------


@app.get("/meetmind/meetings/{meeting_id}/stream")
async def stream_meeting_updates(
    meeting_id: str,
    request: Request,
    token: Optional[str] = None,
    cookie_token: Optional[str] = None
):
    """Enhanced Server-Sent Events endpoint with token and cookie authentication."""
    # Support both token query parameter and cookie authentication
    auth_token = token or cookie_token

    if not auth_token:
        raise HTTPException(
            status_code=401,
            detail="SSE token required (use /meetmind/auth/sse-token to obtain)"
        )

    if not verify_sse_token(auth_token, meeting_id):
        raise HTTPException(status_code=401, detail="Invalid or expired SSE token")

    queue = await update_bus.subscribe(meeting_id)
    snapshot = await meeting_memory.get_meeting_snapshot(meeting_id)

    async def event_generator():
        heartbeat_count = 0
        max_heartbeat_misses = 4  # Allow 4 missed heartbeats before disconnect

        try:
            # Send initial snapshot
            if snapshot and any(value for key, value in snapshot.items() if key not in {"meeting_id", "last_updated"} and value):
                yield {
                    "event": "snapshot",
                    "data": json.dumps(snapshot, default=_json_default),
                }

            while True:
                if await request.is_disconnected():
                    logger.info(f"SSE client disconnected from meeting {meeting_id}")
                    break

                try:
                    # Reduced timeout for more responsive heartbeats
                    message = await asyncio.wait_for(queue.get(), timeout=10)

                    payload = {
                        "meeting_id": meeting_id,
                        "timestamp": message.get("timestamp"),
                        "data": message.get("data"),
                    }
                    yield {
                        "event": message.get("event", "update"),
                        "data": json.dumps(payload, default=_json_default),
                    }

                    # Reset heartbeat counter on successful message
                    heartbeat_count = 0

                except asyncio.TimeoutError:
                    heartbeat_count += 1

                    # Enhanced heartbeat with connection status
                    heartbeat = {
                        "meeting_id": meeting_id,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "heartbeat_count": heartbeat_count,
                        "status": "active" if heartbeat_count < max_heartbeat_misses else "unhealthy",
                    }

                    yield {
                        "event": "heartbeat",
                        "data": json.dumps(heartbeat)
                    }

                    # Disconnect if too many heartbeat misses
                    if heartbeat_count >= max_heartbeat_misses:
                        logger.warning(f"SSE client for meeting {meeting_id} missed {heartbeat_count} heartbeats, disconnecting")
                        break

        except Exception as e:
            logger.error(f"SSE error for meeting {meeting_id}: {e}")
            error_event = {
                "meeting_id": meeting_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "error": str(e),
            }
            yield {
                "event": "error",
                "data": json.dumps(error_event)
            }
        finally:
            await update_bus.unsubscribe(meeting_id, queue)
            logger.info(f"SSE connection closed for meeting {meeting_id}")

    return EventSourceResponse(event_generator())


@app.get("/meetmind/meetings/{meeting_id}/stream/auth")
async def stream_meeting_updates_auth(meeting_id: str, request: Request, _: str = Depends(verify_api_key)):
    """SSE endpoint with API key authentication (for internal services)."""
    queue = await update_bus.subscribe(meeting_id)
    snapshot = await meeting_memory.get_meeting_snapshot(meeting_id)

    async def event_generator():
        try:
            if snapshot and any(value for key, value in snapshot.items() if key not in {"meeting_id", "last_updated"} and value):
                yield {
                    "event": "snapshot",
                    "data": json.dumps(snapshot, default=_json_default),
                }

            while True:
                if await request.is_disconnected():
                    break
                try:
                    message = await asyncio.wait_for(queue.get(), timeout=15)
                    payload = {
                        "meeting_id": meeting_id,
                        "timestamp": message.get("timestamp"),
                        "data": message.get("data"),
                    }
                    yield {
                        "event": message.get("event", "update"),
                        "data": json.dumps(payload, default=_json_default),
                    }
                except asyncio.TimeoutError:
                    heartbeat = {
                        "meeting_id": meeting_id,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "authenticated": True,
                    }
                    yield {"event": "heartbeat", "data": json.dumps(heartbeat)}
        finally:
            await update_bus.unsubscribe(meeting_id, queue)

    return EventSourceResponse(event_generator())


@app.get("/meetmind/meetings/{meeting_id}", dependencies=[Depends(verify_api_key)])
async def fetch_meeting_snapshot(meeting_id: str) -> Dict[str, Any]:
    """Fetch the latest snapshot of meeting state."""
    return await meeting_memory.get_meeting_snapshot(meeting_id)


@app.get("/meetmind/health")
async def health_check(_: str = Depends(verify_api_key)) -> Dict[str, Any]:
    """Health probe for deployment checks."""
    return {
        "status": "ok",
        "bedrock_ready": _bedrock_ready(),
        "stored_meetings": await meeting_memory.list_meetings(),
        "mcp_tools_handler_ready": mcp_tools_handler is not None,
        "registered_tools": len(mcp_tools_handler.tools) if mcp_tools_handler else 0,
    }


@app.get("/meetmind/integration/chatgpt")
async def get_chatgpt_integration(_: str = Depends(verify_api_key)) -> Dict[str, Any]:
    """Get ChatGPT Apps SDK integration documentation and examples."""
    return get_apps_sdk_integration_docs()


@app.get("/meetmind/integration/frontend")
async def get_frontend_integration(_: str = Depends(verify_api_key)) -> Dict[str, Any]:
    """Get custom frontend integration documentation."""
    return {
        "title": "Meetmind Custom Frontend Integration",
        "version": "1.0.0",
        "description": "Integration guide for custom frontend applications",
        "setup": {
            "dependencies": [
                "react",
                "axios",
                "eventsource",  # for SSE support
                "@mcp-ui/client"  # if using MCP UI components
            ],
            "configuration": {
                "mcp_server_url": "https://your-server.com/mcp",
                "sse_base_url": "https://your-server.com/meetmind/meetings"
            }
        },
        "sse_integration": {
            "authentication": "Use POST /meetmind/auth/sse-token to get token",
            "connection": "GET /meetmind/meetings/{meeting_id}/stream?token={token}",
            "events": [
                "snapshot - Initial meeting state",
                "summary - Meeting summary generated",
                "action_items - Action items created",
                "ui_resource - UI resource available",
                "heartbeat - Connection health check",
                "phase_update - Workflow phase completed",
                "workflow_completed - Entire workflow finished"
            ]
        },
        "example_react_component": """
import React, { useEffect, useState } from 'react';
import axios from 'axios';

const MeetingDashboard = ({ meetingId }) => {
  const [meetingData, setMeetingData] = useState(null);
  const [sseToken, setSseToken] = useState('');

  // Get SSE token on component mount
  useEffect(() => {
    const getToken = async () => {
      try {
        const response = await axios.post('/api/sse-token', {
          meeting_id: meetingId
        }, {
          headers: { 'Authorization': \`Bearer \${API_KEY}\` }
        });
        setSseToken(response.data.token);
      } catch (error) {
        console.error('Failed to get SSE token:', error);
      }
    };
    getToken();
  }, [meetingId]);

  // Connect to SSE when token is available
  useEffect(() => {
    if (!sseToken) return;

    const eventSource = new EventSource(
      \`/meetmind/meetings/\${meetingId}/stream?token=\${sseToken}\`
    );

    eventSource.onmessage = (event) => {
      const data = JSON.parse(event.data);
      setMeetingData(prev => ({ ...prev, ...data }));
    };

    eventSource.addEventListener('summary', (event) => {
      const summary = JSON.parse(event.data);
      console.log('New summary:', summary);
    });

    return () => eventSource.close();
  }, [sseToken, meetingId]);

  return (
    <div className="meeting-dashboard">
      <h2>Meeting: {meetingId}</h2>
      {meetingData?.summary && (
        <div className="summary-section">
          <h3>Summary</h3>
          <p>{meetingData.summary}</p>
        </div>
      )}
      {meetingData?.action_items && (
        <div className="action-items-section">
          <h3>Action Items</h3>
          <ul>
            {meetingData.action_items.map((item, index) => (
              <li key={index}>{item.title}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
};

export default MeetingDashboard;
        """,
        "ui_resource_rendering": {
            "raw_html": "Direct HTML injection for simple cases",
            "iframe_srcdoc": "Use iframe with srcDoc for isolated rendering",
            "custom_renderer": "Implement custom renderer for complex UI needs"
        }
    }


@app.get("/meetmind/tools/schemas")
async def get_tool_schemas(_: str = Depends(verify_api_key)) -> Dict[str, Any]:
    """Get JSON schemas for all available MCP tools."""
    if not mcp_tools_handler:
        raise HTTPException(status_code=503, detail="MCP Tools Handler not available")

    return {
        "tools": mcp_tools_handler.get_tool_schemas(),
        "handler_status": mcp_tools_handler.get_tools_status(),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@app.post("/meetmind/tools/{tool_name}/validate")
async def validate_tool_parameters(
    tool_name: str,
    parameters: Dict[str, Any],
    _: str = Depends(verify_api_key)
) -> Dict[str, Any]:
    """Validate tool parameters against Pydantic schemas."""
    if not mcp_tools_handler:
        raise HTTPException(status_code=503, detail="MCP Tools Handler not available")

    if tool_name not in mcp_tools_handler.tools:
        raise HTTPException(status_code=404, detail=f"Tool '{tool_name}' not found")

    try:
        # Use the enhanced tools handler for validation
        result = await mcp_tools_handler.execute_tool(tool_name, parameters)

        return {
            "valid": result.success,
            "tool_name": tool_name,
            "validation_errors": [result.error] if not result.success else [],
            "timestamp": result.timestamp,
        }
    except Exception as e:
        return {
            "valid": False,
            "tool_name": tool_name,
            "validation_errors": [str(e)],
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }


# ---------------------------------------------------------------------------
# MCP tool definitions
# ---------------------------------------------------------------------------


@mcp.tool()
async def summarize_meeting(
    meeting_id: str,
    transcript: str,
    summary_style: str = "executive",
    tenant_id: Optional[str] = None,
    persona_id: Optional[str] = None,
    agenda: Optional[str] = None,
    include_ui_resource: bool = True,
) -> str:
    """Summarise a meeting transcript using Bedrock and update meeting memory."""
    if not meeting_id:
        return _format_tool_response(False, error="meeting_id is required")
    if not transcript:
        return _format_tool_response(False, error="transcript is required")

    tenant_key = tenant_id or "default"
    await meeting_memory.append_transcript(
        meeting_id,
        transcript,
        {"source": "summarize_meeting", "summary_style": summary_style, "tenant_id": tenant_key},
    )

    persona_key = persona_id or summary_style
    preferences = await meeting_memory.get_persona_preferences(tenant_key, persona_key)

    try:
        client = _require_bedrock()
        structured = await client.generate_structured_json(
            system_prompt=SUMMARY_SYSTEM_PROMPT,
            user_prompt=_build_summary_prompt(meeting_id, transcript, summary_style, agenda, preferences),
            max_tokens=1800,
            temperature=0.15,
        )
    except Exception as exc:
        logger.error("summarize_meeting failed: %s", exc, exc_info=True)
        return _format_tool_response(False, error=str(exc))

    summary_payload = {
        "meeting_id": meeting_id,
        "style": summary_style,
        "persona_id": persona_key,
        "tenant_id": tenant_key,
        "summary": structured.get("summary"),
        "highlights": structured.get("highlights", []),
        "risks": structured.get("risks", []),
        "topics": structured.get("topics", []),
        "action_items": structured.get("action_items", []),
        "next_steps": structured.get("next_steps", []),
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }

    await meeting_memory.save_summary(meeting_id, summary_payload, tenant_id=tenant_key)
    if summary_payload["action_items"]:
        await meeting_memory.save_action_items(
            meeting_id, summary_payload["action_items"], tenant_id=tenant_key
        )

    # Generate UIResource if requested and handler is available
    if include_ui_resource and mcp_tools_handler:
        try:
            tool_result = await mcp_tools_handler.execute_tool("summarize_meeting", {
                "meeting_id": meeting_id,
                "transcript": transcript,
                "summary_style": summary_style,
                "tenant_id": tenant_id,
                "persona_id": persona_id,
                "agenda": agenda,
            })

            if tool_result.success and tool_result.data:
                ui_resource = tool_result.data.get("ui_resource")
                if ui_resource:
                    summary_payload["ui_resource"] = ui_resource
                    # Also broadcast UIResource via SSE
                    await _broadcast(meeting_id, "ui_resource", {
                        "tool": "summarize_meeting",
                        "ui_resource": ui_resource
                    })
        except Exception as e:
            logger.warning(f"Failed to generate UIResource for summary: {e}")

    await _broadcast(meeting_id, "summary", summary_payload)

    return _format_tool_response(True, data=summary_payload)


@mcp.tool()
async def generate_action_items(
    meeting_id: str,
    transcript: str,
    focus: Optional[str] = None,
    tenant_id: Optional[str] = None,
    persona_id: Optional[str] = None,
    include_ui_resource: bool = True,
) -> str:
    """Generate structured action items for a meeting."""
    if not meeting_id:
        return _format_tool_response(False, error="meeting_id is required")
    if not transcript:
        return _format_tool_response(False, error="transcript is required")

    tenant_key = tenant_id or "default"
    await meeting_memory.append_transcript(
        meeting_id,
        transcript,
        {"source": "generate_action_items", "focus": focus, "tenant_id": tenant_key},
    )

    persona_key = persona_id or "general"
    preferences = await meeting_memory.get_persona_preferences(tenant_key, persona_key)

    try:
        client = _require_bedrock()
        structured = await client.generate_structured_json(
            system_prompt=ACTION_SYSTEM_PROMPT,
            user_prompt=_build_action_prompt(meeting_id, transcript, focus, preferences),
            max_tokens=1200,
            temperature=0.1,
        )
    except Exception as exc:
        logger.error("generate_action_items failed: %s", exc, exc_info=True)
        return _format_tool_response(False, error=str(exc))

    action_payload = {
        "meeting_id": meeting_id,
        "action_items": structured.get("action_items", []),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "tenant_id": tenant_key,
    }

    if action_payload["action_items"]:
        await meeting_memory.save_action_items(
            meeting_id, action_payload["action_items"], tenant_id=tenant_key
        )

    # Generate UIResource if requested and handler is available
    if include_ui_resource and mcp_tools_handler:
        try:
            tool_result = await mcp_tools_handler.execute_tool("generate_action_items", {
                "meeting_id": meeting_id,
                "transcript": transcript,
                "focus": focus,
                "tenant_id": tenant_id,
                "persona_id": persona_id,
            })

            if tool_result.success and tool_result.data:
                ui_resource = tool_result.data.get("ui_resource")
                if ui_resource:
                    action_payload["ui_resource"] = ui_resource
                    # Also broadcast UIResource via SSE
                    await _broadcast(meeting_id, "ui_resource", {
                        "tool": "generate_action_items",
                        "ui_resource": ui_resource
                    })
        except Exception as e:
            logger.warning(f"Failed to generate UIResource for action items: {e}")

    await _broadcast(meeting_id, "action_items", action_payload)

    return _format_tool_response(True, data=action_payload)


@mcp.tool()
async def prepare_email_summary(
    meeting_id: str,
    recipient_role: str = "stakeholder",
    include_action_items: bool = True,
    tone: str = "professional",
    tenant_id: Optional[str] = None,
    persona_id: Optional[str] = None,
) -> str:
    """Compose an outbound email summary tailored to the recipient."""
    snapshot = await meeting_memory.get_meeting_snapshot(meeting_id)
    summary = snapshot.get("summary")
    if not summary:
        return _format_tool_response(False, error="No summary available for meeting.")

    action_items = snapshot.get("action_items", []) if include_action_items else []

    tenant_key = tenant_id or snapshot.get("tenant_id") or "default"
    persona_key = persona_id or recipient_role.lower()
    preferences = await meeting_memory.get_persona_preferences(tenant_key, persona_key)

    try:
        client = _require_bedrock()
        structured = await client.generate_structured_json(
            system_prompt=EMAIL_SYSTEM_PROMPT,
            user_prompt=_build_email_prompt(
                meeting_id,
                summary,
                action_items,
                recipient_role,
                tone,
                preferences,
            ),
            max_tokens=1000,
            temperature=0.2,
        )
    except Exception as exc:
        logger.error("prepare_email_summary failed: %s", exc, exc_info=True)
        return _format_tool_response(False, error=str(exc))

    email_payload = {
        "meeting_id": meeting_id,
        "subject": structured.get("subject"),
        "preview": structured.get("preview"),
        "body": structured.get("body"),
        "bullet_points": structured.get("bullet_points", []),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "recipient_role": recipient_role,
        "tone": tone,
        "tenant_id": tenant_key,
    }

    await meeting_memory.save_metadata(
        meeting_id, {"last_email_summary": email_payload}, tenant_id=tenant_key
    )
    await _broadcast(meeting_id, "email_summary", email_payload)

    return _format_tool_response(True, data=email_payload)


@mcp.tool()
async def topic_navigation(
    meeting_id: str,
    direction: str = "next",
    current_topic_index: int = 0,
) -> str:
    """Navigate stored meeting topics for UI clients."""
    snapshot = await meeting_memory.get_meeting_snapshot(meeting_id)
    summary = snapshot.get("summary") or {}
    topics = summary.get("topics") or []

    if not topics:
        return _format_tool_response(False, error="No topics available for meeting.")

    direction = direction.lower()
    if direction not in {"next", "previous", "current"}:
        return _format_tool_response(False, error="direction must be next, previous, or current")

    index = max(0, min(current_topic_index, len(topics) - 1))
    if direction == "next":
        index = (index + 1) % len(topics)
    elif direction == "previous":
        index = (index - 1) % len(topics)

    topic_payload = {
        "meeting_id": meeting_id,
        "topic": topics[index],
        "index": index,
        "total_topics": len(topics),
    }

    await _broadcast(meeting_id, "topic_navigation", topic_payload)

    return _format_tool_response(True, data=topic_payload)


@mcp.tool()
async def personalized_focus_view(
    meeting_id: str,
    persona_id: str,
    tenant_id: Optional[str] = None,
    include_action_items: bool = True,
) -> str:
    """Generate a persona-specific focus view from stored meeting data."""
    snapshot = await meeting_memory.get_meeting_snapshot(meeting_id)
    summary = snapshot.get("summary")
    if not summary:
        return _format_tool_response(False, error="No summary available for meeting.")

    action_items = snapshot.get("action_items", []) if include_action_items else []
    tenant_key = tenant_id or snapshot.get("tenant_id") or "default"
    preferences = await meeting_memory.get_persona_preferences(tenant_key, persona_id)

    try:
        client = _require_bedrock()
        structured = await client.generate_structured_json(
            system_prompt=PERSONA_SYSTEM_PROMPT,
            user_prompt=_build_persona_view_prompt(
                meeting_id,
                persona_id,
                summary,
                action_items,
                preferences,
            ),
            max_tokens=1200,
            temperature=0.2,
        )
    except Exception as exc:
        logger.error("personalized_focus_view failed: %s", exc, exc_info=True)
        return _format_tool_response(False, error=str(exc))

    focus_payload = {
        "meeting_id": meeting_id,
        "persona_id": persona_id,
        "sections": structured.get("sections", []),
        "focus_topics": structured.get("focus_topics", []),
        "key_metrics": structured.get("key_metrics", []),
        "next_steps": structured.get("next_steps", []),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "tenant_id": tenant_key,
    }

    await _broadcast(meeting_id, "persona_view", focus_payload)

    return _format_tool_response(True, data=focus_payload)


# ---------------------------------------------------------------------------
# REST helper for internal orchestration
# ---------------------------------------------------------------------------

TOOL_REGISTRY = {
    "summarize_meeting": summarize_meeting,
    "generate_action_items": generate_action_items,
    "prepare_email_summary": prepare_email_summary,
    "topic_navigation": topic_navigation,
    "personalized_focus_view": personalized_focus_view,
}


@app.post("/meetmind/tools/{tool_name}")
async def invoke_tool_endpoint(tool_name: str, request: Request, _: str = Depends(verify_api_key)):
    """HTTP helper allowing internal agents to invoke MCP tools securely."""
    tool = TOOL_REGISTRY.get(tool_name)
    if not tool:
        raise HTTPException(status_code=404, detail=f"Unknown tool '{tool_name}'")

    try:
        payload = await request.json()
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Invalid JSON payload: {exc}") from exc

    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="Payload must be a JSON object.")

    try:
        result = await tool(**payload)
    except TypeError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid parameters: {exc}") from exc

    try:
        return json.loads(result)
    except json.JSONDecodeError:
        return {"raw": result}


# ---------------------------------------------------------------------------
# Documentation and integration helpers
# ---------------------------------------------------------------------------

def get_apps_sdk_integration_docs() -> Dict[str, Any]:
    """Get documentation for ChatGPT Apps SDK integration."""
    return {
        "title": "Meetmind MCP Server - ChatGPT Apps SDK Integration",
        "version": "1.0.0",
        "description": "Integration guide for using Meetmind MCP tools with ChatGPT Apps SDK",
        "setup": {
            "prerequisites": [
                "ChatGPT Plus or Enterprise account",
                "Access to GPT-4 or Claude models",
                "Meetmind MCP server running and accessible"
            ],
            "configuration": {
                "mcp_server_url": "https://your-server.com/mcp",
                "mcp_api_key": "your-api-key",
                "sse_base_url": "https://your-server.com/meetmind/meetings"
            }
        },
        "output_templates": {
            "summary_template": {
                "_meta": {
                    "openai/outputTemplate": "ui://meetmind/summary/v1"
                },
                "description": "Template for displaying meeting summaries in ChatGPT"
            },
            "action_items_template": {
                "_meta": {
                    "openai/outputTemplate": "ui://meetmind/action-items/v1"
                },
                "description": "Template for displaying action items in ChatGPT"
            },
            "email_template": {
                "_meta": {
                    "openai/outputTemplate": "ui://meetmind/email-summary/v1"
                },
                "description": "Template for displaying email summaries in ChatGPT"
            }
        },
        "example_usage": {
            "javascript": """
// Example ChatGPT Apps SDK integration
const { createMCPClient } = require('@modelcontextprotocol/sdk');

// Initialize MCP client
const client = createMCPClient({
  serverUrl: 'https://your-server.com/mcp',
  apiKey: 'your-api-key'
});

// Register output templates
client.registerOutputTemplate('ui://meetmind/summary/v1', {
  render: (data) => `
    <div class="meeting-summary">
      <h2>Meeting Summary</h2>
      <p>${data.summary}</p>
      <ul>
        ${data.highlights.map(h => `<li>${h}</li>`).join('')}
      </ul>
    </div>
  `
});

// Use tools
const result = await client.callTool('summarize_meeting', {
  meeting_id: 'meeting-123',
  transcript: 'Meeting transcript...',
  summary_style: 'executive'
});
            """,
            "python": """
# Example Python integration
import requests
import json

# Get SSE token
token_response = requests.post(
    'https://your-server.com/meetmind/auth/sse-token',
    headers={'Authorization': f'Bearer {api_key}'},
    json={'meeting_id': 'meeting-123'}
)

sse_token = token_response.json()['token']

# Connect to SSE stream
import sseclient

sse_url = f'https://your-server.com/meetmind/meetings/meeting-123/stream?token={sse_token}'
client = sseclient.SSEClient(sse_url)

for event in client.events():
    if event.event == 'summary':
        data = json.loads(event.data)
        print(f"Summary: {data['data']['summary']}")
    elif event.event == 'ui_resource':
        ui_data = json.loads(event.data)
        print(f"UI Resource: {ui_data['ui_resource']['uri']}")
            """
        }
    }


# ---------------------------------------------------------------------------
# Entrypoint helper
# ---------------------------------------------------------------------------


if __name__ == "__main__":  # pragma: no cover - manual launch
    import uvicorn

    host = os.getenv("MCP_HOST", "0.0.0.0")
    port = int(os.getenv("MCP_PORT", "8150"))
    uvicorn.run(app, host=host, port=port, log_level=LOG_LEVEL.lower())
