"""Authentication API routes."""

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


# Firebase Auth helper (placeholder - implement with firebase-admin)
def verify_firebase_token(token: str) -> dict:
    """Verify Firebase ID token."""
    # Implementation with firebase-admin
    # import firebase_admin
    # from firebase_admin import auth
    # decoded_token = auth.verify_id_token(token)
    # return decoded_token
    
    # Placeholder for now
    return {"uid": "firebase_uid", "email": "user@example.com"}


def get_or_create_user(
    db: Session,
    email: str,
    firebase_uid: Optional[str] = None,
    display_name: Optional[str] = None,
) -> User:
    """Get existing user or create new one."""
    user = db.query(User).filter(User.email == email).first()
    
    if not user:
        import uuid
        user = User(
            id=str(uuid.uuid4()),
            email=email,
            firebase_uid=firebase_uid,
            display_name=display_name,
            subscription_tier=SubscriptionTier.FREE,
            credits=0,
        )
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
    
    # Create user
    import uuid
    user = User(
        id=str(uuid.uuid4()),
        email=request.email,
        display_name=request.display_name,
        subscription_tier=SubscriptionTier.FREE,
        credits=0,
    )
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
    
    # For Firebase Auth integration, verify with Firebase
    # For now, we'll use a simplified flow
    
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
    """Login with social provider (Google, Apple)."""
    # Verify social token
    try:
        firebase_data = verify_firebase_token(request.token)
        email = firebase_data.get("email") or request.email
        
        if not email:
            raise AuthenticationException("Email not provided")
        
        # Get or create user
        user = get_or_create_user(
            db,
            email=email,
            firebase_uid=firebase_data.get("uid"),
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
        
    except Exception as e:
        logger.error("Social login failed", error=str(e))
        raise AuthenticationException("Social login failed")


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
