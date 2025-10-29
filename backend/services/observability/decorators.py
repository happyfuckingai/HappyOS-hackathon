"""
Decorators for easy observability integration.
"""

import time
from functools import wraps
from typing import Callable, Any, Optional

from .logger import get_logger, log_execution_time
from .metrics import get_metrics_collector
from .tracing import get_tracing_manager, trace_operation


def observe_ai_call(provider: str, model: str, operation: str):
    """Decorator to observe AI/LLM calls with full observability."""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            logger = get_logger(func.__module__)
            metrics = get_metrics_collector()
            tracing = get_tracing_manager()
            
            # Start trace span
            span = tracing.trace_ai_call(provider, model, operation)
            
            start_time = time.time()
            tokens_used = 0
            cost = 0.0
            status = "success"
            
            try:
                # Execute the AI call
                result = await func(*args, **kwargs)
                
                # Extract metrics from result if available
                if isinstance(result, dict):
                    tokens_used = result.get('tokens_used', 0)
                    cost = result.get('cost', 0.0)
                
                duration_seconds = time.time() - start_time
                
                # Log AI call
                logger.log_ai_call(
                    provider=provider,
                    model=model,
                    tokens_used=tokens_used,
                    cost=cost,
                    duration_ms=duration_seconds * 1000,
                    operation=operation,
                    status=status
                )
                
                # Record metrics
                metrics.record_ai_request(
                    provider=provider,
                    model=model,
                    operation=operation,
                    status=status,
                    duration_seconds=duration_seconds,
                    tokens_used=tokens_used,
                    cost=cost
                )
                
                # Add span tags
                span.set_tag("ai.tokens_used", tokens_used)
                span.set_tag("ai.cost", cost)
                span.set_tag("ai.status", status)
                
                return result
                
            except Exception as e:
                status = "error"
                duration_seconds = time.time() - start_time
                
                # Log error
                logger.error(
                    f"AI call failed: {provider}/{model} {operation}",
                    ai_provider=provider,
                    ai_model=model,
                    ai_operation=operation,
                    duration_ms=duration_seconds * 1000,
                    error_type=type(e).__name__,
                    error_message=str(e)
                )
                
                # Record error metrics
                metrics.record_ai_request(
                    provider=provider,
                    model=model,
                    operation=operation,
                    status=status,
                    duration_seconds=duration_seconds
                )
                
                metrics.record_error(
                    error_type=type(e).__name__,
                    component="ai"
                )
                
                # Add error to span
                span.set_error(e)
                
                raise
            
            finally:
                tracing.finish_span(span)
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            logger = get_logger(func.__module__)
            metrics = get_metrics_collector()
            tracing = get_tracing_manager()
            
            # Start trace span
            span = tracing.trace_ai_call(provider, model, operation)
            
            start_time = time.time()
            tokens_used = 0
            cost = 0.0
            status = "success"
            
            try:
                # Execute the AI call
                result = func(*args, **kwargs)
                
                # Extract metrics from result if available
                if isinstance(result, dict):
                    tokens_used = result.get('tokens_used', 0)
                    cost = result.get('cost', 0.0)
                
                duration_seconds = time.time() - start_time
                
                # Log AI call
                logger.log_ai_call(
                    provider=provider,
                    model=model,
                    tokens_used=tokens_used,
                    cost=cost,
                    duration_ms=duration_seconds * 1000,
                    operation=operation,
                    status=status
                )
                
                # Record metrics
                metrics.record_ai_request(
                    provider=provider,
                    model=model,
                    operation=operation,
                    status=status,
                    duration_seconds=duration_seconds,
                    tokens_used=tokens_used,
                    cost=cost
                )
                
                # Add span tags
                span.set_tag("ai.tokens_used", tokens_used)
                span.set_tag("ai.cost", cost)
                span.set_tag("ai.status", status)
                
                return result
                
            except Exception as e:
                status = "error"
                duration_seconds = time.time() - start_time
                
                # Log error
                logger.error(
                    f"AI call failed: {provider}/{model} {operation}",
                    ai_provider=provider,
                    ai_model=model,
                    ai_operation=operation,
                    duration_ms=duration_seconds * 1000,
                    error_type=type(e).__name__,
                    error_message=str(e)
                )
                
                # Record error metrics
                metrics.record_ai_request(
                    provider=provider,
                    model=model,
                    operation=operation,
                    status=status,
                    duration_seconds=duration_seconds
                )
                
                metrics.record_error(
                    error_type=type(e).__name__,
                    component="ai"
                )
                
                # Add error to span
                span.set_error(e)
                
                raise
            
            finally:
                tracing.finish_span(span)
        
        # Return appropriate wrapper based on function type
        if hasattr(func, '__code__') and func.__code__.co_flags & 0x80:  # CO_COROUTINE
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator


def observe_db_query(query_type: str, table: str):
    """Decorator to observe database queries."""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            logger = get_logger(func.__module__)
            metrics = get_metrics_collector()
            tracing = get_tracing_manager()
            
            # Start trace span
            span = tracing.trace_db_query(query_type, table)
            
            start_time = time.time()
            status = "success"
            rows_affected = None
            
            try:
                result = await func(*args, **kwargs)
                
                # Try to extract rows affected from result
                if hasattr(result, 'rowcount'):
                    rows_affected = result.rowcount
                elif isinstance(result, (list, tuple)):
                    rows_affected = len(result)
                
                duration_seconds = time.time() - start_time
                
                # Log database query
                logger.log_database_query(
                    query_type=query_type,
                    table=table,
                    duration_ms=duration_seconds * 1000,
                    rows_affected=rows_affected
                )
                
                # Record metrics
                metrics.record_db_query(
                    query_type=query_type,
                    table=table,
                    status=status,
                    duration_seconds=duration_seconds
                )
                
                # Add span tags
                span.set_tag("db.rows_affected", rows_affected)
                span.set_tag("db.status", status)
                
                return result
                
            except Exception as e:
                status = "error"
                duration_seconds = time.time() - start_time
                
                # Log error
                logger.error(
                    f"Database query failed: {query_type} on {table}",
                    db_query_type=query_type,
                    db_table=table,
                    duration_ms=duration_seconds * 1000,
                    error_type=type(e).__name__,
                    error_message=str(e)
                )
                
                # Record error metrics
                metrics.record_db_query(
                    query_type=query_type,
                    table=table,
                    status=status,
                    duration_seconds=duration_seconds
                )
                
                metrics.record_error(
                    error_type=type(e).__name__,
                    component="database"
                )
                
                # Add error to span
                span.set_error(e)
                
                raise
            
            finally:
                tracing.finish_span(span)
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            logger = get_logger(func.__module__)
            metrics = get_metrics_collector()
            tracing = get_tracing_manager()
            
            # Start trace span
            span = tracing.trace_db_query(query_type, table)
            
            start_time = time.time()
            status = "success"
            rows_affected = None
            
            try:
                result = func(*args, **kwargs)
                
                # Try to extract rows affected from result
                if hasattr(result, 'rowcount'):
                    rows_affected = result.rowcount
                elif isinstance(result, (list, tuple)):
                    rows_affected = len(result)
                
                duration_seconds = time.time() - start_time
                
                # Log database query
                logger.log_database_query(
                    query_type=query_type,
                    table=table,
                    duration_ms=duration_seconds * 1000,
                    rows_affected=rows_affected
                )
                
                # Record metrics
                metrics.record_db_query(
                    query_type=query_type,
                    table=table,
                    status=status,
                    duration_seconds=duration_seconds
                )
                
                # Add span tags
                span.set_tag("db.rows_affected", rows_affected)
                span.set_tag("db.status", status)
                
                return result
                
            except Exception as e:
                status = "error"
                duration_seconds = time.time() - start_time
                
                # Log error
                logger.error(
                    f"Database query failed: {query_type} on {table}",
                    db_query_type=query_type,
                    db_table=table,
                    duration_ms=duration_seconds * 1000,
                    error_type=type(e).__name__,
                    error_message=str(e)
                )
                
                # Record error metrics
                metrics.record_db_query(
                    query_type=query_type,
                    table=table,
                    status=status,
                    duration_seconds=duration_seconds
                )
                
                metrics.record_error(
                    error_type=type(e).__name__,
                    component="database"
                )
                
                # Add error to span
                span.set_error(e)
                
                raise
            
            finally:
                tracing.finish_span(span)
        
        # Return appropriate wrapper based on function type
        if hasattr(func, '__code__') and func.__code__.co_flags & 0x80:  # CO_COROUTINE
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator


def observe_worker_task(task_type: str):
    """Decorator to observe worker task execution."""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            logger = get_logger(func.__module__)
            metrics = get_metrics_collector()
            tracing = get_tracing_manager()
            
            # Generate task ID
            task_id = f"{task_type}_{int(time.time())}"
            
            # Start trace span
            span = tracing.trace_worker_task(task_type, task_id)
            
            start_time = time.time()
            status = "success"
            
            try:
                result = await func(*args, **kwargs)
                
                duration_seconds = time.time() - start_time
                
                # Log worker task
                logger.log_worker_task(
                    task_type=task_type,
                    task_id=task_id,
                    status=status,
                    duration_ms=duration_seconds * 1000
                )
                
                # Record metrics
                metrics.record_worker_task(
                    task_type=task_type,
                    status=status,
                    duration_seconds=duration_seconds
                )
                
                # Add span tags
                span.set_tag("worker.status", status)
                
                return result
                
            except Exception as e:
                status = "error"
                duration_seconds = time.time() - start_time
                
                # Log error
                logger.error(
                    f"Worker task failed: {task_type}",
                    worker_task_type=task_type,
                    worker_task_id=task_id,
                    duration_ms=duration_seconds * 1000,
                    error_type=type(e).__name__,
                    error_message=str(e)
                )
                
                # Record error metrics
                metrics.record_worker_task(
                    task_type=task_type,
                    status=status,
                    duration_seconds=duration_seconds
                )
                
                metrics.record_error(
                    error_type=type(e).__name__,
                    component="worker"
                )
                
                # Add error to span
                span.set_error(e)
                
                raise
            
            finally:
                tracing.finish_span(span)
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            logger = get_logger(func.__module__)
            metrics = get_metrics_collector()
            tracing = get_tracing_manager()
            
            # Generate task ID
            task_id = f"{task_type}_{int(time.time())}"
            
            # Start trace span
            span = tracing.trace_worker_task(task_type, task_id)
            
            start_time = time.time()
            status = "success"
            
            try:
                result = func(*args, **kwargs)
                
                duration_seconds = time.time() - start_time
                
                # Log worker task
                logger.log_worker_task(
                    task_type=task_type,
                    task_id=task_id,
                    status=status,
                    duration_ms=duration_seconds * 1000
                )
                
                # Record metrics
                metrics.record_worker_task(
                    task_type=task_type,
                    status=status,
                    duration_seconds=duration_seconds
                )
                
                # Add span tags
                span.set_tag("worker.status", status)
                
                return result
                
            except Exception as e:
                status = "error"
                duration_seconds = time.time() - start_time
                
                # Log error
                logger.error(
                    f"Worker task failed: {task_type}",
                    worker_task_type=task_type,
                    worker_task_id=task_id,
                    duration_ms=duration_seconds * 1000,
                    error_type=type(e).__name__,
                    error_message=str(e)
                )
                
                # Record error metrics
                metrics.record_worker_task(
                    task_type=task_type,
                    status=status,
                    duration_seconds=duration_seconds
                )
                
                metrics.record_error(
                    error_type=type(e).__name__,
                    component="worker"
                )
                
                # Add error to span
                span.set_error(e)
                
                raise
            
            finally:
                tracing.finish_span(span)
        
        # Return appropriate wrapper based on function type
        if hasattr(func, '__code__') and func.__code__.co_flags & 0x80:  # CO_COROUTINE
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator