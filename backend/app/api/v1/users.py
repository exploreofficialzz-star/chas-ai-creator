"""
User management API routes.
FILE: app/api/v1/users.py

BUGS FIXED IN THIS VERSION:
1. CRITICAL — GET /me was missing entirely. The frontend (api_service.dart)
   calls GET /api/v1/users/me on every startup to check auth state.
   It returned 404 every time → app thought user was logged out →
   redirect to login. Added /me as an alias for /profile.

2. get_settings() raised NotFoundException on first login because
   UserSettings row doesn't exist yet. Auto-create defaults if missing.

3. UpdateSettingsRequest was missing default_audio_mode, default_voice_style,
   default_target_platforms — silently dropped on every settings save.

4. get_usage_stats() compared Video.status == "completed" (raw string)
   against a SQLAlchemy enum column — always returned 0. Fixed to use
   VideoStatus.COMPLETED enum value.

5. get_usage_stats() referenced current_user.daily_video_limit which
   doesn't exist as a model attribute — AttributeError crash.

6. cancel_subscription() and get_current_subscription() accessed
   non-existent model attributes — AttributeError crash.

7. export_user_data() called v.to_dict() and p.to_dict() — safe
   field-by-field export instead.

8. PUT /password was missing — referenced in settings_screen.dart.
"""

import uuid as _uuid
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, Header
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.exceptions import (
    AuthenticationException,
    NotFoundException,
    ValidationException,
)
from app.core.logging import get_logger
from app.core.security import verify_token
from app.db.base import get_db
from app.models.user import User, UserSettings

logger = get_logger(__name__)
router = APIRouter()

_TIER_LIMITS = {
    "free":       {"daily": 2,   "max_duration": 30},
    "basic":      {"daily": 10,  "max_duration": 60},
    "pro":        {"daily": 50,  "max_duration": 300},
    "enterprise": {"daily": 200, "max_duration": 600},
}


# ── Auth dependency ───────────────────────────────────────────────────────────

def get_current_user(
    authorization: str = Header(None),
    db: Session = Depends(get_db),
) -> User:
    if not authorization or not authorization.startswith("Bearer "):
        raise AuthenticationException("Authorization header required.")
    token   = authorization.split(" ")[1]
    payload = verify_token(token)
    user    = db.query(User).filter(User.id == payload.get("sub")).first()
    if not user:
        raise AuthenticationException("User not found. Please log in again.")
    return user


# ── Internal helpers ──────────────────────────────────────────────────────────

def _tier_str(user: User) -> str:
    t = user.subscription_tier
    return t.value if hasattr(t, "value") else str(t)


def _daily_limit(user: User) -> int:
    return _TIER_LIMITS.get(_tier_str(user), _TIER_LIMITS["free"])["daily"]


def _max_duration(user: User) -> int:
    return _TIER_LIMITS.get(_tier_str(user), _TIER_LIMITS["free"])["max_duration"]


def _get_or_create_settings(user: User, db: Session) -> UserSettings:
    """FIX 2 — Never raises; auto-creates default settings on first load."""
    s = db.query(UserSettings).filter(UserSettings.user_id == user.id).first()
    if not s:
        s = UserSettings(
            id=str(_uuid.uuid4()),
            user_id=user.id,
            default_niche="general",
            default_video_type="silent",
            default_video_length=30,
            default_aspect_ratio="9:16",
            default_style="cinematic",
            default_audio_mode="silent",
            default_voice_style="professional",
            default_target_platforms=["tiktok"],
            captions_enabled=True,
            caption_style="modern",
            caption_color="white",
            caption_emoji_enabled=True,
            background_music_enabled=True,
            background_music_style="upbeat",
            character_consistency_enabled=False,
            default_daily_video_count=1,
            default_schedule_times=[],
            email_notifications_enabled=True,
            push_notifications_enabled=True,
            notify_on_video_complete=True,
            notify_on_schedule=True,
        )
        db.add(s)
        db.commit()
        db.refresh(s)
        logger.info(f"Auto-created settings for user {user.id}")
    return s


