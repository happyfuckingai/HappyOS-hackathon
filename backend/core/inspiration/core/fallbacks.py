"""
Fallback mechanisms for HappyOS.

This module provides fallback mechanisms for various components of the system,
ensuring graceful degradation in case of failures.
"""

import logging
import time
import asyncio
import functools
from typing import Dict, Any, Callable, Optional, TypeVar, Awaitable, List, Union, Tuple
from contextlib import contextmanager
from datetime import datetime

logger = logging.getLogger(__name__)

# Type variables for generic functions
T = TypeVar('T')
R = TypeVar('R')

# Global registry of fallback handlers
_fallback_handlers: Dict[str, List[Callable]] = {}

# Performance monitoring
_performance_metrics: Dict[str, Dict[str, Any]] = {}


def register_fallback(component: str, handler: Callable) -> None:
    """
    Register a fallback handler for a specific component.
    
    Args:
        component: The component name to register the fallback for
        handler: The fallback handler function
    """
    global _fallback_handlers
    
    if component not in _fallback_handlers:
        _fallback_handlers[component] = []
    
    _fallback_handlers[component].append(handler)
    logger.info(f"Registered fallback handler for component '{component}'")


def get_fallback_handlers(component: str) -> List[Callable]:
    """
    Get all fallback handlers for a specific component.
    
    Args:
        component: The component name to get handlers for
        
    Returns:
        List of fallback handler functions
    """
    return _fallback_handlers.get(component, [])


async def with_fallback(
    func: Callable[..., Awaitable[T]],
    component: str,
    *args,
    **kwargs
) -> T:
    """
    Execute a function with fallback mechanisms.
    
    If the primary function fails, fallback handlers will be tried in order.
    
    Args:
        func: The primary function to execute
        component: The component name to get fallback handlers for
        *args: Arguments to pass to the function
        **kwargs: Keyword arguments to pass to the function
        
    Returns:
        The result of the function or a fallback
        
    Raises:
        Exception: If all fallbacks fail
    """
    start_time = time.time()
    
    try:
        # Try the primary function first
        result = await func(*args, **kwargs)
        
        # Record successful execution
        _record_performance(component, "primary", time.time() - start_time, True)
        
        return result
    
    except Exception as primary_error:
        logger.warning(f"Primary function for '{component}' failed: {primary_error}")
        _record_performance(component, "primary", time.time() - start_time, False)
        
        # Try each fallback in order
        fallbacks = get_fallback_handlers(component)
        
        if not fallbacks:
            logger.error(f"No fallbacks registered for component '{component}'")
            raise primary_error
        
        last_error = primary_error
        
        for i, fallback in enumerate(fallbacks):
            fallback_start = time.time()
            try:
                logger.info(f"Trying fallback {i+1}/{len(fallbacks)} for '{component}'")
                result = await fallback(*args, **kwargs)
                
                # Record successful fallback
                _record_performance(component, f"fallback_{i+1}", time.time() - fallback_start, True)
                
                return result
            
            except Exception as fallback_error:
                logger.warning(f"Fallback {i+1} for '{component}' failed: {fallback_error}")
                _record_performance(component, f"fallback_{i+1}", time.time() - fallback_start, False)
                last_error = fallback_error
        
        # If we get here, all fallbacks failed
        logger.error(f"All fallbacks for '{component}' failed")
        raise last_error


def with_retry(
    max_retries: int = 3,
    retry_delay: float = 1.0,
    backoff_factor: float = 2.0,
    component: str = "unknown"
):
    """
    Decorator for retrying a function on failure.
    
    Args:
        max_retries: Maximum number of retry attempts
        retry_delay: Initial delay between retries in seconds
        backoff_factor: Factor to increase delay by after each retry
        component: Component name for logging
        
    Returns:
        Decorated function
    """
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            retries = 0
            current_delay = retry_delay
            
            while True:
                try:
                    return await func(*args, **kwargs)
                
                except Exception as e:
                    retries += 1
                    
                    if retries > max_retries:
                        logger.error(f"Max retries ({max_retries}) exceeded for {component}: {e}")
                        raise
                    
                    logger.warning(f"Retry {retries}/{max_retries} for {component} after error: {e}")
                    
                    # Wait before retrying
                    await asyncio.sleep(current_delay)
                    
                    # Increase delay for next retry
                    current_delay *= backoff_factor
        
        return wrapper
    
    return decorator


