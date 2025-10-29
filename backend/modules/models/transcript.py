"""
T009: Transcript Event Models

Immutable data models for transcript events from LiveKit transcription stream.
These models form the core input to the SummarizerIngestWorker pipeline.

Reference: specs/009-agent-transcript-broker-decoupling/data-model.md
"""

from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional
from datetime import datetime
import uuid


@dataclass
class TranscriptEvent:
    """
    Immutable event from LiveKit transcription stream.
    
    This is the core input model for the SummarizerIngestWorker pipeline.
    All downstream processors (topic_detector, phase_detector, etc.) consume this.
    
    Validation:
    - start_ms < end_ms
    - 0.0 ≤ confidence ≤ 1.0
    - text not empty (except for silence events)
    - meeting_id and speaker_id are non-empty strings
    """
    
    # Identity
    meeting_id: str              # UUID or room name
    speaker_id: str              # Participant identity or "guest-N"
    
    # Content
    text: str                    # Transcript segment (1-100 words typical)
    confidence: float            # 0.0-1.0 (LiveKit Transcribe confidence)
    
    # Timing (in milliseconds from meeting start)
    start_ms: int                # Segment start
    end_ms: int                  # Segment end
    is_final: bool               # True = final segment, False = interim
    
    # Channel & Source
    channel: str = "mono"        # "L", "R", "mono", or speaker_id (for diarization)
    source: str = "livekit_transcribe"  # For extensibility
    
    # Metadata
    meta: Dict[str, Any] = field(default_factory=dict)
    # Possible keys: "language", "accent_confidence", "sentiment_hint", "emotion"
    
    # Computed
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: datetime = field(default_factory=datetime.utcnow)
    
    def __post_init__(self):
        """Validate event after initialization"""
        if self.start_ms >= self.end_ms:
            raise ValueError(f"start_ms ({self.start_ms}) must be < end_ms ({self.end_ms})")
        
        if not (0.0 <= self.confidence <= 1.0):
            raise ValueError(f"confidence ({self.confidence}) must be in [0.0, 1.0]")
        
        if not self.text.strip():
            raise ValueError("text cannot be empty")
        
        if not self.meeting_id.strip():
            raise ValueError("meeting_id cannot be empty")
        
        if not self.speaker_id.strip():
            raise ValueError("speaker_id cannot be empty")
    
    def duration_ms(self) -> int:
        """Return segment duration in milliseconds"""
        return self.end_ms - self.start_ms
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to JSON-serializable dict"""
        return {
            "id": self.id,
            "meeting_id": self.meeting_id,
            "speaker_id": self.speaker_id,
            "text": self.text,
            "confidence": self.confidence,
            "start_ms": self.start_ms,
            "end_ms": self.end_ms,
            "is_final": self.is_final,
            "channel": self.channel,
            "source": self.source,
            "meta": self.meta,
            "created_at": self.created_at.isoformat(),
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TranscriptEvent":
        """Create TranscriptEvent from dict"""
        data_copy = data.copy()
        # Remove computed fields if present
        data_copy.pop("id", None)
        data_copy.pop("created_at", None)
        return cls(**data_copy)


@dataclass
class ActionItem:
    """
    Extracted action from conversation; tracked through lifecycle.
    
    Reference: specs/009-agent-transcript-broker-decoupling/data-model.md
    """
    
    # Identity
    id: str = field(default_factory=lambda: f"action-{uuid.uuid4().hex[:8]}")
    meeting_id: str = ""
    
    # Content
    owner: str = ""              # Person responsible
    what: str = ""               # Description (verb phrase, 5-50 words)
    when: str = ""               # "EOD", "EOW", "2025-10-22", "ASAP", etc.
    
    # Context
    source_quote: Optional[str] = None
    source_timestamp_ms: int = 0
    
    # Lifecycle
    status: str = "open"         # "open" | "in-progress" | "done"
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    
    # Metadata
    priority: str = "normal"     # "low" | "normal" | "high"
    confidence: float = 1.0      # 0-1 (extraction confidence)
    persona_visible: List[str] = field(default_factory=lambda: ["PO", "Eng"])
    
    def __post_init__(self):
        """Validate action item"""
        if not self.owner.strip():
            raise ValueError("owner cannot be empty")
        
        if not (5 <= len(self.what) <= 500):
            raise ValueError(f"what must be 5-500 chars, got {len(self.what)}")
        
        if self.status not in ["open", "in-progress", "done"]:
            raise ValueError(f"status must be open|in-progress|done, got {self.status}")
        
        if self.priority not in ["low", "normal", "high"]:
            raise ValueError(f"priority must be low|normal|high, got {self.priority}")
        
        if not (0.0 <= self.confidence <= 1.0):
            raise ValueError(f"confidence must be in [0.0, 1.0], got {self.confidence}")
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to JSON-serializable dict"""
        return {
            "id": self.id,
            "meeting_id": self.meeting_id,
            "owner": self.owner,
            "what": self.what,
            "when": self.when,
            "source_quote": self.source_quote,
            "source_timestamp_ms": self.source_timestamp_ms,
            "status": self.status,
            "priority": self.priority,
            "confidence": self.confidence,
            "persona_visible": self.persona_visible,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


@dataclass
class Topic:
    """
    Identified discussion topic; tracked through conversation.
    
    Reference: specs/009-agent-transcript-broker-decoupling/data-model.md
    """
    
    # Identity
    id: str = field(default_factory=lambda: f"topic-{uuid.uuid4().hex[:8]}")
    name: str = ""               # Human-readable (10-40 chars)
    
    # Participants
    speakers: List[str] = field(default_factory=list)
    last_speaker: str = ""
    
    # State
    sentiment: str = "neutral"   # "positive" | "neutral" | "negative"
    energy: str = "medium"       # "low" | "medium" | "high"
    
    # Timing
    first_mention_ms: int = 0
    last_update_ms: int = 0
    mention_count: int = 1
    
    # Metadata
    keywords: List[str] = field(default_factory=list)
    
    def __post_init__(self):
        """Validate topic"""
        if not (10 <= len(self.name) <= 100):
            raise ValueError(f"name must be 10-100 chars, got {len(self.name)}")
        
        if self.sentiment not in ["positive", "neutral", "negative"]:
            raise ValueError(f"sentiment must be positive|neutral|negative, got {self.sentiment}")
        
        if self.energy not in ["low", "medium", "high"]:
            raise ValueError(f"energy must be low|medium|high, got {self.energy}")
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to JSON-serializable dict"""
        return {
            "id": self.id,
            "name": self.name,
            "speakers": self.speakers,
            "last_speaker": self.last_speaker,
            "sentiment": self.sentiment,
            "energy": self.energy,
            "first_mention_ms": self.first_mention_ms,
            "last_update_ms": self.last_update_ms,
            "mention_count": self.mention_count,
            "keywords": self.keywords,
        }


@dataclass
class ConversationContext:
    """
    Persona-specific summary of conversation state.
    Read by agent via MCP method: get_conversation_context_async()
    
    Reference: specs/009-agent-transcript-broker-decoupling/data-model.md
    """
    
    # Identity
    meeting_id: str = ""
    persona: str = "PO"          # "PO" | "Eng" | "CS" | "Exec"
    
    # Summary Content
    summary: str = ""            # 2-3 sentences
    topics: List[Topic] = field(default_factory=list)
    actions: List[ActionItem] = field(default_factory=list)
    risks: List[str] = field(default_factory=list)
    
    # State
    phase: str = "scoping"       # "scoping" | "exploring" | "deciding" | "committed" | "wrapping"
    energy_level: str = "medium"  # "low" | "medium" | "high"
    
    # Metadata
    updated_at: datetime = field(default_factory=datetime.utcnow)
    confidence_score: float = 0.8
    
    def __post_init__(self):
        """Validate context"""
        if not (50 <= len(self.summary) <= 1000):
            raise ValueError(f"summary must be 50-1000 chars, got {len(self.summary)}")
        
        if self.phase not in ["scoping", "exploring", "deciding", "committed", "wrapping"]:
            raise ValueError(f"phase must be valid enum, got {self.phase}")
        
        if self.energy_level not in ["low", "medium", "high"]:
            raise ValueError(f"energy_level must be low|medium|high, got {self.energy_level}")
        
        if not (0.0 <= self.confidence_score <= 1.0):
            raise ValueError(f"confidence_score must be in [0.0, 1.0], got {self.confidence_score}")
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to JSON-serializable dict for Redis"""
        return {
            "meeting_id": self.meeting_id,
            "persona": self.persona,
            "summary": self.summary,
            "topics": [t.to_dict() for t in self.topics],
            "actions": [a.to_dict() for a in self.actions],
            "risks": self.risks,
            "phase": self.phase,
            "energy_level": self.energy_level,
            "updated_at": self.updated_at.isoformat(),
            "confidence_score": self.confidence_score,
        }


@dataclass
class Visual:
    """
    UI artifact published to frontend via Redis.
    
    Used in MCP method: get_visuals_async()
    """
    
    # Identity
    id: str = field(default_factory=lambda: f"visual-{uuid.uuid4().hex[:8]}")
    meeting_id: str = ""
    kind: str = ""               # "phase_bar" | "action_card" | "topic_chip" | "highlight"
    
    # Content
    label: str = ""              # Display text
    data: Dict[str, Any] = field(default_factory=dict)
    
    # State
    visible: bool = True
    persona_filter: List[str] = field(default_factory=lambda: ["PO", "Eng"])
    
    # Metadata
    created_at: datetime = field(default_factory=datetime.utcnow)
    ttl_seconds: int = 300       # Time to live
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to JSON-serializable dict"""
        return {
            "id": self.id,
            "meeting_id": self.meeting_id,
            "kind": self.kind,
            "label": self.label,
            "data": self.data,
            "visible": self.visible,
            "persona_filter": self.persona_filter,
            "created_at": self.created_at.isoformat(),
            "ttl_seconds": self.ttl_seconds,
        }
