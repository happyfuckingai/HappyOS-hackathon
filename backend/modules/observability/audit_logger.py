"""
Structured audit logging with tenant/agent/resource context.
"""

import json
import time
import asyncio
from typing import Dict, List, Optional, Any, Union
from datetime import datetime, timezone
from dataclasses import dataclass, field, asdict
from enum import Enum
from pathlib import Path

try:
    import boto3
    from botocore.exceptions import ClientError, NoCredentialsError
    AWS_AVAILABLE = True
except ImportError:
    AWS_AVAILABLE = False

try:
    from backend.modules.config.settings import settings
except ImportError:
    import sys
    import os
    sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))
    from backend.modules.config.settings import settings

from backend.services.observability.logger import get_logger


class AuditEventType(Enum):
    """Types of audit events."""
    # Resource operations
    RESOURCE_CREATE = "resource_create"
    RESOURCE_UPDATE = "resource_update"
    RESOURCE_DELETE = "resource_delete"
    RESOURCE_READ = "resource_read"
    
    # Authentication and authorization
    AUTH_LOGIN = "auth_login"
    AUTH_LOGOUT = "auth_logout"
    AUTH_TOKEN_REFRESH = "auth_token_refresh"
    AUTH_PERMISSION_DENIED = "auth_permission_denied"
    
    # Tenant operations
    TENANT_ACCESS = "tenant_access"
    TENANT_ISOLATION_VIOLATION = "tenant_isolation_violation"
    
    # WebSocket operations
    WEBSOCKET_CONNECT = "websocket_connect"
    WEBSOCKET_DISCONNECT = "websocket_disconnect"
    WEBSOCKET_MESSAGE = "websocket_message"
    
    # Security events
    SECURITY_THREAT_DETECTED = "security_threat_detected"
    SECURITY_RATE_LIMIT_EXCEEDED = "security_rate_limit_exceeded"
    SECURITY_SUSPICIOUS_ACTIVITY = "security_suspicious_activity"
    
    # System events
    SYSTEM_ERROR = "system_error"
    SYSTEM_WARNING = "system_warning"
    SYSTEM_INFO = "system_info"


class AuditSeverity(Enum):
    """Severity levels for audit events."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class AuditEvent:
    """Represents a single audit event with full context."""
    
    # Event identification
    event_id: str = field(default_factory=lambda: f"audit_{int(time.time() * 1000000)}")
    event_type: AuditEventType = AuditEventType.SYSTEM_INFO
    severity: AuditSeverity = AuditSeverity.LOW
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    # Context information
    tenant_id: Optional[str] = None
    session_id: Optional[str] = None
    agent_id: Optional[str] = None
    user_id: Optional[str] = None
    resource_id: Optional[str] = None
    
    # Request context
    correlation_id: Optional[str] = None
    request_id: Optional[str] = None
    trace_id: Optional[str] = None
    
    # Network context
    client_ip: Optional[str] = None
    user_agent: Optional[str] = None
    
    # Event details
    message: str = ""
    details: Dict[str, Any] = field(default_factory=dict)
    
    # Operation context
    operation: Optional[str] = None
    component: Optional[str] = None
    duration_ms: Optional[float] = None
    
    # Security context
    auth_method: Optional[str] = None
    permissions: List[str] = field(default_factory=list)
    
    # Error context (if applicable)
    error_type: Optional[str] = None
    error_message: Optional[str] = None
    stack_trace: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        data = asdict(self)
        
        # Convert enums to strings
        data["event_type"] = self.event_type.value
        data["severity"] = self.severity.value
        data["timestamp"] = self.timestamp.isoformat()
        
        # Remove None values to reduce log size
        return {k: v for k, v in data.items() if v is not None}
    
    def to_json(self) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict(), separators=(',', ':'))


class AuditLogger:
    """Structured audit logging with multiple output destinations."""
    
    def __init__(self):
        self.logger = get_logger(__name__)
        self.local_log_file = Path("logs/audit.jsonl")
        self.s3_client = None
        self.cloudwatch_client = None
        self._log_buffer: List[AuditEvent] = []
        self._buffer_size = 100
        self._setup_outputs()
    
    def _setup_outputs(self):
        """Setup audit log output destinations."""
        # Ensure local log directory exists
        self.local_log_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Setup AWS clients if available
        if AWS_AVAILABLE:
            try:
                self.s3_client = boto3.client(
                    's3',
                    region_name=getattr(settings, 'AWS_REGION', 'us-east-1')
                )
                
                self.cloudwatch_client = boto3.client(
                    'logs',
                    region_name=getattr(settings, 'AWS_REGION', 'us-east-1')
                )
                
                self.logger.info("AWS audit logging clients initialized")
                
            except (NoCredentialsError, Exception) as e:
                self.logger.warning(f"AWS audit logging not available: {e}")
    
    async def log_event(self, event: AuditEvent):
        """Log a single audit event to all configured destinations."""
        try:
            # Add to buffer
            self._log_buffer.append(event)
            
            # Write to local file immediately for critical events
            if event.severity in [AuditSeverity.HIGH, AuditSeverity.CRITICAL]:
                await self._write_to_local_file([event])
            
            # Flush buffer if full
            if len(self._log_buffer) >= self._buffer_size:
                await self._flush_buffer()
            
            # Log to application logger for immediate visibility
            log_level = self._get_log_level(event.severity)
            self.logger.log(
                log_level,
                f"AUDIT: {event.message}",
                extra={
                    "audit_event": True,
                    "event_id": event.event_id,
                    "event_type": event.event_type.value,
                    "severity": event.severity.value,
                    "tenant_id": event.tenant_id,
                    "correlation_id": event.correlation_id,
                    **event.details
                }
            )
            
        except Exception as e:
            self.logger.error(f"Failed to log audit event: {e}")
    
    def _get_log_level(self, severity: AuditSeverity) -> int:
        """Convert audit severity to logging level."""
        mapping = {
            AuditSeverity.LOW: 10,      # DEBUG
            AuditSeverity.MEDIUM: 20,   # INFO
            AuditSeverity.HIGH: 30,     # WARNING
            AuditSeverity.CRITICAL: 40  # ERROR
        }
        return mapping.get(severity, 20)
    
    async def _flush_buffer(self):
        """Flush audit log buffer to all destinations."""
        if not self._log_buffer:
            return
        
        events_to_flush = self._log_buffer.copy()
        self._log_buffer.clear()
        
        # Write to all destinations concurrently
        tasks = [
            self._write_to_local_file(events_to_flush),
            self._write_to_s3(events_to_flush),
            self._write_to_cloudwatch(events_to_flush)
        ]
        
        await asyncio.gather(*tasks, return_exceptions=True)
    
    async def _write_to_local_file(self, events: List[AuditEvent]):
        """Write audit events to local JSONL file."""
        try:
            with open(self.local_log_file, 'a', encoding='utf-8') as f:
                for event in events:
                    f.write(event.to_json() + '\n')
            
            self.logger.debug(f"Wrote {len(events)} audit events to local file")
            
        except Exception as e:
            self.logger.error(f"Failed to write audit events to local file: {e}")
    
    async def _write_to_s3(self, events: List[AuditEvent]):
        """Write audit events to S3 for long-term storage."""
        if not self.s3_client:
            return
        
        try:
            # Group events by tenant and date for efficient storage
            grouped_events = self._group_events_for_s3(events)
            
            for key, event_group in grouped_events.items():
                # Create JSONL content
                content = '\n'.join(event.to_json() for event in event_group)
                
                # Upload to S3
                await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: self.s3_client.put_object(
                        Bucket=getattr(settings, 'AUDIT_LOG_S3_BUCKET', 'meetmind-audit-logs'),
                        Key=key,
                        Body=content.encode('utf-8'),
                        ContentType='application/x-ndjson',
                        ServerSideEncryption='AES256'
                    )
                )
            
            self.logger.debug(f"Wrote {len(events)} audit events to S3")
            
        except Exception as e:
            self.logger.error(f"Failed to write audit events to S3: {e}")
    
    def _group_events_for_s3(self, events: List[AuditEvent]) -> Dict[str, List[AuditEvent]]:
        """Group events by tenant and date for S3 storage."""
        groups = {}
        
        for event in events:
            # Create S3 key: tenant/year/month/day/hour/events.jsonl
            date_path = event.timestamp.strftime("%Y/%m/%d/%H")
            tenant = event.tenant_id or "system"
            key = f"audit-logs/{tenant}/{date_path}/events_{int(time.time())}.jsonl"
            
            if key not in groups:
                groups[key] = []
            groups[key].append(event)
        
        return groups
    
    async def _write_to_cloudwatch(self, events: List[AuditEvent]):
        """Write audit events to CloudWatch Logs."""
        if not self.cloudwatch_client:
            return
        
        try:
            log_group = f"/meetmind/audit-logs/{settings.ENVIRONMENT}"
            
            # Group events by tenant for separate log streams
            tenant_events = {}
            for event in events:
                tenant = event.tenant_id or "system"
                if tenant not in tenant_events:
                    tenant_events[tenant] = []
                tenant_events[tenant].append(event)
            
            # Send to CloudWatch for each tenant
            for tenant, tenant_event_list in tenant_events.items():
                log_stream = f"{tenant}-{datetime.now(timezone.utc).strftime('%Y-%m-%d')}"
                
                log_events = [
                    {
                        'timestamp': int(event.timestamp.timestamp() * 1000),
                        'message': event.to_json()
                    }
                    for event in tenant_event_list
                ]
                
                await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: self._put_log_events(log_group, log_stream, log_events)
                )
            
            self.logger.debug(f"Wrote {len(events)} audit events to CloudWatch")
            
        except Exception as e:
            self.logger.error(f"Failed to write audit events to CloudWatch: {e}")
    
    def _put_log_events(self, log_group: str, log_stream: str, log_events: List[Dict]):
        """Put log events to CloudWatch (synchronous helper)."""
        try:
            # Ensure log group exists
            try:
                self.cloudwatch_client.create_log_group(logGroupName=log_group)
            except ClientError as e:
                if e.response['Error']['Code'] != 'ResourceAlreadyExistsException':
                    raise
            
            # Ensure log stream exists
            try:
                self.cloudwatch_client.create_log_stream(
                    logGroupName=log_group,
                    logStreamName=log_stream
                )
            except ClientError as e:
                if e.response['Error']['Code'] != 'ResourceAlreadyExistsException':
                    raise
            
            # Put log events
            self.cloudwatch_client.put_log_events(
                logGroupName=log_group,
                logStreamName=log_stream,
                logEvents=log_events
            )
            
        except Exception as e:
            self.logger.error(f"Failed to put log events to CloudWatch: {e}")
    
    # Convenience methods for common audit events
    
    async def log_resource_operation(
        self,
        operation: str,
        resource_id: str,
        tenant_id: str,
        session_id: str = None,
        agent_id: str = None,
        user_id: str = None,
        success: bool = True,
        duration_ms: float = None,
        details: Dict[str, Any] = None,
        correlation_id: str = None
    ):
        """Log resource operation audit event."""
        event_type_map = {
            "create": AuditEventType.RESOURCE_CREATE,
            "update": AuditEventType.RESOURCE_UPDATE,
            "delete": AuditEventType.RESOURCE_DELETE,
            "read": AuditEventType.RESOURCE_READ
        }
        
        event = AuditEvent(
            event_type=event_type_map.get(operation, AuditEventType.SYSTEM_INFO),
            severity=AuditSeverity.LOW if success else AuditSeverity.MEDIUM,
            tenant_id=tenant_id,
            session_id=session_id,
            agent_id=agent_id,
            user_id=user_id,
            resource_id=resource_id,
            correlation_id=correlation_id,
            operation=operation,
            component="resource_manager",
            duration_ms=duration_ms,
            message=f"Resource {operation} {'succeeded' if success else 'failed'}: {resource_id}",
            details=details or {}
        )
        
        await self.log_event(event)
    
    async def log_security_event(
        self,
        event_type: AuditEventType,
        message: str,
        severity: AuditSeverity = AuditSeverity.HIGH,
        tenant_id: str = None,
        user_id: str = None,
        client_ip: str = None,
        details: Dict[str, Any] = None,
        correlation_id: str = None
    ):
        """Log security-related audit event."""
        event = AuditEvent(
            event_type=event_type,
            severity=severity,
            tenant_id=tenant_id,
            user_id=user_id,
            client_ip=client_ip,
            correlation_id=correlation_id,
            component="security",
            message=message,
            details=details or {}
        )
        
        await self.log_event(event)
    
    async def log_tenant_isolation_violation(
        self,
        attempted_tenant: str,
        actual_tenant: str,
        resource_id: str = None,
        user_id: str = None,
        client_ip: str = None,
        correlation_id: str = None
    ):
        """Log tenant isolation violation."""
        await self.log_security_event(
            AuditEventType.TENANT_ISOLATION_VIOLATION,
            f"Tenant isolation violation: attempted access to {attempted_tenant} from {actual_tenant}",
            AuditSeverity.CRITICAL,
            tenant_id=actual_tenant,
            user_id=user_id,
            client_ip=client_ip,
            correlation_id=correlation_id,
            details={
                "attempted_tenant": attempted_tenant,
                "actual_tenant": actual_tenant,
                "resource_id": resource_id
            }
        )
    
    async def log_authentication_event(
        self,
        event_type: AuditEventType,
        user_id: str,
        tenant_id: str = None,
        success: bool = True,
        auth_method: str = None,
        client_ip: str = None,
        user_agent: str = None,
        correlation_id: str = None
    ):
        """Log authentication-related audit event."""
        event = AuditEvent(
            event_type=event_type,
            severity=AuditSeverity.LOW if success else AuditSeverity.MEDIUM,
            tenant_id=tenant_id,
            user_id=user_id,
            client_ip=client_ip,
            user_agent=user_agent,
            correlation_id=correlation_id,
            auth_method=auth_method,
            component="authentication",
            message=f"Authentication {event_type.value} {'succeeded' if success else 'failed'} for user {user_id}"
        )
        
        await self.log_event(event)
    
    async def flush_all_events(self):
        """Flush all remaining events in buffer."""
        if self._log_buffer:
            await self._flush_buffer()
    
    async def query_events(
        self,
        tenant_id: str = None,
        event_type: AuditEventType = None,
        start_time: datetime = None,
        end_time: datetime = None,
        limit: int = 100
    ) -> List[AuditEvent]:
        """Query audit events from local storage (basic implementation)."""
        events = []
        
        try:
            if not self.local_log_file.exists():
                return events
            
            with open(self.local_log_file, 'r', encoding='utf-8') as f:
                for line in f:
                    try:
                        event_data = json.loads(line.strip())
                        
                        # Apply filters
                        if tenant_id and event_data.get('tenant_id') != tenant_id:
                            continue
                        
                        if event_type and event_data.get('event_type') != event_type.value:
                            continue
                        
                        event_time = datetime.fromisoformat(event_data['timestamp'].replace('Z', '+00:00'))
                        
                        if start_time and event_time < start_time:
                            continue
                        
                        if end_time and event_time > end_time:
                            continue
                        
                        events.append(event_data)
                        
                        if len(events) >= limit:
                            break
                            
                    except (json.JSONDecodeError, KeyError):
                        continue
            
        except Exception as e:
            self.logger.error(f"Failed to query audit events: {e}")
        
        return events


# Global audit logger instance
_audit_logger: Optional[AuditLogger] = None


def get_audit_logger() -> AuditLogger:
    """Get or create the global audit logger."""
    global _audit_logger
    if _audit_logger is None:
        _audit_logger = AuditLogger()
    return _audit_logger