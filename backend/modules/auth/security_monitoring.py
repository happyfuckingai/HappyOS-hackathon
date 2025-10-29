"""
Security Monitoring and Alerting Service

Implements comprehensive security monitoring with:
- Real-time threat detection
- Rate limiting per tenant and agent
- Suspicious activity detection
- Alert generation and notification
- Security metrics collection

Requirements: 6.5
"""

import asyncio
import logging
from collections import defaultdict, deque
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Set, Tuple, Any
from uuid import uuid4
from enum import Enum

from pydantic import BaseModel, Field

from .jwt_service import JWTClaims
from ..config.settings import settings

logger = logging.getLogger(__name__)


class AlertSeverity(Enum):
    """Alert severity levels"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ThreatType(Enum):
    """Types of security threats"""
    CROSS_TENANT_ACCESS = "cross_tenant_access"
    RATE_LIMIT_EXCEEDED = "rate_limit_exceeded"
    SUSPICIOUS_ACTIVITY = "suspicious_activity"
    INVALID_TOKEN = "invalid_token"
    BRUTE_FORCE = "brute_force"
    ANOMALOUS_BEHAVIOR = "anomalous_behavior"
    PRIVILEGE_ESCALATION = "privilege_escalation"


class SecurityEvent(BaseModel):
    """Security event record"""
    event_id: str = Field(default_factory=lambda: str(uuid4()))
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    threat_type: ThreatType
    severity: AlertSeverity
    user_id: str
    tenant_id: Optional[str] = None
    session_id: Optional[str] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    details: Dict[str, Any] = Field(default_factory=dict)
    resolved: bool = False
    resolution_notes: Optional[str] = None


class RateLimitRule(BaseModel):
    """Rate limiting rule configuration"""
    name: str
    requests_per_minute: int
    window_minutes: int = 1
    tenant_specific: bool = False
    agent_specific: bool = False
    endpoints: List[str] = Field(default_factory=list)


class SecurityAlert(BaseModel):
    """Security alert"""
    alert_id: str = Field(default_factory=lambda: str(uuid4()))
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    severity: AlertSeverity
    title: str
    description: str
    events: List[str] = Field(default_factory=list)  # Event IDs
    tenant_id: Optional[str] = None
    user_id: Optional[str] = None
    acknowledged: bool = False
    resolved: bool = False
    resolution_time: Optional[str] = None


class SecurityMetrics(BaseModel):
    """Security metrics snapshot"""
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    total_events: int = 0
    events_by_severity: Dict[str, int] = Field(default_factory=dict)
    events_by_type: Dict[str, int] = Field(default_factory=dict)
    active_alerts: int = 0
    blocked_users: int = 0
    rate_limit_violations: int = 0
    cross_tenant_attempts: int = 0


class RateLimiter:
    """Rate limiter with tenant and agent isolation"""
    
    def __init__(self):
        # Request counters: key -> deque of timestamps
        self._request_counters: Dict[str, deque] = defaultdict(deque)
        self._blocked_keys: Set[str] = set()
        self._block_expiry: Dict[str, datetime] = {}
    
    def _get_rate_limit_key(
        self,
        user_id: str,
        tenant_id: Optional[str] = None,
        agent_id: Optional[str] = None,
        endpoint: Optional[str] = None
    ) -> str:
        """Generate rate limit key"""
        parts = [user_id]
        if tenant_id:
            parts.append(f"tenant:{tenant_id}")
        if agent_id:
            parts.append(f"agent:{agent_id}")
        if endpoint:
            parts.append(f"endpoint:{endpoint}")
        return ":".join(parts)
    
    def _cleanup_expired_blocks(self):
        """Clean up expired blocks"""
        now = datetime.now(timezone.utc)
        expired_keys = [
            key for key, expiry in self._block_expiry.items()
            if now > expiry
        ]
        for key in expired_keys:
            self._blocked_keys.discard(key)
            del self._block_expiry[key]
    
    def check_rate_limit(
        self,
        user_id: str,
        tenant_id: Optional[str] = None,
        agent_id: Optional[str] = None,
        endpoint: Optional[str] = None,
        requests_per_minute: int = 60,
        window_minutes: int = 1
    ) -> Tuple[bool, Optional[str]]:
        """
        Check if request is within rate limits
        
        Args:
            user_id: User identifier
            tenant_id: Tenant identifier
            agent_id: Agent identifier
            endpoint: Endpoint path
            requests_per_minute: Rate limit
            window_minutes: Time window
            
        Returns:
            Tuple of (allowed, reason)
        """
        self._cleanup_expired_blocks()
        
        key = self._get_rate_limit_key(user_id, tenant_id, agent_id, endpoint)
        
        # Check if blocked
        if key in self._blocked_keys:
            return False, "Rate limit exceeded - temporarily blocked"
        
        now = datetime.now(timezone.utc)
        window_start = now - timedelta(minutes=window_minutes)
        
        # Clean old requests
        counter = self._request_counters[key]
        while counter and datetime.fromisoformat(counter[0]) < window_start:
            counter.popleft()
        
        # Check rate limit
        if len(counter) >= requests_per_minute:
            # Block for 5 minutes
            self._blocked_keys.add(key)
            self._block_expiry[key] = now + timedelta(minutes=5)
            return False, f"Rate limit exceeded: {requests_per_minute} requests per {window_minutes} minute(s)"
        
        # Record request
        counter.append(now.isoformat())
        return True, None
    
    def get_request_count(
        self,
        user_id: str,
        tenant_id: Optional[str] = None,
        agent_id: Optional[str] = None,
        endpoint: Optional[str] = None,
        window_minutes: int = 1
    ) -> int:
        """Get current request count for a key"""
        key = self._get_rate_limit_key(user_id, tenant_id, agent_id, endpoint)
        
        now = datetime.now(timezone.utc)
        window_start = now - timedelta(minutes=window_minutes)
        
        counter = self._request_counters[key]
        return sum(1 for ts in counter if datetime.fromisoformat(ts) >= window_start)


class SuspiciousActivityDetector:
    """Detects suspicious activity patterns"""
    
    def __init__(self):
        self._user_activity: Dict[str, List[Dict]] = defaultdict(list)
        self._tenant_activity: Dict[str, List[Dict]] = defaultdict(list)
    
    def record_activity(
        self,
        user_id: str,
        tenant_id: Optional[str],
        activity_type: str,
        details: Dict[str, Any]
    ):
        """Record user activity for analysis"""
        activity = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "type": activity_type,
            "tenant_id": tenant_id,
            "details": details
        }
        
        # Record user activity
        self._user_activity[user_id].append(activity)
        
        # Keep only recent activity (last 1000 entries)
        if len(self._user_activity[user_id]) > 1000:
            self._user_activity[user_id] = self._user_activity[user_id][-1000:]
        
        # Record tenant activity
        if tenant_id:
            self._tenant_activity[tenant_id].append(activity)
            if len(self._tenant_activity[tenant_id]) > 1000:
                self._tenant_activity[tenant_id] = self._tenant_activity[tenant_id][-1000:]
    
    def detect_suspicious_patterns(
        self,
        user_id: str,
        window_minutes: int = 10
    ) -> List[Dict[str, Any]]:
        """Detect suspicious activity patterns for a user"""
        suspicious_patterns = []
        
        if user_id not in self._user_activity:
            return suspicious_patterns
        
        activities = self._user_activity[user_id]
        now = datetime.now(timezone.utc)
        window_start = now - timedelta(minutes=window_minutes)
        
        # Filter to recent activities
        recent_activities = [
            a for a in activities
            if datetime.fromisoformat(a["timestamp"]) >= window_start
        ]
        
        if not recent_activities:
            return suspicious_patterns
        
        # Pattern 1: Multiple tenant access attempts
        tenant_attempts = set()
        for activity in recent_activities:
            if activity["type"] == "tenant_access" and activity.get("tenant_id"):
                tenant_attempts.add(activity["tenant_id"])
        
        if len(tenant_attempts) > 3:
            suspicious_patterns.append({
                "pattern": "multiple_tenant_access",
                "severity": "high",
                "description": f"User accessed {len(tenant_attempts)} different tenants in {window_minutes} minutes",
                "tenant_count": len(tenant_attempts),
                "tenants": list(tenant_attempts)
            })
        
        # Pattern 2: High error rate
        error_count = sum(1 for a in recent_activities if a.get("details", {}).get("error"))
        if error_count > 10:
            suspicious_patterns.append({
                "pattern": "high_error_rate",
                "severity": "medium",
                "description": f"User generated {error_count} errors in {window_minutes} minutes",
                "error_count": error_count
            })
        
        # Pattern 3: Rapid resource creation
        create_count = sum(1 for a in recent_activities if a["type"] == "resource_create")
        if create_count > 50:
            suspicious_patterns.append({
                "pattern": "rapid_resource_creation",
                "severity": "medium",
                "description": f"User created {create_count} resources in {window_minutes} minutes",
                "create_count": create_count
            })
        
        return suspicious_patterns


class SecurityMonitoringService:
    """Main security monitoring service"""
    
    def __init__(self):
        self._events: List[SecurityEvent] = []
        self._alerts: List[SecurityAlert] = []
        self._rate_limiter = RateLimiter()
        self._activity_detector = SuspiciousActivityDetector()
        self._blocked_users: Set[str] = set()
        self._monitoring_enabled = True
        
        # Default rate limit rules
        self._rate_limit_rules = [
            RateLimitRule(
                name="global_api",
                requests_per_minute=100,
                window_minutes=1
            ),
            RateLimitRule(
                name="tenant_api",
                requests_per_minute=60,
                window_minutes=1,
                tenant_specific=True
            ),
            RateLimitRule(
                name="agent_api",
                requests_per_minute=120,
                window_minutes=1,
                agent_specific=True
            ),
            RateLimitRule(
                name="auth_endpoints",
                requests_per_minute=10,
                window_minutes=1,
                endpoints=["/auth/", "/mcp-ui/agents/register"]
            )
        ]
    
    def record_security_event(
        self,
        threat_type: ThreatType,
        severity: AlertSeverity,
        user_id: str,
        tenant_id: Optional[str] = None,
        session_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ) -> SecurityEvent:
        """Record a security event"""
        if not self._monitoring_enabled:
            return None
        
        event = SecurityEvent(
            threat_type=threat_type,
            severity=severity,
            user_id=user_id,
            tenant_id=tenant_id,
            session_id=session_id,
            ip_address=ip_address,
            user_agent=user_agent,
            details=details or {}
        )
        
        self._events.append(event)
        
        # Keep only recent events (last 5000)
        if len(self._events) > 5000:
            self._events = self._events[-5000:]
        
        # Record activity for pattern detection
        self._activity_detector.record_activity(
            user_id, tenant_id, threat_type.value, details or {}
        )
        
        # Check if alert should be generated
        self._check_alert_conditions(event)
        
        logger.warning(
            f"Security event: {threat_type.value} (severity: {severity.value}) "
            f"user: {user_id}, tenant: {tenant_id}, ip: {ip_address}"
        )
        
        return event
    
    def check_rate_limit(
        self,
        claims: JWTClaims,
        endpoint: Optional[str] = None,
        ip_address: Optional[str] = None
    ) -> Tuple[bool, Optional[str]]:
        """Check rate limits for a request"""
        if not self._monitoring_enabled:
            return True, None
        
        user_id = claims.sub
        tenant_id = claims.tenantId
        agent_id = claims.agentId
        
        # Check applicable rate limit rules
        for rule in self._rate_limit_rules:
            # Check if rule applies to this request
            if rule.endpoints and endpoint:
                if not any(endpoint.startswith(ep) for ep in rule.endpoints):
                    continue
            
            # Determine rate limit parameters
            requests_per_minute = rule.requests_per_minute
            
            # Apply rule
            allowed, reason = self._rate_limiter.check_rate_limit(
                user_id=user_id,
                tenant_id=tenant_id if rule.tenant_specific else None,
                agent_id=agent_id if rule.agent_specific else None,
                endpoint=endpoint if rule.endpoints else None,
                requests_per_minute=requests_per_minute,
                window_minutes=rule.window_minutes
            )
            
            if not allowed:
                # Record rate limit violation
                self.record_security_event(
                    threat_type=ThreatType.RATE_LIMIT_EXCEEDED,
                    severity=AlertSeverity.MEDIUM,
                    user_id=user_id,
                    tenant_id=tenant_id,
                    ip_address=ip_address,
                    details={
                        "rule": rule.name,
                        "limit": requests_per_minute,
                        "window_minutes": rule.window_minutes,
                        "endpoint": endpoint
                    }
                )
                return False, reason
        
        return True, None
    
    def detect_suspicious_activity(
        self,
        user_id: str,
        tenant_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Detect suspicious activity for a user"""
        if not self._monitoring_enabled:
            return []
        
        patterns = self._activity_detector.detect_suspicious_patterns(user_id)
        
        # Generate security events for suspicious patterns
        for pattern in patterns:
            severity = AlertSeverity.HIGH if pattern["severity"] == "high" else AlertSeverity.MEDIUM
            
            self.record_security_event(
                threat_type=ThreatType.SUSPICIOUS_ACTIVITY,
                severity=severity,
                user_id=user_id,
                tenant_id=tenant_id,
                details=pattern
            )
        
        return patterns
    
    def block_user(self, user_id: str, reason: str, duration_minutes: int = 60) -> bool:
        """Block a user temporarily"""
        self._blocked_users.add(user_id)
        
        # Schedule unblock (in production, use proper task scheduler)
        asyncio.create_task(self._unblock_user_after_delay(user_id, duration_minutes))
        
        self.record_security_event(
            threat_type=ThreatType.BRUTE_FORCE,
            severity=AlertSeverity.HIGH,
            user_id=user_id,
            details={
                "action": "user_blocked",
                "reason": reason,
                "duration_minutes": duration_minutes
            }
        )
        
        logger.warning(f"Blocked user {user_id} for {duration_minutes} minutes: {reason}")
        return True
    
    async def _unblock_user_after_delay(self, user_id: str, delay_minutes: int):
        """Unblock user after delay"""
        await asyncio.sleep(delay_minutes * 60)
        self._blocked_users.discard(user_id)
        logger.info(f"Unblocked user {user_id} after {delay_minutes} minutes")
    
    def is_user_blocked(self, user_id: str) -> bool:
        """Check if user is blocked"""
        return user_id in self._blocked_users
    
    def _check_alert_conditions(self, event: SecurityEvent):
        """Check if an alert should be generated based on event"""
        # Generate alert for critical events
        if event.severity == AlertSeverity.CRITICAL:
            self._generate_alert(
                severity=AlertSeverity.CRITICAL,
                title=f"Critical Security Event: {event.threat_type.value}",
                description=f"Critical security event detected for user {event.user_id}",
                events=[event.event_id],
                tenant_id=event.tenant_id,
                user_id=event.user_id
            )
        
        # Generate alert for multiple high-severity events from same user
        recent_high_events = [
            e for e in self._events[-50:]  # Check last 50 events
            if (e.user_id == event.user_id and 
                e.severity in [AlertSeverity.HIGH, AlertSeverity.CRITICAL] and
                datetime.fromisoformat(e.timestamp) > 
                datetime.now(timezone.utc) - timedelta(minutes=10))
        ]
        
        if len(recent_high_events) >= 3:
            self._generate_alert(
                severity=AlertSeverity.HIGH,
                title=f"Multiple Security Events: {event.user_id}",
                description=f"User {event.user_id} triggered {len(recent_high_events)} high-severity events in 10 minutes",
                events=[e.event_id for e in recent_high_events],
                tenant_id=event.tenant_id,
                user_id=event.user_id
            )
    
    def _generate_alert(
        self,
        severity: AlertSeverity,
        title: str,
        description: str,
        events: List[str],
        tenant_id: Optional[str] = None,
        user_id: Optional[str] = None
    ) -> SecurityAlert:
        """Generate a security alert"""
        alert = SecurityAlert(
            severity=severity,
            title=title,
            description=description,
            events=events,
            tenant_id=tenant_id,
            user_id=user_id
        )
        
        self._alerts.append(alert)
        
        # Keep only recent alerts (last 1000)
        if len(self._alerts) > 1000:
            self._alerts = self._alerts[-1000:]
        
        logger.error(f"Security alert generated: {title} (severity: {severity.value})")
        
        # In production, send notifications here
        # self._send_alert_notification(alert)
        
        return alert
    
    def get_security_metrics(self) -> SecurityMetrics:
        """Get current security metrics"""
        # Count events by severity
        events_by_severity = defaultdict(int)
        for event in self._events:
            events_by_severity[event.severity.value] += 1
        
        # Count events by type
        events_by_type = defaultdict(int)
        for event in self._events:
            events_by_type[event.threat_type.value] += 1
        
        # Count active alerts
        active_alerts = sum(1 for alert in self._alerts if not alert.resolved)
        
        # Count specific threat types
        rate_limit_violations = events_by_type.get(ThreatType.RATE_LIMIT_EXCEEDED.value, 0)
        cross_tenant_attempts = events_by_type.get(ThreatType.CROSS_TENANT_ACCESS.value, 0)
        
        return SecurityMetrics(
            total_events=len(self._events),
            events_by_severity=dict(events_by_severity),
            events_by_type=dict(events_by_type),
            active_alerts=active_alerts,
            blocked_users=len(self._blocked_users),
            rate_limit_violations=rate_limit_violations,
            cross_tenant_attempts=cross_tenant_attempts
        )
    
    def get_recent_events(
        self,
        limit: int = 100,
        severity: Optional[AlertSeverity] = None,
        threat_type: Optional[ThreatType] = None,
        user_id: Optional[str] = None,
        tenant_id: Optional[str] = None
    ) -> List[SecurityEvent]:
        """Get recent security events with filtering"""
        events = self._events
        
        # Apply filters
        if severity:
            events = [e for e in events if e.severity == severity]
        
        if threat_type:
            events = [e for e in events if e.threat_type == threat_type]
        
        if user_id:
            events = [e for e in events if e.user_id == user_id]
        
        if tenant_id:
            events = [e for e in events if e.tenant_id == tenant_id]
        
        # Sort by timestamp (newest first) and limit
        events.sort(key=lambda e: e.timestamp, reverse=True)
        return events[:limit]
    
    def get_active_alerts(self) -> List[SecurityAlert]:
        """Get active (unresolved) security alerts"""
        return [alert for alert in self._alerts if not alert.resolved]
    
    def acknowledge_alert(self, alert_id: str) -> bool:
        """Acknowledge a security alert"""
        for alert in self._alerts:
            if alert.alert_id == alert_id:
                alert.acknowledged = True
                logger.info(f"Alert acknowledged: {alert_id}")
                return True
        return False
    
    def resolve_alert(self, alert_id: str, resolution_notes: str = "") -> bool:
        """Resolve a security alert"""
        for alert in self._alerts:
            if alert.alert_id == alert_id:
                alert.resolved = True
                alert.resolution_time = datetime.now(timezone.utc).isoformat()
                logger.info(f"Alert resolved: {alert_id}")
                return True
        return False


# Global security monitoring service
security_monitoring_service = SecurityMonitoringService()