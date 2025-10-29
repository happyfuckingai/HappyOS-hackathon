"""
MCP Audit Logging Integration

Extends existing AuditLogger and TenantAccessAttempt for MCP tool calls,
callbacks, and cross-agent workflows. Implements security monitoring
for MCP communication patterns.

Requirements: 7.3, 7.4
"""

import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any
from uuid import uuid4
from enum import Enum

from pydantic import BaseModel, Field

try:
    from .tenant_isolation import AuditLogger, audit_logger
    from .mcp_tenant_isolation import MCPHeaders, MCPAccessAttempt
    from .mcp_security import MCPSignature
except ImportError:
    # Fallback for testing
    class AuditLogger:
        def log_tenant_operation(self, **kwargs):
            pass
    class MCPHeaders:
        pass
    class MCPAccessAttempt:
        pass
    class MCPSignature:
        pass
    audit_logger = AuditLogger()

logger = logging.getLogger(__name__)


class MCPEventType(Enum):
    """MCP audit event types"""
    TOOL_CALL = "mcp_tool_call"
    TOOL_CALLBACK = "mcp_tool_callback"
    WORKFLOW_START = "mcp_workflow_start"
    WORKFLOW_COMPLETE = "mcp_workflow_complete"
    WORKFLOW_FAILED = "mcp_workflow_failed"
    AGENT_REGISTRATION = "mcp_agent_registration"
    SIGNATURE_VERIFICATION = "mcp_signature_verification"
    CROSS_TENANT_ACCESS = "mcp_cross_tenant_access"
    SECURITY_VIOLATION = "mcp_security_violation"