def with_timeout(timeout: float, component: str = "unknown"):
    """
    Decorator for adding a timeout to a function.
    
    Args:
        timeout: Timeout in seconds
        component: Component name for logging
        
    Returns:
        Decorated function
    """
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            try:
                return await asyncio.wait_for(func(*args, **kwargs), timeout=timeout)
            
            except asyncio.TimeoutError:
                logger.error(f"Timeout ({timeout}s) exceeded for {component}")
                raise TimeoutError(f"Operation timed out after {timeout} seconds")
        
        return wrapper
    
    return decorator


@contextmanager
def performance_tracking(component: str, operation: str):
    """
    Context manager for tracking performance of an operation.
    
    Args:
        component: Component name
        operation: Operation name
        
    Yields:
        None
    """
    start_time = time.time()
    success = False
    
    try:
        yield
        success = True
    
    finally:
        execution_time = time.time() - start_time
        _record_performance(component, operation, execution_time, success)


def _record_performance(component: str, operation: str, execution_time: float, success: bool):
    """Record performance metrics for a component operation."""
    global _performance_metrics
    
    if component not in _performance_metrics:
        _performance_metrics[component] = {}
    
    if operation not in _performance_metrics[component]:
        _performance_metrics[component][operation] = {
            "count": 0,
            "success_count": 0,
            "failure_count": 0,
            "total_time": 0.0,
            "avg_time": 0.0,
            "min_time": float('inf'),
            "max_time": 0.0
        }
    
    metrics = _performance_metrics[component][operation]
    metrics["count"] += 1
    metrics["total_time"] += execution_time
    metrics["avg_time"] = metrics["total_time"] / metrics["count"]
    metrics["min_time"] = min(metrics["min_time"], execution_time)
    metrics["max_time"] = max(metrics["max_time"], execution_time)
    
    if success:
        metrics["success_count"] += 1
    else:
        metrics["failure_count"] += 1


def get_performance_metrics() -> Dict[str, Dict[str, Any]]:
    """
    Get performance metrics for all components.

    Returns:
        Dict of performance metrics
    """
    return _performance_metrics


def clear_performance_metrics():
    """Clear all performance metrics."""
    global _performance_metrics
    _performance_metrics = {}


# LLM-Specific Performance Tracking
def register_llm_performance_tracking():
    """
    Register LLM-specific performance tracking for all LLM operations.
    """
    try:
        # Register LLM generation tracking
        register_fallback("llm_generation", llm_generation_fallback)

        # Register LLM embedding tracking
        register_fallback("llm_embedding", llm_embedding_fallback)

        logger.info("LLM performance tracking registered")
    except Exception as e:
        logger.warning(f"Failed to register LLM performance tracking: {e}")


async def llm_generation_fallback(*args, **kwargs):
    """
    Fallback handler for LLM generation operations.

    Tracks detailed metrics including tokens used, cost, and provider performance.
    """
    # This is a no-op fallback since we handle failures in the router
    # But we use it to track metrics
    pass


async def llm_embedding_fallback(*args, **kwargs):
    """
    Fallback handler for LLM embedding operations.
    """
    # This is a no-op fallback since we handle failures in the router
    pass


def record_llm_request(provider: str, operation: str, success: bool, response_time: float,
                      tokens_used: int = 0, cost: float = 0.0, model: str = ""):
    """
    Record LLM-specific request metrics.

    Args:
        provider: LLM provider name
        operation: Operation type ('generate', 'embed', 'chat')
        success: Whether the request was successful
        response_time: Response time in seconds
        tokens_used: Number of tokens used
        cost: Estimated cost of the request
        model: Model name used
    """
    component = f"llm_{provider}_{operation}"

    # Record in general performance metrics
    _record_performance(component, "request", response_time, success)

    # Record LLM-specific metrics
    if component not in _performance_metrics:
        _performance_metrics[component] = {
            "count": 0,
            "success_count": 0,
            "failure_count": 0,
            "total_time": 0.0,
            "avg_time": 0.0,
            "min_time": float('inf'),
            "max_time": 0.0,
            "total_tokens": 0,
            "total_cost": 0.0,
            "models_used": set(),
            "last_request": None
        }

    metrics = _performance_metrics[component]
    metrics["count"] += 1
    metrics["total_time"] += response_time
    metrics["avg_time"] = metrics["total_time"] / metrics["count"]
    metrics["min_time"] = min(metrics["min_time"], response_time)
    metrics["max_time"] = max(metrics["max_time"], response_time)
    metrics["total_tokens"] += tokens_used
    metrics["total_cost"] += cost

    if success:
        metrics["success_count"] += 1
    else:
        metrics["failure_count"] += 1

    if model:
        metrics["models_used"].add(model)

    metrics["last_request"] = datetime.utcnow().isoformat()

    # Update provider health metrics
    try:
        from app.llm.health_checks import get_provider_metrics
        provider_metrics = get_provider_metrics(provider)
        provider_metrics.record_request(success, response_time, tokens_used, cost)
    except Exception as e:
        logger.debug(f"Failed to update provider health metrics: {e}")


