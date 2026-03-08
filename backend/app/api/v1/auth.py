"""Authentication API routes - Nigeria Friendly Version (Custom JWT Auth)."""

from datetime import timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Header, Request
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from app.core.exceptions import AuthenticationException, ValidationException
from app.core.logging import get_logger
from app.core.security import (
    create_access_token,
    create_refresh_token,
    verify_token,
    get_password_hash,
    verify_password,
)
from app.db.base import get_db
from app.models.user import User, UserSettings, SubscriptionTier

logger = get_logger(__name__)
router = APIRouter()


# Request/Response Models
class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    display_name: Optional[str] = None


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class SocialLoginRequest(BaseModel):
    provider: str  # google, apple
    token: str
    email: Optional[str] = None
    display_name: Optional[str] = None


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    user: dict


class UserResponse(BaseModel):
    id: str
    email: str
    display_name: Optional[str]
    subscription_tier: str
    credits: int


class PasswordResetRequest(BaseModel):
    email: EmailStr


class PasswordResetConfirm(BaseModel):
    token: str
    new_password: str


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


def get_or_create_user(
    db: Session,
    email: str,
    display_name: Optional[str] = None,
    password: Optional[str] = None,
) -> User:
    """Get existing user or create new one."""
    user = db.query(User).filter(User.email == email).first()
    
    if not user:
        import uuid
        user = User(
            id=str(uuid.uuid4()),
            email=email,
            display_name=display_name,
            subscription_tier=SubscriptionTier.FREE,
            credits=0,
        )
        
        # Hash password if provided
        if password:
            user.password_hash = get_password_hash(password)
        
        db.add(user)
        db.commit()
        db.refresh(user)
        
        # Create default settings
        settings = UserSettings(
            id=str(uuid.uuid4()),
            user_id=user.id,
        )
        db.add(settings)
        db.commit()
        
        logger.info("New user created", user_id=user.id, email=email)
    
    return user


@router.post("/register", response_model=TokenResponse)
async def register(
    request: RegisterRequest,
    db: Session = Depends(get_db),
):
    """Register new user with email and password."""
    # Check if user exists
    existing_user = db.query(User).filter(User.email == request.email).first()
    if existing_user:
        raise ValidationException("Email already registered")
    
    # Validate password
    if len(request.password) < 8:
        raise ValidationException("Password must be at least 8 characters")
    
    # Create user with hashed password
    import uuid
    user = User(
        id=str(uuid.uuid4()),
        email=request.email,
        display_name=request.display_name,
        subscription_tier=SubscriptionTier.FREE,
        credits=0,
    )
    user.password_hash = get_password_hash(request.password)
    
    db.add(user)
    db.commit()
    db.refresh(user)
    
    # Create default settings
    settings = UserSettings(
        id=str(uuid.uuid4()),
        user_id=user.id,
    )
    db.add(settings)
    db.commit()
    
    logger.info("User registered", user_id=user.id, email=request.email)
    
    # Generate tokens
    access_token = create_access_token({"sub": user.id, "email": user.email})
    refresh_token = create_refresh_token({"sub": user.id})
    
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=60 * 24 * 7,  # 7 days
        user={
            "id": user.id,
            "email": user.email,
            "display_name": user.display_name,
            "subscription_tier": user.subscription_tier.value,
            "credits": user.credits,
        },
    )


@router.post("/login", response_model=TokenResponse)
async def login(
    request: LoginRequest,
    db: Session = Depends(get_db),
):
    """Login with email and password."""
    # Find user
    user = db.query(User).filter(User.email == request.email).first()
    if not user:
        raise AuthenticationException("Invalid email or password")
    
    # Verify password
    if not hasattr(user, 'password_hash') or not user.password_hash:
        raise AuthenticationException("Please set a password first")
    
    if not verify_password(request.password, user.password_hash):
        raise AuthenticationException("Invalid email or password")
    
    # Update last login
    from datetime import datetime
    user.last_login_at = datetime.utcnow()
    db.commit()
    
    logger.info("User logged in", user_id=user.id, email=request.email)
    
    # Generate tokens
    access_token = create_access_token({"sub": user.id, "email": user.email})
    refresh_token = create_refresh_token({"sub": user.id})
    
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=60 * 24 * 7,  # 7 days
        user={
            "id": user.id,
            "email": user.email,
            "display_name": user.display_name,
            "subscription_tier": user.subscription_tier.value,
            "credits": user.credits,
        },
    )


