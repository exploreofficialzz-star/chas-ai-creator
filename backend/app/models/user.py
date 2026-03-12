"""
User models.
FILE: app/models/user.py

FIXES:
1. CRITICAL — User.password_hash column was named "password_hash" in the
   model but security.py and auth.py write to current_user.hashed_password.
   Every login, registration and password change raised AttributeError.
   Fixed: renamed column to hashed_password with a DB column alias.

2. SubscriptionTier was missing "basic" — used in _TIER_LIMITS dicts
   across videos.py, users.py, payments.py. Tier lookups for basic users
   silently fell through to free-tier limits. Added BASIC = "basic".

3. User.daily_video_limit and User.max_video_length properties imported
   settings inside the property body — settings is loaded at app startup,
   calling it inside a property adds latency on every access and can
   fail in test environments. Replaced with a simple inline dict lookup.

4. UserSettings.to_dict() was missing default_audio_mode,
   default_voice_style, default_target_platforms — the three new columns
   added by users.py. get_settings() would return these columns but
   to_dict() silently dropped them, breaking the settings export endpoint.

5. UserSettings was missing the three new columns as SQLAlchemy Column
   definitions — they existed in Pydantic models but not in the DB schema,
   so Alembic / create_all() never created them. Added the columns.

6. User relationship to VideoSchedule had back_populates="user" but
   VideoSchedule already defines back_populates="user" — correct. However
   UserSubscription back_populates="user" and User.subscription used
   uselist=False which is fine, but the relationship wasn't cascade-aware.
   Added cascade="all, delete-orphan" to UserSettings and UserSubscription
   so deleting a user cleans up everything.
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
    Integer,
    JSON,
    String,
    Text,
)
from sqlalchemy.orm import relationship

from app.db.base import Base


# ─── ENUMS ────────────────────────────────────────────────────────────────────

class SubscriptionTier(str, Enum):
    FREE       = "free"
    BASIC      = "basic"       # FIX 2 — was missing
    PRO        = "pro"
    ENTERPRISE = "enterprise"


# ─── TIER LIMITS (FIX 3) ─────────────────────────────────────────────────────
# Single source of truth — used by the properties below and by
# videos.py / users.py / payments.py via their own local copies.
_TIER_DAILY_LIMITS = {
    SubscriptionTier.FREE:       2,
    SubscriptionTier.BASIC:      10,
    SubscriptionTier.PRO:        50,
    SubscriptionTier.ENTERPRISE: 200,
}
_TIER_MAX_LENGTH = {
    SubscriptionTier.FREE:       30,
    SubscriptionTier.BASIC:      60,
    SubscriptionTier.PRO:        300,
    SubscriptionTier.ENTERPRISE: 600,
}


# ─── USER ─────────────────────────────────────────────────────────────────────

class User(Base):
    __tablename__ = "users"

    id    = Column(String(36),  primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)

    # FIX 1 — column name matches what auth.py / security.py / users.py write
    hashed_password = Column(
        "password_hash",   # keeps DB column name unchanged — no migration needed
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
        cascade="all, delete-orphan",   # FIX 6
    )
    subscription = relationship(
        "UserSubscription", back_populates="user", uselist=False,
        cascade="all, delete-orphan",   # FIX 6
    )
    videos       = relationship("Video",         back_populates="user")
    payments     = relationship("Payment",       back_populates="user")
    schedules    = relationship("VideoSchedule", back_populates="user")

    def __repr__(self) -> str:
        return f"<User(id={self.id}, email={self.email}, tier={self.subscription_tier})>"

    # ── Properties (FIX 3 — no settings import, inline dict) ──────────────

    @property
    def daily_video_limit(self) -> int:
        return _TIER_DAILY_LIMITS.get(self.subscription_tier, 2)

    @property
    def max_video_length(self) -> int:
        return _TIER_MAX_LENGTH.get(self.subscription_tier, 30)

    def has_active_subscription(self) -> bool:
        if self.subscription_tier == SubscriptionTier.FREE:
            return True
        if self.subscription_expires_at is None:
            return False
        return self.subscription_expires_at > datetime.utcnow()


# ─── USER SUBSCRIPTION ────────────────────────────────────────────────────────

class UserSubscription(Base):
    __tablename__ = "user_subscriptions"

    id      = Column(String(36), primary_key=True, index=True)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)

    paystack_customer_code     = Column(String(100), nullable=True)
    paystack_subscription_code = Column(String(100), nullable=True)

    plan_id = Column(String(50), nullable=False)
    status  = Column(String(20), default="active")   # active | canceled | past_due

    current_period_start  = Column(DateTime, nullable=True)
    current_period_end    = Column(DateTime, nullable=True)
    cancel_at_period_end  = Column(Boolean,  default=False)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="subscription")

    def __repr__(self) -> str:
        return f"<UserSubscription(user={self.user_id}, plan={self.plan_id}, status={self.status})>"


# ─── USER SETTINGS ────────────────────────────────────────────────────────────

class UserSettings(Base):
    __tablename__ = "user_settings"

    id      = Column(String(36), primary_key=True, index=True)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"),
                     nullable=False, unique=True)

    # Video defaults
    default_niche        = Column(String(50),  default="general")
    default_video_type   = Column(String(20),  default="silent")
    default_video_length = Column(Integer,     default=30)
    default_aspect_ratio = Column(String(10),  default="9:16")
    default_style        = Column(String(50),  default="cinematic")

    # FIX 5 — new columns (were in Pydantic but missing from DB schema)
    default_audio_mode       = Column(String(20),  default="silent")
    default_voice_style      = Column(String(50),  default="professional")
    default_target_platforms = Column(JSON,         default=lambda: ["tiktok"])

    # Character consistency
    character_consistency_enabled = Column(Boolean, default=False)
    character_description         = Column(Text,    nullable=True)
    character_images              = Column(JSON,    default=list)

    # Captions
    captions_enabled      = Column(Boolean, default=True)
    caption_style         = Column(String(50), default="modern")
    caption_color         = Column(String(20), default="white")
    caption_emoji_enabled = Column(Boolean,    default=True)

    # Music
    background_music_enabled = Column(Boolean,    default=True)
    background_music_style   = Column(String(50), default="upbeat")

    # Scheduling
    default_daily_video_count = Column(Integer, default=1)
    default_schedule_times    = Column(JSON,    default=list)

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
        """FIX 4 — includes all columns including the three new ones."""
        def g(attr, default=None):
            v = getattr(self, attr, None)
            return v if v is not None else default

        return {
            "default_niche":              g("default_niche",        "general"),
            "default_video_type":         g("default_video_type",   "silent"),
            "default_video_length":       g("default_video_length", 30),
            "default_aspect_ratio":       g("default_aspect_ratio", "9:16"),
            "default_style":              g("default_style",        "cinematic"),
            # FIX 4 — new columns
            "default_audio_mode":         g("default_audio_mode",       "silent"),
            "default_voice_style":        g("default_voice_style",      "professional"),
            "default_target_platforms":   g("default_target_platforms", ["tiktok"]),
            # Character
            "character_consistency_enabled": g("character_consistency_enabled", False),
            "character_description":         g("character_description"),
            "character_images":              g("character_images", []),
            # Captions
            "captions_enabled":      g("captions_enabled",      True),
            "caption_style":         g("caption_style",         "modern"),
            "caption_color":         g("caption_color",         "white"),
            "caption_emoji_enabled": g("caption_emoji_enabled", True),
            # Music
            "background_music_enabled": g("background_music_enabled", True),
            "background_music_style":   g("background_music_style",   "upbeat"),
            # Scheduling
            "default_daily_video_count": g("default_daily_video_count", 1),
            "default_schedule_times":    g("default_schedule_times",    []),
            # Notifications
            "email_notifications_enabled": g("email_notifications_enabled", True),
            "push_notifications_enabled":  g("push_notifications_enabled",  True),
            "notify_on_video_complete":    g("notify_on_video_complete",    True),
            "notify_on_schedule":          g("notify_on_schedule",          True),
            # Privacy
            "auto_delete_videos_days": g("auto_delete_videos_days"),
        }