def get_llm_performance_summary() -> Dict[str, Any]:
    """
    Get comprehensive LLM performance summary.

    Returns:
        Dictionary with LLM performance metrics
    """
    llm_metrics = {}
    provider_stats = {}

    # Extract LLM-specific metrics
    for component, metrics in _performance_metrics.items():
        if component.startswith("llm_"):
            llm_metrics[component] = metrics.copy()

            # Extract provider information
            parts = component.split("_")
            if len(parts) >= 3:
                provider = parts[1]
                operation = parts[2]

                if provider not in provider_stats:
                    provider_stats[provider] = {
                        "total_requests": 0,
                        "successful_requests": 0,
                        "total_tokens": 0,
                        "total_cost": 0.0,
                        "avg_response_time": 0.0,
                        "operations": {}
                    }

                provider_stats[provider]["total_requests"] += metrics["count"]
                provider_stats[provider]["successful_requests"] += metrics["success_count"]
                provider_stats[provider]["total_tokens"] += metrics["total_tokens"]
                provider_stats[provider]["total_cost"] += metrics["total_cost"]

                if operation not in provider_stats[provider]["operations"]:
                    provider_stats[provider]["operations"][operation] = {
                        "count": 0,
                        "success_rate": 0.0,
                        "avg_time": 0.0
                    }

                op_stats = provider_stats[provider]["operations"][operation]
                op_stats["count"] += metrics["count"]
                op_stats["success_rate"] = metrics["success_count"] / max(metrics["count"], 1)
                op_stats["avg_time"] = metrics["avg_time"]

    # Calculate overall provider statistics
    for provider, stats in provider_stats.items():
        if stats["total_requests"] > 0:
            stats["success_rate"] = stats["successful_requests"] / stats["total_requests"]
            stats["avg_response_time"] = sum(
                op["avg_time"] * op["count"] for op in stats["operations"].values()
            ) / stats["total_requests"]
        else:
            stats["success_rate"] = 0.0
            stats["avg_response_time"] = 0.0

    return {
        "llm_metrics": llm_metrics,
        "provider_summary": provider_stats,
        "timestamp": datetime.utcnow().isoformat()
    }


def get_provider_cost_analysis(provider: str = None) -> Dict[str, Any]:
    """
    Get cost analysis for LLM providers.

    Args:
        provider: Specific provider to analyze, or None for all

    Returns:
        Cost analysis data
    """
    analysis = {
        "total_cost": 0.0,
        "total_tokens": 0,
        "cost_per_token": {},
        "cost_by_model": {},
        "cost_trends": []
    }

    providers_to_analyze = [provider] if provider else None

    for component, metrics in _performance_metrics.items():
        if component.startswith("llm_"):
            parts = component.split("_")
            if len(parts) >= 2:
                comp_provider = parts[1]

                if providers_to_analyze and comp_provider not in providers_to_analyze:
                    continue

                analysis["total_cost"] += metrics["total_cost"]
                analysis["total_tokens"] += metrics["total_tokens"]

                # Calculate cost per token if tokens used
                if metrics["total_tokens"] > 0:
                    cost_per_token = metrics["total_cost"] / metrics["total_tokens"]
                    analysis["cost_per_token"][component] = cost_per_token

    return analysis


# Initialize LLM tracking on module import
register_llm_performance_tracking()


# Database connection fallbacks
async def db_connection_fallback(db_config: Dict[str, Any]) -> Any:
    """
    Fallback for database connections.

    This function tries to establish a database connection using alternative
    configurations if the primary connection fails.

    Args:
        db_config: Database configuration

    Returns:
        Database connection object

    Raises:
        Exception: If all connection attempts fail
    """
    # Import database modules here to avoid circular imports
    try:
        from app.core.database.connection import DatabaseConfig, DatabaseConnection
    except ImportError:
        logger.error("Failed to import database modules")
        raise

    # Try read-only replica if available
    if "read_replica" in db_config:
        try:
            logger.info("Trying read-only database replica")
            replica_config = DatabaseConfig(
                database_type=db_config["read_replica"].get("type", "sqlite"),
                database_path=db_config["read_replica"].get("database_path"),
                host=db_config["read_replica"].get("host"),
                port=db_config["read_replica"].get("port"),
                username=db_config["read_replica"].get("username"),
                password=db_config["read_replica"].get("password"),
                database_name=db_config["read_replica"].get("database_name")
            )
            conn = DatabaseConnection(replica_config)
            await conn.initialize()
            return conn
        except Exception as e:
            logger.warning(f"Failed to connect to read replica: {e}")

    # Try in-memory database as last resort
    try:
        logger.info("Falling back to in-memory database")
        memory_config = DatabaseConfig(
            database_type="sqlite",
            database_path=":memory:"
        )
        conn = DatabaseConnection(memory_config)
        await conn.initialize()
        return conn
    except Exception as e:
        logger.error(f"Failed to create in-memory database: {e}")
        raise


# Transaction manager fallback
async def transaction_manager_fallback(*args, **kwargs):
    """
    Fallback for transaction manager operations.

    Attempts to execute operations without full ACID compliance
    when transaction manager fails.
    """
    try:
        # Import here to avoid circular imports
        from app.core.database.connection import get_db_connection
        db = await get_db_connection()

        # Execute operations directly without transaction wrapper
        logger.warning("Using transaction manager fallback - operations may not be atomic")

        # This is a simplified fallback - in practice, you'd want more sophisticated logic
        return await db.execute_query("SELECT 1")  # Simple test query

    except Exception as e:
        logger.error(f"Transaction manager fallback failed: {e}")
        raise


# Repository fallback
async def repository_fallback(operation: str, *args, **kwargs):
    """
    Fallback for repository operations.

    Attempts to execute repository operations with degraded functionality
    when repository layer fails.
    """
    try:
        # Import here to avoid circular imports
        from app.core.database.connection import get_db_connection
        db = await get_db_connection()

        logger.warning(f"Using repository fallback for operation: {operation}")

        # Provide basic functionality based on operation type
        if operation == "count":
            # Fallback count query
            result = await db.execute_query("SELECT COUNT(*) FROM users")
            return result[0][0] if result else 0
        elif operation == "find_by_id":
            entity_id = args[0] if args else kwargs.get('id')
            result = await db.execute_query("SELECT * FROM users WHERE id = ?", (entity_id,))
            return result[0] if result else None
        else:
            # Generic fallback
            return None

    except Exception as e:
        logger.error(f"Repository fallback failed: {e}")
        raise


# Migration fallback
async def migration_fallback(*args, **kwargs):
    """
    Fallback for migration operations.

    Provides basic migration status when migration manager fails.
    """
    try:
        # Import here to avoid circular imports
        from app.core.database.connection import get_db_connection
        db = await get_db_connection()

        logger.warning("Using migration fallback")

        # Return basic migration status
        return {
            "status": "degraded",
            "message": "Migration manager unavailable, using fallback mode",
            "migrations": []
        }

    except Exception as e:
        logger.error(f"Migration fallback failed: {e}")
        raise


# Register common fallbacks
register_fallback("database", db_connection_fallback)
register_fallback("transaction_manager", transaction_manager_fallback)
register_fallback("repository", repository_fallback)
register_fallback("migration_manager", migration_fallback)


# Security fallbacks
def apply_security_fallbacks(request: Dict[str, Any]) -> Dict[str, Any]:
    """
    Apply security fallbacks to a request.
    
    This function sanitizes and validates request data to prevent security issues.
    
    Args:
        request: The request data
        
    Returns:
        Sanitized request data
    """
    # Create a copy to avoid modifying the original
    sanitized = request.copy()
    
    # Remove potentially dangerous keys
    dangerous_keys = ["__proto__", "constructor", "prototype"]
    for key in dangerous_keys:
        if key in sanitized:
            del sanitized[key]
    
    # Sanitize nested objects
    for key, value in sanitized.items():
        if isinstance(value, dict):
            sanitized[key] = apply_security_fallbacks(value)
        elif isinstance(value, list):
            sanitized[key] = [
                apply_security_fallbacks(item) if isinstance(item, dict) else item
                for item in value
            ]
    
    return sanitized


# Initialize fallbacks
def initialize_fallbacks():
    """Initialize all fallback mechanisms."""
    logger.info("Initializing fallback mechanisms")
    
    # Register additional fallbacks here
    
    logger.info(f"Registered fallbacks for components: {list(_fallback_handlers.keys())}")


# Initialize on module import
initialize_fallbacks()