@router.post("/social-login", response_model=TokenResponse)
async def social_login(
    request: SocialLoginRequest,
    db: Session = Depends(get_db),
):
    """Login with social provider (Google, Apple) - Simplified for Nigeria."""
    # For Nigeria version, we accept social login tokens directly
    # In production, you should verify these tokens with Google/Apple
    # For now, we trust the frontend verification
    
    if not request.email:
        raise AuthenticationException("Email not provided")
    
    # Get or create user
    user = get_or_create_user(
        db,
        email=request.email,
        display_name=request.display_name,
    )
    
    # Update last login
    from datetime import datetime
    user.last_login_at = datetime.utcnow()
    db.commit()
    
    logger.info("Social login successful", user_id=user.id, provider=request.provider)
    
    # Generate tokens
    access_token = create_access_token({"sub": user.id, "email": user.email})
    refresh_token = create_refresh_token({"sub": user.id})
    
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=60 * 24 * 7,
        user={
            "id": user.id,
            "email": user.email,
            "display_name": user.display_name,
            "subscription_tier": user.subscription_tier.value,
            "credits": user.credits,
        },
    )


@router.post("/refresh")
async def refresh_token(refresh_token: str):
    """Refresh access token."""
    try:
        payload = verify_token(refresh_token, token_type="refresh")
        user_id = payload.get("sub")
        
        # Generate new access token
        access_token = create_access_token({"sub": user_id})
        
        return {
            "access_token": access_token,
            "token_type": "bearer",
            "expires_in": 60 * 24 * 7,
        }
        
    except Exception as e:
        raise AuthenticationException("Invalid refresh token")


@router.post("/logout")
async def logout(
    authorization: str = Header(None),
):
    """Logout user (invalidate token)."""
    # In a production app, you might want to blacklist the token
    # For now, we just return success
    return {"message": "Logged out successfully"}


@router.get("/me", response_model=UserResponse)
async def get_current_user(
    authorization: str = Header(None),
    db: Session = Depends(get_db),
):
    """Get current authenticated user."""
    if not authorization or not authorization.startswith("Bearer "):
        raise AuthenticationException("Authorization header required")
    
    token = authorization.split(" ")[1]
    payload = verify_token(token)
    user_id = payload.get("sub")
    
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise AuthenticationException("User not found")
    
    return UserResponse(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        subscription_tier=user.subscription_tier.value,
        credits=user.credits,
    )


@router.post("/change-password")
async def change_password(
    request: ChangePasswordRequest,
    authorization: str = Header(None),
    db: Session = Depends(get_db),
):
    """Change user password."""
    if not authorization or not authorization.startswith("Bearer "):
        raise AuthenticationException("Authorization header required")
    
    token = authorization.split(" ")[1]
    payload = verify_token(token)
    user_id = payload.get("sub")
    
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise AuthenticationException("User not found")
    
    # Verify current password
    if not hasattr(user, 'password_hash') or not user.password_hash:
        raise AuthenticationException("No password set")
    
    if not verify_password(request.current_password, user.password_hash):
        raise AuthenticationException("Current password is incorrect")
    
    # Validate new password
    if len(request.new_password) < 8:
        raise ValidationException("Password must be at least 8 characters")
    
    # Update password
    user.password_hash = get_password_hash(request.new_password)
    db.commit()
    
    logger.info("Password changed", user_id=user.id)
    
    return {"message": "Password changed successfully"}


@router.post("/forgot-password")
async def forgot_password(
    request: PasswordResetRequest,
    db: Session = Depends(get_db),
):
    """Request password reset - Sends email with reset token."""
    user = db.query(User).filter(User.email == request.email).first()
    
    if not user:
        # Don't reveal if email exists
        return {"message": "If the email exists, a reset link has been sent"}
    
    # Generate reset token (valid for 1 hour)
    reset_token = create_access_token(
        {"sub": user.id, "type": "password_reset"},
        expires_delta=timedelta(hours=1)
    )
    
    # TODO: Send email with reset link
    # For now, just log it
    logger.info("Password reset requested", user_id=user.id, email=request.email)
    
    return {"message": "If the email exists, a reset link has been sent"}


@router.post("/reset-password")
async def reset_password(
    request: PasswordResetConfirm,
    db: Session = Depends(get_db),
):
    """Reset password using token from email."""
    try:
        payload = verify_token(request.token)
        
        if payload.get("type") != "password_reset":
            raise AuthenticationException("Invalid token type")
        
        user_id = payload.get("sub")
        user = db.query(User).filter(User.id == user_id).first()
        
        if not user:
            raise AuthenticationException("User not found")
        
        # Validate new password
        if len(request.new_password) < 8:
            raise ValidationException("Password must be at least 8 characters")
        
        # Update password
        user.password_hash = get_password_hash(request.new_password)
        db.commit()
        
        logger.info("Password reset successful", user_id=user.id)
        
        return {"message": "Password reset successful"}
        
    except Exception as e:
        raise AuthenticationException("Invalid or expired token")