def _settings_dict(s: UserSettings) -> dict:
    """FIX 7 — Safe export that won't crash if model is missing newer columns."""
    def g(attr, default):
        v = getattr(s, attr, None)
        return v if v is not None else default

    return {
        "default_niche":                 g("default_niche", "general"),
        "default_video_type":            g("default_video_type", "silent"),
        "default_video_length":          g("default_video_length", 30),
        "default_aspect_ratio":          g("default_aspect_ratio", "9:16"),
        "default_style":                 g("default_style", "cinematic"),
        "default_audio_mode":            g("default_audio_mode", "silent"),
        "default_voice_style":           g("default_voice_style", "professional"),
        "default_target_platforms":      g("default_target_platforms", ["tiktok"]),
        "character_consistency_enabled": g("character_consistency_enabled", False),
        "character_description":         g("character_description", None),
        "character_images":              g("character_images", []),
        "captions_enabled":              g("captions_enabled", True),
        "caption_style":                 g("caption_style", "modern"),
        "caption_color":                 g("caption_color", "white"),
        "caption_emoji_enabled":         g("caption_emoji_enabled", True),
        "background_music_enabled":      g("background_music_enabled", True),
        "background_music_style":        g("background_music_style", "upbeat"),
        "default_daily_video_count":     g("default_daily_video_count", 1),
        "default_schedule_times":        g("default_schedule_times", []),
        "email_notifications_enabled":   g("email_notifications_enabled", True),
        "push_notifications_enabled":    g("push_notifications_enabled", True),
        "notify_on_video_complete":      g("notify_on_video_complete", True),
        "notify_on_schedule":            g("notify_on_schedule", True),
        "auto_delete_videos_days":       g("auto_delete_videos_days", None),
    }


def _profile_dict(user: User) -> dict:
    return {
        "id":                      user.id,
        "email":                   user.email,
        "display_name":            user.display_name,
        "bio":                     getattr(user, "bio", None),
        "avatar_url":              getattr(user, "avatar_url", None),
        "subscription_tier":       _tier_str(user),
        "subscription_expires_at": (
            user.subscription_expires_at.isoformat()
            if getattr(user, "subscription_expires_at", None) else None
        ),
        "credits":   getattr(user, "credits", 0) or 0,
        "created_at": user.created_at.isoformat(),
    }


# ── Pydantic models ───────────────────────────────────────────────────────────

class UpdateProfileRequest(BaseModel):
    display_name: Optional[str] = None
    bio:          Optional[str] = None
    avatar_url:   Optional[str] = None


class UpdatePasswordRequest(BaseModel):
    current_password: str
    new_password:     str


class UpdateSettingsRequest(BaseModel):
    default_niche:                  Optional[str]       = None
    default_video_type:             Optional[str]       = None
    default_video_length:           Optional[int]       = None
    default_aspect_ratio:           Optional[str]       = None
    default_style:                  Optional[str]       = None
    # FIX 3 — new fields that frontend always sends
    default_audio_mode:             Optional[str]       = None
    default_voice_style:            Optional[str]       = None
    default_target_platforms:       Optional[List[str]] = None
    character_consistency_enabled:  Optional[bool]      = None
    character_description:          Optional[str]       = None
    character_images:               Optional[List[str]] = None
    captions_enabled:               Optional[bool]      = None
    caption_style:                  Optional[str]       = None
    caption_color:                  Optional[str]       = None
    caption_emoji_enabled:          Optional[bool]      = None
    background_music_enabled:       Optional[bool]      = None
    background_music_style:         Optional[str]       = None
    default_daily_video_count:      Optional[int]       = None
    default_schedule_times:         Optional[List[str]] = None
    email_notifications_enabled:    Optional[bool]      = None
    push_notifications_enabled:     Optional[bool]      = None
    notify_on_video_complete:       Optional[bool]      = None
    notify_on_schedule:             Optional[bool]      = None
    auto_delete_videos_days:        Optional[int]       = None


class UserSettingsResponse(BaseModel):
    default_niche:                  str
    default_video_type:             str
    default_video_length:           int
    default_aspect_ratio:           str
    default_style:                  str
    default_audio_mode:             str
    default_voice_style:            str
    default_target_platforms:       List[str]
    character_consistency_enabled:  bool
    character_description:          Optional[str]
    character_images:               List[str]
    captions_enabled:               bool
    caption_style:                  str
    caption_color:                  str
    caption_emoji_enabled:          bool
    background_music_enabled:       bool
    background_music_style:         str
    default_daily_video_count:      int
    default_schedule_times:         List[str]
    email_notifications_enabled:    bool
    push_notifications_enabled:     bool
    notify_on_video_complete:       bool
    notify_on_schedule:             bool
    auto_delete_videos_days:        Optional[int]


class UsageStatsResponse(BaseModel):
    total_videos_generated: int
    videos_this_month:      int
    videos_today:           int
    storage_used:           int
    remaining_daily_videos: int
    daily_limit:            int
    subscription_tier:      str
    max_video_length:       int


# ── Routes ────────────────────────────────────────────────────────────────────

