"""
HappyOS SDK - Unified Audit Logging

Standardized audit logging for all HappyOS agents with GDPR compliance.
Provides consistent audit trails across Agent Svea, Felicia's Finance, and MeetMind.

Requirements: 5.4, 11.1, 11.2, 11.3
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any, Union
from uuid import uuid4
from dataclasses import dataclass, asdict
from enum import Enum
import json

from .mcp_security import MCPHeaders
from .tenant_isolation import TenantAccessAttempt

logger = logging.getLogger(__name__)


class AuditEventType(Enum):
    """Audit event types"""
    MCP_TOOL_CALL = "mcp_tool_call"
    MCP_CALLBACK = "mcp_callback"
    MCP_WORKFLOW_START = "mcp_workflow_start"
    MCP_WORKFLOW_COMPLETE = "mcp_workflow_complete"
    MCP_WORKFLOW_FAILED = "mcp_workflow_failed"
    TENANT_ACCESS = "tenant_access"
    SECURITY_VIOLATION = "security_violation"
    AUTHENTICATION_EVENT = "authentication_event"
    DATA_ACCESS = "data_access"
    DATA_MODIFICATION = "data_modification"
    SYSTEM_EVENT = "system_event"
    COMPLIANCE_EVENT = "compliance_event"


class AuditSeverity(Enum):
    """Audit severity levels"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class AuditOutcome(Enum):
    """Audit event outcomes"""
    SUCCESS = "success"
    FAILURE = "failure"
    PARTIAL = "partial"
    UNKNOWN = "unknown"


@dataclass
class AuditContext:
    """Audit context information"""
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    agent_id: Optional[str] = None
    tenant_id: Optional[str] = None
    trace_id: Optional[str] = None
    conversation_id: Optional[str] = None
    client_ip: Optional[str] = None
    user_agent: Optional[str] = None
    request_id: Optional[str] = None


@dataclass
class AuditEvent:
    """Standardized audit event record"""
    event_id: str
    timestamp: str
    event_type: AuditEventType
    severity: AuditSeverity
    outcome: AuditOutcome
    action: str
    description: str
    context: AuditContext
    details: Dict[str, Any]
    
    # GDPR compliance fields
    data_subject_id: Optional[str] = None
    personal_data_categories: List[str] = None
    legal_basis: Optional[str] = None
    retention_period_days: Optional[int] = None
    
    def __post_init__(self):
        if self.personal_data_categories is None:
            self.personal_data_categories = []
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage/transmission"""
        return asdict(self)
    
    def contains_personal_data(self) -> bool:
        """Check if event contains personal data"""
        return bool(self.personal_data_categories)
    
    def is_expired(self) -> bool:
        """Check if event has exceeded retention period"""
        if not self.retention_period_days:
            return False
        
        event_time = datetime.fromisoformat(self.timestamp.replace('Z', '+00:00'))
        expiry_time = event_time + timedelta(days=self.retention_period_days)
        
        return datetime.now(timezone.utc) > expiry_time


@dataclass
class ComplianceReport:
    """GDPR compliance report"""
    report_id: str
    generated_at: str
    tenant_id: str
    data_subject_id: Optional[str] = None
    report_type: str = "audit_trail"
    events: List[AuditEvent] = None
    summary: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.events is None:
            self.events = []
        if self.summary is None:
            self.summary = {}


class UnifiedAuditLogger:
    """Unified audit logger for all HappyOS agents"""
    
    def __init__(self):
        # In-memory storage for demo - in production use secure database
        self._audit_events: List[AuditEvent] = []
        
        # GDPR compliance tracking
        self._data_subjects: Dict[str, List[str]] = {}  # subject_id -> event_ids
        self._retention_policies: Dict[str, int] = {
            "default": 2555,  # 7 years in days
            "authentication": 365,  # 1 year
            "system_events": 90,   # 3 months
            "security_violations": 2555,  # 7 years
            "compliance_events": 2555,    # 7 years
            "personal_data": 2555         # 7 years
        }
        
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
        contains_personal_data: bool = False
    ) -> str:
        """
        Log MCP tool call event
        
        Args:
            headers: MCP headers
            target_agent: Target agent identifier
            tool_name: Tool being called
            arguments: Tool arguments (sanitized)
            success: Whether call succeeded
            response_time_ms: Response time in milliseconds
            error_message: Error message if failed
            contains_personal_data: Whether call involves personal data
            
        Returns:
            Event ID
        """
        context = AuditContext(
            agent_id=headers.caller,
            tenant_id=headers.tenant_id,
            trace_id=headers.trace_id,
            conversation_id=headers.conversation_id
        )
        
        # Determine severity
        severity = AuditSeverity.LOW
        if not success:
            severity = AuditSeverity.MEDIUM
        if error_message and "security" in error_message.lower():
            severity = AuditSeverity.HIGH
        
        # Sanitize arguments to remove sensitive data
        sanitized_args = self._sanitize_data(arguments)
        
        details = {
            "target_agent": target_agent,
            "tool_name": tool_name,
            "arguments": sanitized_args,
            "reply_to": headers.reply_to,
            "response_time_ms": response_time_ms,
            "error_message": error_message
        }
        
        # GDPR compliance
        personal_data_categories = []
        if contains_personal_data:
            personal_data_categories = ["user_interactions", "system_logs"]
        
        event = AuditEvent(
            event_id=str(uuid4()),
            timestamp=datetime.now(timezone.utc).isoformat(),
            event_type=AuditEventType.MCP_TOOL_CALL,
            severity=severity,
            outcome=AuditOutcome.SUCCESS if success else AuditOutcome.FAILURE,
            action=f"mcp_call_{tool_name}",
            description=f"MCP tool call: {headers.caller} -> {target_agent}.{tool_name}",
            context=context,
            details=details,
            data_subject_id=headers.caller if contains_personal_data else None,
            personal_data_categories=personal_data_categories,
            legal_basis="legitimate_interest" if contains_personal_data else None,
            retention_period_days=self._get_retention_period("personal_data" if contains_personal_data else "default")
        )
        
        self._store_event(event)
        
        # Track performance metrics
        if response_time_ms:
            metric_key = f"{target_agent}.{tool_name}"
            if metric_key not in self._performance_metrics:
                self._performance_metrics[metric_key] = []
            self._performance_metrics[metric_key].append(response_time_ms)
        
        return event.event_id
    
    def log_mcp_callback(
        self,
        headers: MCPHeaders,
        original_trace_id: str,
        callback_data: Dict[str, Any],
        success: bool,
        processing_time_ms: Optional[float] = None,
        error_message: Optional[str] = None
    ) -> str:
        """
        Log MCP callback event
        
        Args:
            headers: MCP callback headers
            original_trace_id: Original request trace ID
            callback_data: Callback payload (sanitized)
            success: Whether callback succeeded
            processing_time_ms: Processing time in milliseconds
            error_message: Error message if failed
            
        Returns:
            Event ID
        """
        context = AuditContext(
            agent_id=headers.caller,
            tenant_id=headers.tenant_id,
            trace_id=headers.trace_id,
            conversation_id=headers.conversation_id
        )
        
        # Sanitize callback data
        sanitized_data = self._sanitize_data(callback_data)
        
        details = {
            "original_trace_id": original_trace_id,
            "callback_data_size": len(str(callback_data)),
            "reply_to": headers.reply_to,
            "processing_time_ms": processing_time_ms,
            "error_message": error_message,
            "callback_summary": self._create_data_summary(sanitized_data)
        }
        
        event = AuditEvent(
            event_id=str(uuid4()),
            timestamp=datetime.now(timezone.utc).isoformat(),
            event_type=AuditEventType.MCP_CALLBACK,
            severity=AuditSeverity.LOW if success else AuditSeverity.MEDIUM,
            outcome=AuditOutcome.SUCCESS if success else AuditOutcome.FAILURE,
            action="mcp_callback",
            description=f"MCP callback: {headers.caller} -> {headers.reply_to}",
            context=context,
            details=details,
            retention_period_days=self._get_retention_period("default")
        )
        
        self._store_event(event)
        return event.event_id
    
    def log_tenant_access(
        self,
        access_attempt: TenantAccessAttempt,
        additional_context: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Log tenant access attempt
        
        Args:
            access_attempt: Tenant access attempt record
            additional_context: Additional context information
            
        Returns:
            Event ID
        """
        context = AuditContext(
            agent_id=access_attempt.caller_agent,
            tenant_id=access_attempt.tenant_id,
            trace_id=access_attempt.trace_id,
            conversation_id=access_attempt.conversation_id
        )
        
        details = {
            "target_agent": access_attempt.target_agent,
            "tool_name": access_attempt.tool_name,
            "operation": access_attempt.operation,
            "reason": access_attempt.reason,
            "attempt_id": access_attempt.attempt_id
        }
        
        if additional_context:
            details.update(additional_context)
        
        # Determine severity based on outcome
        severity = AuditSeverity.LOW if access_attempt.allowed else AuditSeverity.HIGH
        if not access_attempt.allowed and "cross-tenant" in access_attempt.reason.lower():
            severity = AuditSeverity.CRITICAL
        
        event = AuditEvent(
            event_id=str(uuid4()),
            timestamp=access_attempt.timestamp,
            event_type=AuditEventType.TENANT_ACCESS,
            severity=severity,
            outcome=AuditOutcome.SUCCESS if access_attempt.allowed else AuditOutcome.FAILURE,
            action=f"tenant_access_{access_attempt.operation}",
            description=f"Tenant access: {access_attempt.caller_agent} -> {access_attempt.target_agent}",
            context=context,
            details=details,
            retention_period_days=self._get_retention_period("security_violations" if not access_attempt.allowed else "default")
        )
        
        self._store_event(event)
        return event.event_id
    
    def log_security_violation(
        self,
        tenant_id: str,
        agent_id: str,
        violation_type: str,
        description: str,
        evidence: Dict[str, Any],
        severity: AuditSeverity = AuditSeverity.HIGH,
        trace_id: Optional[str] = None
    ) -> str:
        """
        Log security violation
        
        Args:
            tenant_id: Tenant identifier
            agent_id: Agent identifier
            violation_type: Type of violation
            description: Violation description
            evidence: Evidence of violation (sanitized)
            severity: Violation severity
            trace_id: Optional trace ID
            
        Returns:
            Event ID
        """
        context = AuditContext(
            agent_id=agent_id,
            tenant_id=tenant_id,
            trace_id=trace_id
        )
        
        # Sanitize evidence
        sanitized_evidence = self._sanitize_data(evidence)
        
        details = {
            "violation_type": violation_type,
            "evidence": sanitized_evidence,
            "investigation_required": severity in [AuditSeverity.HIGH, AuditSeverity.CRITICAL]
        }
        
        event = AuditEvent(
            event_id=str(uuid4()),
            timestamp=datetime.now(timezone.utc).isoformat(),
            event_type=AuditEventType.SECURITY_VIOLATION,
            severity=severity,
            outcome=AuditOutcome.FAILURE,
            action=f"security_violation_{violation_type}",
            description=description,
            context=context,
            details=details,
            retention_period_days=self._get_retention_period("security_violations")
        )
        
        self._store_event(event)
        
        # Log to system logger for immediate attention
        logger.warning(
            f"Security violation logged: {violation_type} - {description} "
            f"(Agent: {agent_id}, Tenant: {tenant_id}, Event: {event.event_id})"
        )
        
        return event.event_id
    
    def log_compliance_event(
        self,
        tenant_id: str,
        event_type: str,
        description: str,
        data_subject_id: Optional[str] = None,
        personal_data_categories: List[str] = None,
        legal_basis: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Log GDPR compliance event
        
        Args:
            tenant_id: Tenant identifier
            event_type: Type of compliance event
            description: Event description
            data_subject_id: Data subject identifier
            personal_data_categories: Categories of personal data involved
            legal_basis: Legal basis for processing
            details: Additional details
            
        Returns:
            Event ID
        """
        context = AuditContext(
            tenant_id=tenant_id
        )
        
        event = AuditEvent(
            event_id=str(uuid4()),
            timestamp=datetime.now(timezone.utc).isoformat(),
            event_type=AuditEventType.COMPLIANCE_EVENT,
            severity=AuditSeverity.MEDIUM,
            outcome=AuditOutcome.SUCCESS,
            action=f"compliance_{event_type}",
            description=description,
            context=context,
            details=details or {},
            data_subject_id=data_subject_id,
            personal_data_categories=personal_data_categories or [],
            legal_basis=legal_basis,
            retention_period_days=self._get_retention_period("compliance_events")
        )
        
        self._store_event(event)
        return event.event_id
    
    def get_audit_events(
        self,
        tenant_id: Optional[str] = None,
        agent_id: Optional[str] = None,
        event_type: Optional[AuditEventType] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        severity: Optional[AuditSeverity] = None,
        limit: int = 100
    ) -> List[AuditEvent]:
        """
        Get audit events with filtering
        
        Args:
            tenant_id: Filter by tenant
            agent_id: Filter by agent
            event_type: Filter by event type
            start_time: Filter by start time
            end_time: Filter by end time
            severity: Filter by severity
            limit: Maximum number of results
            
        Returns:
            List of audit events
        """
        events = self._audit_events
        
        # Apply filters
        if tenant_id:
            events = [e for e in events if e.context.tenant_id == tenant_id]
        
        if agent_id:
            events = [e for e in events if e.context.agent_id == agent_id]
        
        if event_type:
            events = [e for e in events if e.event_type == event_type]
        
        if start_time:
            events = [e for e in events if datetime.fromisoformat(e.timestamp.replace('Z', '+00:00')) >= start_time]
        
        if end_time:
            events = [e for e in events if datetime.fromisoformat(e.timestamp.replace('Z', '+00:00')) <= end_time]
        
        if severity:
            events = [e for e in events if e.severity == severity]
        
        # Sort by timestamp (newest first) and limit
        events.sort(key=lambda e: e.timestamp, reverse=True)
        return events[:limit]
    
    def generate_compliance_report(
        self,
        tenant_id: str,
        data_subject_id: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None
    ) -> ComplianceReport:
        """
        Generate GDPR compliance report
        
        Args:
            tenant_id: Tenant identifier
            data_subject_id: Optional data subject identifier
            start_time: Optional start time
            end_time: Optional end time
            
        Returns:
            Compliance report
        """
        # Filter events
        events = self.get_audit_events(
            tenant_id=tenant_id,
            start_time=start_time,
            end_time=end_time
        )
        
        # Further filter by data subject if specified
        if data_subject_id:
            events = [e for e in events if e.data_subject_id == data_subject_id]
        
        # Generate summary
        summary = {
            "total_events": len(events),
            "events_with_personal_data": len([e for e in events if e.contains_personal_data()]),
            "event_types": self._get_event_type_counts(events),
            "severity_distribution": self._get_severity_distribution(events),
            "legal_bases": self._get_legal_bases(events),
            "retention_status": self._get_retention_status(events)
        }
        
        report = ComplianceReport(
            report_id=str(uuid4()),
            generated_at=datetime.now(timezone.utc).isoformat(),
            tenant_id=tenant_id,
            data_subject_id=data_subject_id,
            events=events,
            summary=summary
        )
        
        return report
    
    def exercise_right_to_be_forgotten(
        self,
        data_subject_id: str,
        tenant_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Exercise right to be forgotten (GDPR Article 17)
        
        Args:
            data_subject_id: Data subject identifier
            tenant_id: Optional tenant filter
            
        Returns:
            Summary of deletion actions
        """
        # Find events containing personal data for this subject
        events_to_delete = []
        events_to_anonymize = []
        
        for event in self._audit_events:
            if event.data_subject_id == data_subject_id:
                if tenant_id and event.context.tenant_id != tenant_id:
                    continue
                
                # Check if event can be deleted or must be anonymized
                if event.event_type in [AuditEventType.SECURITY_VIOLATION, AuditEventType.COMPLIANCE_EVENT]:
                    # Security and compliance events must be anonymized, not deleted
                    events_to_anonymize.append(event)
                else:
                    events_to_delete.append(event)
        
        # Delete eligible events
        for event in events_to_delete:
            self._audit_events.remove(event)
        
        # Anonymize security/compliance events
        for event in events_to_anonymize:
            event.data_subject_id = None
            event.personal_data_categories = []
            event.details = self._anonymize_data(event.details)
            event.description = self._anonymize_text(event.description)
        
        # Update data subject tracking
        if data_subject_id in self._data_subjects:
            del self._data_subjects[data_subject_id]
        
        summary = {
            "data_subject_id": data_subject_id,
            "tenant_id": tenant_id,
            "events_deleted": len(events_to_delete),
            "events_anonymized": len(events_to_anonymize),
            "deletion_timestamp": datetime.now(timezone.utc).isoformat()
        }
        
        # Log the deletion action
        self.log_compliance_event(
            tenant_id=tenant_id or "system",
            event_type="right_to_be_forgotten",
            description=f"Exercised right to be forgotten for data subject",
            details=summary
        )
        
        logger.info(f"Right to be forgotten exercised for {data_subject_id}: {summary}")
        return summary
    
    def cleanup_expired_events(self) -> Dict[str, int]:
        """
        Clean up expired audit events based on retention policies
        
        Returns:
            Summary of cleanup actions
        """
        expired_events = []
        
        for event in self._audit_events:
            if event.is_expired():
                expired_events.append(event)
        
        # Remove expired events
        for event in expired_events:
            self._audit_events.remove(event)
            
            # Update data subject tracking
            if event.data_subject_id and event.data_subject_id in self._data_subjects:
                if event.event_id in self._data_subjects[event.data_subject_id]:
                    self._data_subjects[event.data_subject_id].remove(event.event_id)
        
        summary = {
            "expired_events_deleted": len(expired_events),
            "cleanup_timestamp": datetime.now(timezone.utc).isoformat(),
            "remaining_events": len(self._audit_events)
        }
        
        if expired_events:
            logger.info(f"Cleaned up {len(expired_events)} expired audit events")
        
        return summary
    
    def _store_event(self, event: AuditEvent):
        """Store audit event"""
        self._audit_events.append(event)
        
        # Track data subjects
        if event.data_subject_id:
            if event.data_subject_id not in self._data_subjects:
                self._data_subjects[event.data_subject_id] = []
            self._data_subjects[event.data_subject_id].append(event.event_id)
        
        # Keep only recent events (last 50000)
        if len(self._audit_events) > 50000:
            # Remove oldest events
            oldest_events = sorted(self._audit_events, key=lambda e: e.timestamp)[:10000]
            for old_event in oldest_events:
                self._audit_events.remove(old_event)
    
    def _get_retention_period(self, category: str) -> int:
        """Get retention period for event category"""
        return self._retention_policies.get(category, self._retention_policies["default"])
    
    def _sanitize_data(self, data: Any) -> Any:
        """Sanitize data to remove sensitive information"""
        if isinstance(data, dict):
            sanitized = {}
            for key, value in data.items():
                if key.lower() in ["password", "secret", "key", "token", "auth"]:
                    sanitized[key] = "[REDACTED]"
                elif key.lower() in ["email", "phone", "ssn", "personal_id"]:
                    sanitized[key] = "[PII_REDACTED]"
                else:
                    sanitized[key] = self._sanitize_data(value)
            return sanitized
        elif isinstance(data, list):
            return [self._sanitize_data(item) for item in data]
        elif isinstance(data, str) and len(data) > 1000:
            return data[:1000] + "...[TRUNCATED]"
        else:
            return data
    
    def _anonymize_data(self, data: Any) -> Any:
        """Anonymize data for GDPR compliance"""
        if isinstance(data, dict):
            anonymized = {}
            for key, value in data.items():
                if key.lower() in ["user_id", "agent_id", "caller", "email", "name"]:
                    anonymized[key] = "[ANONYMIZED]"
                else:
                    anonymized[key] = self._anonymize_data(value)
            return anonymized
        elif isinstance(data, list):
            return [self._anonymize_data(item) for item in data]
        else:
            return data
    
    def _anonymize_text(self, text: str) -> str:
        """Anonymize text content"""
        # Simple anonymization - in production use more sophisticated methods
        return text.replace("user", "[USER]").replace("agent", "[AGENT]")
    
    def _create_data_summary(self, data: Any) -> Dict[str, Any]:
        """Create summary of data without exposing sensitive content"""
        if isinstance(data, dict):
            return {
                "type": "object",
                "keys": list(data.keys()),
                "size": len(data)
            }
        elif isinstance(data, list):
            return {
                "type": "array",
                "length": len(data),
                "item_types": list(set(type(item).__name__ for item in data))
            }
        else:
            return {
                "type": type(data).__name__,
                "size": len(str(data)) if hasattr(data, '__len__') else 1
            }
    
    def _get_event_type_counts(self, events: List[AuditEvent]) -> Dict[str, int]:
        """Get count of events by type"""
        counts = {}
        for event in events:
            event_type = event.event_type.value
            counts[event_type] = counts.get(event_type, 0) + 1
        return counts
    
    def _get_severity_distribution(self, events: List[AuditEvent]) -> Dict[str, int]:
        """Get distribution of events by severity"""
        distribution = {}
        for event in events:
            severity = event.severity.value
            distribution[severity] = distribution.get(severity, 0) + 1
        return distribution
    
    def _get_legal_bases(self, events: List[AuditEvent]) -> Dict[str, int]:
        """Get legal bases used for personal data processing"""
        bases = {}
        for event in events:
            if event.legal_basis:
                bases[event.legal_basis] = bases.get(event.legal_basis, 0) + 1
        return bases
    
    def _get_retention_status(self, events: List[AuditEvent]) -> Dict[str, int]:
        """Get retention status of events"""
        status = {"active": 0, "expiring_soon": 0, "expired": 0}
        now = datetime.now(timezone.utc)
        
        for event in events:
            if event.is_expired():
                status["expired"] += 1
            elif event.retention_period_days:
                event_time = datetime.fromisoformat(event.timestamp.replace('Z', '+00:00'))
                expiry_time = event_time + timedelta(days=event.retention_period_days)
                days_until_expiry = (expiry_time - now).days
                
                if days_until_expiry <= 30:  # Expiring within 30 days
                    status["expiring_soon"] += 1
                else:
                    status["active"] += 1
            else:
                status["active"] += 1
        
        return status


# Global service for HappyOS SDK
unified_audit_logger = UnifiedAuditLogger()


def log_mcp_event(
    event_type: str,
    headers: MCPHeaders,
    details: Dict[str, Any],
    success: bool = True,
    contains_personal_data: bool = False
) -> str:
    """
    Convenience function to log MCP events
    
    Args:
        event_type: Type of MCP event
        headers: MCP headers
        details: Event details
        success: Whether event was successful
        contains_personal_data: Whether event involves personal data
        
    Returns:
        Event ID
    """
    if event_type == "tool_call":
        return unified_audit_logger.log_mcp_tool_call(
            headers=headers,
            target_agent=details.get("target_agent", "unknown"),
            tool_name=details.get("tool_name", "unknown"),
            arguments=details.get("arguments", {}),
            success=success,
            response_time_ms=details.get("response_time_ms"),
            error_message=details.get("error_message"),
            contains_personal_data=contains_personal_data
        )
    elif event_type == "callback":
        return unified_audit_logger.log_mcp_callback(
            headers=headers,
            original_trace_id=details.get("original_trace_id", ""),
            callback_data=details.get("callback_data", {}),
            success=success,
            processing_time_ms=details.get("processing_time_ms"),
            error_message=details.get("error_message")
        )
    else:
        # Generic event logging
        context = AuditContext(
            agent_id=headers.caller,
            tenant_id=headers.tenant_id,
            trace_id=headers.trace_id,
            conversation_id=headers.conversation_id
        )
        
        event = AuditEvent(
            event_id=str(uuid4()),
            timestamp=datetime.now(timezone.utc).isoformat(),
            event_type=AuditEventType.SYSTEM_EVENT,
            severity=AuditSeverity.LOW,
            outcome=AuditOutcome.SUCCESS if success else AuditOutcome.FAILURE,
            action=event_type,
            description=f"MCP event: {event_type}",
            context=context,
            details=details,
            retention_period_days=unified_audit_logger._get_retention_period("default")
        )
        
        unified_audit_logger._store_event(event)
        return event.event_id