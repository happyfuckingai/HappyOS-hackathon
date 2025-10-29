"""
HappyOS SDK Exceptions

Custom exceptions for the HappyOS SDK to provide clear error handling
for agent modules.
"""


class HappyOSSDKError(Exception):
    """Base exception for HappyOS SDK errors."""
    pass


class A2AError(HappyOSSDKError):
    """Exception raised for A2A protocol communication errors."""
    pass


class ServiceUnavailableError(HappyOSSDKError):
    """Exception raised when a service is unavailable."""
    pass


class CircuitBreakerOpenError(HappyOSSDKError):
    """Exception raised when circuit breaker is open."""
    pass


class TransportError(A2AError):
    """Exception raised for transport-level errors."""
    pass


class AuthenticationError(A2AError):
    """Exception raised for authentication failures."""
    pass


class MessageTimeoutError(A2AError):
    """Exception raised when message times out."""
    pass


class InvalidMessageError(A2AError):
    """Exception raised for invalid message format."""
    pass


class AuthorizationError(HappyOSSDKError):
    """Exception raised for authorization failures."""
    pass


class ConfigurationError(HappyOSSDKError):
    """Exception raised for configuration errors."""
    pass