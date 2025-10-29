from sqlalchemy import create_engine, Column, Integer, String, DateTime, ForeignKey, Table, Text, JSON, text, Float, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime
import uuid
from ..config.settings import settings

engine = create_engine(settings.DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

# Association table for meeting participants
meeting_participants = Table(
    'meeting_participants',
    Base.metadata,
    Column('meeting_id', String, ForeignKey('meetings.id')),
    Column('user_id', String, ForeignKey('users.id'))
)

class User(Base):
    __tablename__ = "users"
    id = Column(String, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    email = Column(String, unique=True, index=True)
    password_hash = Column(String)
    role = Column(String, default="user")
    ui_preferences = Column(JSON, nullable=True)  # Stores popup preferences and UI settings
    created_at = Column(DateTime, default=datetime.utcnow)

class Agent(Base):
    __tablename__ = "agents"
    id = Column(String, primary_key=True, index=True)
    name = Column(String)
    status = Column(String, default="stopped")
    created_at = Column(DateTime, default=datetime.utcnow)
    participant_id = Column(String, nullable=True)

class AgentProcess(Base):
    __tablename__ = "agent_processes"
    
    id = Column(String, primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    agent_id = Column(String, ForeignKey('agents.id'), index=True)
    process_type = Column(String)  # subprocess, container, worker
    pid = Column(Integer, nullable=True)
    container_id = Column(String, nullable=True)
    worker_id = Column(String, nullable=True)
    status = Column(String, default="starting")  # starting, running, stopping, stopped, failed
    last_heartbeat = Column(DateTime, nullable=True)
    resource_usage = Column(JSON, nullable=True)
    config = Column(JSON, nullable=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationship to agent
    agent = relationship("Agent", backref="processes")

class Meeting(Base):
    __tablename__ = "meetings"
    id = Column(String, primary_key=True, index=True)
    name = Column(String)
    status = Column(String, default="active")
    created_at = Column(DateTime, default=datetime.utcnow)
    owner_id = Column(String, ForeignKey('users.id'))
    participants = relationship("User", secondary=meeting_participants, backref="meetings")
    mem0_context = Column(JSON, nullable=True)  # Mem0-specifik konfiguration för möte

class Memory(Base):
    __tablename__ = "memories"
    id = Column(String, primary_key=True, index=True)
    content = Column(Text)
    memory_metadata = Column(JSON, nullable=True)
    user_id = Column(String, nullable=True)
    meeting_id = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class RefreshToken(Base):
    __tablename__ = "refresh_tokens"
    id = Column(String, primary_key=True, index=True)
    user_id = Column(String, ForeignKey('users.id'), nullable=False)
    jti = Column(String, unique=True, index=True, nullable=False)
    expires_at = Column(DateTime, nullable=False)
    revoked = Column(String, default="false")  # Using string for SQLite compatibility
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationship to user
    user = relationship("User", backref="refresh_tokens")

class RateLimit(Base):
    __tablename__ = "rate_limits"
    id = Column(String, primary_key=True, index=True)
    key = Column(String, index=True, nullable=False)
    count = Column(Integer, default=0)
    window_start = Column(DateTime, nullable=False)
    expires_at = Column(DateTime, nullable=False)


# AI Usage Tracking Models
class AIUsage(Base):
    """Track AI usage per user and meeting"""
    __tablename__ = "ai_usage"
    
    id = Column(String, primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id"), index=True)
    meeting_id = Column(String, ForeignKey("meetings.id"), index=True, nullable=True)
    provider = Column(String)  # openai, google, bedrock
    model = Column(String)
    operation = Column(String)  # summarize, topics, actions, etc.
    tokens_used = Column(Integer)
    cost = Column(Float)
    request_time = Column(DateTime, default=datetime.utcnow)
    response_time_ms = Column(Integer)
    success = Column(Boolean, default=True)
    error_message = Column(Text, nullable=True)
    usage_metadata = Column(JSON, nullable=True)


class UserQuota(Base):
    """User quota settings"""
    __tablename__ = "user_quotas"
    
    id = Column(String, primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id"), unique=True, index=True)
    tier = Column(String, default="free")
    daily_tokens = Column(Integer, default=10000)
    monthly_tokens = Column(Integer, default=300000)
    daily_requests = Column(Integer, default=100)
    monthly_requests = Column(Integer, default=3000)
    max_tokens_per_request = Column(Integer, default=4000)
    daily_cost_limit = Column(Float, default=10.0)
    monthly_cost_limit = Column(Float, default=300.0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)


class QuotaUsage(Base):
    """Track quota usage by time period"""
    __tablename__ = "quota_usage"
    
    id = Column(String, primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id"), index=True)
    period_type = Column(String)  # daily, monthly
    period_start = Column(DateTime)
    period_end = Column(DateTime)
    tokens_used = Column(Integer, default=0)
    requests_made = Column(Integer, default=0)
    total_cost = Column(Float, default=0.0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)

Base.metadata.create_all(bind=engine)

async def init_db():
    """Initialize database - tables are created at module import"""
    pass

async def get_db_health():
    """Check database health"""
    try:
        # Try to connect and execute a simple query
        db = SessionLocal()
        db.execute(text("SELECT 1"))
        db.close()
        return {"healthy": True, "message": "Database connection successful"}
    except Exception as e:
        return {"healthy": False, "message": f"Database health check failed: {str(e)}"}

async def close_db_connections():
    """Close database connections"""
    pass

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()