"""
Audit Logger - Comprehensive logging of all self-building operations.
Tracks all auto-generations, registrations, and system changes.
"""

import logging
import json
import asyncio
from typing import Dict, Any, List, Optional, Union
from pathlib import Path
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from enum import Enum

logger = logging.getLogger(__name__)


class AuditEventType(Enum):
    """Types of audit events."""
    COMPONENT_DISCOVERED = "component_discovered"
    COMPONENT_REGISTERED = "component_registered"
    COMPONENT_ACTIVATED = "component_activated"
    COMPONENT_DEACTIVATED = "component_deactivated"
    COMPONENT_RELOADED = "component_reloaded"
    SKILL_AUTO_GENERATED = "skill_auto_generated"
    PLUGIN_AUTO_GENERATED = "plugin_auto_generated"
    MCP_SERVER_AUTO_GENERATED = "mcp_server_auto_generated"
    FILE_CREATED = "file_created"
    FILE_MODIFIED = "file_modified"
    ERROR_OCCURRED = "error_occurred"
    SYSTEM_STARTUP = "system_startup"
    SYSTEM_SHUTDOWN = "system_shutdown"


@dataclass
class AuditEvent:
    """Represents an audit event."""
    event_id: str
    event_type: AuditEventType
    timestamp: datetime
    component_name: Optional[str] = None
    component_type: Optional[str] = None
    user_request: Optional[str] = None
    details: Dict[str, Any] = None
    success: bool = True
    error_message: Optional[str] = None
    duration_seconds: Optional[float] = None
    metadata: Dict[str, Any] = None

    def __post_init__(self):
        if self.details is None:
            self.details = {}
        if self.metadata is None:
            self.metadata = {}


