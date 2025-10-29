from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from datetime import datetime
import uuid
try:
    from backend.modules.auth import (
        ProductionAuthService, 
        get_current_user, 
        check_auth_rate_limit
    )
    from backend.modules.database import get_db, User
    from backend.modules.models import LoginRequest, TokenResponse, RefreshTokenRequest, User as UserModel
except ImportError:
    import sys
    import os
    sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
    from backend.modules.auth import (
        ProductionAuthService, 
        get_current_user, 
        check_auth_rate_limit
    )
    from backend.modules.database import get_db, User
    from backend.modules.models import LoginRequest, TokenResponse, RefreshTokenRequest, User as UserModel
import logging

logger = logging.getLogger(__name__)
router = APIRouter()

@router.post("/login", response_model=TokenResponse)
async def login(
    request: LoginRequest,
    http_request: Request,
    db: Session = Depends(get_db),
    _: None = Depends(check_auth_rate_limit)
):
    """Production-grade login with bcrypt password verification and rate limiting"""
    try:
        # Get user from local database
        user = db.query(User).filter(User.email == request.email).first()
        
        if not user:
            # For demo purposes, create user if doesn't exist
            user = User(
                id=f"user_{uuid.uuid4()}",
                username=request.email.split('@')[0],
                email=request.email,
                password_hash=ProductionAuthService.get_password_hash(request.password),
                role="user"
            )
            db.add(user)
            db.commit()
            db.refresh(user)
            logger.info(f"Created new user: {user.email}")
        else:
            # Verify password for existing user
            if not ProductionAuthService.verify_password(request.password, user.password_hash):
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid email or password"
                )
        
        # Create token pair with database tracking
        user_data = {
            "sub": user.id,
            "username": user.username,
            "role": user.role
        }
        
        tokens = ProductionAuthService.create_token_pair(user_data, db)
        
        return TokenResponse(
            access_token=tokens.access_token,
            refresh_token=tokens.refresh_token,
            expires_in=tokens.expires_in
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Login error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Login failed"
        )

@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    request: RefreshTokenRequest,
    http_request: Request,
    db: Session = Depends(get_db),
    _: None = Depends(check_auth_rate_limit)
):
    """Refresh tokens with rotation - invalidates old refresh token"""
    try:
        tokens = ProductionAuthService.refresh_tokens(request.refresh_token, db)
        
        return TokenResponse(
            access_token=tokens.access_token,
            refresh_token=tokens.refresh_token,
            expires_in=tokens.expires_in
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Token refresh error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Token refresh failed"
        )

@router.post("/logout")
async def logout(
    request: RefreshTokenRequest,
    db: Session = Depends(get_db)
):
    """Logout by revoking refresh token"""
    try:
        payload = ProductionAuthService.verify_token(request.refresh_token)
        if payload and payload.get("jti"):
            ProductionAuthService.revoke_refresh_token(payload["jti"], db)
        
        return {"message": "Successfully logged out"}
        
    except Exception as e:
        logger.error(f"Logout error: {e}")
        # Don't fail logout even if token revocation fails
        return {"message": "Logged out"}

@router.get("/me", response_model=UserModel)
async def get_me(current_user: UserModel = Depends(get_current_user)):
    """Get current user information"""
    return current_user

@router.patch("/me/preferences")
async def update_user_preferences(
    preferences: dict,
    current_user: UserModel = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update user UI preferences (popup positions, settings, etc.)"""
    try:
        # Update preferences in local database
        user = db.query(User).filter(User.id == current_user.id).first()
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
        
        user.ui_preferences = preferences
        db.commit()
        
        return {"success": True, "preferences": preferences}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Preference update error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update preferences"
        )