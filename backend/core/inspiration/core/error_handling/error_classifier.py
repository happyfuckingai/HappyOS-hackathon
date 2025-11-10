"""
🏷️ ERROR CLASSIFIER

Intelligent error classification system:
- Automatic error categorization
- Severity assessment
- Recovery strategy recommendation
- Error pattern recognition
"""

import logging
import re
from typing import Dict, Any, Optional, List, Set
from dataclasses import dataclass
from enum import Enum
from datetime import datetime

logger = logging.getLogger(__name__)


class HappyOSError(Exception):
    """Base exception for HappyOS application."""
    def __init__(self, message, category=None, severity=None, details=None):
        super().__init__(message)
        self.category = category or ErrorCategory.UNKNOWN
        self.severity = severity or ErrorSeverity.MEDIUM
        self.details = details or {}

def error_handler(func):
    """Decorator to handle HappyOSErrors and other exceptions."""
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except HappyOSError as e:
            logger.error(f"HappyOS Error in {func.__name__}: {e}", exc_info=True)
            # Re-raise or handle as needed
            raise
        except Exception as e:
            logger.error(f"Unhandled exception in {func.__name__}: {e}", exc_info=True)
            # Wrap in HappyOSError or re-raise
            raise HappyOSError(f"Unhandled exception: {e}", category=ErrorCategory.SYSTEM, severity=ErrorSeverity.CRITICAL) from e
    return wrapper


class ErrorSeverity(Enum):
    """Error severity levels."""
    LOW = "low"           # Minor issues, system continues normally
    MEDIUM = "medium"     # Moderate issues, some functionality affected
    HIGH = "high"         # Serious issues, major functionality affected
    CRITICAL = "critical" # System-threatening issues, immediate attention needed


class ErrorCategory(Enum):
    """Error categories."""
    NETWORK = "network"                 # Network connectivity issues
    AUTHENTICATION = "authentication"   # Authentication/authorization failures
    VALIDATION = "validation"           # Input validation errors
    RESOURCE = "resource"               # Resource exhaustion (memory, disk, etc.)
    EXTERNAL_SERVICE = "external_service" # External service failures
    DATABASE = "database"               # Database connectivity/query issues
    CONFIGURATION = "configuration"     # Configuration errors
    BUSINESS_LOGIC = "business_logic"   # Business rule violations
    SYSTEM = "system"                   # System-level errors
    USER_ERROR = "user_error"           # User input/behavior errors
    UNKNOWN = "unknown"                 # Unclassified errors


@dataclass
class ErrorClassification:
    """Error classification result."""
    category: ErrorCategory
    severity: ErrorSeverity
    confidence: float  # 0.0-1.0
    description: str
    suggested_actions: List[str]
    retryable: bool
    user_facing: bool  # Should this error be shown to users?
    
    # Additional metadata
    error_code: Optional[str] = None
    component: Optional[str] = None
    recovery_time_estimate: Optional[int] = None  # Seconds


class ErrorPattern:
    """Error pattern for classification."""
    
    def __init__(self, name: str, category: ErrorCategory, severity: ErrorSeverity,
                 patterns: List[str], confidence: float = 1.0,
                 suggested_actions: List[str] = None, retryable: bool = True,
                 user_facing: bool = False):
        self.name = name
        self.category = category
        self.severity = severity
        self.patterns = [re.compile(pattern, re.IGNORECASE) for pattern in patterns]
        self.confidence = confidence
        self.suggested_actions = suggested_actions or []
        self.retryable = retryable
        self.user_facing = user_facing
    
    def matches(self, error_text: str) -> bool:
        """Check if error text matches this pattern."""
        return any(pattern.search(error_text) for pattern in self.patterns)


