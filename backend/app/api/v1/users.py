"""User management API routes."""

from typing import Optional, List

from fastapi import APIRouter, Depends, Header
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundException, AuthenticationException, ValidationException
from app.core.logging import get_logger
from app.core.security import verify_token
from app.db.base import get_db
from app.models.user import User, UserSettings, SubscriptionTier

logger = get_logger(__name__)
router = APIRouter()


# Dependency to get current user
def get_current_user(
    authorization: str = Header(None),
    db: Session = Depends(get_db),
) -> User:
    """Get current authenticated user."""
    if not authorization or not authorization.startswith("Bearer "):
        raise AuthenticationException("Authorization header required")
    
    token = authorization.split(" ")[1]
    payload = verify_token(token)
    user_id = payload.get("sub")
    
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise AuthenticationException("User not found")
    
    return user


# Request/Response Models
class UpdateProfileRequest(BaseModel):
    display_name: Optional[str] = None
    bio: Optional[str] = None
    avatar_url: Optional[str] = None


class UpdateSettingsRequest(BaseModel):
    default_niche: Optional[str] = None
    default_video_type: Optional[str] = None
    default_video_length: Optional[int] = None
    default_aspect_ratio: Optional[str] = None
    character_consistency_enabled: Optional[bool] = None
    character_description: Optional[str] = None
    character_images: Optional[List[str]] = None
    captions_enabled: Optional[bool] = None
    caption_style: Optional[str] = None
    caption_color: Optional[str] = None
    caption_emoji_enabled: Optional[bool] = None
    background_music_enabled: Optional[bool] = None
    background_music_style: Optional[str] = None
    default_style: Optional[str] = None
    default_daily_video_count: Optional[int] = None
    default_schedule_times: Optional[List[str]] = None
    email_notifications_enabled: Optional[bool] = None
    push_notifications_enabled: Optional[bool] = None
    notify_on_video_complete: Optional[bool] = None
    notify_on_schedule: Optional[bool] = None
    auto_delete_videos_days: Optional[int] = None


class UserProfileResponse(BaseModel):
    id: str
    email: str
    display_name: Optional[str]
    bio: Optional[str]
    avatar_url: Optional[str]
    subscription_tier: str
    subscription_expires_at: Optional[str]
    credits: int
    created_at: str


class UserSettingsResponse(BaseModel):
    default_niche: str
    default_video_type: str
    default_video_length: int
    default_aspect_ratio: str
    character_consistency_enabled: bool
    character_description: Optional[str]
    character_images: List[str]
    captions_enabled: bool
    caption_style: str
    caption_color: str
    caption_emoji_enabled: bool
    background_music_enabled: bool
    background_music_style: str
    default_style: str
    default_daily_video_count: int
    default_schedule_times: List[str]
    email_notifications_enabled: bool
    push_notifications_enabled: bool
    notify_on_video_complete: bool
    notify_on_schedule: bool
    auto_delete_videos_days: Optional[int]


class UsageStatsResponse(BaseModel):
    total_videos_generated: int
    videos_this_month: int
    videos_today: int
    storage_used: int
    remaining_daily_videos: int


@router.get("/profile", response_model=UserProfileResponse)
async def get_profile(
    current_user: User = Depends(get_current_user),
):
    """Get user profile."""
    return UserProfileResponse(
        id=current_user.id,
        email=current_user.email,
        display_name=current_user.display_name,
        bio=current_user.bio,
        avatar_url=current_user.avatar_url,
        subscription_tier=current_user.subscription_tier.value,
        subscription_expires_at=current_user.subscription_expires_at.isoformat() 
            if current_user.subscription_expires_at else None,
        credits=current_user.credits,
        created_at=current_user.created_at.isoformat(),
    )


@router.put("/profile")
async def update_profile(
    request: UpdateProfileRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update user profile."""
    if request.display_name is not None:
        current_user.display_name = request.display_name
    if request.bio is not None:
        current_user.bio = request.bio
    if request.avatar_url is not None:
        current_user.avatar_url = request.avatar_url
    
    db.commit()
    db.refresh(current_user)
    
    logger.info("Profile updated", user_id=current_user.id)
    
    return {"message": "Profile updated successfully"}


@router.get("/settings", response_model=UserSettingsResponse)
async def get_settings(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get user settings."""
    settings = db.query(UserSettings).filter(
        UserSettings.user_id == current_user.id
    ).first()
    
    if not settings:
        raise NotFoundException("Settings not found")
    
    return UserSettingsResponse(**settings.to_dict())


@router.put("/settings")
async def update_settings(
    request: UpdateSettingsRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update user settings."""
    settings = db.query(UserSettings).filter(
        UserSettings.user_id == current_user.id
    ).first()
    
    if not settings:
        raise NotFoundException("Settings not found")
    
    # Update fields
    update_data = request.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(settings, field, value)
    
    db.commit()
    db.refresh(settings)
    
    logger.info("Settings updated", user_id=current_user.id)
    
    return {"message": "Settings updated successfully", "settings": settings.to_dict()}


@router.get("/usage", response_model=UsageStatsResponse)
async def get_usage_stats(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get user usage statistics."""
    from datetime import datetime, timedelta
    from app.models.video import Video
    
    # Total videos
    total_videos = db.query(Video).filter(
        Video.user_id == current_user.id,
        Video.status == "completed"
    ).count()
    
    # Videos this month
    month_start = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    videos_this_month = db.query(Video).filter(
        Video.user_id == current_user.id,
        Video.status == "completed",
        Video.created_at >= month_start
    ).count()
    
    # Videos today
    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    videos_today = db.query(Video).filter(
        Video.user_id == current_user.id,
        Video.created_at >= today_start
    ).count()
    
    # Calculate remaining daily videos
    daily_limit = current_user.daily_video_limit
    remaining_daily = max(0, daily_limit - videos_today)
    
    # Storage used (simplified - would need actual file size tracking)
    storage_used = 0
    
    return UsageStatsResponse(
        total_videos_generated=total_videos,
        videos_this_month=videos_this_month,
        videos_today=videos_today,
        storage_used=storage_used,
        remaining_daily_videos=remaining_daily,
    )


@router.delete("/account")
async def delete_account(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Delete user account (GDPR compliance)."""
    # In production, you might want to:
    # 1. Archive user data
    # 2. Cancel subscriptions
    # 3. Delete generated videos
    # 4. Anonymize data instead of hard delete
    
    user_id = current_user.id
    
    # Delete user (cascade will handle related records)
    db.delete(current_user)
    db.commit()
    
    logger.info("Account deleted", user_id=user_id)
    
    return {"message": "Account deleted successfully"}


@router.post("/export-data")
async def export_user_data(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Export all user data (GDPR compliance)."""
    from app.models.video import Video
    from app.models.payment import Payment
    
    # Gather all user data
    videos = db.query(Video).filter(Video.user_id == current_user.id).all()
    payments = db.query(Payment).filter(Payment.user_id == current_user.id).all()
    
    export_data = {
        "profile": {
            "id": current_user.id,
            "email": current_user.email,
            "display_name": current_user.display_name,
            "bio": current_user.bio,
            "subscription_tier": current_user.subscription_tier.value,
            "created_at": current_user.created_at.isoformat(),
        },
        "settings": current_user.settings.to_dict() if current_user.settings else None,
        "videos": [v.to_dict() for v in videos],
        "payments": [p.to_dict() for p in payments],
    }
    
    logger.info("Data exported", user_id=current_user.id)
    
    return {"data": export_data}