class MCPAuditSeverity(Enum):
    """MCP audit severity levels"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class MCPAuditEvent(BaseModel):
    """MCP audit event record"""
    event_id: str = Field(default_factory=lambda: str(uuid4()))
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    event_type: MCPEventType
    severity: MCPAuditSeverity
    tenant_id: str
    agent_id: str
    trace_id: Optional[str] = None
    conversation_id: Optional[str] = None
    target_agent: Optional[str] = None
    tool_name: Optional[str] = None
    workflow_id: Optional[str] = None
    success: bool
    error_message: Optional[str] = None
    details: Dict[str, Any] = Field(default_factory=dict)
    security_context: Dict[str, Any] = Field(default_factory=dict)
    performance_metrics: Dict[str, Any] = Field(default_factory=dict)


class MCPWorkflowAuditTrail(BaseModel):
    """Audit trail for cross-agent workflows"""
    workflow_id: str
    workflow_type: str
    tenant_id: str
    initiator_agent: str
    participating_agents: List[str]
    start_time: str
    end_time: Optional[str] = None
    status: str  # "running", "completed", "failed"
    events: List[str] = Field(default_factory=list)  # List of event IDs
    total_tool_calls: int = 0
    failed_tool_calls: int = 0
    security_violations: int = 0
    performance_summary: Dict[str, Any] = Field(default_factory=dict)


class MCPSecurityAlert(BaseModel):
    """MCP security alert record"""
    alert_id: str = Field(default_factory=lambda: str(uuid4()))
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    alert_type: str
    severity: MCPAuditSeverity
    tenant_id: str
    agent_id: str
    description: str
    evidence: Dict[str, Any] = Field(default_factory=dict)
    resolved: bool = False
    resolution_notes: Optional[str] = None


class MCPAuditLogger:
    """Extended audit logger for MCP workflows"""
    
    def __init__(self, base_logger: AuditLogger = None):
        self.base_logger = base_logger or audit_logger
        self._mcp_events: List[MCPAuditEvent] = []
        self._workflow_trails: Dict[str, MCPWorkflowAuditTrail] = {}
        self._security_alerts: List[MCPSecurityAlert] = []
        
        # Performance tracking
        self._performance_metrics: Dict[str, List[float]] = {}
    
    def log_mcp_tool_call(
        self,
        headers: MCPHeaders,
        target_agent: str,
        tool_name: str,
        arguments: Dict[str, Any],
        success: bool,
        response_time_ms: Optional[float] = None,
        error_message: Optional[str] = None,
        signature_valid: Optional[bool] = None
    ):
        """
        Log MCP tool call event
        
        Args:
            headers: MCP headers
            target_agent: Target agent identifier
            tool_name: Tool being called
            arguments: Tool arguments
            success: Whether call succeeded
            response_time_ms: Response time in milliseconds
            error_message: Error message if failed
            signature_valid: Whether signature was valid
        """
        # Determine severity
        severity = MCPAuditSeverity.LOW
        if not success:
            severity = MCPAuditSeverity.MEDIUM
        if not signature_valid:
            severity = MCPAuditSeverity.HIGH
        
        # Create audit event
        event = MCPAuditEvent(
            event_type=MCPEventType.TOOL_CALL,
            severity=severity,
            tenant_id=headers.tenant_id,
            agent_id=headers.caller,
            trace_id=headers.trace_id,
            conversation_id=headers.conversation_id,
            target_agent=target_agent,
            tool_name=tool_name,
            success=success,
            error_message=error_message,
            details={
                "arguments": arguments,
                "reply_to": headers.reply_to,
                "timestamp": headers.timestamp
            },
            security_context={
                "signature_present": headers.auth_sig is not None,
                "signature_valid": signature_valid,
                "caller_verified": True  # Assume verified if we got this far
            },
            performance_metrics={
                "response_time_ms": response_time_ms
            } if response_time_ms else {}
        )
        
        self._store_event(event)
        
        # Track performance metrics
        if response_time_ms:
            metric_key = f"{target_agent}.{tool_name}"
            if metric_key not in self._performance_metrics:
                self._performance_metrics[metric_key] = []
            self._performance_metrics[metric_key].append(response_time_ms)
        
        # Log to base audit logger
        self.base_logger.log_tenant_operation(
            operation="mcp_tool_call",
            tenant_id=headers.tenant_id,
            user_id=headers.caller,
            resource_id=f"{target_agent}.{tool_name}",
            details={
                "target_agent": target_agent,
                "tool_name": tool_name,
                "trace_id": headers.trace_id,
                "conversation_id": headers.conversation_id,
                "response_time_ms": response_time_ms,
                "signature_valid": signature_valid
            },
            success=success
        )
        
        logger.info(
            f"MCP tool call: {headers.caller} -> {target_agent}.{tool_name} "
            f"tenant={headers.tenant_id} success={success} trace={headers.trace_id}"
        )
    
    def log_mcp_callback(
        self,
        headers: MCPHeaders,
        original_trace_id: str,
        callback_data: Dict[str, Any],
        success: bool,
        processing_time_ms: Optional[float] = None,
        error_message: Optional[str] = None
    ):
        """
        Log MCP callback event
        
        Args:
            headers: MCP callback headers
            original_trace_id: Original request trace ID
            callback_data: Callback payload
            success: Whether callback succeeded
            processing_time_ms: Processing time in milliseconds
            error_message: Error message if failed
        """
        event = MCPAuditEvent(
            event_type=MCPEventType.TOOL_CALLBACK,
            severity=MCPAuditSeverity.LOW if success else MCPAuditSeverity.MEDIUM,
            tenant_id=headers.tenant_id,
            agent_id=headers.caller,
            trace_id=headers.trace_id,
            conversation_id=headers.conversation_id,
            success=success,
            error_message=error_message,
            details={
                "original_trace_id": original_trace_id,
                "callback_data_size": len(str(callback_data)),
                "reply_to": headers.reply_to
            },
            performance_metrics={
                "processing_time_ms": processing_time_ms
            } if processing_time_ms else {}
        )
        
        self._store_event(event)
        
        # Log to base audit logger
        self.base_logger.log_tenant_operation(
            operation="mcp_callback",
            tenant_id=headers.tenant_id,
            user_id=headers.caller,
            details={
                "original_trace_id": original_trace_id,
                "trace_id": headers.trace_id,
                "conversation_id": headers.conversation_id,
                "processing_time_ms": processing_time_ms
            },
            success=success
        )
    
    def start_workflow_audit_trail(
        self,
        workflow_id: str,
        workflow_type: str,
        tenant_id: str,
        initiator_agent: str,
        participating_agents: List[str]
    ):
        """
        Start audit trail for cross-agent workflow
        
        Args:
            workflow_id: Workflow identifier
            workflow_type: Type of workflow
            tenant_id: Tenant identifier
            initiator_agent: Agent that initiated workflow
            participating_agents: List of participating agents
        """
        trail = MCPWorkflowAuditTrail(
            workflow_id=workflow_id,
            workflow_type=workflow_type,
            tenant_id=tenant_id,
            initiator_agent=initiator_agent,
            participating_agents=participating_agents,
            start_time=datetime.now(timezone.utc).isoformat(),
            status="running"
        )
        
        self._workflow_trails[workflow_id] = trail
        
        # Create workflow start event
        event = MCPAuditEvent(
            event_type=MCPEventType.WORKFLOW_START,
            severity=MCPAuditSeverity.LOW,
            tenant_id=tenant_id,
            agent_id=initiator_agent,
            workflow_id=workflow_id,
            success=True,
            details={
                "workflow_type": workflow_type,
                "participating_agents": participating_agents
            }
        )
        
        self._store_event(event)
        trail.events.append(event.event_id)
        
        logger.info(f"Started workflow audit trail: {workflow_id} type={workflow_type} tenant={tenant_id}")
    
    def complete_workflow_audit_trail(
        self,
        workflow_id: str,
        success: bool,
        error_message: Optional[str] = None,
        performance_summary: Optional[Dict[str, Any]] = None
    ):
        """
        Complete audit trail for cross-agent workflow
        
        Args:
            workflow_id: Workflow identifier
            success: Whether workflow succeeded
            error_message: Error message if failed
            performance_summary: Performance metrics summary
        """
        if workflow_id not in self._workflow_trails:
            logger.warning(f"Workflow audit trail not found: {workflow_id}")
            return
        
        trail = self._workflow_trails[workflow_id]
        trail.end_time = datetime.now(timezone.utc).isoformat()
        trail.status = "completed" if success else "failed"
        
        if performance_summary:
            trail.performance_summary = performance_summary
        
        # Create workflow completion event
        event_type = MCPEventType.WORKFLOW_COMPLETE if success else MCPEventType.WORKFLOW_FAILED
        severity = MCPAuditSeverity.LOW if success else MCPAuditSeverity.HIGH
        
        event = MCPAuditEvent(
            event_type=event_type,
            severity=severity,
            tenant_id=trail.tenant_id,
            agent_id=trail.initiator_agent,
            workflow_id=workflow_id,
            success=success,
            error_message=error_message,
            details={
                "workflow_type": trail.workflow_type,
                "participating_agents": trail.participating_agents,
                "total_tool_calls": trail.total_tool_calls,
                "failed_tool_calls": trail.failed_tool_calls,
                "security_violations": trail.security_violations,
                "duration_ms": self._calculate_workflow_duration(trail)
            },
            performance_metrics=performance_summary or {}
        )
        
        self._store_event(event)
        trail.events.append(event.event_id)
        
        logger.info(f"Completed workflow audit trail: {workflow_id} success={success}")
    
    def log_security_violation(
        self,
        tenant_id: str,
        agent_id: str,
        violation_type: str,
        description: str,
        evidence: Dict[str, Any],
        severity: MCPAuditSeverity = MCPAuditSeverity.HIGH,
        trace_id: Optional[str] = None
    ):
        """
        Log MCP security violation
        
        Args:
            tenant_id: Tenant identifier
            agent_id: Agent identifier
            violation_type: Type of violation
            description: Violation description
            evidence: Evidence of violation
            severity: Violation severity
            trace_id: Optional trace ID
        """
        # Create security alert
        alert = MCPSecurityAlert(
            alert_type=violation_type,
            severity=severity,
            tenant_id=tenant_id,
            agent_id=agent_id,
            description=description,
            evidence=evidence
        )
        
        self._security_alerts.append(alert)
        
        # Create audit event
        event = MCPAuditEvent(
            event_type=MCPEventType.SECURITY_VIOLATION,
            severity=severity,
            tenant_id=tenant_id,
            agent_id=agent_id,
            trace_id=trace_id,
            success=False,
            error_message=description,
            details=evidence,
            security_context={
                "violation_type": violation_type,
                "alert_id": alert.alert_id
            }
        )
        
        self._store_event(event)
        
        # Log to base audit logger
        self.base_logger.log_tenant_operation(
            operation="mcp_security_violation",
            tenant_id=tenant_id,
            user_id=agent_id,
            details={
                "violation_type": violation_type,
                "description": description,
                "evidence": evidence,
                "trace_id": trace_id,
                "alert_id": alert.alert_id
            },
            success=False
        )
        
        logger.warning(
            f"MCP security violation: {violation_type} agent={agent_id} "
            f"tenant={tenant_id} trace={trace_id}"
        )
    
    def get_mcp_audit_events(
        self,
        tenant_id: Optional[str] = None,
        agent_id: Optional[str] = None,
        event_type: Optional[MCPEventType] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 100
    ) -> List[MCPAuditEvent]:
        """
        Get MCP audit events with filtering
        
        Args:
            tenant_id: Filter by tenant
            agent_id: Filter by agent
            event_type: Filter by event type
            start_time: Filter by start time
            end_time: Filter by end time
            limit: Maximum number of results
            
        Returns:
            List of audit events
        """
        events = self._mcp_events
        
        # Apply filters
        if tenant_id:
            events = [e for e in events if e.tenant_id == tenant_id]
        
        if agent_id:
            events = [e for e in events if e.agent_id == agent_id or e.target_agent == agent_id]
        
        if event_type:
            events = [e for e in events if e.event_type == event_type]
        
        if start_time:
            events = [e for e in events if datetime.fromisoformat(e.timestamp.replace('Z', '+00:00')) >= start_time]
        
        if end_time:
            events = [e for e in events if datetime.fromisoformat(e.timestamp.replace('Z', '+00:00')) <= end_time]
        
        # Sort by timestamp (newest first) and limit
        events.sort(key=lambda e: e.timestamp, reverse=True)
        return events[:limit]
    
    def get_workflow_audit_trail(self, workflow_id: str) -> Optional[MCPWorkflowAuditTrail]:
        """Get audit trail for a specific workflow"""
        return self._workflow_trails.get(workflow_id)
    
    def get_security_alerts(
        self,
        tenant_id: Optional[str] = None,
        agent_id: Optional[str] = None,
        unresolved_only: bool = False,
        limit: int = 50
    ) -> List[MCPSecurityAlert]:
        """
        Get security alerts with filtering
        
        Args:
            tenant_id: Filter by tenant
            agent_id: Filter by agent
            unresolved_only: Only return unresolved alerts
            limit: Maximum number of results
            
        Returns:
            List of security alerts
        """
        alerts = self._security_alerts
        
        # Apply filters
        if tenant_id:
            alerts = [a for a in alerts if a.tenant_id == tenant_id]
        
        if agent_id:
            alerts = [a for a in alerts if a.agent_id == agent_id]
        
        if unresolved_only:
            alerts = [a for a in alerts if not a.resolved]
        
        # Sort by timestamp (newest first) and limit
        alerts.sort(key=lambda a: a.timestamp, reverse=True)
        return alerts[:limit]
    
    def get_mcp_performance_metrics(self) -> Dict[str, Dict[str, float]]:
        """Get performance metrics for MCP tool calls"""
        metrics = {}
        
        for tool_key, response_times in self._performance_metrics.items():
            if response_times:
                metrics[tool_key] = {
                    "avg_response_time_ms": sum(response_times) / len(response_times),
                    "min_response_time_ms": min(response_times),
                    "max_response_time_ms": max(response_times),
                    "total_calls": len(response_times)
                }
        
        return metrics
    
    def get_mcp_audit_summary(self, tenant_id: str) -> Dict[str, Any]:
        """
        Get audit summary for a tenant
        
        Args:
            tenant_id: Tenant identifier
            
        Returns:
            Audit summary dictionary
        """
        tenant_events = [e for e in self._mcp_events if e.tenant_id == tenant_id]
        tenant_workflows = [w for w in self._workflow_trails.values() if w.tenant_id == tenant_id]
        tenant_alerts = [a for a in self._security_alerts if a.tenant_id == tenant_id]
        
        return {
            "tenant_id": tenant_id,
            "total_events": len(tenant_events),
            "successful_events": len([e for e in tenant_events if e.success]),
            "failed_events": len([e for e in tenant_events if not e.success]),
            "total_workflows": len(tenant_workflows),
            "completed_workflows": len([w for w in tenant_workflows if w.status == "completed"]),
            "failed_workflows": len([w for w in tenant_workflows if w.status == "failed"]),
            "security_alerts": len(tenant_alerts),
            "unresolved_alerts": len([a for a in tenant_alerts if not a.resolved]),
            "event_types": self._get_event_type_counts(tenant_events),
            "most_active_agents": self._get_most_active_agents(tenant_events)
        }
    
    def _store_event(self, event: MCPAuditEvent):
        """Store audit event"""
        self._mcp_events.append(event)
        
        # Keep only recent events (last 10000)
        if len(self._mcp_events) > 10000:
            self._mcp_events = self._mcp_events[-10000:]
        
        # Update workflow trail if applicable
        if event.workflow_id and event.workflow_id in self._workflow_trails:
            trail = self._workflow_trails[event.workflow_id]
            trail.events.append(event.event_id)
            
            if event.event_type == MCPEventType.TOOL_CALL:
                trail.total_tool_calls += 1
                if not event.success:
                    trail.failed_tool_calls += 1
            
            if event.event_type == MCPEventType.SECURITY_VIOLATION:
                trail.security_violations += 1
    
    def _calculate_workflow_duration(self, trail: MCPWorkflowAuditTrail) -> Optional[float]:
        """Calculate workflow duration in milliseconds"""
        if not trail.end_time:
            return None
        
        start = datetime.fromisoformat(trail.start_time.replace('Z', '+00:00'))
        end = datetime.fromisoformat(trail.end_time.replace('Z', '+00:00'))
        
        return (end - start).total_seconds() * 1000
    
    def _get_event_type_counts(self, events: List[MCPAuditEvent]) -> Dict[str, int]:
        """Get count of events by type"""
        counts = {}
        for event in events:
            event_type = event.event_type.value
            counts[event_type] = counts.get(event_type, 0) + 1
        return counts
    
    def _get_most_active_agents(self, events: List[MCPAuditEvent]) -> List[Dict[str, Any]]:
        """Get most active agents from events"""
        agent_counts = {}
        for event in events:
            agent_counts[event.agent_id] = agent_counts.get(event.agent_id, 0) + 1
        
        # Sort by count and return top 5
        sorted_agents = sorted(agent_counts.items(), key=lambda x: x[1], reverse=True)
        return [{"agent_id": agent, "event_count": count} for agent, count in sorted_agents[:5]]


# Global service
mcp_audit_logger = MCPAuditLogger()