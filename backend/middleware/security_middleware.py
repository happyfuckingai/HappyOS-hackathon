"""
Security Middleware for Advanced Security Features

This middleware integrates all security features:
- API key validation
- Request signature verification
- IP whitelisting and geographic restrictions
- Threat detection and prevention
- Audit logging for all requests
"""

import time
import logging
from typing import Callable, Optional
from fastapi import Request, Response, HTTPException, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from backend.config.security_config import get_global_security_config
from backend.services.infrastructure.api_key_manager import get_api_key_manager
from backend.services.infrastructure.request_signing import get_request_signer, SignatureMiddleware
from backend.services.infrastructure.audit_logger import get_audit_logger, AuditEventType, AuditSeverity, AuditOutcome, AuditContext
from backend.services.infrastructure.ip_whitelist import get_ip_whitelist_manager
from backend.services.infrastructure.threat_detection import get_threat_detector
from backend.modules.database.connection import get_db

logger = logging.getLogger(__name__)


class SecurityMiddleware(BaseHTTPMiddleware):
    """
    Comprehensive security middleware that integrates all security features.
    
    Features:
    - API key validation for protected endpoints
    - Request signature verification
    - IP whitelisting and geographic restrictions
    - Real-time threat detection and prevention
    - Comprehensive audit logging
    """
    
    def __init__(self, app, config=None):
        super().__init__(app)
        self.config = config or get_global_security_config()
        
        # Initialize security services
        self.api_key_manager = None
        self.request_signer = None
        self.signature_middleware = None
        self.audit_logger = None
        self.ip_whitelist_manager = None
        self.threat_detector = None
        
        # Protected endpoints that require API key
        self.protected_endpoints = [
            "/api/admin/",
            "/api/security/",
            "/api/meetings/*/export",
            "/api/mem0/",
            "/api/webhooks/"
        ]
        
        # Public endpoints that don't require security checks
        self.public_endpoints = [
            "/health",
            "/docs",
            "/openapi.json",
            "/api/auth/login",
            "/api/auth/register",
            "/api/auth/refresh"
        ]
    
    async def initialize_services(self):
        """Initialize security services lazily"""
        if self.config.enable_api_key_management and not self.api_key_manager:
            self.api_key_manager = await get_api_key_manager()
        
        if self.config.enable_request_signing and not self.request_signer:
            self.request_signer = get_request_signer()
            self.signature_middleware = SignatureMiddleware(self.request_signer)
        
        if self.config.enable_audit_logging and not self.audit_logger:
            self.audit_logger = await get_audit_logger()
        
        if self.config.enable_ip_whitelisting and not self.ip_whitelist_manager:
            self.ip_whitelist_manager = await get_ip_whitelist_manager()
        
        if self.config.enable_threat_detection and not self.threat_detector:
            self.threat_detector = await get_threat_detector()
    
    def _is_public_endpoint(self, path: str) -> bool:
        """Check if endpoint is public and doesn't require security checks"""
        return any(path.startswith(endpoint) for endpoint in self.public_endpoints)
    
    def _is_protected_endpoint(self, path: str) -> bool:
        """Check if endpoint requires API key authentication"""
        return any(path.startswith(endpoint) for endpoint in self.protected_endpoints)
    
    def _get_client_ip(self, request: Request) -> str:
        """Extract client IP address from request"""
        # Check for forwarded IP (proxy/load balancer)
        forwarded_for = request.headers.get("x-forwarded-for")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()
        
        # Check for real IP header
        real_ip = request.headers.get("x-real-ip")
        if real_ip:
            return real_ip
        
        # Fall back to direct client IP
        return str(request.client.host)
    
    async def _validate_api_key(self, request: Request) -> Optional[dict]:
        """Validate API key from request headers"""
        if not self.api_key_manager:
            return None
        
        # Get API key from Authorization header
        auth_header = request.headers.get("authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            return None
        
        api_key = auth_header[7:]  # Remove "Bearer " prefix
        
        # Validate API key
        db = next(get_db())
        try:
            api_key_record = await self.api_key_manager.verify_api_key(api_key, db)
            if api_key_record:
                return {
                    "key_id": api_key_record.key_id,
                    "name": api_key_record.name,
                    "permissions": api_key_record.permissions,
                    "rate_limit": api_key_record.rate_limit
                }
            return None
        finally:
            db.close()
    
    async def _check_ip_access(self, request: Request, api_key_info: Optional[dict] = None) -> tuple[bool, Optional[str]]:
        """Check IP access restrictions"""
        if not self.ip_whitelist_manager:
            return True, None
        
        client_ip = self._get_client_ip(request)
        
        access_granted, reason, location = await self.ip_whitelist_manager.check_ip_access(
            ip=client_ip,
            request=request,
            api_key_id=api_key_info.get("key_id") if api_key_info else None,
            endpoint=request.url.path
        )
        
        # Store IP location in request state for later use
        request.state.client_ip = client_ip
        request.state.ip_location = location
        
        return access_granted, reason
    
    async def _check_threat_detection(self, request: Request, response_status: int, response_time: float) -> Optional[dict]:
        """Check for threats in the request"""
        if not self.threat_detector:
            return None
        
        # Check if IP/user is already blocked
        client_ip = self._get_client_ip(request)
        user_id = getattr(request.state, 'user_id', None)
        session_id = getattr(request.state, 'session_id', None)
        
        is_blocked, block_reason = await self.threat_detector.is_blocked(client_ip, user_id, session_id)
        if is_blocked:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=block_reason
            )
        
        # Analyze request for threats
        threat_event = await self.threat_detector.analyze_request(
            request=request,
            user_id=user_id,
            session_id=session_id,
            response_status=response_status,
            response_time=response_time
        )
        
        if threat_event:
            return {
                "event_id": threat_event.event_id,
                "threat_type": threat_event.threat_type.value,
                "severity": threat_event.severity.value,
                "confidence": threat_event.confidence
            }
        
        return None
    
    async def _log_request(
        self,
        request: Request,
        response_status: int,
        response_time: float,
        api_key_info: Optional[dict] = None,
        threat_info: Optional[dict] = None,
        error: Optional[str] = None
    ):
        """Log request to audit system"""
        if not self.audit_logger:
            return
        
        client_ip = self._get_client_ip(request)
        
        # Create audit context
        context = AuditContext(
            user_id=getattr(request.state, 'user_id', None),
            session_id=getattr(request.state, 'session_id', None),
            api_key_id=api_key_info.get("key_id") if api_key_info else None,
            client_ip=client_ip,
            user_agent=request.headers.get("user-agent"),
            request_id=request.headers.get("x-request-id")
        )
        
        # Determine event type and outcome
        if error:
            event_type = AuditEventType.SECURITY_INCIDENT
            outcome = AuditOutcome.FAILURE
            severity = AuditSeverity.HIGH
            description = f"Security error: {error}"
        elif threat_info:
            event_type = AuditEventType.SECURITY_INCIDENT
            outcome = AuditOutcome.FAILURE
            severity = AuditSeverity.HIGH if threat_info["severity"] in ["high", "critical"] else AuditSeverity.MEDIUM
            description = f"Threat detected: {threat_info['threat_type']}"
        elif response_status >= 400:
            event_type = AuditEventType.DATA_ACCESS
            outcome = AuditOutcome.FAILURE
            severity = AuditSeverity.MEDIUM
            description = f"Failed request: {request.method} {request.url.path}"
        else:
            event_type = AuditEventType.DATA_ACCESS
            outcome = AuditOutcome.SUCCESS
            severity = AuditSeverity.LOW
            description = f"Successful request: {request.method} {request.url.path}"
        
        # Prepare details
        details = {
            "method": request.method,
            "path": request.url.path,
            "query_params": str(request.url.query) if request.url.query else None,
            "response_status": response_status,
            "response_time": response_time,
            "user_agent": request.headers.get("user-agent"),
            "referer": request.headers.get("referer")
        }
        
        if api_key_info:
            details["api_key_name"] = api_key_info["name"]
        
        if threat_info:
            details["threat_info"] = threat_info
        
        if error:
            details["error"] = error
        
        # Log the event
        db = next(get_db())
        try:
            await self.audit_logger.log_event(
                event_type=event_type,
                action=f"{request.method} {request.url.path}",
                description=description,
                context=context,
                severity=severity,
                outcome=outcome,
                details=details,
                db=db
            )
        finally:
            db.close()
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Main middleware dispatch method"""
        start_time = time.time()
        
        try:
            # Initialize services if needed
            await self.initialize_services()
            
            # Skip security checks for public endpoints
            if self._is_public_endpoint(request.url.path):
                response = await call_next(request)
                return response
            
            # 1. IP Whitelisting Check
            if self.config.enable_ip_whitelisting:
                access_granted, access_reason = await self._check_ip_access(request)
                if not access_granted:
                    await self._log_request(
                        request, 403, time.time() - start_time,
                        error=f"IP access denied: {access_reason}"
                    )
                    return JSONResponse(
                        status_code=status.HTTP_403_FORBIDDEN,
                        content={"error": "Access denied", "reason": access_reason}
                    )
            
            # 2. API Key Validation (for protected endpoints)
            api_key_info = None
            if self.config.enable_api_key_management and self._is_protected_endpoint(request.url.path):
                api_key_info = await self._validate_api_key(request)
                if not api_key_info:
                    await self._log_request(
                        request, 401, time.time() - start_time,
                        error="Invalid or missing API key"
                    )
                    return JSONResponse(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        content={"error": "Invalid or missing API key"}
                    )
                
                # Store API key info in request state
                request.state.api_key_info = api_key_info
            
            # 3. Request Signature Validation (if enabled and required)
            if (self.config.enable_request_signing and 
                self.signature_middleware and 
                api_key_info and 
                self.signature_middleware.should_validate_signature(request.url.path)):
                
                # Create mock API key record for signature validation
                mock_api_key = type('MockAPIKey', (), {
                    'key_hash': api_key_info['key_id']  # Use key_id as hash for validation
                })()
                
                try:
                    signature_valid = await self.signature_middleware.validate_request(request, mock_api_key)
                    if not signature_valid:
                        await self._log_request(
                            request, 401, time.time() - start_time,
                            api_key_info=api_key_info,
                            error="Invalid request signature"
                        )
                        return JSONResponse(
                            status_code=status.HTTP_401_UNAUTHORIZED,
                            content={"error": "Invalid request signature"}
                        )
                except Exception as e:
                    logger.error(f"Signature validation error: {e}")
                    await self._log_request(
                        request, 500, time.time() - start_time,
                        api_key_info=api_key_info,
                        error=f"Signature validation error: {str(e)}"
                    )
                    return JSONResponse(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        content={"error": "Signature validation failed"}
                    )
            
            # 4. Process the request
            response = await call_next(request)
            response_time = time.time() - start_time
            
            # 5. Threat Detection (post-request analysis)
            threat_info = None
            if self.config.enable_threat_detection:
                try:
                    threat_info = await self._check_threat_detection(
                        request, response.status_code, response_time
                    )
                    
                    if threat_info:
                        # Add threat headers for monitoring
                        response.headers["X-Threat-Detected"] = threat_info["threat_type"]
                        response.headers["X-Threat-Severity"] = threat_info["severity"]
                        response.headers["X-Threat-Confidence"] = str(threat_info["confidence"])
                        
                except Exception as e:
                    logger.error(f"Threat detection error: {e}")
            
            # 6. Audit Logging
            if self.config.enable_audit_logging:
                try:
                    await self._log_request(
                        request, response.status_code, response_time,
                        api_key_info=api_key_info,
                        threat_info=threat_info
                    )
                except Exception as e:
                    logger.error(f"Audit logging error: {e}")
            
            # Add security headers
            response.headers["X-Content-Type-Options"] = "nosniff"
            response.headers["X-Frame-Options"] = "DENY"
            response.headers["X-XSS-Protection"] = "1; mode=block"
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
            response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
            
            return response
            
        except HTTPException:
            # Re-raise HTTP exceptions (like blocked IPs)
            raise
        except Exception as e:
            logger.error(f"Security middleware error: {e}")
            response_time = time.time() - start_time
            
            # Log the error
            if self.config.enable_audit_logging:
                try:
                    await self._log_request(
                        request, 500, response_time,
                        error=f"Middleware error: {str(e)}"
                    )
                except:
                    pass  # Don't fail if audit logging fails
            
            # Return generic error response
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={"error": "Internal security error"}
            )


def create_security_middleware(app, config=None):
    """Factory function to create security middleware"""
    return SecurityMiddleware(app, config)


# Rate limiting middleware (separate from main security middleware for performance)
class RateLimitMiddleware(BaseHTTPMiddleware):
    """Rate limiting middleware using the production rate limiter"""
    
    def __init__(self, app):
        super().__init__(app)
        self.rate_limiter = None
    
    async def initialize_rate_limiter(self):
        """Initialize rate limiter lazily"""
        if not self.rate_limiter:
            from backend.services.infrastructure.rate_limiter import get_rate_limiter
            self.rate_limiter = await get_rate_limiter()
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Rate limiting dispatch"""
        try:
            await self.initialize_rate_limiter()
            
            # Check rate limits
            result = await self.rate_limiter.check_rate_limit(request)
            
            if not result.allowed:
                # Return rate limit exceeded response
                return self.rate_limiter.create_rate_limit_response(result)
            
            # Process request
            response = await call_next(request)
            
            # Add rate limit headers
            headers = self.rate_limiter.get_rate_limit_headers(result)
            for key, value in headers.items():
                response.headers[key] = value
            
            return response
            
        except Exception as e:
            logger.error(f"Rate limiting error: {e}")
            # Continue without rate limiting on error
            return await call_next(request)