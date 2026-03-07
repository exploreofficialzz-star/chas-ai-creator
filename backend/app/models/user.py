"""User models for authentication and user management."""

from datetime import datetime
from enum import Enum
from typing import List, Optional

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum as SQLEnum,
    ForeignKey,
    Integer,
    String,
    Text,
    JSON,
)
from sqlalchemy.orm import relationship

from app.db.base import Base


class SubscriptionTier(str, Enum):
    """Subscription tier levels."""
    FREE = "free"
    PRO = "pro"
    ENTERPRISE = "enterprise"


class User(Base):
    """User model for authentication and profile management."""
    
    __tablename__ = "users"
    
    id = Column(String(36), primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    firebase_uid = Column(String(128), unique=True, index=True, nullable=True)
    
    # Profile
    display_name = Column(String(100), nullable=True)
    avatar_url = Column(String(500), nullable=True)
    bio = Column(Text, nullable=True)
    
    # Status
    is_active = Column(Boolean, default=True)
    is_verified = Column(Boolean, default=False)
    is_admin = Column(Boolean, default=False)
    
    # Subscription
    subscription_tier = Column(SQLEnum(SubscriptionTier), default=SubscriptionTier.FREE)
    subscription_expires_at = Column(DateTime, nullable=True)
    
    # Credits for pay-per-video
    credits = Column(Integer, default=0)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_login_at = Column(DateTime, nullable=True)
    
    # Relationships
    settings = relationship("UserSettings", back_populates="user", uselist=False)
    subscription = relationship("UserSubscription", back_populates="user", uselist=False)
    videos = relationship("Video", back_populates="user")
    payments = relationship("Payment", back_populates="user")
    schedules = relationship("VideoSchedule", back_populates="user")
    
    def __repr__(self) -> str:
        return f"<User(id={self.id}, email={self.email}, tier={self.subscription_tier})>"
    
    @property
    def daily_video_limit(self) -> int:
        """Get daily video limit based on subscription tier."""
        from app.config import settings
        
        limits = {
            SubscriptionTier.FREE: settings.FREE_TIER_DAILY_VIDEOS,
            SubscriptionTier.PRO: settings.PRO_TIER_DAILY_VIDEOS,
            SubscriptionTier.ENTERPRISE: settings.ENTERPRISE_TIER_DAILY_VIDEOS,
        }
        return limits.get(self.subscription_tier, settings.FREE_TIER_DAILY_VIDEOS)
    
    @property
    def max_video_length(self) -> int:
        """Get max video length based on subscription tier."""
        from app.config import settings
        
        limits = {
            SubscriptionTier.FREE: settings.FREE_TIER_MAX_VIDEO_LENGTH,
            SubscriptionTier.PRO: settings.PRO_TIER_MAX_VIDEO_LENGTH,
            SubscriptionTier.ENTERPRISE: settings.ENTERPRISE_TIER_MAX_VIDEO_LENGTH,
        }
        return limits.get(self.subscription_tier, settings.FREE_TIER_MAX_VIDEO_LENGTH)
    
    def has_active_subscription(self) -> bool:
        """Check if user has an active subscription."""
        if self.subscription_tier == SubscriptionTier.FREE:
            return True
        if self.subscription_expires_at is None:
            return False
        return self.subscription_expires_at > datetime.utcnow()


class UserSubscription(Base):
    """User subscription details."""
    
    __tablename__ = "user_subscriptions"
    
    id = Column(String(36), primary_key=True, index=True)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    
    # Stripe
    stripe_customer_id = Column(String(100), nullable=True)
    stripe_subscription_id = Column(String(100), nullable=True)
    
    # Subscription details
    plan_id = Column(String(50), nullable=False)
    status = Column(String(20), default="active")  # active, canceled, past_due
    
    # Billing
    current_period_start = Column(DateTime, nullable=True)
    current_period_end = Column(DateTime, nullable=True)
    cancel_at_period_end = Column(Boolean, default=False)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user = relationship("User", back_populates="subscription")
    
    def __repr__(self) -> str:
        return f"<UserSubscription(user_id={self.user_id}, plan={self.plan_id})>"


class UserSettings(Base):
    """User preferences and default settings for video generation."""
    
    __tablename__ = "user_settings"
    
    id = Column(String(36), primary_key=True, index=True)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, unique=True)
    
    # Default Niche
    default_niche = Column(String(50), default="general")  # animals, tech, cooking, motivation, etc.
    
    # Default Video Settings
    default_video_type = Column(String(20), default="silent")  # silent, narration
    default_video_length = Column(Integer, default=30)  # seconds
    default_aspect_ratio = Column(String(10), default="9:16")  # 16:9, 9:16, 1:1
    
    # Character Consistency
    character_consistency_enabled = Column(Boolean, default=False)
    character_description = Column(Text, nullable=True)
    character_images = Column(JSON, default=list)  # URLs to character reference images
    
    # Captions
    captions_enabled = Column(Boolean, default=True)
    caption_style = Column(String(50), default="modern")  # modern, classic, bold
    caption_color = Column(String(20), default="white")
    caption_emoji_enabled = Column(Boolean, default=True)
    
    # Background Music
    background_music_enabled = Column(Boolean, default=True)
    background_music_style = Column(String(50), default="upbeat")  # upbeat, calm, dramatic
    
    # Style/Mood
    default_style = Column(String(50), default="cinematic")  # cartoon, cinematic, realistic, funny, dramatic
    
    # Scheduling
    default_daily_video_count = Column(Integer, default=1)
    default_schedule_times = Column(JSON, default=list)  # ["09:00", "15:00", "20:00"]
    
    # Notifications
    email_notifications_enabled = Column(Boolean, default=True)
    push_notifications_enabled = Column(Boolean, default=True)
    notify_on_video_complete = Column(Boolean, default=True)
    notify_on_schedule = Column(Boolean, default=True)
    
    # Privacy
    auto_delete_videos_days = Column(Integer, nullable=True)  # null = never delete
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user = relationship("User", back_populates="settings")
    
    def __repr__(self) -> str:
        return f"<UserSettings(user_id={self.user_id}, niche={self.default_niche})>"
    
    def to_dict(self) -> dict:
        """Convert settings to dictionary."""
        return {
            "default_niche": self.default_niche,
            "default_video_type": self.default_video_type,
            "default_video_length": self.default_video_length,
            "default_aspect_ratio": self.default_aspect_ratio,
            "character_consistency_enabled": self.character_consistency_enabled,
            "character_description": self.character_description,
            "character_images": self.character_images,
            "captions_enabled": self.captions_enabled,
            "caption_style": self.caption_style,
            "caption_color": self.caption_color,
            "caption_emoji_enabled": self.caption_emoji_enabled,
            "background_music_enabled": self.background_music_enabled,
            "background_music_style": self.background_music_style,
            "default_style": self.default_style,
            "default_daily_video_count": self.default_daily_video_count,
            "default_schedule_times": self.default_schedule_times,
            "email_notifications_enabled": self.email_notifications_enabled,
            "push_notifications_enabled": self.push_notifications_enabled,
            "notify_on_video_complete": self.notify_on_video_complete,
            "notify_on_schedule": self.notify_on_schedule,
            "auto_delete_videos_days": self.auto_delete_videos_days,
  }
