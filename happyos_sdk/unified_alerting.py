"""
Unified Alerting System for HappyOS SDK

Provides standardized alerting with consistent thresholds and notification
patterns across all HappyOS agent systems.
"""

import asyncio
import json
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum

from .logging import get_logger
from .metrics_collection import StandardizedMetrics

# Try to import backend observability for integration
try:
    from backend.modules.observability.audit_logger import get_audit_logger, AuditEventType, AuditSeverity
    AUDIT_LOGGING_AVAILABLE = True
except ImportError:
    AUDIT_LOGGING_AVAILABLE = False

logger = get_logger(__name__)


class AlertSeverity(Enum):
    """Alert severity levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class AlertStatus(Enum):
    """Alert status."""
    ACTIVE = "active"
    RESOLVED = "resolved"
    ACKNOWLEDGED = "acknowledged"
    SUPPRESSED = "suppressed"


@dataclass
class AlertCondition:
    """Defines when an alert should trigger."""
    
    metric_name: str
    threshold: float
    operator: str  # "gt", "lt", "eq", "gte", "lte"
    evaluation_window_seconds: int = 300
    evaluation_periods: int = 2
    dimensions: Dict[str, str] = field(default_factory=dict)
    
    def evaluate(self, metric_value: float) -> bool:
        """Evaluate if the condition is met."""
        operators = {
            "gt": lambda x, y: x > y,
            "lt": lambda x, y: x < y,
            "eq": lambda x, y: x == y,
            "gte": lambda x, y: x >= y,
            "lte": lambda x, y: x <= y
        }
        
        op_func = operators.get(self.operator)
        if not op_func:
            raise ValueError(f"Unknown operator: {self.operator}")
        
        return op_func(metric_value, self.threshold)


@dataclass
class AlertRule:
    """Defines an alert rule with conditions and actions."""
    
    rule_id: str
    name: str
    description: str
    severity: AlertSeverity
    condition: AlertCondition
    agent_types: List[str] = field(default_factory=list)  # Empty = all agents
    enabled: bool = True
    
    # Notification settings
    notification_channels: List[str] = field(default_factory=list)
    escalation_delay_seconds: int = 3600  # 1 hour
    auto_resolve: bool = True
    
    # Suppression settings
    suppression_window_seconds: int = 300  # 5 minutes
    max_alerts_per_window: int = 5
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "rule_id": self.rule_id,
            "name": self.name,
            "description": self.description,
            "severity": self.severity.value,
            "condition": {
                "metric_name": self.condition.metric_name,
                "threshold": self.condition.threshold,
                "operator": self.condition.operator,
                "evaluation_window_seconds": self.condition.evaluation_window_seconds,
                "evaluation_periods": self.condition.evaluation_periods,
                "dimensions": self.condition.dimensions
            },
            "agent_types": self.agent_types,
            "enabled": self.enabled,
            "notification_channels": self.notification_channels,
            "escalation_delay_seconds": self.escalation_delay_seconds,
            "auto_resolve": self.auto_resolve,
            "suppression_window_seconds": self.suppression_window_seconds,
            "max_alerts_per_window": self.max_alerts_per_window
        }


@dataclass
class Alert:
    """Represents an active alert instance."""
    
    alert_id: str
    rule_id: str
    rule_name: str
    severity: AlertSeverity
    status: AlertStatus
    message: str
    
    # Context
    agent_type: str
    agent_id: str
    tenant_id: Optional[str] = None
    
    # Timing
    triggered_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    acknowledged_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None
    
    # Metric context
    metric_name: str = ""
    metric_value: float = 0.0
    threshold: float = 0.0
    
    # Additional context
    details: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "alert_id": self.alert_id,
            "rule_id": self.rule_id,
            "rule_name": self.rule_name,
            "severity": self.severity.value,
            "status": self.status.value,
            "message": self.message,
            "agent_type": self.agent_type,
            "agent_id": self.agent_id,
            "tenant_id": self.tenant_id,
            "triggered_at": self.triggered_at.isoformat(),
            "acknowledged_at": self.acknowledged_at.isoformat() if self.acknowledged_at else None,
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
            "metric_name": self.metric_name,
            "metric_value": self.metric_value,
            "threshold": self.threshold,
            "details": self.details
        }


class UnifiedAlertingSystem:
    """Unified alerting system for HappyOS agents."""
    
    def __init__(self):
        """Initialize the alerting system."""
        self.alert_rules: Dict[str, AlertRule] = {}
        self.active_alerts: Dict[str, Alert] = {}
        self.alert_history: List[Alert] = []
        
        # Notification handlers
        self.notification_handlers: Dict[str, Callable] = {}
        
        # Alert suppression tracking
        self.alert_counts: Dict[str, List[datetime]] = {}
        
        # Integration with backend audit logging
        self.audit_logger = None
        if AUDIT_LOGGING_AVAILABLE:
            try:
                self.audit_logger = get_audit_logger()
                logger.info("Audit logging integration enabled for alerts")
            except Exception as e:
                logger.warning(f"Audit logging not available: {e}")
        
        # Load standard alert rules
        self._load_standard_alert_rules()
        
        logger.info("Unified alerting system initialized")
    
    def _load_standard_alert_rules(self):
        """Load standard alert rules for HappyOS agents."""
        
        # SLA Breach Alerts (Critical)
        self.add_alert_rule(AlertRule(
            rule_id="sla_response_time_breach",
            name="SLA Response Time Breach",
            description="Agent response time exceeds 5-second SLA target",
            severity=AlertSeverity.CRITICAL,
            condition=AlertCondition(
                metric_name="AgentResponseTime",
                threshold=5000.0,  # 5 seconds in milliseconds
                operator="gt",
                evaluation_periods=2
            ),
            notification_channels=["email", "slack", "pagerduty"],
            escalation_delay_seconds=300  # 5 minutes for critical
        ))
        
        self.add_alert_rule(AlertRule(
            rule_id="sla_uptime_breach",
            name="SLA Uptime Breach",
            description="Agent health status indicates downtime (SLA breach)",
            severity=AlertSeverity.CRITICAL,
            condition=AlertCondition(
                metric_name="HealthStatus",
                threshold=0.5,  # Less than degraded (unhealthy = 0)
                operator="lt",
                evaluation_periods=1
            ),
            notification_channels=["email", "slack", "pagerduty"],
            escalation_delay_seconds=300
        ))
        
        # Error Rate Alerts (High)
        self.add_alert_rule(AlertRule(
            rule_id="high_error_rate",
            name="High Error Rate",
            description="MCP call error rate exceeds acceptable threshold",
            severity=AlertSeverity.HIGH,
            condition=AlertCondition(
                metric_name="MCPCallError",
                threshold=10.0,  # More than 10 errors per 5 minutes
                operator="gt",
                evaluation_periods=2
            ),
            notification_channels=["email", "slack"],
            escalation_delay_seconds=1800  # 30 minutes
        ))
        
        # Circuit Breaker Alerts (High)
        self.add_alert_rule(AlertRule(
            rule_id="circuit_breaker_open",
            name="Circuit Breaker Open",
            description="Service circuit breaker has opened due to failures",
            severity=AlertSeverity.HIGH,
            condition=AlertCondition(
                metric_name="CircuitBreakerState",
                threshold=0.5,  # Greater than closed (open = 1)
                operator="gt",
                evaluation_periods=1
            ),
            notification_channels=["email", "slack"],
            escalation_delay_seconds=900  # 15 minutes
        ))
        
        # Isolation Violation Alerts (Critical)
        self.add_alert_rule(AlertRule(
            rule_id="isolation_violation",
            name="Agent Isolation Violation",
            description="Backend.* import detected in agent (architectural violation)",
            severity=AlertSeverity.CRITICAL,
            condition=AlertCondition(
                metric_name="IsolationViolations",
                threshold=0.0,  # Any violation is critical
                operator="gt",
                evaluation_periods=1
            ),
            notification_channels=["email", "slack", "pagerduty"],
            escalation_delay_seconds=0,  # Immediate escalation
            auto_resolve=False  # Manual resolution required
        ))
        
        # Performance Degradation Alerts (Medium)
        self.add_alert_rule(AlertRule(
            rule_id="performance_degradation",
            name="Performance Degradation",
            description="Agent response time showing degradation trend",
            severity=AlertSeverity.MEDIUM,
            condition=AlertCondition(
                metric_name="AgentResponseTime",
                threshold=2000.0,  # 2 seconds
                operator="gt",
                evaluation_periods=3
            ),
            notification_channels=["email"],
            escalation_delay_seconds=3600  # 1 hour
        ))
        
        # Cross-Agent Workflow Alerts (Medium)
        self.add_alert_rule(AlertRule(
            rule_id="workflow_failure_rate",
            name="High Workflow Failure Rate",
            description="Cross-agent workflow failure rate is elevated",
            severity=AlertSeverity.MEDIUM,
            condition=AlertCondition(
                metric_name="WorkflowSteps",
                threshold=5.0,  # More than 5 failed steps per 5 minutes
                operator="gt",
                evaluation_periods=2,
                dimensions={"Status": "error"}
            ),
            notification_channels=["email", "slack"],
            escalation_delay_seconds=1800
        ))
        
        # Fan-in Logic Alerts (Medium - MeetMind specific)
        self.add_alert_rule(AlertRule(
            rule_id="fan_in_failure",
            name="Fan-in Logic Failure",
            description="MeetMind fan-in result collection failures",
            severity=AlertSeverity.MEDIUM,
            condition=AlertCondition(
                metric_name="FanInResults",
                threshold=3.0,  # More than 3 failures per 5 minutes
                operator="gt",
                evaluation_periods=2,
                dimensions={"Status": "error"}
            ),
            agent_types=["meetmind"],
            notification_channels=["email"],
            escalation_delay_seconds=1800
        ))
        
        # Resource Usage Alerts (Low)
        self.add_alert_rule(AlertRule(
            rule_id="high_memory_usage",
            name="High Memory Usage",
            description="Agent memory usage is elevated",
            severity=AlertSeverity.LOW,
            condition=AlertCondition(
                metric_name="AgentMemoryUsage",
                threshold=1024.0,  # 1GB
                operator="gt",
                evaluation_periods=3
            ),
            notification_channels=["email"],
            escalation_delay_seconds=7200  # 2 hours
        ))
        
        logger.info(f"Loaded {len(self.alert_rules)} standard alert rules")
    
    def add_alert_rule(self, rule: AlertRule):
        """Add an alert rule to the system."""
        self.alert_rules[rule.rule_id] = rule
        logger.debug(f"Added alert rule: {rule.name}")
    
    def remove_alert_rule(self, rule_id: str) -> bool:
        """Remove an alert rule from the system."""
        if rule_id in self.alert_rules:
            del self.alert_rules[rule_id]
            logger.debug(f"Removed alert rule: {rule_id}")
            return True
        return False
    
    def register_notification_handler(self, channel: str, handler: Callable):
        """Register a notification handler for a channel."""
        self.notification_handlers[channel] = handler
        logger.debug(f"Registered notification handler for channel: {channel}")
    
    async def evaluate_metric(self, metric_name: str, value: float, 
                            dimensions: Dict[str, str] = None,
                            agent_type: str = None, agent_id: str = None,
                            tenant_id: str = None):
        """Evaluate a metric value against all applicable alert rules."""
        dimensions = dimensions or {}
        
        for rule in self.alert_rules.values():
            if not rule.enabled:
                continue
            
            # Check if rule applies to this agent type
            if rule.agent_types and agent_type not in rule.agent_types:
                continue
            
            # Check if metric matches
            if rule.condition.metric_name != metric_name:
                continue
            
            # Check if dimensions match
            if not self._dimensions_match(rule.condition.dimensions, dimensions):
                continue
            
            # Evaluate condition
            try:
                if rule.condition.evaluate(value):
                    await self._trigger_alert(
                        rule, value, agent_type, agent_id, tenant_id, dimensions
                    )
                else:
                    # Check for auto-resolution
                    if rule.auto_resolve:
                        await self._resolve_alerts_for_rule(rule.rule_id, agent_type, agent_id)
                        
            except Exception as e:
                logger.error(f"Error evaluating alert rule {rule.rule_id}: {e}")
    
    def _dimensions_match(self, rule_dimensions: Dict[str, str], 
                         metric_dimensions: Dict[str, str]) -> bool:
        """Check if metric dimensions match rule dimensions."""
        for key, value in rule_dimensions.items():
            if metric_dimensions.get(key) != value:
                return False
        return True
    
    async def _trigger_alert(self, rule: AlertRule, metric_value: float,
                           agent_type: str = None, agent_id: str = None,
                           tenant_id: str = None, dimensions: Dict[str, str] = None):
        """Trigger an alert for a rule."""
        
        # Check for suppression
        if self._is_suppressed(rule.rule_id, agent_type):
            logger.debug(f"Alert suppressed for rule {rule.rule_id}")
            return
        
        # Create alert ID
        alert_id = f"{rule.rule_id}_{agent_type}_{agent_id}_{int(datetime.now().timestamp())}"
        
        # Check if similar alert is already active
        existing_alert = self._find_active_alert(rule.rule_id, agent_type, agent_id)
        if existing_alert:
            logger.debug(f"Alert already active for rule {rule.rule_id}")
            return
        
        # Create alert
        alert = Alert(
            alert_id=alert_id,
            rule_id=rule.rule_id,
            rule_name=rule.name,
            severity=rule.severity,
            status=AlertStatus.ACTIVE,
            message=self._generate_alert_message(rule, metric_value, agent_type),
            agent_type=agent_type or "unknown",
            agent_id=agent_id or "unknown",
            tenant_id=tenant_id,
            metric_name=rule.condition.metric_name,
            metric_value=metric_value,
            threshold=rule.condition.threshold,
            details={
                "dimensions": dimensions or {},
                "operator": rule.condition.operator,
                "evaluation_periods": rule.condition.evaluation_periods
            }
        )
        
        # Store alert
        self.active_alerts[alert_id] = alert
        self.alert_history.append(alert)
        
        # Update suppression tracking
        self._update_suppression_tracking(rule.rule_id, agent_type)
        
        # Send notifications
        await self._send_notifications(alert, rule)
        
        # Log to audit system
        await self._audit_alert(alert, "triggered")
        
        logger.warning(
            f"Alert triggered: {rule.name}",
            extra={
                "alert_id": alert_id,
                "rule_id": rule.rule_id,
                "severity": rule.severity.value,
                "agent_type": agent_type,
                "agent_id": agent_id,
                "metric_value": metric_value,
                "threshold": rule.condition.threshold
            }
        )
    
    def _generate_alert_message(self, rule: AlertRule, metric_value: float, 
                              agent_type: str = None) -> str:
        """Generate a human-readable alert message."""
        agent_info = f" for {agent_type}" if agent_type else ""
        
        return (
            f"{rule.description}{agent_info}. "
            f"Current value: {metric_value}, "
            f"Threshold: {rule.condition.threshold} "
            f"({rule.condition.operator})"
        )
    
    def _is_suppressed(self, rule_id: str, agent_type: str = None) -> bool:
        """Check if alerts for this rule should be suppressed."""
        suppression_key = f"{rule_id}_{agent_type}"
        
        if suppression_key not in self.alert_counts:
            return False
        
        rule = self.alert_rules.get(rule_id)
        if not rule:
            return False
        
        # Clean old entries
        cutoff_time = datetime.now(timezone.utc).timestamp() - rule.suppression_window_seconds
        self.alert_counts[suppression_key] = [
            alert_time for alert_time in self.alert_counts[suppression_key]
            if alert_time.timestamp() > cutoff_time
        ]
        
        # Check if we've exceeded the limit
        return len(self.alert_counts[suppression_key]) >= rule.max_alerts_per_window
    
    def _update_suppression_tracking(self, rule_id: str, agent_type: str = None):
        """Update suppression tracking for a rule."""
        suppression_key = f"{rule_id}_{agent_type}"
        
        if suppression_key not in self.alert_counts:
            self.alert_counts[suppression_key] = []
        
        self.alert_counts[suppression_key].append(datetime.now(timezone.utc))
    
    def _find_active_alert(self, rule_id: str, agent_type: str = None, 
                          agent_id: str = None) -> Optional[Alert]:
        """Find an active alert for the given criteria."""
        for alert in self.active_alerts.values():
            if (alert.rule_id == rule_id and 
                alert.status == AlertStatus.ACTIVE and
                (not agent_type or alert.agent_type == agent_type) and
                (not agent_id or alert.agent_id == agent_id)):
                return alert
        return None
    
    async def _resolve_alerts_for_rule(self, rule_id: str, agent_type: str = None,
                                     agent_id: str = None):
        """Resolve active alerts for a rule when conditions are no longer met."""
        alerts_to_resolve = []
        
        for alert_id, alert in self.active_alerts.items():
            if (alert.rule_id == rule_id and 
                alert.status == AlertStatus.ACTIVE and
                (not agent_type or alert.agent_type == agent_type) and
                (not agent_id or alert.agent_id == agent_id)):
                alerts_to_resolve.append(alert_id)
        
        for alert_id in alerts_to_resolve:
            await self.resolve_alert(alert_id, "Auto-resolved: condition no longer met")
    
    async def _send_notifications(self, alert: Alert, rule: AlertRule):
        """Send notifications for an alert."""
        for channel in rule.notification_channels:
            handler = self.notification_handlers.get(channel)
            if handler:
                try:
                    await handler(alert, rule)
                except Exception as e:
                    logger.error(f"Failed to send notification via {channel}: {e}")
            else:
                logger.warning(f"No handler registered for notification channel: {channel}")
    
    async def _audit_alert(self, alert: Alert, action: str):
        """Log alert to audit system."""
        if not self.audit_logger:
            return
        
        try:
            await self.audit_logger.log_security_event(
                event_type=AuditEventType.SYSTEM_WARNING if alert.severity in [AlertSeverity.LOW, AlertSeverity.MEDIUM] else AuditEventType.SYSTEM_ERROR,
                message=f"Alert {action}: {alert.rule_name}",
                severity=AuditSeverity.CRITICAL if alert.severity == AlertSeverity.CRITICAL else AuditSeverity.HIGH,
                tenant_id=alert.tenant_id,
                correlation_id=alert.alert_id,
                details={
                    "alert_id": alert.alert_id,
                    "rule_id": alert.rule_id,
                    "agent_type": alert.agent_type,
                    "agent_id": alert.agent_id,
                    "metric_name": alert.metric_name,
                    "metric_value": alert.metric_value,
                    "threshold": alert.threshold,
                    "action": action
                }
            )
        except Exception as e:
            logger.error(f"Failed to audit alert: {e}")
    
    async def acknowledge_alert(self, alert_id: str, acknowledged_by: str = None) -> bool:
        """Acknowledge an active alert."""
        if alert_id not in self.active_alerts:
            return False
        
        alert = self.active_alerts[alert_id]
        if alert.status != AlertStatus.ACTIVE:
            return False
        
        alert.status = AlertStatus.ACKNOWLEDGED
        alert.acknowledged_at = datetime.now(timezone.utc)
        
        await self._audit_alert(alert, f"acknowledged by {acknowledged_by or 'system'}")
        
        logger.info(f"Alert acknowledged: {alert_id}")
        return True
    
    async def resolve_alert(self, alert_id: str, resolution_note: str = None) -> bool:
        """Resolve an active alert."""
        if alert_id not in self.active_alerts:
            return False
        
        alert = self.active_alerts[alert_id]
        alert.status = AlertStatus.RESOLVED
        alert.resolved_at = datetime.now(timezone.utc)
        
        if resolution_note:
            alert.details["resolution_note"] = resolution_note
        
        # Remove from active alerts
        del self.active_alerts[alert_id]
        
        await self._audit_alert(alert, "resolved")
        
        logger.info(f"Alert resolved: {alert_id}")
        return True
    
    def get_active_alerts(self, agent_type: str = None, 
                         severity: AlertSeverity = None) -> List[Alert]:
        """Get active alerts with optional filtering."""
        alerts = list(self.active_alerts.values())
        
        if agent_type:
            alerts = [a for a in alerts if a.agent_type == agent_type]
        
        if severity:
            alerts = [a for a in alerts if a.severity == severity]
        
        return sorted(alerts, key=lambda a: a.triggered_at, reverse=True)
    
    def get_alert_summary(self) -> Dict[str, Any]:
        """Get summary of alert system status."""
        active_alerts = list(self.active_alerts.values())
        
        return {
            "total_rules": len(self.alert_rules),
            "enabled_rules": len([r for r in self.alert_rules.values() if r.enabled]),
            "active_alerts": len(active_alerts),
            "alerts_by_severity": {
                severity.value: len([a for a in active_alerts if a.severity == severity])
                for severity in AlertSeverity
            },
            "alerts_by_agent": {
                agent_type: len([a for a in active_alerts if a.agent_type == agent_type])
                for agent_type in ["agent_svea", "felicias_finance", "meetmind"]
            },
            "notification_channels": list(self.notification_handlers.keys()),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }


# Global alerting system instance
_alerting_system: Optional[UnifiedAlertingSystem] = None


def get_alerting_system() -> UnifiedAlertingSystem:
    """Get or create unified alerting system."""
    global _alerting_system
    if _alerting_system is None:
        _alerting_system = UnifiedAlertingSystem()
    return _alerting_system


# Notification handler examples
async def email_notification_handler(alert: Alert, rule: AlertRule):
    """Example email notification handler."""
    logger.info(f"EMAIL ALERT: {alert.message}")
    # Would integrate with actual email service


async def slack_notification_handler(alert: Alert, rule: AlertRule):
    """Example Slack notification handler."""
    logger.info(f"SLACK ALERT: {alert.message}")
    # Would integrate with Slack API


async def pagerduty_notification_handler(alert: Alert, rule: AlertRule):
    """Example PagerDuty notification handler."""
    logger.info(f"PAGERDUTY ALERT: {alert.message}")
    # Would integrate with PagerDuty API