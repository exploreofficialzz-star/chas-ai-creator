"""
User models.
FILE: app/models/user.py

BUGS FIXED (on top of previous session fixes):
1. CRITICAL — _TIER_DAILY_LIMITS and _TIER_MAX_LENGTH used SubscriptionTier
   enum members as dict keys. SQLAlchemy returns the enum member from a
   SQLEnum column in most cases, BUT raw SQL inserts, test fixtures, or
   Alembic data migrations can leave a plain string "free" / "pro" in the
   column. dict.get(SubscriptionTier.FREE) misses the string "free" and
   falls through to the default (2 videos / 30s) regardless of the user's
   real tier — effectively downgrading every user whose tier arrived as a
   string. Fixed: _tier_key() normalises to string before lookup so both
   enum members and plain strings resolve correctly.

2. CRITICAL — UserSettings.character_images = Column(JSON, default=list)
   passes the class `list` as the SQLAlchemy column default. SQLAlchemy
   calls it as a callable to produce the default value, which works, BUT
   it stores a reference to the same list object across rows in some
   SQLAlchemy versions — can cause one user's character_images to bleed
   into another's. Fixed: use default=lambda: [] (a fresh list each time).
   Same fix applied to default_target_platforms and default_schedule_times.

3. UserSubscription had no index on user_id — every auth check that joins
   users → subscriptions does a full table scan. Added index=True.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum as SQLEnum,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
)
from sqlalchemy.orm import relationship

from app.db.base import Base


# ── Enums ─────────────────────────────────────────────────────────────────────

class SubscriptionTier(str, Enum):
    FREE       = "free"
    BASIC      = "basic"
    PRO        = "pro"
    ENTERPRISE = "enterprise"


# ── Tier limits ───────────────────────────────────────────────────────────────
# FIX 1 — keyed by plain string so lookups always succeed regardless of
# whether subscription_tier arrives as an enum member or a raw string.

_TIER_DAILY: Dict[str, int] = {
    "free":       2,
    "basic":      10,
    "pro":        50,
    "enterprise": 200,
}

_TIER_MAX_DURATION: Dict[str, int] = {
    "free":       30,
    "basic":      60,
    "pro":        300,
    "enterprise": 600,
}


def _tier_key(tier_value) -> str:
    """
    FIX 1 — Normalise tier to a plain lowercase string so dict lookups
    work for both SubscriptionTier.FREE and the raw string "free".
    """
    if isinstance(tier_value, SubscriptionTier):
        return tier_value.value
    return str(tier_value).lower().strip() if tier_value else "free"


# ── User ──────────────────────────────────────────────────────────────────────

class User(Base):
    __tablename__ = "users"

    id    = Column(String(36),  primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)

    # Column name in DB stays "password_hash" to avoid a migration.
    # Application code always uses .hashed_password
    hashed_password = Column(
        "password_hash",
        String(255), nullable=True,
    )

    # Profile
    display_name = Column(String(100), nullable=True)
    avatar_url   = Column(String(500), nullable=True)
    bio          = Column(Text,        nullable=True)

    # Status
    is_active   = Column(Boolean, default=True)
    is_verified = Column(Boolean, default=False)
    is_admin    = Column(Boolean, default=False)

    # Subscription
    subscription_tier       = Column(SQLEnum(SubscriptionTier), default=SubscriptionTier.FREE)
    subscription_expires_at = Column(DateTime, nullable=True)

    # Credits
    credits = Column(Integer, default=0)

    # Timestamps
    created_at    = Column(DateTime, default=datetime.utcnow)
    updated_at    = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_login_at = Column(DateTime, nullable=True)

    # Relationships
    settings     = relationship(
        "UserSettings", back_populates="user", uselist=False,
        cascade="all, delete-orphan",
    )
    subscription = relationship(
        "UserSubscription", back_populates="user", uselist=False,
        cascade="all, delete-orphan",
    )
    videos    = relationship("Video",         back_populates="user")
    payments  = relationship("Payment",       back_populates="user")
    schedules = relationship("VideoSchedule", back_populates="user")

    def __repr__(self) -> str:
        return f"<User(id={self.id}, email={self.email}, tier={self.subscription_tier})>"

    # ── Tier helpers (FIX 1) ──────────────────────────────────────────────────

    @property
    def daily_video_limit(self) -> int:
        return _TIER_DAILY.get(_tier_key(self.subscription_tier), 2)

    @property
    def max_video_length(self) -> int:
        return _TIER_MAX_DURATION.get(_tier_key(self.subscription_tier), 30)

    def has_active_subscription(self) -> bool:
        if _tier_key(self.subscription_tier) == "free":
            return True
        if self.subscription_expires_at is None:
            return False
        return self.subscription_expires_at > datetime.utcnow()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id":           self.id,
            "email":        self.email,
            "display_name": self.display_name,
            "avatar_url":   self.avatar_url,
            "bio":          self.bio,
            "subscription_tier": _tier_key(self.subscription_tier),
            "subscription_expires_at": (
                self.subscription_expires_at.isoformat()
                if self.subscription_expires_at else None
            ),
            "credits":        self.credits or 0,
            "is_active":      self.is_active,
            "is_verified":    self.is_verified,
            "daily_video_limit": self.daily_video_limit,
            "max_video_length":  self.max_video_length,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


# ── UserSubscription ──────────────────────────────────────────────────────────

class UserSubscription(Base):
    __tablename__ = "user_subscriptions"

    id      = Column(String(36), primary_key=True, index=True)
    # FIX 3 — added index=True (was missing; every auth check was doing a full scan)
    user_id = Column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )

    paystack_customer_code     = Column(String(100), nullable=True)
    paystack_subscription_code = Column(String(100), nullable=True)

    plan_id = Column(String(50),  nullable=False)
    status  = Column(String(20),  default="active")   # active | canceled | past_due

    current_period_start = Column(DateTime, nullable=True)
    current_period_end   = Column(DateTime, nullable=True)
    cancel_at_period_end = Column(Boolean,  default=False)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="subscription")

    def __repr__(self) -> str:
        return (
            f"<UserSubscription(user={self.user_id}, "
            f"plan={self.plan_id}, status={self.status})>"
        )


# ── UserSettings ──────────────────────────────────────────────────────────────

class UserSettings(Base):
    __tablename__ = "user_settings"

    id      = Column(String(36), primary_key=True, index=True)
    user_id = Column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False, unique=True,
    )

    # Video defaults
    default_niche        = Column(String(50), default="general")
    default_video_type   = Column(String(20), default="silent")
    default_video_length = Column(Integer,    default=30)
    default_aspect_ratio = Column(String(10), default="9:16")
    default_style        = Column(String(50), default="cinematic")

    # Audio defaults (new columns — must be in Alembic migration)
    default_audio_mode       = Column(String(20), default="silent")
    default_voice_style      = Column(String(50), default="professional")
    # FIX 2 — lambda: [] ensures a fresh list per row, not a shared reference
    default_target_platforms = Column(JSON, default=lambda: ["tiktok"])

    # Character consistency
    character_consistency_enabled = Column(Boolean, default=False)
    character_description         = Column(Text,    nullable=True)
    # FIX 2 — lambda: [] instead of bare `list`
    character_images = Column(JSON, default=lambda: [])

    # Captions
    captions_enabled      = Column(Boolean,    default=True)
    caption_style         = Column(String(50), default="modern")
    caption_color         = Column(String(20), default="white")
    caption_emoji_enabled = Column(Boolean,    default=True)

    # Music
    background_music_enabled = Column(Boolean,    default=True)
    background_music_style   = Column(String(50), default="upbeat")

    # Scheduling
    default_daily_video_count = Column(Integer, default=1)
    # FIX 2 — lambda: [] instead of bare `list`
    default_schedule_times    = Column(JSON, default=lambda: [])

    # Notifications
    email_notifications_enabled = Column(Boolean, default=True)
    push_notifications_enabled  = Column(Boolean, default=True)
    notify_on_video_complete    = Column(Boolean, default=True)
    notify_on_schedule          = Column(Boolean, default=True)

    # Privacy
    auto_delete_videos_days = Column(Integer, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="settings")

    def __repr__(self) -> str:
        return f"<UserSettings(user={self.user_id}, niche={self.default_niche})>"

    def to_dict(self) -> Dict[str, Any]:
        def g(attr, default=None):
            v = getattr(self, attr, None)
            return v if v is not None else default

        return {
            "default_niche":         g("default_niche",        "general"),
            "default_video_type":    g("default_video_type",   "silent"),
            "default_video_length":  g("default_video_length", 30),
            "default_aspect_ratio":  g("default_aspect_ratio", "9:16"),
            "default_style":         g("default_style",        "cinematic"),
            "default_audio_mode":    g("default_audio_mode",       "silent"),
            "default_voice_style":   g("default_voice_style",      "professional"),
            "default_target_platforms": g("default_target_platforms", ["tiktok"]),
            "character_consistency_enabled": g("character_consistency_enabled", False),
            "character_description":         g("character_description"),
            "character_images":              g("character_images", []),
            "captions_enabled":       g("captions_enabled",      True),
            "caption_style":          g("caption_style",         "modern"),
            "caption_color":          g("caption_color",         "white"),
            "caption_emoji_enabled":  g("caption_emoji_enabled", True),
            "background_music_enabled": g("background_music_enabled", True),
            "background_music_style":   g("background_music_style",   "upbeat"),
            "default_daily_video_count": g("default_daily_video_count", 1),
            "default_schedule_times":    g("default_schedule_times",    []),
            "email_notifications_enabled": g("email_notifications_enabled", True),
            "push_notifications_enabled":  g("push_notifications_enabled",  True),
            "notify_on_video_complete":    g("notify_on_video_complete",    True),
            "notify_on_schedule":          g("notify_on_schedule",          True),
            "auto_delete_videos_days":     g("auto_delete_videos_days"),
        }
