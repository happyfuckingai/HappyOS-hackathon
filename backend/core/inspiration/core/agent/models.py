"""
🤖 Agent Data Models
Dataclasses and Enums for the Enhanced Mr Happy Agent.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, Any, List, Optional

class ConversationState(Enum):
    """Enhanced conversation states."""
    IDLE = "idle"
    LISTENING = "listening"
    ANALYZING = "analyzing"
    SKILL_SEARCHING = "skill_searching"
    SKILL_GENERATING = "skill_generating"
    EXECUTING = "executing"
    WAITING_FOR_CLARIFICATION = "waiting_for_clarification"
    ERROR_RECOVERY = "error_recovery"
    COMPLETED = "completed"


@dataclass
class EnhancedStatusUpdate:
    """Enhanced status update with more context."""
    type: str  # "status", "progress", "result", "error", "personality"
    message: str
    data: Dict[str, Any]
    timestamp: datetime
    conversation_id: str
    personality_tone: str = "friendly"  # "friendly", "encouraging", "apologetic", "excited"
    confidence_level: float = 1.0
    estimated_completion: Optional[datetime] = None


@dataclass
class ConversationContext:
    """Enhanced conversation context."""
    conversation_id: str
    user_id: str
    state: ConversationState
    current_task: Optional[str]
    history: List[Dict[str, Any]]
    context_data: Dict[str, Any]
    created_at: datetime
    last_activity: datetime
    pending_tasks: Dict[str, Dict[str, Any]]
    user_preferences: Dict[str, Any]
    skill_generation_history: List[Dict[str, Any]]
    error_recovery_attempts: int = 0
    personality_context: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TaskInfo:
    """Enhanced task information."""
    task_id: str
    description: str
    started_at: datetime
    status: str
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    skill_used: Optional[str] = None
    skill_generated: bool = False
    execution_time: Optional[float] = None
    retry_count: int = 0
    personality_feedback: List[str] = field(default_factory=list)
