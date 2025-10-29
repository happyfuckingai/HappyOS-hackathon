from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
import bcrypt
import uuid
import secrets
import logging

# Optional slowapi import for rate limiting
try:
    from slowapi import Limiter, _rate_limit_exceeded_handler
    from slowapi.util import get_remote_address
    from slowapi.errors import RateLimitExceeded
    SLOWAPI_AVAILABLE = True
except ImportError:
    SLOWAPI_AVAILABLE = False
    # Mock classes for when slowapi is not available
    class Limiter:
        def __init__(self, *args, **kwargs):
            pass
        def limit(self, *args, **kwargs):
            def decorator(func):
                return func
            return decorator
    
    class RateLimitExceeded(Exception):
        pass
    
    def get_remote_address(request):
        return "127.0.0.1"
    
    def _rate_limit_exceeded_handler(request, exc):
        return HTTPException(status_code=429, detail="Rate limit exceeded")

from ..database.connection import get_db, User, RefreshToken, RateLimit
from ..config.settings import settings
from ..models.base import User as UserModel, TokenPair

# Configure logging
logger = logging.getLogger(__name__)

# Use direct bcrypt for password hashing

# Initialize rate limiter
limiter = Limiter(key_func=get_remote_address)

# HTTP Bearer security
security = HTTPBearer()

class ProductionAuthService:
    """Production-grade authentication service with bcrypt, JWT rotation, and rate limiting"""
    
    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        """Verify password using bcrypt"""
        try:
            # Handle both bcrypt and legacy SHA256 hashes
            if hashed_password.startswith('$2b$'):
                # bcrypt hash
                return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))
            elif len(hashed_password) == 64:
                # Legacy SHA256 hash
                import hashlib
                return hashlib.sha256(plain_password.encode()).hexdigest() == hashed_password
            else:
                logger.warning(f"Unknown hash format: {hashed_password[:20]}...")
                return False
        except Exception as e:
            logger.error(f"Password verification error: {e}")
            return False
    
    @staticmethod
    def get_password_hash(password: str) -> str:
        """Hash password using bcrypt"""
        try:
            salt = bcrypt.gensalt()
            return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')
        except Exception as e:
            logger.error(f"Password hashing error: {e}")
            # Fallback to SHA256 for development
            import hashlib
            logger.warning("Falling back to SHA256 hashing - not recommended for production")
            return hashlib.sha256(password.encode()).hexdigest()
    
    @staticmethod
    def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
        """Create JWT access token with expiration"""
        to_encode = data.copy()
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        
        to_encode.update({
            "exp": expire,
            "iat": datetime.utcnow(),
            "type": "access"
        })
        
        try:
            encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
            return encoded_jwt
        except Exception as e:
            logger.error(f"Token creation error: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Token creation failed"
            )
    
    @staticmethod
    def create_refresh_token(user_id: str, db: Session) -> str:
        """Create JWT refresh token with database tracking"""
        jti = str(uuid.uuid4())
        expire = datetime.utcnow() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
        
        to_encode = {
            "sub": user_id,
            "exp": expire,
            "iat": datetime.utcnow(),
            "jti": jti,
            "type": "refresh"
        }
        
        try:
            # Create token
            encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
            
            # Store in database
            refresh_token_record = RefreshToken(
                id=str(uuid.uuid4()),
                user_id=user_id,
                jti=jti,
                expires_at=expire,
                revoked="false"
            )
            db.add(refresh_token_record)
            db.commit()
            
            return encoded_jwt
        except Exception as e:
            logger.error(f"Refresh token creation error: {e}")
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Refresh token creation failed"
            )
    
    @staticmethod
    def create_token_pair(user_data: dict, db: Session) -> TokenPair:
        """Create both access and refresh tokens"""
        access_token = ProductionAuthService.create_access_token(data=user_data)
        refresh_token = ProductionAuthService.create_refresh_token(user_data["sub"], db)
        
        return TokenPair(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
        )
    
    @staticmethod
    def verify_token(token: str) -> Optional[dict]:
        """Verify JWT token and return payload"""
        try:
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
            return payload
        except JWTError as e:
            logger.warning(f"Token verification failed: {e}")
            return None
    
    @staticmethod
    def refresh_tokens(refresh_token: str, db: Session) -> TokenPair:
        """Refresh tokens with rotation - invalidate old refresh token"""
        payload = ProductionAuthService.verify_token(refresh_token)
        if not payload or payload.get("type") != "refresh":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid refresh token"
            )
        
        jti = payload.get("jti")
        user_id = payload.get("sub")
        
        if not jti or not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid refresh token payload"
            )
        
        # Check if refresh token exists and is not revoked
        refresh_token_record = db.query(RefreshToken).filter(
            RefreshToken.jti == jti,
            RefreshToken.revoked == "false"
        ).first()
        
        if not refresh_token_record:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Refresh token not found or revoked"
            )
        
        # Check if token is expired
        if refresh_token_record.expires_at < datetime.utcnow():
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Refresh token expired"
            )
        
        # Get user data
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found"
            )
        
        try:
            # Revoke old refresh token
            refresh_token_record.revoked = "true"
            
            # Create new token pair
            user_data = {
                "sub": user.id,
                "username": user.username,
                "role": user.role
            }
            
            new_tokens = ProductionAuthService.create_token_pair(user_data, db)
            db.commit()
            
            return new_tokens
        except Exception as e:
            logger.error(f"Token refresh error: {e}")
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Token refresh failed"
            )
    
    @staticmethod
    def revoke_refresh_token(token_jti: str, db: Session) -> bool:
        """Revoke a refresh token"""
        try:
            refresh_token_record = db.query(RefreshToken).filter(
                RefreshToken.jti == token_jti
            ).first()
            
            if refresh_token_record:
                refresh_token_record.revoked = "true"
                db.commit()
                return True
            return False
        except Exception as e:
            logger.error(f"Token revocation error: {e}")
            db.rollback()
            return False