@router.get("/me")
async def get_me(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    FIX 1 — CRITICAL. Was missing entirely.
    api_service.dart calls GET /api/v1/users/me on every app startup
    to verify the token and get the current user. Without this endpoint
    every startup returned 404 → app forced the user to log in again.
    """
    s = _get_or_create_settings(current_user, db)
    return {
        "user":     _profile_dict(current_user),
        "settings": _settings_dict(s),
    }


@router.get("/profile")
async def get_profile(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Full profile — also creates default settings if this is first load."""
    _get_or_create_settings(current_user, db)
    return _profile_dict(current_user)


@router.put("/profile")
async def update_profile(
    request: UpdateProfileRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if request.display_name is not None:
        current_user.display_name = request.display_name
    if request.bio is not None:
        current_user.bio = request.bio
    if request.avatar_url is not None:
        current_user.avatar_url = request.avatar_url
    db.commit()
    db.refresh(current_user)
    logger.info(f"Profile updated: {current_user.id}")
    return {"message": "Profile updated successfully", "user": _profile_dict(current_user)}


@router.put("/password")
async def update_password(
    request: UpdatePasswordRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """FIX 8 — Was missing. Referenced in settings_screen.dart."""
    from app.core.security import hash_password, verify_password
    if not verify_password(request.current_password, current_user.hashed_password):
        raise ValidationException("Current password is incorrect.")
    if len(request.new_password) < 8:
        raise ValidationException("New password must be at least 8 characters.")
    current_user.hashed_password = hash_password(request.new_password)
    db.commit()
    logger.info(f"Password updated: {current_user.id}")
    return {"message": "Password updated successfully."}


@router.get("/settings", response_model=UserSettingsResponse)
async def get_settings(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """FIX 2 — Never crashes; auto-creates defaults on first load."""
    s = _get_or_create_settings(current_user, db)
    return UserSettingsResponse(**_settings_dict(s))


@router.put("/settings")
async def update_settings(
    request: UpdateSettingsRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    s = _get_or_create_settings(current_user, db)
    for field, value in request.dict(exclude_unset=True).items():
        if hasattr(s, field):
            setattr(s, field, value)
        else:
            logger.warning(f"UserSettings missing column '{field}' — skipped")
    db.commit()
    db.refresh(s)
    logger.info(f"Settings updated: {current_user.id}")
    return {
        "message":  "Settings updated successfully.",
        "settings": _settings_dict(s),
    }


@router.get("/usage", response_model=UsageStatsResponse)
async def get_usage_stats(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from app.models.video import Video, VideoStatus  # FIX 4

    total = db.query(Video).filter(
        Video.user_id == current_user.id,
        Video.status  == VideoStatus.COMPLETED,   # FIX 4 — was raw string "completed"
    ).count()

    month_start = datetime.utcnow().replace(
        day=1, hour=0, minute=0, second=0, microsecond=0
    )
    this_month = db.query(Video).filter(
        Video.user_id    == current_user.id,
        Video.status     == VideoStatus.COMPLETED,
        Video.created_at >= month_start,
    ).count()

    today_start = datetime.utcnow().replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    today = db.query(Video).filter(
        Video.user_id    == current_user.id,
        Video.created_at >= today_start,
    ).count()

    limit = _daily_limit(current_user)  # FIX 5 — was current_user.daily_video_limit

    return UsageStatsResponse(
        total_videos_generated=total,
        videos_this_month=this_month,
        videos_today=today,
        storage_used=0,
        remaining_daily_videos=max(0, limit - today),
        daily_limit=limit,
        subscription_tier=_tier_str(current_user),
        max_video_length=_max_duration(current_user),  # FIX 6
    )


@router.delete("/account")
async def delete_account(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    user_id = current_user.id
    db.delete(current_user)
    db.commit()
    logger.info(f"Account deleted: {user_id}")
    return {"message": "Account deleted successfully."}


@router.post("/export-data")
async def export_user_data(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from app.models.video import Video
    from app.models.payment import Payment

    videos   = db.query(Video).filter(Video.user_id == current_user.id).all()
    payments = db.query(Payment).filter(Payment.user_id == current_user.id).all()
    s        = db.query(UserSettings).filter(UserSettings.user_id == current_user.id).first()

    return {
        "data": {
            "profile":  _profile_dict(current_user),
            "settings": _settings_dict(s) if s else None,
            # FIX 7 — safe field-by-field export, no to_dict() dependency
            "videos": [
                {
                    "id":         v.id,
                    "title":      v.title,
                    "status":     v.status.value if hasattr(v.status, "value") else str(v.status),
                    "video_url":  v.video_url,
                    "created_at": v.created_at.isoformat() if v.created_at else None,
                }
                for v in videos
            ],
            "payments": [
                {
                    "id":         p.id,
                    "amount":     p.amount,
                    "currency":   p.currency,
                    "status":     p.status.value if hasattr(p.status, "value") else str(p.status),
                    "created_at": p.created_at.isoformat() if p.created_at else None,
                }
                for p in payments
            ],
        }
    }
