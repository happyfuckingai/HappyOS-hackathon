"""
FastAPI middleware for observability integration.
"""

import time
import uuid
from typing import Callable
from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from .logger import get_logger, LogContext
from .metrics import get_metrics_collector
from .tracing import get_tracing_manager


class ObservabilityMiddleware(BaseHTTPMiddleware):
    """Middleware to add observability to all HTTP requests."""
    
    def __init__(self, app, exclude_paths: list = None):
        super().__init__(app)
        self.logger = get_logger(__name__)
        self.metrics = get_metrics_collector()
        self.tracing = get_tracing_manager()
        self.exclude_paths = exclude_paths or ["/health", "/metrics", "/docs", "/openapi.json"]
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request with full observability."""
        
        # Skip observability for excluded paths
        if any(request.url.path.startswith(path) for path in self.exclude_paths):
            return await call_next(request)
        
        # Generate request ID
        request_id = str(uuid.uuid4())
        
        # Extract user and meeting IDs from request if available
        user_id = None
        meeting_id = None
        
        # Try to extract from headers
        if "x-user-id" in request.headers:
            user_id = request.headers["x-user-id"]
        if "x-meeting-id" in request.headers:
            meeting_id = request.headers["x-meeting-id"]
        
        # Try to extract from path parameters
        if "/meetings/" in request.url.path:
            path_parts = request.url.path.split("/")
            if "meetings" in path_parts:
                meeting_index = path_parts.index("meetings")
                if meeting_index + 1 < len(path_parts):
                    meeting_id = path_parts[meeting_index + 1]
        
        # Start timing
        start_time = time.time()
        
        # Create logging context
        with LogContext(request_id=request_id, meeting_id=meeting_id, user_id=user_id):
            # Start trace
            trace_span = self.tracing.trace_http_request(
                method=request.method,
                path=request.url.path,
                user_id=user_id,
                meeting_id=meeting_id,
                request_id=request_id
            )
            
            try:
                # Add request details to span
                trace_span.set_tag("http.url", str(request.url))
                trace_span.set_tag("http.user_agent", request.headers.get("user-agent", ""))
                trace_span.set_tag("http.remote_addr", request.client.host if request.client else "")
                
                # Log request start
                self.logger.info(
                    f"Request started: {request.method} {request.url.path}",
                    http_method=request.method,
                    http_path=request.url.path,
                    http_query_params=str(request.query_params),
                    http_user_agent=request.headers.get("user-agent", ""),
                    http_remote_addr=request.client.host if request.client else ""
                )
                
                # Process request
                response = await call_next(request)
                
                # Calculate duration
                duration_seconds = time.time() - start_time
                duration_ms = duration_seconds * 1000
                
                # Add response details to span
                trace_span.set_tag("http.status_code", response.status_code)
                trace_span.set_tag("http.response_size", response.headers.get("content-length", 0))
                
                # Record metrics
                self.metrics.record_http_request(
                    method=request.method,
                    endpoint=request.url.path,
                    status_code=response.status_code,
                    duration_seconds=duration_seconds
                )
                
                # Log request completion
                self.logger.log_request(
                    method=request.method,
                    path=request.url.path,
                    status_code=response.status_code,
                    duration_ms=duration_ms,
                    response_size=response.headers.get("content-length", 0)
                )
                
                # Add observability headers to response
                response.headers["x-request-id"] = request_id
                response.headers["x-response-time"] = f"{duration_ms:.2f}ms"
                
                return response
                
            except Exception as e:
                # Calculate duration for error case
                duration_seconds = time.time() - start_time
                duration_ms = duration_seconds * 1000
                
                # Record error in span and metrics
                trace_span.set_error(e)
                self.metrics.record_error(
                    error_type=type(e).__name__,
                    component="http"
                )
                
                # Record error metrics
                self.metrics.record_http_request(
                    method=request.method,
                    endpoint=request.url.path,
                    status_code=500,
                    duration_seconds=duration_seconds
                )
                
                # Log error
                self.logger.error(
                    f"Request failed: {request.method} {request.url.path}",
                    http_method=request.method,
                    http_path=request.url.path,
                    duration_ms=duration_ms,
                    error_type=type(e).__name__,
                    error_message=str(e),
                    exc_info=True
                )
                
                # Return error response
                return JSONResponse(
                    status_code=500,
                    content={
                        "detail": "Internal server error",
                        "request_id": request_id,
                        "error_type": type(e).__name__
                    },
                    headers={
                        "x-request-id": request_id,
                        "x-response-time": f"{duration_ms:.2f}ms"
                    }
                )
            
            finally:
                # Finish trace span
                self.tracing.finish_span(trace_span)


class MetricsEndpointMiddleware:
    """Middleware to expose Prometheus metrics endpoint."""
    
    def __init__(self, app):
        self.app = app
        self.metrics = get_metrics_collector()
    
    async def __call__(self, scope, receive, send):
        """Handle metrics endpoint requests."""
        
        if scope["type"] == "http" and scope["path"] == "/metrics":
            # Generate metrics response
            metrics_data = self.metrics.get_metrics()
            
            response = {
                "type": "http.response.start",
                "status": 200,
                "headers": [
                    [b"content-type", b"text/plain; version=0.0.4; charset=utf-8"],
                    [b"content-length", str(len(metrics_data)).encode()],
                ],
            }
            await send(response)
            
            await send({
                "type": "http.response.body",
                "body": metrics_data,
            })
            return
        
        # Pass through to main app
        await self.app(scope, receive, send)