class AuditLogger:
    """
    Comprehensive audit logging for the self-building system.
    Tracks all operations, changes, and events.
    """
    
    def __init__(self, log_dir: str = None):
        # Use relative path from current working directory
        if log_dir is None:
            # Get current working directory and create logs relative to it
            current_dir = Path.cwd()
            self.log_dir = current_dir / "logs" / "audit"
        else:
            self.log_dir = Path(log_dir)
        
        try:
            self.log_dir.mkdir(parents=True, exist_ok=True)
        except PermissionError:
            # Fallback to current directory if default path fails
            fallback_dir = Path.cwd() / "logs_audit"
            self.log_dir = fallback_dir
            self.log_dir.mkdir(parents=True, exist_ok=True)
        
        self.events: List[AuditEvent] = []
        self.event_counter = 0
        
        # Setup file logging
        self.setup_file_logging()
        
        # Statistics
        self.stats = {
            "total_events": 0,
            "events_by_type": {},
            "errors_count": 0,
            "last_event": None
        }
    
    def setup_file_logging(self):
        """Setup file-based audit logging."""
        
        # Create audit log file with date
        today = datetime.now().strftime("%Y%m%d")
        self.audit_file = self.log_dir / f"audit_{today}.jsonl"
        
        # Setup structured logger
        audit_logger = logging.getLogger("audit")
        audit_logger.setLevel(logging.INFO)
        
        # File handler for audit logs
        file_handler = logging.FileHandler(self.audit_file)
        file_handler.setLevel(logging.INFO)
        
        # JSON formatter
        formatter = logging.Formatter('%(message)s')
        file_handler.setFormatter(formatter)
        
        audit_logger.addHandler(file_handler)
        
        self.audit_logger = audit_logger
    
    async def log_event(
        self,
        event_type: AuditEventType,
        component_name: Optional[str] = None,
        component_type: Optional[str] = None,
        user_request: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        success: bool = True,
        error_message: Optional[str] = None,
        duration_seconds: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Log an audit event.
        
        Args:
            event_type: Type of event
            component_name: Name of component involved
            component_type: Type of component
            user_request: Original user request that triggered this
            details: Additional event details
            success: Whether the operation was successful
            error_message: Error message if failed
            duration_seconds: How long the operation took
            metadata: Additional metadata
            
        Returns:
            Event ID
        """
        
        # Generate unique event ID
        self.event_counter += 1
        event_id = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{self.event_counter:04d}"
        
        # Create audit event
        event = AuditEvent(
            event_id=event_id,
            event_type=event_type,
            timestamp=datetime.now(),
            component_name=component_name,
            component_type=component_type,
            user_request=user_request,
            details=details or {},
            success=success,
            error_message=error_message,
            duration_seconds=duration_seconds,
            metadata=metadata or {}
        )
        
        # Store in memory
        self.events.append(event)
        
        # Write to file
        await self._write_event_to_file(event)
        
        # Update statistics
        self._update_stats(event)
        
        logger.debug(f"Logged audit event: {event_id} ({event_type.value})")
        
        return event_id
    
    async def _write_event_to_file(self, event: AuditEvent):
        """Write an audit event to the log file."""
        
        try:
            # Convert to dict and serialize
            event_dict = asdict(event)
            event_dict['timestamp'] = event.timestamp.isoformat()
            event_dict['event_type'] = event.event_type.value
            
            # Write as JSON line
            json_line = json.dumps(event_dict, default=str)
            self.audit_logger.info(json_line)
            
        except Exception as e:
            logger.error(f"Failed to write audit event to file: {e}")
    
    def _update_stats(self, event: AuditEvent):
        """Update audit statistics."""
        
        self.stats["total_events"] += 1
        self.stats["last_event"] = event.timestamp
        
        # Count by type
        event_type_str = event.event_type.value
        if event_type_str not in self.stats["events_by_type"]:
            self.stats["events_by_type"][event_type_str] = 0
        self.stats["events_by_type"][event_type_str] += 1
        
        # Count errors
        if not event.success:
            self.stats["errors_count"] += 1
    
    async def log_component_discovered(
        self, 
        component_name: str, 
        component_type: str, 
        file_path: str
    ):
        """Log component discovery."""
        
        await self.log_event(
            AuditEventType.COMPONENT_DISCOVERED,
            component_name=component_name,
            component_type=component_type,
            details={"file_path": file_path},
            metadata={"discovery_method": "file_scan"}
        )
    
    async def log_component_registered(
        self, 
        component_name: str, 
        component_type: str,
        success: bool = True,
        error_message: Optional[str] = None
    ):
        """Log component registration."""
        
        await self.log_event(
            AuditEventType.COMPONENT_REGISTERED,
            component_name=component_name,
            component_type=component_type,
            success=success,
            error_message=error_message
        )
    
    async def log_component_activated(
        self, 
        component_name: str, 
        component_type: str,
        duration_seconds: Optional[float] = None
    ):
        """Log component activation."""
        
        await self.log_event(
            AuditEventType.COMPONENT_ACTIVATED,
            component_name=component_name,
            component_type=component_type,
            duration_seconds=duration_seconds
        )
    
    async def log_component_reloaded(
        self, 
        component_name: str, 
        component_type: str,
        change_type: str,
        success: bool = True,
        error_message: Optional[str] = None,
        duration_seconds: Optional[float] = None
    ):
        """Log component reload."""
        
        await self.log_event(
            AuditEventType.COMPONENT_RELOADED,
            component_name=component_name,
            component_type=component_type,
            details={"change_type": change_type},
            success=success,
            error_message=error_message,
            duration_seconds=duration_seconds
        )
    
    async def log_skill_auto_generated(
        self,
        skill_name: str,
        user_request: str,
        skill_type: str,
        file_path: str,
        success: bool = True,
        error_message: Optional[str] = None,
        duration_seconds: Optional[float] = None,
        llm_model: Optional[str] = None
    ):
        """Log automatic skill generation."""
        
        await self.log_event(
            AuditEventType.SKILL_AUTO_GENERATED,
            component_name=skill_name,
            component_type="skills",
            user_request=user_request,
            details={
                "skill_type": skill_type,
                "file_path": file_path,
                "llm_model": llm_model
            },
            success=success,
            error_message=error_message,
            duration_seconds=duration_seconds,
            metadata={"generation_method": "llm_auto"}
        )
    
    async def log_error(
        self,
        error_message: str,
        component_name: Optional[str] = None,
        component_type: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        """Log an error event."""
        
        await self.log_event(
            AuditEventType.ERROR_OCCURRED,
            component_name=component_name,
            component_type=component_type,
            details=details or {},
            success=False,
            error_message=error_message
        )
    
    async def log_system_startup(self, startup_details: Dict[str, Any]):
        """Log system startup."""
        
        await self.log_event(
            AuditEventType.SYSTEM_STARTUP,
            details=startup_details,
            metadata={"system_version": "1.0.0"}
        )
    
    async def log_system_shutdown(self, shutdown_details: Dict[str, Any]):
        """Log system shutdown."""
        
        await self.log_event(
            AuditEventType.SYSTEM_SHUTDOWN,
            details=shutdown_details
        )
    
    def get_events(
        self,
        event_type: Optional[AuditEventType] = None,
        component_name: Optional[str] = None,
        component_type: Optional[str] = None,
        since: Optional[datetime] = None,
        limit: int = 100
    ) -> List[AuditEvent]:
        """
        Get audit events with optional filtering.
        
        Args:
            event_type: Filter by event type
            component_name: Filter by component name
            component_type: Filter by component type
            since: Filter events since this timestamp
            limit: Maximum number of events to return
            
        Returns:
            List of matching audit events
        """
        
        events = self.events
        
        # Apply filters
        if event_type:
            events = [e for e in events if e.event_type == event_type]
        
        if component_name:
            events = [e for e in events if e.component_name == component_name]
        
        if component_type:
            events = [e for e in events if e.component_type == component_type]
        
        if since:
            events = [e for e in events if e.timestamp >= since]
        
        # Sort by timestamp (newest first) and limit
        events = sorted(events, key=lambda x: x.timestamp, reverse=True)
        
        return events[:limit]
    
    def get_audit_stats(self) -> Dict[str, Any]:
        """Get audit statistics."""
        
        # Calculate additional stats
        recent_events = self.get_events(since=datetime.now() - timedelta(hours=24))
        error_events = [e for e in self.events if not e.success]
        
        return {
            **self.stats,
            "events_last_24h": len(recent_events),
            "error_rate": (
                len(error_events) / len(self.events) 
                if self.events else 0
            ),
            "recent_errors": [
                {
                    "timestamp": e.timestamp.isoformat(),
                    "component": e.component_name,
                    "error": e.error_message
                }
                for e in error_events[-5:]  # Last 5 errors
            ]
        }
    
    async def export_audit_log(
        self, 
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        format: str = "json"
    ) -> str:
        """
        Export audit log to file.
        
        Args:
            start_date: Start date for export
            end_date: End date for export
            format: Export format ('json' or 'csv')
            
        Returns:
            Path to exported file
        """
        
        # Filter events by date range
        events = self.events
        
        if start_date:
            events = [e for e in events if e.timestamp >= start_date]
        
        if end_date:
            events = [e for e in events if e.timestamp <= end_date]
        
        # Generate export filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        export_file = self.log_dir / f"audit_export_{timestamp}.{format}"
        
        try:
            if format == "json":
                # Export as JSON
                export_data = [asdict(event) for event in events]
                
                # Convert datetime and enum to strings
                for event_data in export_data:
                    event_data['timestamp'] = event_data['timestamp'].isoformat()
                    event_data['event_type'] = event_data['event_type'].value
                
                with open(export_file, 'w') as f:
                    json.dump(export_data, f, indent=2, default=str)
            
            elif format == "csv":
                # Export as CSV
                import csv
                
                with open(export_file, 'w', newline='') as f:
                    if events:
                        writer = csv.DictWriter(f, fieldnames=asdict(events[0]).keys())
                        writer.writeheader()
                        
                        for event in events:
                            event_dict = asdict(event)
                            event_dict['timestamp'] = event.timestamp.isoformat()
                            event_dict['event_type'] = event.event_type.value
                            writer.writerow(event_dict)
            
            logger.info(f"Exported {len(events)} audit events to {export_file}")
            return str(export_file)
            
        except Exception as e:
            logger.error(f"Failed to export audit log: {e}")
            raise
    
    async def cleanup_old_logs(self, days_to_keep: int = 30):
        """Clean up old audit log files."""
        
        cutoff_date = datetime.now() - timedelta(days=days_to_keep)
        
        cleaned_files = 0
        
        for log_file in self.log_dir.glob("audit_*.jsonl"):
            try:
                # Extract date from filename
                date_str = log_file.stem.split('_')[1]
                file_date = datetime.strptime(date_str, "%Y%m%d")
                
                if file_date < cutoff_date:
                    log_file.unlink()
                    cleaned_files += 1
                    logger.info(f"Cleaned up old audit log: {log_file}")
                    
            except Exception as e:
                logger.error(f"Error cleaning up log file {log_file}: {e}")
        
        return cleaned_files


# Global audit logger instance
audit_logger = AuditLogger()


# Convenience functions
async def log_component_discovered(component_name: str, component_type: str, file_path: str):
    """Log component discovery."""
    await audit_logger.log_component_discovered(component_name, component_type, file_path)


async def log_skill_auto_generated(
    skill_name: str, 
    user_request: str, 
    success: bool = True,
    error_message: Optional[str] = None
):
    """Log automatic skill generation."""
    await audit_logger.log_skill_auto_generated(
        skill_name, user_request, "auto", "", success, error_message
    )


async def log_error(error_message: str, component_name: Optional[str] = None):
    """Log an error."""
    await audit_logger.log_error(error_message, component_name)