class RateLimitService:
    """Rate limiting service for authentication endpoints"""
    
    @staticmethod
    def check_rate_limit(key: str, limit: int, window_seconds: int, db: Session) -> bool:
        """Check if request is within rate limit"""
        now = datetime.utcnow()
        window_start = now - timedelta(seconds=window_seconds)
        
        # Clean up expired entries
        db.query(RateLimit).filter(RateLimit.expires_at < now).delete()
        
        # Get current count for this key
        rate_limit_record = db.query(RateLimit).filter(
            RateLimit.key == key,
            RateLimit.window_start >= window_start
        ).first()
        
        if not rate_limit_record:
            # Create new rate limit record
            rate_limit_record = RateLimit(
                id=str(uuid.uuid4()),
                key=key,
                count=1,
                window_start=now,
                expires_at=now + timedelta(seconds=window_seconds)
            )
            db.add(rate_limit_record)
            db.commit()
            return True
        
        if rate_limit_record.count >= limit:
            return False
        
        # Increment counter
        rate_limit_record.count += 1
        db.commit()
        return True
    
    @staticmethod
    def get_rate_limit_key(request: Request, endpoint: str) -> str:
        """Generate rate limit key based on IP and endpoint"""
        client_ip = get_remote_address(request)
        return f"{endpoint}:{client_ip}"

# Authentication dependency functions
def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> UserModel:
    """Get current authenticated user"""
    token = credentials.credentials
    payload = ProductionAuthService.verify_token(token)
    
    if not payload or payload.get("type") != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid access token",
            headers={"WWW-Authenticate": "Bearer"}
        )
    
    user_id: str = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
            headers={"WWW-Authenticate": "Bearer"}
        )
    
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"}
        )
    
    return UserModel(
        id=user.id,
        username=user.username,
        email=user.email,
        role=user.role
    )

def check_auth_rate_limit(request: Request, db: Session = Depends(get_db)):
    """Check rate limit for authentication endpoints"""
    key = RateLimitService.get_rate_limit_key(request, "auth")
    
    # 5 attempts per minute for auth endpoints
    if not RateLimitService.check_rate_limit(key, 5, 60, db):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many authentication attempts. Please try again later.",
            headers={"Retry-After": "60"}
        )

# Legacy functions for backward compatibility
def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Legacy function - use ProductionAuthService.verify_password instead"""
    return ProductionAuthService.verify_password(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    """Legacy function - use ProductionAuthService.get_password_hash instead"""
    return ProductionAuthService.get_password_hash(password)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Legacy function - use ProductionAuthService.create_access_token instead"""
    return ProductionAuthService.create_access_token(data, expires_delta)

def create_refresh_token(data: dict) -> str:
    """Legacy function - deprecated, use ProductionAuthService.create_refresh_token instead"""
    logger.warning("Using deprecated create_refresh_token function")
    # For backward compatibility, create a simple refresh token without DB tracking
    expire = datetime.utcnow() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode = data.copy()
    to_encode.update({"exp": expire, "type": "refresh"})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)

def verify_token(token: str) -> Optional[dict]:
    """Legacy function - use ProductionAuthService.verify_token instead"""
    return ProductionAuthService.verify_token(token)

def verify_jwt_token(token: str) -> dict:
    """
    Verify JWT token and return claims for MCP UI Hub
    
    Raises HTTPException if token is invalid or expired.
    Used by MCP UI Hub for tenant isolation and access control.
    """
    payload = ProductionAuthService.verify_token(token)
    
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"}
        )
    
    if payload.get("type") != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type",
            headers={"WWW-Authenticate": "Bearer"}
        )
    
    return payload

def verify_ui_scope(jwt_claims: dict, required_scope: str) -> bool:
    """
    Verify JWT token has required UI scope for MCP UI Hub operations
    
    Supports multi-tenant access control with scopes like:
    - ui:read:{tenantId}:{sessionId}
    - ui:write:{tenantId}:{sessionId}
    - ui:read:{tenantId}:*
    - ui:write:{tenantId}:*
    """
    scopes = jwt_claims.get("scopes", [])
    
    # Check exact scope match
    if required_scope in scopes:
        return True
    
    # Check wildcard scopes
    scope_parts = required_scope.split(":")
    if len(scope_parts) == 4:
        operation, resource, tenant_id, session_id = scope_parts
        wildcard_scope = f"{operation}:{resource}:{tenant_id}:*"
        if wildcard_scope in scopes:
            return True
    
    return False