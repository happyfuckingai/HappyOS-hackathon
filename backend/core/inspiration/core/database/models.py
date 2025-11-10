"""
📊 DATABASE MODELS - DATA STRUCTURES FOR HAPPYOS

Defines the data models for:
- Conversations and messages
- User profiles and preferences
- Skill usage analytics
- Performance metrics
- System configuration
"""

import json
from datetime import datetime
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, asdict, field
from enum import Enum


class ConversationState(Enum):
    """Conversation states."""
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    ARCHIVED = "archived"
    ERROR = "error"


class MessageType(Enum):
    """Message types."""
    USER_INPUT = "user_input"
    AGENT_RESPONSE = "agent_response"
    SYSTEM_MESSAGE = "system_message"
    STATUS_UPDATE = "status_update"
    ERROR_MESSAGE = "error_message"


class SkillExecutionStatus(Enum):
    """Skill execution status."""
    SUCCESS = "success"
    FAILURE = "failure"
    TIMEOUT = "timeout"
    ERROR = "error"
    CANCELLED = "cancelled"


@dataclass
class Conversation:
    """Conversation model."""
    conversation_id: str
    user_id: str
    state: ConversationState
    created_at: datetime
    last_activity: datetime
    context_data: Dict[str, Any] = field(default_factory=dict)
    user_preferences: Dict[str, Any] = field(default_factory=dict)
    personality_context: Dict[str, Any] = field(default_factory=dict)
    total_messages: int = 0
    total_skills_used: int = 0
    total_skills_generated: int = 0
    average_response_time: float = 0.0
    user_satisfaction_score: Optional[float] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for database storage."""
        data = asdict(self)
        data['state'] = self.state.value
        data['created_at'] = self.created_at.isoformat()
        data['last_activity'] = self.last_activity.isoformat()
        data['context_data'] = json.dumps(self.context_data)
        data['user_preferences'] = json.dumps(self.user_preferences)
        data['personality_context'] = json.dumps(self.personality_context)
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Conversation':
        """Create from dictionary from database."""
        return cls(
            conversation_id=data['conversation_id'],
            user_id=data['user_id'],
            state=ConversationState(data['state']),
            created_at=datetime.fromisoformat(data['created_at']),
            last_activity=datetime.fromisoformat(data['last_activity']),
            context_data=json.loads(data.get('context_data', '{}')),
            user_preferences=json.loads(data.get('user_preferences', '{}')),
            personality_context=json.loads(data.get('personality_context', '{}')),
            total_messages=data.get('total_messages', 0),
            total_skills_used=data.get('total_skills_used', 0),
            total_skills_generated=data.get('total_skills_generated', 0),
            average_response_time=data.get('average_response_time', 0.0),
            user_satisfaction_score=data.get('user_satisfaction_score')
        )


@dataclass
class ConversationMessage:
    """Conversation message model."""
    message_id: str
    conversation_id: str
    message_type: MessageType
    content: str
    timestamp: datetime
    metadata: Dict[str, Any] = field(default_factory=dict)
    task_id: Optional[str] = None
    skill_used: Optional[str] = None
    response_time: Optional[float] = None
    confidence_score: Optional[float] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for database storage."""
        data = asdict(self)
        data['message_type'] = self.message_type.value
        data['timestamp'] = self.timestamp.isoformat()
        data['metadata'] = json.dumps(self.metadata)
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ConversationMessage':
        """Create from dictionary from database."""
        return cls(
            message_id=data['message_id'],
            conversation_id=data['conversation_id'],
            message_type=MessageType(data['message_type']),
            content=data['content'],
            timestamp=datetime.fromisoformat(data['timestamp']),
            metadata=json.loads(data.get('metadata', '{}')),
            task_id=data.get('task_id'),
            skill_used=data.get('skill_used'),
            response_time=data.get('response_time'),
            confidence_score=data.get('confidence_score')
        )


@dataclass
class UserProfile:
    """User profile model."""
    user_id: str
    username: Optional[str]
    email: Optional[str]
    created_at: datetime
    last_active: datetime
    preferences: Dict[str, Any] = field(default_factory=dict)
    personality_traits: Dict[str, Any] = field(default_factory=dict)
    interaction_patterns: Dict[str, Any] = field(default_factory=dict)
    skill_preferences: Dict[str, Any] = field(default_factory=dict)
    total_conversations: int = 0
    total_messages: int = 0
    total_skills_used: int = 0
    average_session_duration: float = 0.0
    preferred_communication_style: Optional[str] = None
    timezone: Optional[str] = None
    language: str = "en"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for database storage."""
        data = asdict(self)
        data['created_at'] = self.created_at.isoformat()
        data['last_active'] = self.last_active.isoformat()
        data['preferences'] = json.dumps(self.preferences)
        data['personality_traits'] = json.dumps(self.personality_traits)
        data['interaction_patterns'] = json.dumps(self.interaction_patterns)
        data['skill_preferences'] = json.dumps(self.skill_preferences)
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'UserProfile':
        """Create from dictionary from database."""
        return cls(
            user_id=data['user_id'],
            username=data.get('username'),
            email=data.get('email'),
            created_at=datetime.fromisoformat(data['created_at']),
            last_active=datetime.fromisoformat(data['last_active']),
            preferences=json.loads(data.get('preferences', '{}')),
            personality_traits=json.loads(data.get('personality_traits', '{}')),
            interaction_patterns=json.loads(data.get('interaction_patterns', '{}')),
            skill_preferences=json.loads(data.get('skill_preferences', '{}')),
            total_conversations=data.get('total_conversations', 0),
            total_messages=data.get('total_messages', 0),
            total_skills_used=data.get('total_skills_used', 0),
            average_session_duration=data.get('average_session_duration', 0.0),
            preferred_communication_style=data.get('preferred_communication_style'),
            timezone=data.get('timezone'),
            language=data.get('language', 'en')
        )


@dataclass
class SkillUsage:
    """Skill usage analytics model."""
    usage_id: str
    skill_id: str
    skill_name: str
    user_id: str
    conversation_id: str
    execution_status: SkillExecutionStatus
    execution_time: float
    timestamp: datetime
    input_data: Dict[str, Any] = field(default_factory=dict)
    output_data: Dict[str, Any] = field(default_factory=dict)
    error_details: Optional[Dict[str, Any]] = None
    confidence_score: Optional[float] = None
    user_feedback: Optional[str] = None
    skill_generated: bool = False
    generation_time: Optional[float] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for database storage."""
        data = asdict(self)
        data['execution_status'] = self.execution_status.value
        data['timestamp'] = self.timestamp.isoformat()
        data['input_data'] = json.dumps(self.input_data)
        data['output_data'] = json.dumps(self.output_data)
        data['error_details'] = json.dumps(self.error_details) if self.error_details else None
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'SkillUsage':
        """Create from dictionary from database."""
        return cls(
            usage_id=data['usage_id'],
            skill_id=data['skill_id'],
            skill_name=data['skill_name'],
            user_id=data['user_id'],
            conversation_id=data['conversation_id'],
            execution_status=SkillExecutionStatus(data['execution_status']),
            execution_time=data['execution_time'],
            timestamp=datetime.fromisoformat(data['timestamp']),
            input_data=json.loads(data.get('input_data', '{}')),
            output_data=json.loads(data.get('output_data', '{}')),
            error_details=json.loads(data['error_details']) if data.get('error_details') else None,
            confidence_score=data.get('confidence_score'),
            user_feedback=data.get('user_feedback'),
            skill_generated=data.get('skill_generated', False),
            generation_time=data.get('generation_time')
        )


@dataclass
class PerformanceMetric:
    """Performance metric model."""
    metric_id: str
    component: str
    metric_name: str
    metric_value: float
    timestamp: datetime
    context: Dict[str, Any] = field(default_factory=dict)
    user_id: Optional[str] = None
    conversation_id: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for database storage."""
        data = asdict(self)
        data['timestamp'] = self.timestamp.isoformat()
        data['context'] = json.dumps(self.context)
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'PerformanceMetric':
        """Create from dictionary from database."""
        return cls(
            metric_id=data['metric_id'],
            component=data['component'],
            metric_name=data['metric_name'],
            metric_value=data['metric_value'],
            timestamp=datetime.fromisoformat(data['timestamp']),
            context=json.loads(data.get('context', '{}')),
            user_id=data.get('user_id'),
            conversation_id=data.get('conversation_id')
        )


@dataclass
class SystemConfig:
    """System configuration model."""
    config_key: str
    config_value: str
    config_type: str  # "string", "integer", "float", "boolean", "json"
    description: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    created_by: Optional[str] = None
    updated_by: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for database storage."""
        data = asdict(self)
        data['created_at'] = self.created_at.isoformat()
        data['updated_at'] = self.updated_at.isoformat()
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'SystemConfig':
        """Create from dictionary from database."""
        return cls(
            config_key=data['config_key'],
            config_value=data['config_value'],
            config_type=data['config_type'],
            description=data.get('description'),
            created_at=datetime.fromisoformat(data['created_at']),
            updated_at=datetime.fromisoformat(data['updated_at']),
            created_by=data.get('created_by'),
            updated_by=data.get('updated_by')
        )
    
    def get_typed_value(self) -> Any:
        """Get the configuration value with proper type conversion."""
        if self.config_type == "integer":
            return int(self.config_value)
        elif self.config_type == "float":
            return float(self.config_value)
        elif self.config_type == "boolean":
            return self.config_value.lower() in ("true", "1", "yes", "on")
        elif self.config_type == "json":
            return json.loads(self.config_value)
        else:
            return self.config_value

@dataclass
class Organization:
    """Organization (tenant) model."""
    organization_id: str
    name: str
    schema_name: str # e.g., org_abc_123
    created_at: datetime = field(default_factory=datetime.utcnow)
    
    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data['created_at'] = self.created_at.isoformat()
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Organization':
        return cls(
            organization_id=data['organization_id'],
            name=data['name'],
            schema_name=data['schema_name'],
            created_at=datetime.fromisoformat(data['created_at'])
        )

@dataclass
class UserOrganization:
    """Association table for users and organizations."""
    user_id: str
    organization_id: str
    role: str # e.g., 'admin', 'member', 'auditor'