class ErrorClassifier:
    """
    Intelligent error classifier for HappyOS.
    """
    
    def __init__(self):
        self.patterns: List[ErrorPattern] = []
        self._initialize_default_patterns()
        self._classification_history: List[Dict[str, Any]] = []
    
    def _initialize_default_patterns(self):
        """Initialize default error patterns."""
        
        # Network errors
        self.patterns.extend([
            ErrorPattern(
                "connection_timeout",
                ErrorCategory.NETWORK,
                ErrorSeverity.MEDIUM,
                [
                    r"connection.*timeout",
                    r"timeout.*connection",
                    r"read timeout",
                    r"connect timeout"
                ],
                confidence=0.9,
                suggested_actions=[
                    "Check network connectivity",
                    "Verify service availability",
                    "Retry with exponential backoff"
                ],
                retryable=True
            ),
            ErrorPattern(
                "connection_refused",
                ErrorCategory.NETWORK,
                ErrorSeverity.HIGH,
                [
                    r"connection refused",
                    r"connection reset",
                    r"no route to host",
                    r"network unreachable"
                ],
                confidence=0.95,
                suggested_actions=[
                    "Check service status",
                    "Verify network configuration",
                    "Check firewall settings"
                ],
                retryable=True
            ),
            ErrorPattern(
                "dns_resolution",
                ErrorCategory.NETWORK,
                ErrorSeverity.MEDIUM,
                [
                    r"name resolution failed",
                    r"dns.*failed",
                    r"host not found",
                    r"nodename nor servname provided"
                ],
                confidence=0.9,
                suggested_actions=[
                    "Check DNS configuration",
                    "Verify hostname spelling",
                    "Try alternative DNS servers"
                ],
                retryable=True
            )
        ])
        
        # Authentication errors
        self.patterns.extend([
            ErrorPattern(
                "authentication_failed",
                ErrorCategory.AUTHENTICATION,
                ErrorSeverity.MEDIUM,
                [
                    r"authentication failed",
                    r"invalid credentials",
                    r"unauthorized",
                    r"access denied",
                    r"401.*unauthorized"
                ],
                confidence=0.95,
                suggested_actions=[
                    "Verify credentials",
                    "Check authentication token",
                    "Refresh access token"
                ],
                retryable=False,
                user_facing=True
            ),
            ErrorPattern(
                "token_expired",
                ErrorCategory.AUTHENTICATION,
                ErrorSeverity.LOW,
                [
                    r"token.*expired",
                    r"expired.*token",
                    r"session.*expired"
                ],
                confidence=0.9,
                suggested_actions=[
                    "Refresh authentication token",
                    "Re-authenticate user"
                ],
                retryable=True
            )
        ])
        
        # Validation errors
        self.patterns.extend([
            ErrorPattern(
                "validation_error",
                ErrorCategory.VALIDATION,
                ErrorSeverity.LOW,
                [
                    r"validation.*failed",
                    r"invalid.*input",
                    r"bad request",
                    r"400.*bad request",
                    r"malformed.*request"
                ],
                confidence=0.8,
                suggested_actions=[
                    "Validate input data",
                    "Check request format",
                    "Review API documentation"
                ],
                retryable=False,
                user_facing=True
            ),
            ErrorPattern(
                "missing_parameter",
                ErrorCategory.VALIDATION,
                ErrorSeverity.LOW,
                [
                    r"missing.*parameter",
                    r"required.*field",
                    r"parameter.*required"
                ],
                confidence=0.9,
                suggested_actions=[
                    "Check required parameters",
                    "Validate request payload"
                ],
                retryable=False,
                user_facing=True
            )
        ])
        
        # Resource errors
        self.patterns.extend([
            ErrorPattern(
                "memory_error",
                ErrorCategory.RESOURCE,
                ErrorSeverity.HIGH,
                [
                    r"out of memory",
                    r"memory.*exhausted",
                    r"cannot allocate memory",
                    r"memoryerror"
                ],
                confidence=0.95,
                suggested_actions=[
                    "Free up memory",
                    "Restart service",
                    "Scale up resources"
                ],
                retryable=True
            ),
            ErrorPattern(
                "disk_space",
                ErrorCategory.RESOURCE,
                ErrorSeverity.HIGH,
                [
                    r"no space left",
                    r"disk.*full",
                    r"insufficient.*space",
                    r"quota.*exceeded"
                ],
                confidence=0.95,
                suggested_actions=[
                    "Free up disk space",
                    "Clean up temporary files",
                    "Increase storage capacity"
                ],
                retryable=False
            )
        ])
        
        # Database errors
        self.patterns.extend([
            ErrorPattern(
                "database_connection",
                ErrorCategory.DATABASE,
                ErrorSeverity.HIGH,
                [
                    r"database.*connection.*failed",
                    r"connection.*database.*lost",
                    r"database.*unavailable",
                    r"database.*timeout"
                ],
                confidence=0.9,
                suggested_actions=[
                    "Check database status",
                    "Verify connection parameters",
                    "Restart database connection"
                ],
                retryable=True
            ),
            ErrorPattern(
                "sql_syntax",
                ErrorCategory.DATABASE,
                ErrorSeverity.MEDIUM,
                [
                    r"sql.*syntax.*error",
                    r"syntax.*error.*sql",
                    r"invalid.*sql",
                    r"malformed.*query"
                ],
                confidence=0.95,
                suggested_actions=[
                    "Review SQL query syntax",
                    "Check database schema",
                    "Validate query parameters"
                ],
                retryable=False
            )
        ])
        
        # External service errors
        self.patterns.extend([
            ErrorPattern(
                "service_unavailable",
                ErrorCategory.EXTERNAL_SERVICE,
                ErrorSeverity.MEDIUM,
                [
                    r"service unavailable",
                    r"503.*service unavailable",
                    r"server.*temporarily.*unavailable",
                    r"maintenance.*mode"
                ],
                confidence=0.9,
                suggested_actions=[
                    "Wait and retry",
                    "Check service status page",
                    "Use fallback service"
                ],
                retryable=True
            ),
            ErrorPattern(
                "rate_limit",
                ErrorCategory.EXTERNAL_SERVICE,
                ErrorSeverity.MEDIUM,
                [
                    r"rate.*limit.*exceeded",
                    r"too many requests",
                    r"429.*too many requests",
                    r"quota.*exceeded"
                ],
                confidence=0.95,
                suggested_actions=[
                    "Implement rate limiting",
                    "Wait before retrying",
                    "Optimize request frequency"
                ],
                retryable=True
            )
        ])
        
        # Configuration errors
        self.patterns.extend([
            ErrorPattern(
                "config_missing",
                ErrorCategory.CONFIGURATION,
                ErrorSeverity.HIGH,
                [
                    r"configuration.*missing",
                    r"config.*not found",
                    r"missing.*environment.*variable",
                    r"setting.*not.*configured"
                ],
                confidence=0.9,
                suggested_actions=[
                    "Check configuration files",
                    "Verify environment variables",
                    "Review setup documentation"
                ],
                retryable=False
            ),
            ErrorPattern(
                "config_invalid",
                ErrorCategory.CONFIGURATION,
                ErrorSeverity.MEDIUM,
                [
                    r"invalid.*configuration",
                    r"configuration.*error",
                    r"malformed.*config",
                    r"config.*syntax.*error"
                ],
                confidence=0.85,
                suggested_actions=[
                    "Validate configuration syntax",
                    "Check configuration values",
                    "Review configuration schema"
                ],
                retryable=False
            )
        ])
        
        logger.info(f"Initialized error classifier with {len(self.patterns)} patterns")
    
    def classify_error(self, exception: Exception, context: Dict[str, Any] = None) -> ErrorClassification:
        """
        Classify an error and provide recommendations.
        
        Args:
            exception: The exception to classify
            context: Additional context information
            
        Returns:
            ErrorClassification with category, severity, and recommendations
        """
        error_text = str(exception)
        exception_type = type(exception).__name__
        
        # Combine error text and exception type for matching
        full_error_text = f"{exception_type}: {error_text}"
        
        # Find matching patterns
        matches = []
        for pattern in self.patterns:
            if pattern.matches(full_error_text):
                matches.append(pattern)
        
        # Select best match
        if matches:
            # Sort by confidence and take the highest
            best_match = max(matches, key=lambda p: p.confidence)
            
            classification = ErrorClassification(
                category=best_match.category,
                severity=best_match.severity,
                confidence=best_match.confidence,
                description=f"Classified as {best_match.name}",
                suggested_actions=best_match.suggested_actions.copy(),
                retryable=best_match.retryable,
                user_facing=best_match.user_facing,
                component=context.get('component') if context else None
            )
        else:
            # Default classification for unknown errors
            classification = self._classify_by_exception_type(exception, context)
        
        # Add context-specific adjustments
        if context:
            classification = self._adjust_classification_with_context(classification, context)
        
        # Record classification
        self._record_classification(exception, classification, context)
        
        logger.debug(f"Classified error '{error_text}' as {classification.category.value} "
                    f"with severity {classification.severity.value} "
                    f"(confidence: {classification.confidence:.2f})")
        
        return classification
    
    def _classify_by_exception_type(self, exception: Exception, context: Dict[str, Any] = None) -> ErrorClassification:
        """Classify error based on exception type when no pattern matches."""
        exception_type = type(exception).__name__
        
        # Common Python exception mappings
        type_mappings = {
            'ConnectionError': (ErrorCategory.NETWORK, ErrorSeverity.MEDIUM, True),
            'TimeoutError': (ErrorCategory.NETWORK, ErrorSeverity.MEDIUM, True),
            'ValueError': (ErrorCategory.VALIDATION, ErrorSeverity.LOW, False),
            'TypeError': (ErrorCategory.VALIDATION, ErrorSeverity.LOW, False),
            'KeyError': (ErrorCategory.VALIDATION, ErrorSeverity.LOW, False),
            'AttributeError': (ErrorCategory.SYSTEM, ErrorSeverity.MEDIUM, False),
            'MemoryError': (ErrorCategory.RESOURCE, ErrorSeverity.CRITICAL, False),
            'PermissionError': (ErrorCategory.AUTHENTICATION, ErrorSeverity.MEDIUM, False),
            'FileNotFoundError': (ErrorCategory.CONFIGURATION, ErrorSeverity.MEDIUM, False),
            'OSError': (ErrorCategory.SYSTEM, ErrorSeverity.MEDIUM, True),
        }
        
        if exception_type in type_mappings:
            category, severity, retryable = type_mappings[exception_type]
            confidence = 0.7  # Lower confidence for type-based classification
        else:
            # Default for unknown exception types
            category = ErrorCategory.UNKNOWN
            severity = ErrorSeverity.MEDIUM
            retryable = False
            confidence = 0.5
        
        return ErrorClassification(
            category=category,
            severity=severity,
            confidence=confidence,
            description=f"Classified by exception type: {exception_type}",
            suggested_actions=[
                "Review error details",
                "Check system logs",
                "Contact support if issue persists"
            ],
            retryable=retryable,
            user_facing=False,
            component=context.get('component') if context else None
        )
    
    def _adjust_classification_with_context(self, classification: ErrorClassification, 
                                          context: Dict[str, Any]) -> ErrorClassification:
        """Adjust classification based on context."""
        # Increase severity if error occurs in critical component
        critical_components = context.get('critical_components', [])
        if classification.component in critical_components:
            if classification.severity == ErrorSeverity.LOW:
                classification.severity = ErrorSeverity.MEDIUM
            elif classification.severity == ErrorSeverity.MEDIUM:
                classification.severity = ErrorSeverity.HIGH
        
        # Adjust based on error frequency
        error_count = context.get('recent_error_count', 0)
        if error_count > 5:
            classification.suggested_actions.insert(0, "High error frequency detected - investigate root cause")
            if classification.severity != ErrorSeverity.CRITICAL:
                classification.severity = ErrorSeverity.HIGH
        
        # Add component-specific actions
        component = context.get('component')
        if component:
            component_actions = {
                'mr_happy_agent': ["Check personality engine", "Verify skill integration"],
                'skill_registry': ["Check skill cache", "Verify skill metadata"],
                'orchestrator': ["Check processing strategy", "Verify component health"],
                'database': ["Check connection pool", "Verify schema integrity"]
            }
            
            if component in component_actions:
                classification.suggested_actions.extend(component_actions[component])
        
        return classification
    
    def _record_classification(self, exception: Exception, classification: ErrorClassification, 
                             context: Dict[str, Any] = None):
        """Record classification for analysis."""
        record = {
            'timestamp': datetime.utcnow().isoformat(),
            'exception_type': type(exception).__name__,
            'exception_message': str(exception),
            'category': classification.category.value,
            'severity': classification.severity.value,
            'confidence': classification.confidence,
            'retryable': classification.retryable,
            'user_facing': classification.user_facing,
            'component': classification.component,
            'context': context or {}
        }
        
        self._classification_history.append(record)
        
        # Keep only recent history
        if len(self._classification_history) > 1000:
            self._classification_history = self._classification_history[-500:]
    
    def add_custom_pattern(self, pattern: ErrorPattern):
        """Add custom error pattern."""
        self.patterns.append(pattern)
        logger.info(f"Added custom error pattern: {pattern.name}")
    
    def get_classification_stats(self) -> Dict[str, Any]:
        """Get classification statistics."""
        if not self._classification_history:
            return {"total_classifications": 0}
        
        total = len(self._classification_history)
        
        # Count by category
        category_counts = {}
        for record in self._classification_history:
            category = record['category']
            category_counts[category] = category_counts.get(category, 0) + 1
        
        # Count by severity
        severity_counts = {}
        for record in self._classification_history:
            severity = record['severity']
            severity_counts[severity] = severity_counts.get(severity, 0) + 1
        
        # Count by component
        component_counts = {}
        for record in self._classification_history:
            component = record.get('component', 'unknown')
            component_counts[component] = component_counts.get(component, 0) + 1
        
        # Calculate average confidence
        avg_confidence = sum(r['confidence'] for r in self._classification_history) / total
        
        return {
            "total_classifications": total,
            "category_distribution": category_counts,
            "severity_distribution": severity_counts,
            "component_distribution": component_counts,
            "average_confidence": avg_confidence,
            "retryable_percentage": sum(1 for r in self._classification_history if r['retryable']) / total * 100,
            "user_facing_percentage": sum(1 for r in self._classification_history if r['user_facing']) / total * 100
        }
    
    def get_recent_classifications(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Get recent error classifications."""
        return self._classification_history[-limit:]
    
    def get_error_patterns_by_component(self, component: str) -> List[Dict[str, Any]]:
        """Get error patterns for a specific component."""
        component_errors = [
            r for r in self._classification_history
            if r.get('component') == component
        ]
        
        # Group by category and count
        pattern_counts = {}
        for error in component_errors:
            key = (error['category'], error['severity'])
            if key not in pattern_counts:
                pattern_counts[key] = {
                    'category': error['category'],
                    'severity': error['severity'],
                    'count': 0,
                    'recent_examples': []
                }
            
            pattern_counts[key]['count'] += 1
            if len(pattern_counts[key]['recent_examples']) < 3:
                pattern_counts[key]['recent_examples'].append({
                    'timestamp': error['timestamp'],
                    'exception_type': error['exception_type'],
                    'message': error['exception_message']
                })
        
        return list(pattern_counts.values())


# Global error classifier
_error_classifier: Optional[ErrorClassifier] = None


def get_error_classifier() -> ErrorClassifier:
    """Get global error classifier."""
    global _error_classifier
    
    if _error_classifier is None:
        _error_classifier = ErrorClassifier()
    
    return _error_classifier


def classify_error(exception: Exception, context: Dict[str, Any] = None) -> ErrorClassification:
    """Convenience function for error classification."""
    classifier = get_error_classifier()
    return classifier.classify_error(exception, context)

