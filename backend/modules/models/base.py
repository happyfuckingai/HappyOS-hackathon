from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

class User(BaseModel):
    id: str
    username: str
    email: str
    role: str  # "admin", "user", etc.

class LoginRequest(BaseModel):
    email: str
    password: str

class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int = 1800  # 30 minutes in seconds

class RefreshTokenRequest(BaseModel):
    refresh_token: str

class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    expires_in: int = 1800

class Agent(BaseModel):
    id: str
    name: str
    status: str  # "running", "stopped", "error"
    created_at: datetime
    participant_id: Optional[str] = None

class AgentProcess(BaseModel):
    id: str
    agent_id: str
    process_type: str  # subprocess, container, worker
    pid: Optional[int] = None
    container_id: Optional[str] = None
    worker_id: Optional[str] = None
    status: str  # starting, running, stopping, stopped, failed
    last_heartbeat: Optional[datetime] = None
    resource_usage: Optional[dict] = None
    config: Optional[dict] = None
    error_message: Optional[str] = None
    created_at: datetime
    updated_at: datetime

class AgentConfig(BaseModel):
    name: str
    process_type: str = "subprocess"  # subprocess, container, worker
    command: Optional[str] = None
    args: Optional[List[str]] = None
    env: Optional[dict] = None
    working_dir: Optional[str] = None
    timeout: Optional[int] = 30
    restart_policy: str = "on-failure"  # never, on-failure, always
    max_restarts: int = 3
    resource_limits: Optional[dict] = None

class AgentStatus(BaseModel):
    agent_id: str
    process_id: Optional[str] = None
    status: str
    pid: Optional[int] = None
    container_id: Optional[str] = None
    worker_id: Optional[str] = None
    last_heartbeat: Optional[datetime] = None
    resource_usage: Optional[dict] = None
    uptime_seconds: Optional[int] = None
    restart_count: int = 0

class ResourceMetrics(BaseModel):
    cpu_percent: Optional[float] = None
    memory_mb: Optional[float] = None
    memory_percent: Optional[float] = None
    disk_io_read_mb: Optional[float] = None
    disk_io_write_mb: Optional[float] = None
    network_io_sent_mb: Optional[float] = None
    network_io_recv_mb: Optional[float] = None
    open_files: Optional[int] = None
    threads: Optional[int] = None

class AgentStartRequest(BaseModel):
    name: str
    participant_id: Optional[str] = None

class AgentSessionRequest(BaseModel):
    participant_id: Optional[str] = None

class AgentSessionResponse(BaseModel):
    session_id: str
    agent_name: str
    room: str
    metadata: Optional[dict] = None

class Meeting(BaseModel):
    id: str
    name: str
    status: str  # "active", "completed", "cancelled"
    created_at: datetime
    participants: List[str] = []
    owner_id: str
    mem0_context: Optional[dict] = None

class MeetingCreateRequest(BaseModel):
    name: str
    participants: Optional[List[str]] = []
    memory_mode: Optional[str] = "auto"  # auto, manual, hybrid
    memory_retention_days: Optional[int] = 90
    allow_participant_memories: Optional[bool] = True

class MeetingJoinRequest(BaseModel):
    participant_id: str

class SummarizeRequest(BaseModel):
    meeting_id: str
    content: str

class SummarizeResponse(BaseModel):
    summary: str
    topics: List[str]
    action_items: List[str]

class ToolInfo(BaseModel):
    name: str
    description: str
    parameters: dict

# ========== MEM0 MODELS ==========

class Memory(BaseModel):
    id: Optional[str] = None
    content: str
    metadata: Optional[dict] = None
    user_id: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

class MemoryCreateRequest(BaseModel):
    content: str
    metadata: Optional[dict] = None
    user_id: Optional[str] = None

class MemoryUpdateRequest(BaseModel):
    content: Optional[str] = None
    metadata: Optional[dict] = None

class MemorySearchRequest(BaseModel):
    query: str
    limit: Optional[int] = 20
    filters: Optional[dict] = None

class MemoryLinkRequest(BaseModel):
    memory_ids: List[str]

class MeetingMemoryStats(BaseModel):
    meeting_id: str
    total_memories: int
    categories: dict
    linked_at: Optional[datetime] = None

class MemoryStats(BaseModel):
    total_memories: int
    memories_with_metadata: int
    categories: dict
    this_week: int
    this_month: int
    average_per_week: int
    oldest_memory: Optional[datetime] = None
    newest_memory: Optional[datetime] = None

class MemoryExportResponse(BaseModel):
    memories: List[Memory]
    exported_at: datetime
    total_count: int
    user_id: str

class MemoryCategory(BaseModel):
    name: str
    count: int
    latest_memory: Optional[datetime] = None

class MemoryCategoriesResponse(BaseModel):
    categories: List[MemoryCategory]
    total_categories: int

class MemoryFilterRequest(BaseModel):
    date_range: Optional[dict] = None  # {"start": "2024-01-01", "end": "2024-12-31"}
    categories: Optional[List[str]] = None
    has_metadata: Optional[bool] = None

class SemanticSearchRequest(BaseModel):
    query: str
    limit: Optional[int] = 10
    threshold: Optional[float] = 0.7
    filters: Optional[dict] = None

class MemoryAnalysisRequest(BaseModel):
    time_range: Optional[str] = None  # "day", "week", "month", "all"
    categories: Optional[List[str]] = None
    include_trends: Optional[bool] = True
    include_insights: Optional[bool] = True
