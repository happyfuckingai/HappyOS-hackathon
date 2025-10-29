"""
Unified Database Service for Agent Systems

Provides a unified database layer that supports all three agent systems
(Agent Svea, Felicia's Finance, and MeetMind) with proper tenant isolation
and agent-specific data access methods.
"""

import asyncio
import logging
import uuid
from typing import Dict, Any, List, Optional, Union
from datetime import datetime
from sqlalchemy import Column, String, DateTime, JSON, Text, Integer, Float, Boolean, ForeignKey, Index
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker
from sqlalchemy import create_engine

from backend.modules.database.connection import Base, SessionLocal, engine
from backend.core.a2a.constants import AgentType

logger = logging.getLogger(__name__)

# Agent-specific database models

class AgentData(Base):
    """Base table for agent-specific data with tenant isolation."""
    __tablename__ = "agent_data"
    
    id = Column(String, primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    agent_type = Column(String, index=True, nullable=False)  # agent_svea, felicias_finance, meetmind
    tenant_id = Column(String, index=True, nullable=False)
    data_type = Column(String, index=True, nullable=False)  # erp_document, trading_record, meeting_transcript, etc.
    data_id = Column(String, index=True, nullable=False)  # Agent-specific data identifier
    data_content = Column(JSON, nullable=False)
    metadata = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Composite indexes for efficient querying
    __table_args__ = (
        Index('idx_agent_tenant_type', 'agent_type', 'tenant_id', 'data_type'),
        Index('idx_agent_tenant_id', 'agent_type', 'tenant_id', 'data_id'),
    )


class AgentSveaData(Base):
    """Agent Svea specific data tables."""
    __tablename__ = "agent_svea_data"
    
    id = Column(String, primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, index=True, nullable=False)
    
    # ERP Document fields
    document_type = Column(String, index=True)  # invoice, receipt, bas_account, etc.
    document_id = Column(String, index=True)
    erp_data = Column(JSON, nullable=False)
    
    # BAS Account fields
    bas_account_number = Column(String, index=True, nullable=True)
    bas_account_name = Column(String, nullable=True)
    bas_account_type = Column(String, nullable=True)
    
    # Compliance fields
    compliance_status = Column(String, nullable=True)  # compliant, non_compliant, pending
    skatteverket_status = Column(String, nullable=True)  # submitted, approved, rejected
    validation_result = Column(JSON, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    __table_args__ = (
        Index('idx_svea_tenant_doc', 'tenant_id', 'document_type', 'document_id'),
        Index('idx_svea_bas_account', 'tenant_id', 'bas_account_number'),
    )


class FeliciasFinanceData(Base):
    """Felicia's Finance specific data tables."""
    __tablename__ = "felicias_finance_data"
    
    id = Column(String, primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, index=True, nullable=False)
    
    # Trading data fields
    trade_id = Column(String, index=True, nullable=True)
    symbol = Column(String, index=True, nullable=True)
    trade_type = Column(String, nullable=True)  # buy, sell, hold
    quantity = Column(Float, nullable=True)
    price = Column(Float, nullable=True)
    
    # Portfolio fields
    portfolio_id = Column(String, index=True, nullable=True)
    asset_type = Column(String, nullable=True)  # crypto, stock, bond, etc.
    portfolio_data = Column(JSON, nullable=True)
    
    # Banking fields
    transaction_id = Column(String, index=True, nullable=True)
    transaction_type = Column(String, nullable=True)  # deposit, withdrawal, transfer
    amount = Column(Float, nullable=True)
    currency = Column(String, nullable=True)
    
    # Analysis fields
    analysis_type = Column(String, nullable=True)  # risk_assessment, portfolio_analysis
    analysis_result = Column(JSON, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    __table_args__ = (
        Index('idx_finance_tenant_trade', 'tenant_id', 'trade_id'),
        Index('idx_finance_tenant_portfolio', 'tenant_id', 'portfolio_id'),
        Index('idx_finance_tenant_transaction', 'tenant_id', 'transaction_id'),
    )


class MeetMindData(Base):
    """MeetMind specific data tables."""
    __tablename__ = "meetmind_data"
    
    id = Column(String, primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, index=True, nullable=False)
    
    # Meeting fields
    meeting_id = Column(String, index=True, nullable=True)
    transcript_id = Column(String, index=True, nullable=True)
    transcript_content = Column(Text, nullable=True)
    
    # Analysis fields
    summary = Column(Text, nullable=True)
    topics = Column(JSON, nullable=True)
    action_items = Column(JSON, nullable=True)
    insights = Column(JSON, nullable=True)
    
    # Participants
    participants = Column(JSON, nullable=True)
    duration = Column(Integer, nullable=True)  # in seconds
    
    # AI processing metadata
    ai_model_used = Column(String, nullable=True)
    processing_time = Column(Float, nullable=True)
    confidence_score = Column(Float, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    __table_args__ = (
        Index('idx_meetmind_tenant_meeting', 'tenant_id', 'meeting_id'),
        Index('idx_meetmind_tenant_transcript', 'tenant_id', 'transcript_id'),
    )


class CrossAgentWorkflow(Base):
    """Cross-agent workflow tracking."""
    __tablename__ = "cross_agent_workflows"
    
    id = Column(String, primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    workflow_id = Column(String, unique=True, index=True, nullable=False)
    tenant_id = Column(String, index=True, nullable=False)
    
    workflow_type = Column(String, index=True, nullable=False)
    participating_agents = Column(JSON, nullable=False)  # List of agent types
    workflow_data = Column(JSON, nullable=False)
    
    status = Column(String, index=True, default="created")  # created, running, completed, failed
    current_step = Column(Integer, default=0)
    total_steps = Column(Integer, nullable=False)
    
    results = Column(JSON, nullable=True)
    error_message = Column(Text, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    __table_args__ = (
        Index('idx_workflow_tenant_status', 'tenant_id', 'status'),
        Index('idx_workflow_type_status', 'workflow_type', 'status'),
    )


class AgentRegistry(Base):
    """Agent registry for discovery and health monitoring."""
    __tablename__ = "agent_registry"
    
    id = Column(String, primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    agent_id = Column(String, unique=True, index=True, nullable=False)
    agent_type = Column(String, index=True, nullable=False)
    
    capabilities = Column(JSON, nullable=False)  # List of capabilities
    endpoint = Column(String, nullable=False)
    metadata = Column(JSON, nullable=True)
    
    status = Column(String, index=True, default="active")  # active, inactive, maintenance
    health_status = Column(String, index=True, default="healthy")  # healthy, degraded, unhealthy
    
    last_heartbeat = Column(DateTime, nullable=True, index=True)
    last_health_check = Column(DateTime, nullable=True)
    failure_count = Column(Integer, default=0)
    
    registered_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    __table_args__ = (
        Index('idx_agent_type_status', 'agent_type', 'status'),
        Index('idx_agent_health_status', 'health_status', 'last_heartbeat'),
    )


# Create all tables
Base.metadata.create_all(bind=engine)


class UnifiedDatabaseService:
    """
    Unified database service for all agent systems.
    
    Provides agent-specific data access methods with tenant isolation
    and supports migration utilities for existing agent data.
    """
    
    def __init__(self):
        self.logger = logging.getLogger(f"{__name__}.UnifiedDatabaseService")
        self.session_factory = SessionLocal
    
    def get_session(self):
        """Get database session."""
        return self.session_factory()
    
    # Agent Svea specific methods
    
    async def store_agent_svea_data(self, data: Dict[str, Any], tenant_id: str) -> str:
        """Store Agent Svea specific data."""
        try:
            with self.get_session() as session:
                svea_data = AgentSveaData(
                    tenant_id=tenant_id,
                    document_type=data.get("document_type"),
                    document_id=data.get("document_id"),
                    erp_data=data.get("erp_data", {}),
                    bas_account_number=data.get("bas_account_number"),
                    bas_account_name=data.get("bas_account_name"),
                    bas_account_type=data.get("bas_account_type"),
                    compliance_status=data.get("compliance_status"),
                    skatteverket_status=data.get("skatteverket_status"),
                    validation_result=data.get("validation_result")
                )
                
                session.add(svea_data)
                session.commit()
                
                self.logger.debug(f"Stored Agent Svea data: {svea_data.id}")
                return svea_data.id
                
        except Exception as e:
            self.logger.error(f"Failed to store Agent Svea data: {e}")
            raise
    
    async def get_agent_svea_data(self, data_id: str, tenant_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve Agent Svea specific data."""
        try:
            with self.get_session() as session:
                svea_data = session.query(AgentSveaData).filter(
                    AgentSveaData.id == data_id,
                    AgentSveaData.tenant_id == tenant_id
                ).first()
                
                if not svea_data:
                    return None
                
                return {
                    "id": svea_data.id,
                    "tenant_id": svea_data.tenant_id,
                    "document_type": svea_data.document_type,
                    "document_id": svea_data.document_id,
                    "erp_data": svea_data.erp_data,
                    "bas_account_number": svea_data.bas_account_number,
                    "bas_account_name": svea_data.bas_account_name,
                    "bas_account_type": svea_data.bas_account_type,
                    "compliance_status": svea_data.compliance_status,
                    "skatteverket_status": svea_data.skatteverket_status,
                    "validation_result": svea_data.validation_result,
                    "created_at": svea_data.created_at.isoformat(),
                    "updated_at": svea_data.updated_at.isoformat()
                }
                
        except Exception as e:
            self.logger.error(f"Failed to get Agent Svea data: {e}")
            raise
    
    async def query_agent_svea_data(self, query: Dict[str, Any], tenant_id: str) -> List[Dict[str, Any]]:
        """Query Agent Svea data with filters."""
        try:
            with self.get_session() as session:
                query_obj = session.query(AgentSveaData).filter(
                    AgentSveaData.tenant_id == tenant_id
                )
                
                # Apply filters
                if "document_type" in query:
                    query_obj = query_obj.filter(AgentSveaData.document_type == query["document_type"])
                
                if "bas_account_number" in query:
                    query_obj = query_obj.filter(AgentSveaData.bas_account_number == query["bas_account_number"])
                
                if "compliance_status" in query:
                    query_obj = query_obj.filter(AgentSveaData.compliance_status == query["compliance_status"])
                
                # Apply limit
                limit = query.get("limit", 100)
                results = query_obj.limit(limit).all()
                
                return [
                    {
                        "id": item.id,
                        "document_type": item.document_type,
                        "document_id": item.document_id,
                        "erp_data": item.erp_data,
                        "bas_account_number": item.bas_account_number,
                        "compliance_status": item.compliance_status,
                        "created_at": item.created_at.isoformat()
                    }
                    for item in results
                ]
                
        except Exception as e:
            self.logger.error(f"Failed to query Agent Svea data: {e}")
            raise
    
    # Felicia's Finance specific methods
    
    async def store_felicias_finance_data(self, data: Dict[str, Any], tenant_id: str) -> str:
        """Store Felicia's Finance specific data."""
        try:
            with self.get_session() as session:
                finance_data = FeliciasFinanceData(
                    tenant_id=tenant_id,
                    trade_id=data.get("trade_id"),
                    symbol=data.get("symbol"),
                    trade_type=data.get("trade_type"),
                    quantity=data.get("quantity"),
                    price=data.get("price"),
                    portfolio_id=data.get("portfolio_id"),
                    asset_type=data.get("asset_type"),
                    portfolio_data=data.get("portfolio_data"),
                    transaction_id=data.get("transaction_id"),
                    transaction_type=data.get("transaction_type"),
                    amount=data.get("amount"),
                    currency=data.get("currency"),
                    analysis_type=data.get("analysis_type"),
                    analysis_result=data.get("analysis_result")
                )
                
                session.add(finance_data)
                session.commit()
                
                self.logger.debug(f"Stored Felicia's Finance data: {finance_data.id}")
                return finance_data.id
                
        except Exception as e:
            self.logger.error(f"Failed to store Felicia's Finance data: {e}")
            raise
    
    async def get_felicias_finance_data(self, data_id: str, tenant_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve Felicia's Finance specific data."""
        try:
            with self.get_session() as session:
                finance_data = session.query(FeliciasFinanceData).filter(
                    FeliciasFinanceData.id == data_id,
                    FeliciasFinanceData.tenant_id == tenant_id
                ).first()
                
                if not finance_data:
                    return None
                
                return {
                    "id": finance_data.id,
                    "tenant_id": finance_data.tenant_id,
                    "trade_id": finance_data.trade_id,
                    "symbol": finance_data.symbol,
                    "trade_type": finance_data.trade_type,
                    "quantity": finance_data.quantity,
                    "price": finance_data.price,
                    "portfolio_id": finance_data.portfolio_id,
                    "asset_type": finance_data.asset_type,
                    "portfolio_data": finance_data.portfolio_data,
                    "transaction_id": finance_data.transaction_id,
                    "transaction_type": finance_data.transaction_type,
                    "amount": finance_data.amount,
                    "currency": finance_data.currency,
                    "analysis_type": finance_data.analysis_type,
                    "analysis_result": finance_data.analysis_result,
                    "created_at": finance_data.created_at.isoformat(),
                    "updated_at": finance_data.updated_at.isoformat()
                }
                
        except Exception as e:
            self.logger.error(f"Failed to get Felicia's Finance data: {e}")
            raise
    
    # MeetMind specific methods
    
    async def store_meetmind_data(self, data: Dict[str, Any], tenant_id: str) -> str:
        """Store MeetMind specific data."""
        try:
            with self.get_session() as session:
                meetmind_data = MeetMindData(
                    tenant_id=tenant_id,
                    meeting_id=data.get("meeting_id"),
                    transcript_id=data.get("transcript_id"),
                    transcript_content=data.get("transcript_content"),
                    summary=data.get("summary"),
                    topics=data.get("topics"),
                    action_items=data.get("action_items"),
                    insights=data.get("insights"),
                    participants=data.get("participants"),
                    duration=data.get("duration"),
                    ai_model_used=data.get("ai_model_used"),
                    processing_time=data.get("processing_time"),
                    confidence_score=data.get("confidence_score")
                )
                
                session.add(meetmind_data)
                session.commit()
                
                self.logger.debug(f"Stored MeetMind data: {meetmind_data.id}")
                return meetmind_data.id
                
        except Exception as e:
            self.logger.error(f"Failed to store MeetMind data: {e}")
            raise
    
    async def get_meetmind_data(self, data_id: str, tenant_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve MeetMind specific data."""
        try:
            with self.get_session() as session:
                meetmind_data = session.query(MeetMindData).filter(
                    MeetMindData.id == data_id,
                    MeetMindData.tenant_id == tenant_id
                ).first()
                
                if not meetmind_data:
                    return None
                
                return {
                    "id": meetmind_data.id,
                    "tenant_id": meetmind_data.tenant_id,
                    "meeting_id": meetmind_data.meeting_id,
                    "transcript_id": meetmind_data.transcript_id,
                    "transcript_content": meetmind_data.transcript_content,
                    "summary": meetmind_data.summary,
                    "topics": meetmind_data.topics,
                    "action_items": meetmind_data.action_items,
                    "insights": meetmind_data.insights,
                    "participants": meetmind_data.participants,
                    "duration": meetmind_data.duration,
                    "ai_model_used": meetmind_data.ai_model_used,
                    "processing_time": meetmind_data.processing_time,
                    "confidence_score": meetmind_data.confidence_score,
                    "created_at": meetmind_data.created_at.isoformat(),
                    "updated_at": meetmind_data.updated_at.isoformat()
                }
                
        except Exception as e:
            self.logger.error(f"Failed to get MeetMind data: {e}")
            raise
    
    # Cross-agent workflow methods
    
    async def create_cross_agent_workflow(self, workflow_data: Dict[str, Any], tenant_id: str) -> str:
        """Create cross-agent workflow record."""
        try:
            with self.get_session() as session:
                workflow = CrossAgentWorkflow(
                    workflow_id=workflow_data["workflow_id"],
                    tenant_id=tenant_id,
                    workflow_type=workflow_data["workflow_type"],
                    participating_agents=workflow_data["participating_agents"],
                    workflow_data=workflow_data.get("data", {}),
                    total_steps=len(workflow_data.get("steps", []))
                )
                
                session.add(workflow)
                session.commit()
                
                self.logger.debug(f"Created cross-agent workflow: {workflow.workflow_id}")
                return workflow.workflow_id
                
        except Exception as e:
            self.logger.error(f"Failed to create cross-agent workflow: {e}")
            raise
    
    async def update_workflow_status(self, workflow_id: str, status: str, 
                                   current_step: int = None, results: Dict[str, Any] = None,
                                   error_message: str = None) -> bool:
        """Update workflow status."""
        try:
            with self.get_session() as session:
                workflow = session.query(CrossAgentWorkflow).filter(
                    CrossAgentWorkflow.workflow_id == workflow_id
                ).first()
                
                if not workflow:
                    return False
                
                workflow.status = status
                if current_step is not None:
                    workflow.current_step = current_step
                if results is not None:
                    workflow.results = results
                if error_message is not None:
                    workflow.error_message = error_message
                
                if status == "running" and not workflow.started_at:
                    workflow.started_at = datetime.utcnow()
                elif status in ["completed", "failed"]:
                    workflow.completed_at = datetime.utcnow()
                
                session.commit()
                return True
                
        except Exception as e:
            self.logger.error(f"Failed to update workflow status: {e}")
            raise
    
    # Agent registry methods
    
    async def register_agent(self, agent_data: Dict[str, Any]) -> str:
        """Register agent in the registry."""
        try:
            with self.get_session() as session:
                # Check if agent already exists
                existing_agent = session.query(AgentRegistry).filter(
                    AgentRegistry.agent_id == agent_data["agent_id"]
                ).first()
                
                if existing_agent:
                    # Update existing agent
                    existing_agent.agent_type = agent_data["agent_type"]
                    existing_agent.capabilities = agent_data["capabilities"]
                    existing_agent.endpoint = agent_data["endpoint"]
                    existing_agent.metadata = agent_data.get("metadata", {})
                    existing_agent.status = "active"
                    existing_agent.updated_at = datetime.utcnow()
                    session.commit()
                    return existing_agent.agent_id
                else:
                    # Create new agent
                    agent = AgentRegistry(
                        agent_id=agent_data["agent_id"],
                        agent_type=agent_data["agent_type"],
                        capabilities=agent_data["capabilities"],
                        endpoint=agent_data["endpoint"],
                        metadata=agent_data.get("metadata", {})
                    )
                    
                    session.add(agent)
                    session.commit()
                    
                    self.logger.debug(f"Registered agent: {agent.agent_id}")
                    return agent.agent_id
                
        except Exception as e:
            self.logger.error(f"Failed to register agent: {e}")
            raise
    
    async def get_agents_by_capability(self, capabilities: List[str]) -> List[Dict[str, Any]]:
        """Get agents that have required capabilities."""
        try:
            with self.get_session() as session:
                agents = session.query(AgentRegistry).filter(
                    AgentRegistry.status == "active",
                    AgentRegistry.health_status.in_(["healthy", "degraded"])
                ).all()
                
                matching_agents = []
                for agent in agents:
                    agent_capabilities = agent.capabilities or []
                    if all(cap in agent_capabilities for cap in capabilities):
                        matching_agents.append({
                            "agent_id": agent.agent_id,
                            "agent_type": agent.agent_type,
                            "capabilities": agent.capabilities,
                            "endpoint": agent.endpoint,
                            "metadata": agent.metadata,
                            "health_status": agent.health_status,
                            "last_heartbeat": agent.last_heartbeat.isoformat() if agent.last_heartbeat else None
                        })
                
                return matching_agents
                
        except Exception as e:
            self.logger.error(f"Failed to get agents by capability: {e}")
            raise
    
    async def update_agent_heartbeat(self, agent_id: str) -> bool:
        """Update agent heartbeat timestamp."""
        try:
            with self.get_session() as session:
                agent = session.query(AgentRegistry).filter(
                    AgentRegistry.agent_id == agent_id
                ).first()
                
                if not agent:
                    return False
                
                agent.last_heartbeat = datetime.utcnow()
                agent.failure_count = 0  # Reset failure count on successful heartbeat
                if agent.health_status == "unhealthy":
                    agent.health_status = "healthy"  # Recover from unhealthy state
                
                session.commit()
                return True
                
        except Exception as e:
            self.logger.error(f"Failed to update agent heartbeat: {e}")
            raise
    
    # Migration utilities
    
    async def migrate_existing_agent_data(self, agent_type: str, source_data: List[Dict[str, Any]], 
                                        tenant_id: str) -> Dict[str, Any]:
        """Migrate existing agent data to unified database."""
        try:
            migrated_count = 0
            failed_count = 0
            
            for data_item in source_data:
                try:
                    if agent_type == AgentType.AGENT_SVEA.value:
                        await self.store_agent_svea_data(data_item, tenant_id)
                    elif agent_type == AgentType.FELICIAS_FINANCE.value:
                        await self.store_felicias_finance_data(data_item, tenant_id)
                    elif agent_type == AgentType.MEETMIND.value:
                        await self.store_meetmind_data(data_item, tenant_id)
                    
                    migrated_count += 1
                    
                except Exception as e:
                    self.logger.error(f"Failed to migrate data item: {e}")
                    failed_count += 1
            
            return {
                "agent_type": agent_type,
                "total_items": len(source_data),
                "migrated_count": migrated_count,
                "failed_count": failed_count,
                "success_rate": migrated_count / len(source_data) if source_data else 0
            }
            
        except Exception as e:
            self.logger.error(f"Failed to migrate agent data: {e}")
            raise
    
    async def get_database_health(self) -> Dict[str, Any]:
        """Get database health status."""
        try:
            with self.get_session() as session:
                # Test basic connectivity
                session.execute("SELECT 1")
                
                # Get table counts
                agent_data_count = session.query(AgentData).count()
                svea_data_count = session.query(AgentSveaData).count()
                finance_data_count = session.query(FeliciasFinanceData).count()
                meetmind_data_count = session.query(MeetMindData).count()
                workflow_count = session.query(CrossAgentWorkflow).count()
                registry_count = session.query(AgentRegistry).count()
                
                return {
                    "status": "healthy",
                    "tables": {
                        "agent_data": agent_data_count,
                        "agent_svea_data": svea_data_count,
                        "felicias_finance_data": finance_data_count,
                        "meetmind_data": meetmind_data_count,
                        "cross_agent_workflows": workflow_count,
                        "agent_registry": registry_count
                    },
                    "total_records": (agent_data_count + svea_data_count + 
                                    finance_data_count + meetmind_data_count),
                    "timestamp": datetime.utcnow().isoformat()
                }
                
        except Exception as e:
            self.logger.error(f"Database health check failed: {e}")
            return {
                "status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }


# Global unified database service instance
unified_db_service = UnifiedDatabaseService()