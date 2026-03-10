"""Video models for content generation and management."""

from datetime import datetime
from enum import Enum
from typing import List, Optional, Dict, Any

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum as SQLEnum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    JSON,
    Float,
    event,
)
from sqlalchemy.orm import relationship

from app.db.base import Base


# ─── ENUMS ────────────────────────────────────────────────────────────────────

class VideoStatus(str, Enum):
    PENDING = "pending"
    SCRIPT_GENERATING = "script_generating"
    IMAGES_GENERATING = "images_generating"
    VIDEO_GENERATING = "video_generating"
    AUDIO_GENERATING = "audio_generating"
    COMPOSING = "composing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class VideoType(str, Enum):
    SILENT = "silent"
    NARRATION = "narration"


class VideoStyle(str, Enum):
    CARTOON = "cartoon"
    CINEMATIC = "cinematic"
    REALISTIC = "realistic"
    FUNNY = "funny"
    DRAMATIC = "dramatic"
    MINIMAL = "minimal"


class SceneStatus(str, Enum):
    PENDING = "pending"
    GENERATING = "generating"
    COMPLETED = "completed"
    FAILED = "failed"


# ─── VIDEO MODEL ──────────────────────────────────────────────────────────────

class Video(Base):
    """Video model for generated content."""

    __tablename__ = "videos"

    # FIX 1 - added composite indexes for the most common query patterns
    __table_args__ = (
        Index("ix_videos_user_status", "user_id", "status"),
        Index("ix_videos_user_created", "user_id", "created_at"),
    )

    id = Column(String(36), primary_key=True, index=True)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    # Basic Info
    title = Column(String(200), nullable=True)
    description = Column(Text, nullable=True)
    niche = Column(String(50), nullable=False)

    # Video Configuration
    video_type = Column(SQLEnum(VideoType), default=VideoType.SILENT, nullable=False)
    duration = Column(Integer, default=30, nullable=False)
    aspect_ratio = Column(String(10), default="9:16", nullable=False)
    style = Column(SQLEnum(VideoStyle), default=VideoStyle.CINEMATIC, nullable=False)

    # Character Consistency
    character_consistency_enabled = Column(Boolean, default=False, nullable=False)
    character_description = Column(Text, nullable=True)

    # Captions
    captions_enabled = Column(Boolean, default=True, nullable=False)
    caption_style = Column(String(50), default="modern", nullable=False)
    caption_color = Column(String(20), default="white", nullable=False)
    caption_emoji_enabled = Column(Boolean, default=True, nullable=False)

    # Background Music
    background_music_enabled = Column(Boolean, default=True, nullable=False)
    background_music_url = Column(String(500), nullable=True)
    background_music_style = Column(String(50), default="upbeat", nullable=False)

    # User Instructions
    user_instructions = Column(Text, nullable=True)
    scene_priority_notes = Column(Text, nullable=True)

    # Generated Content
    script = Column(JSON, nullable=True)
    narration_text = Column(Text, nullable=True)
    # FIX 2 - use lambda for mutable JSON default to avoid shared state bug
    hashtags = Column(JSON, default=lambda: [])

    # Status & Progress
    status = Column(SQLEnum(VideoStatus), default=VideoStatus.PENDING, nullable=False, index=True)
    progress = Column(Integer, default=0, nullable=False)
    error_message = Column(Text, nullable=True)

    # File URLs
    video_url = Column(String(500), nullable=True)
    thumbnail_url = Column(String(500), nullable=True)

    # Metadata
    file_size = Column(Integer, nullable=True)
    resolution = Column(String(20), nullable=True)
    fps = Column(Integer, default=24, nullable=False)

    # Analytics
    view_count = Column(Integer, default=0, nullable=False)
    download_count = Column(Integer, default=0, nullable=False)

    # Scheduling
    is_scheduled = Column(Boolean, default=False, nullable=False)
    scheduled_for = Column(DateTime, nullable=True)
    # FIX 3 - use_alter=True fixes circular FK dependency between
    # videos <-> video_schedules that caused table creation order errors
    schedule_id = Column(
        String(36),
        ForeignKey("video_schedules.id", use_alter=True, name="fk_video_schedule_id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)

    # Relationships
    user = relationship("User", back_populates="videos")
    scenes = relationship(
        "VideoScene",
        back_populates="video",
        cascade="all, delete-orphan",
        order_by="VideoScene.scene_number",  # FIX 4 - always return scenes in order
    )
    schedule = relationship(
        "VideoSchedule",
        back_populates="videos",
        foreign_keys=[schedule_id],
    )

    def __repr__(self) -> str:
        return f"<Video(id={self.id}, status={self.status}, niche={self.niche})>"

    # ── Properties ─────────────────────────────────────────────────────────

    @property
    def is_completed(self) -> bool:
        return self.status == VideoStatus.COMPLETED

    @property
    def is_failed(self) -> bool:
        return self.status == VideoStatus.FAILED

    @property
    def is_processing(self) -> bool:
        return self.status in [
            VideoStatus.SCRIPT_GENERATING,
            VideoStatus.IMAGES_GENERATING,
            VideoStatus.VIDEO_GENERATING,
            VideoStatus.AUDIO_GENERATING,
            VideoStatus.COMPOSING,
        ]

    @property
    def is_pending(self) -> bool:
        return self.status == VideoStatus.PENDING

    # FIX 5 - added human-readable progress label for frontend display
    @property
    def status_label(self) -> str:
        labels = {
            VideoStatus.PENDING: "⏳ Waiting to start...",
            VideoStatus.SCRIPT_GENERATING: "✍️ Writing script...",
            VideoStatus.IMAGES_GENERATING: "🎨 Generating images...",
            VideoStatus.VIDEO_GENERATING: "🎬 Creating video clips...",
            VideoStatus.AUDIO_GENERATING: "🎙️ Generating audio...",
            VideoStatus.COMPOSING: "🎞️ Composing final video...",
            VideoStatus.COMPLETED: "✅ Video ready!",
            VideoStatus.FAILED: "❌ Generation failed",
            VideoStatus.CANCELLED: "🚫 Cancelled",
        }
        return labels.get(self.status, "Unknown")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "niche": self.niche,
            "video_type": self.video_type.value,
            "duration": self.duration,
            "aspect_ratio": self.aspect_ratio,
            "style": self.style.value,
            "captions_enabled": self.captions_enabled,
            "background_music_enabled": self.background_music_enabled,
            "status": self.status.value,
            "status_label": self.status_label,
            "progress": self.progress,
            "video_url": self.video_url,
            "thumbnail_url": self.thumbnail_url,
            "resolution": self.resolution,
            "view_count": self.view_count,
            "download_count": self.download_count,
            "error_message": self.error_message,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }


# ─── VIDEO SCENE MODEL ────────────────────────────────────────────────────────

class VideoScene(Base):
    """Individual scene within a video."""

    __tablename__ = "video_scenes"

    __table_args__ = (
        Index("ix_scenes_video_number", "video_id", "scene_number"),
    )

    id = Column(String(36), primary_key=True, index=True)
    video_id = Column(
        String(36),
        ForeignKey("videos.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    scene_number = Column(Integer, nullable=False)

    # Content
    description = Column(Text, nullable=False)
    caption = Column(Text, nullable=True)
    narration = Column(Text, nullable=True)

    # Generated Assets
    image_url = Column(String(500), nullable=True)
    image_prompt = Column(Text, nullable=True)
    video_clip_url = Column(String(500), nullable=True)

    # Timing
    duration = Column(Float, default=3.0, nullable=False)
    start_time = Column(Float, nullable=True)
    end_time = Column(Float, nullable=True)

    # FIX 6 - use proper Enum for scene status instead of raw String
    status = Column(
        SQLEnum(SceneStatus),
        default=SceneStatus.PENDING,
        nullable=False,
    )
    error_message = Column(Text, nullable=True)  # FIX 7 - store scene-level errors

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    video = relationship("Video", back_populates="scenes")

    def __repr__(self) -> str:
        return f"<VideoScene(video_id={self.video_id}, scene={self.scene_number}, status={self.status})>"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "scene_number": self.scene_number,
            "description": self.description,
            "caption": self.caption,
            "narration": self.narration,
            "image_url": self.image_url,
            "video_clip_url": self.video_clip_url,
            "duration": self.duration,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "status": self.status.value,
            "error_message": self.error_message,
        }


# ─── VIDEO SCHEDULE MODEL ─────────────────────────────────────────────────────

class VideoSchedule(Base):
    """Scheduled video generation tasks."""

    __tablename__ = "video_schedules"

    id = Column(String(36), primary_key=True, index=True)
    user_id = Column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    name = Column(String(100), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)

    # Frequency
    frequency = Column(String(20), default="daily", nullable=False)
    # FIX 8 - lambda default for mutable JSON
    days_of_week = Column(JSON, default=lambda: [0, 1, 2, 3, 4, 5, 6])
    schedule_times = Column(JSON, default=lambda: [])
    cron_expression = Column(String(100), nullable=True)

    # Video Configuration
    video_config = Column(JSON, default=lambda: {})

    # Limits & Tracking
    max_videos_per_day = Column(Integer, default=1, nullable=False)
    videos_generated_today = Column(Integer, default=0, nullable=False)
    last_generated_at = Column(DateTime, nullable=True)
    last_reset_at = Column(DateTime, nullable=True)  # FIX 9 - track when daily count was reset

    # Statistics
    total_videos_generated = Column(Integer, default=0, nullable=False)
    total_videos_failed = Column(Integer, default=0, nullable=False)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    user = relationship("User", back_populates="schedules")
    videos = relationship(
        "Video",
        back_populates="schedule",
        foreign_keys="Video.schedule_id",
    )

    def __repr__(self) -> str:
        return f"<VideoSchedule(id={self.id}, user_id={self.user_id}, active={self.is_active})>"

    def can_generate_today(self) -> bool:
        """Check if schedule can generate more videos today."""
        if not self.is_active:
            return False

        # FIX 10 - auto-reset daily count if it's a new day
        if self.last_reset_at:
            now = datetime.utcnow()
            last_reset_day = self.last_reset_at.date()
            if now.date() > last_reset_day:
                self.reset_daily_count()

        if self.videos_generated_today >= self.max_videos_per_day:
            return False

        if self.days_of_week:
            today = datetime.utcnow().weekday()
            if today not in self.days_of_week:
                return False

        return True

    def reset_daily_count(self) -> None:
        """Reset daily video count and record reset time."""
        self.videos_generated_today = 0
        self.last_reset_at = datetime.utcnow()

    def record_generated(self, success: bool = True) -> None:
        """Record a video generation attempt."""
        self.videos_generated_today += 1
        self.last_generated_at = datetime.utcnow()
        if success:
            self.total_videos_generated += 1
        else:
            self.total_videos_failed += 1

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "is_active": self.is_active,
            "frequency": self.frequency,
            "days_of_week": self.days_of_week,
            "schedule_times": self.schedule_times,
            "max_videos_per_day": self.max_videos_per_day,
            "videos_generated_today": self.videos_generated_today,
            "total_videos_generated": self.total_videos_generated,
            "total_videos_failed": self.total_videos_failed,
            "last_generated_at": self.last_generated_at.isoformat() if self.last_generated_at else None,
            "video_config": self.video_config,
            "created_at": self.created_at.isoformat() if self.created_at else None,
}