# Database schema definitions for different database types
SQLITE_SCHEMA = {
    "organizations": """
        CREATE TABLE IF NOT EXISTS organizations (
            organization_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            schema_name TEXT NOT NULL UNIQUE,
            created_at TEXT NOT NULL
        )
    """,
    "user_organizations": """
        CREATE TABLE IF NOT EXISTS user_organizations (
            user_id TEXT NOT NULL,
            organization_id TEXT NOT NULL,
            role TEXT NOT NULL,
            PRIMARY KEY (user_id, organization_id),
            FOREIGN KEY (user_id) REFERENCES user_profiles (user_id),
            FOREIGN KEY (organization_id) REFERENCES organizations (organization_id)
        )
    """,
    "conversations": """
        CREATE TABLE IF NOT EXISTS conversations (
            conversation_id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            state TEXT NOT NULL,
            created_at TEXT NOT NULL,
            last_activity TEXT NOT NULL,
            context_data TEXT DEFAULT '{}',
            user_preferences TEXT DEFAULT '{}',
            personality_context TEXT DEFAULT '{}',
            total_messages INTEGER DEFAULT 0,
            total_skills_used INTEGER DEFAULT 0,
            total_skills_generated INTEGER DEFAULT 0,
            average_response_time REAL DEFAULT 0.0,
            user_satisfaction_score REAL,
            FOREIGN KEY (user_id) REFERENCES user_profiles (user_id)
        )
    """,
    
    "conversation_messages": """
        CREATE TABLE IF NOT EXISTS conversation_messages (
            message_id TEXT PRIMARY KEY,
            conversation_id TEXT NOT NULL,
            message_type TEXT NOT NULL,
            content TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            metadata TEXT DEFAULT '{}',
            task_id TEXT,
            skill_used TEXT,
            response_time REAL,
            confidence_score REAL,
            FOREIGN KEY (conversation_id) REFERENCES conversations (conversation_id)
        )
    """,
    
    "user_profiles": """
        CREATE TABLE IF NOT EXISTS user_profiles (
            user_id TEXT PRIMARY KEY,
            username TEXT,
            email TEXT,
            created_at TEXT NOT NULL,
            last_active TEXT NOT NULL,
            preferences TEXT DEFAULT '{}',
            personality_traits TEXT DEFAULT '{}',
            interaction_patterns TEXT DEFAULT '{}',
            skill_preferences TEXT DEFAULT '{}',
            total_conversations INTEGER DEFAULT 0,
            total_messages INTEGER DEFAULT 0,
            total_skills_used INTEGER DEFAULT 0,
            average_session_duration REAL DEFAULT 0.0,
            preferred_communication_style TEXT,
            timezone TEXT,
            language TEXT DEFAULT 'en'
        )
    """,
    
    "skill_usage": """
        CREATE TABLE IF NOT EXISTS skill_usage (
            usage_id TEXT PRIMARY KEY,
            skill_id TEXT NOT NULL,
            skill_name TEXT NOT NULL,
            user_id TEXT NOT NULL,
            conversation_id TEXT NOT NULL,
            execution_status TEXT NOT NULL,
            execution_time REAL NOT NULL,
            timestamp TEXT NOT NULL,
            input_data TEXT DEFAULT '{}',
            output_data TEXT DEFAULT '{}',
            error_details TEXT,
            confidence_score REAL,
            user_feedback TEXT,
            skill_generated BOOLEAN DEFAULT FALSE,
            generation_time REAL,
            FOREIGN KEY (user_id) REFERENCES user_profiles (user_id),
            FOREIGN KEY (conversation_id) REFERENCES conversations (conversation_id)
        )
    """,
    
    "performance_metrics": """
        CREATE TABLE IF NOT EXISTS performance_metrics (
            metric_id TEXT PRIMARY KEY,
            component TEXT NOT NULL,
            metric_name TEXT NOT NULL,
            metric_value REAL NOT NULL,
            timestamp TEXT NOT NULL,
            context TEXT DEFAULT '{}',
            user_id TEXT,
            conversation_id TEXT,
            FOREIGN KEY (user_id) REFERENCES user_profiles (user_id),
            FOREIGN KEY (conversation_id) REFERENCES conversations (conversation_id)
        )
    """,
    
    "system_config": """
        CREATE TABLE IF NOT EXISTS system_config (
            config_key TEXT PRIMARY KEY,
            config_value TEXT NOT NULL,
            config_type TEXT NOT NULL,
            description TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            created_by TEXT,
            updated_by TEXT
        )
    """
}

# Indexes for better performance
SQLITE_INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_conversations_user_id ON conversations (user_id)",
    "CREATE INDEX IF NOT EXISTS idx_conversations_state ON conversations (state)",
    "CREATE INDEX IF NOT EXISTS idx_conversations_last_activity ON conversations (last_activity)",
    "CREATE INDEX IF NOT EXISTS idx_messages_conversation_id ON conversation_messages (conversation_id)",
    "CREATE INDEX IF NOT EXISTS idx_messages_timestamp ON conversation_messages (timestamp)",
    "CREATE INDEX IF NOT EXISTS idx_messages_type ON conversation_messages (message_type)",
    "CREATE INDEX IF NOT EXISTS idx_skill_usage_user_id ON skill_usage (user_id)",
    "CREATE INDEX IF NOT EXISTS idx_skill_usage_skill_id ON skill_usage (skill_id)",
    "CREATE INDEX IF NOT EXISTS idx_skill_usage_timestamp ON skill_usage (timestamp)",
    "CREATE INDEX IF NOT EXISTS idx_skill_usage_status ON skill_usage (execution_status)",
    "CREATE INDEX IF NOT EXISTS idx_performance_component ON performance_metrics (component)",
    "CREATE INDEX IF NOT EXISTS idx_performance_timestamp ON performance_metrics (timestamp)",
    "CREATE INDEX IF NOT EXISTS idx_performance_metric_name ON performance_metrics (metric_name)",
    "CREATE INDEX IF NOT EXISTS idx_user_organizations_user_id ON user_organizations (user_id)",
    "CREATE INDEX IF NOT EXISTS idx_user_organizations_organization_id ON user_organizations (organization_id)"
]

