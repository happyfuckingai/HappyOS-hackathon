"""
🛡️ ERROR HANDLER - LEGACY COMPATIBILITY

This module provides backward compatibility for the old error_handler module.
It re-exports functionality from the new error_handling module.
"""

from .error_handling.error_classifier import ErrorClassifier
from .error_handling.graceful_degradation import GracefulDegradationManager

# Define HappyOSError exception for backward compatibility
class HappyOSError(Exception):
    """HappyOS base exception class."""
    pass

def safe_execute(func, *args, **kwargs):
    """
    Safely execute a function with error handling.
    
    Args:
        func: Function to execute
        *args: Arguments to pass to the function
        **kwargs: Keyword arguments to pass to the function
        
    Returns:
        Result of the function execution or None if an error occurs
    """
    try:
        return func(*args, **kwargs)
    except Exception as e:
        # Log the error (in a real implementation, this would use proper logging)
        print(f"Error executing {func.__name__}: {str(e)}")
        return None

def error_handler(default_return=None):
    """
    Decorator for handling errors in a function.
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                # In a real implementation, you would use the ErrorClassifier here
                # For now, we'll just log the error and return the default value
                print(f"Error in {func.__name__}: {e}")
                return default_return
        return wrapper
    return decorator

__all__ = ['error_handler', 'ErrorClassifier', 'GracefulDegradationManager', 'HappyOSError', 'safe_execute']
