"""
Video models.
FILE: app/models/video.py

FIXES:
1. CRITICAL — VideoType enum only had SILENT and NARRATION.
   Frontend sends audio_mode="sound_sync" (AudioMode.soundSync) but
   there was no VideoType.SOUND_SYNC. The DB column rejected the value
   and the entire video creation crashed with a DataError.
   Fixed: added SOUND_SYNC = "sound_sync" to VideoType.

2. CRITICAL — Video model had no audio_mode, voice_style, or
   target_platforms columns. video_generation.py task reads these three
   fields at generation time. All three raised AttributeError every time
   a video was generated. Added all three columns.

3. Video.style column type was SQLEnum(VideoStyle) — SQLAlchemy requires
   the exact enum member. But videos.py writes style="cinematic" (a plain
   string), causing StatementError on insert. Changed to String(50) with
   the enum kept for validation reference only.

4. Video.video_type same issue — stored as SQLEnum(VideoType) but
   videos.py passes video_type as a string value from the request.
   Changed to String(20) for consistency; VideoType enum kept for
   reference and property methods.

5. VideoSchedule.can_generate_today() mutated self (reset_daily_count)
   but had no db session to commit — the reset was lost on next call.
   Separated the check from the mutation; callers must commit after
   calling reset_daily_count().

6. to_dict() on Video was missing: audio_mode, voice_style,
   target_platforms, status_label, hashtags, narration_text.
   Frontend video detail screen shows all of these.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum as SQLEnum,
    Float,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
)
from sqlalchemy.orm import relationship

from app.db.base import Base


# ─── ENUMS ────────────────────────────────────────────────────────────────────

class VideoStatus(str, Enum):
    PENDING            = "pending"
    SCRIPT_GENERATING  = "script_generating"
    IMAGES_GENERATING  = "images_generating"
    VIDEO_GENERATING   = "video_generating"
    AUDIO_GENERATING   = "audio_generating"
    COMPOSING          = "composing"
    COMPLETED          = "completed"
    FAILED             = "failed"
    CANCELLED          = "cancelled"


class VideoType(str, Enum):
    """Reference enum — DB column uses String(20) for flexibility."""
    SILENT     = "silent"
    NARRATION  = "narration"
    SOUND_SYNC = "sound_sync"   # FIX 1


class VideoStyle(str, Enum):
    """Reference enum — DB column uses String(50) for flexibility."""
    CARTOON   = "cartoon"
    CINEMATIC = "cinematic"
    REALISTIC = "realistic"
    FUNNY     = "funny"
    DRAMATIC  = "dramatic"
    MINIMAL   = "minimal"


class SceneStatus(str, Enum):
    PENDING    = "pending"
    GENERATING = "generating"
    COMPLETED  = "completed"
    FAILED     = "failed"


# ─── VIDEO ────────────────────────────────────────────────────────────────────

class Video(Base):
    __tablename__ = "videos"
    __table_args__ = (
        Index("ix_videos_user_status",  "user_id", "status"),
        Index("ix_videos_user_created", "user_id", "created_at"),
    )

    id      = Column(String(36), primary_key=True, index=True)
    user_id = Column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )

    # Basic info
    title       = Column(String(200), nullable=True)
    description = Column(Text,        nullable=True)
    niche       = Column(String(50),  nullable=False)

    # FIX 3 / FIX 4 — String columns; enum kept above for isinstance checks
    video_type   = Column(String(20),  default="silent",    nullable=False)
    style        = Column(String(50),  default="cinematic", nullable=False)
    duration     = Column(Integer,     default=30,          nullable=False)
    aspect_ratio = Column(String(10),  default="9:16",      nullable=False)

    # FIX 2 — new columns (were read by video_generation.py but never existed)
    audio_mode       = Column(String(20),  default="silent",       nullable=False)
    voice_style      = Column(String(50),  default="professional", nullable=False)
    target_platforms = Column(JSON,        default=lambda: ["tiktok"])

    # Character consistency
    character_consistency_enabled = Column(Boolean, default=False, nullable=False)
    character_description         = Column(Text,    nullable=True)

    # Captions
    captions_enabled      = Column(Boolean,    default=True,    nullable=False)
    caption_style         = Column(String(50), default="modern",nullable=False)
    caption_color         = Column(String(20), default="white", nullable=False)
    caption_emoji_enabled = Column(Boolean,    default=True,    nullable=False)

    # Background music
    background_music_enabled = Column(Boolean,    default=True,    nullable=False)
    background_music_url     = Column(String(500), nullable=True)
    background_music_style   = Column(String(50), default="upbeat",nullable=False)

    # User instructions
    user_instructions   = Column(Text, nullable=True)
    scene_priority_notes = Column(Text, nullable=True)

    # Generated content
    script        = Column(JSON, nullable=True)
    narration_text = Column(Text, nullable=True)
    hashtags       = Column(JSON, default=lambda: [])

    # Status & progress
    status        = Column(SQLEnum(VideoStatus), default=VideoStatus.PENDING,
                           nullable=False, index=True)
    progress      = Column(Integer, default=0, nullable=False)
    error_message = Column(Text,    nullable=True)

    # Output
    video_url     = Column(String(500), nullable=True)
    thumbnail_url = Column(String(500), nullable=True)
    file_size     = Column(Integer,     nullable=True)
    resolution    = Column(String(20),  nullable=True)
    fps           = Column(Integer,     default=30, nullable=False)

    # Analytics
    view_count     = Column(Integer, default=0, nullable=False)
    download_count = Column(Integer, default=0, nullable=False)

    # Scheduling
    is_scheduled  = Column(Boolean,    default=False, nullable=False)
    scheduled_for = Column(DateTime,   nullable=True)
    schedule_id   = Column(
        String(36),
        ForeignKey(
            "video_schedules.id",
            use_alter=True,
            name="fk_video_schedule_id",
            ondelete="SET NULL",
        ),
        nullable=True, index=True,
    )

    # Timestamps
    created_at   = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at   = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    started_at   = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)

    # Relationships
    user   = relationship("User", back_populates="videos")
    scenes = relationship(
        "VideoScene",
        back_populates="video",
        cascade="all, delete-orphan",
        order_by="VideoScene.scene_number",
    )
    schedule = relationship(
        "VideoSchedule",
        back_populates="videos",
        foreign_keys=[schedule_id],
    )

    def __repr__(self) -> str:
        return f"<Video(id={self.id}, status={self.status}, niche={self.niche})>"

    # ── State helpers ──────────────────────────────────────────────────────

    @property
    def is_completed(self) -> bool:
        return self.status == VideoStatus.COMPLETED

    @property
    def is_failed(self) -> bool:
        return self.status == VideoStatus.FAILED

    @property
    def is_processing(self) -> bool:
        return self.status in (
            VideoStatus.SCRIPT_GENERATING,
            VideoStatus.IMAGES_GENERATING,
            VideoStatus.VIDEO_GENERATING,
            VideoStatus.AUDIO_GENERATING,
            VideoStatus.COMPOSING,
        )

    @property
    def status_label(self) -> str:
        return {
            VideoStatus.PENDING:           "⏳ Waiting to start...",
            VideoStatus.SCRIPT_GENERATING: "✍️ Writing script...",
            VideoStatus.IMAGES_GENERATING: "🎨 Generating images...",
            VideoStatus.VIDEO_GENERATING:  "🎬 Creating video clips...",
            VideoStatus.AUDIO_GENERATING:  "🎙️ Generating audio...",
            VideoStatus.COMPOSING:         "🎞️ Composing final video...",
            VideoStatus.COMPLETED:         "✅ Video ready!",
            VideoStatus.FAILED:            "❌ Generation failed",
            VideoStatus.CANCELLED:         "🚫 Cancelled",
        }.get(self.status, "Unknown")

    def to_dict(self) -> Dict[str, Any]:
        """FIX 6 — includes audio_mode, voice_style, target_platforms, hashtags."""
        return {
            "id":          self.id,
            "title":       self.title,
            "description": self.description,
            "niche":       self.niche,
            "video_type":  self.video_type,
            "audio_mode":  self.audio_mode,      # FIX 6
            "voice_style": self.voice_style,     # FIX 6
            "target_platforms": self.target_platforms or [],  # FIX 6
            "duration":     self.duration,
            "aspect_ratio": self.aspect_ratio,
            "style":        self.style,
            "captions_enabled":         self.captions_enabled,
            "caption_style":            self.caption_style,
            "background_music_enabled": self.background_music_enabled,
            "background_music_style":   self.background_music_style,
            "character_consistency_enabled": self.character_consistency_enabled,
            "status":        self.status.value,
            "status_label":  self.status_label,  # FIX 6
            "progress":      self.progress,
            "video_url":     self.video_url,
            "thumbnail_url": self.thumbnail_url,
            "file_size":     self.file_size,
            "resolution":    self.resolution,
            "hashtags":      self.hashtags or [],  # FIX 6
            "narration_text": self.narration_text, # FIX 6
            "view_count":    self.view_count,
            "download_count":self.download_count,
            "error_message": self.error_message,
            "is_scheduled":  self.is_scheduled,
            "created_at":    self.created_at.isoformat()   if self.created_at   else None,
            "started_at":    self.started_at.isoformat()   if self.started_at   else None,
            "completed_at":  self.completed_at.isoformat() if self.completed_at else None,
        }


# ─── VIDEO SCENE ──────────────────────────────────────────────────────────────

class VideoScene(Base):
    __tablename__ = "video_scenes"
    __table_args__ = (
        Index("ix_scenes_video_number", "video_id", "scene_number"),
    )

    id       = Column(String(36), primary_key=True, index=True)
    video_id = Column(
        String(36), ForeignKey("videos.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )

    scene_number = Column(Integer, nullable=False)
    description  = Column(Text,    nullable=False)
    caption      = Column(Text,    nullable=True)
    narration    = Column(Text,    nullable=True)

    image_url      = Column(String(500), nullable=True)
    image_prompt   = Column(Text,        nullable=True)
    video_clip_url = Column(String(500), nullable=True)

    duration   = Column(Float,   default=3.0, nullable=False)
    start_time = Column(Float,   nullable=True)
    end_time   = Column(Float,   nullable=True)

    status        = Column(SQLEnum(SceneStatus), default=SceneStatus.PENDING, nullable=False)
    error_message = Column(Text, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    video = relationship("Video", back_populates="scenes")

    def __repr__(self) -> str:
        return f"<VideoScene(video={self.video_id}, #{self.scene_number}, {self.status})>"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id":            self.id,
            "scene_number":  self.scene_number,
            "description":   self.description,
            "caption":       self.caption,
            "narration":     self.narration,
            "image_url":     self.image_url,
            "video_clip_url":self.video_clip_url,
            "duration":      self.duration,
            "start_time":    self.start_time,
            "end_time":      self.end_time,
            "status":        self.status.value,
            "error_message": self.error_message,
        }


# ─── VIDEO SCHEDULE ───────────────────────────────────────────────────────────

class VideoSchedule(Base):
    __tablename__ = "video_schedules"

    id      = Column(String(36), primary_key=True, index=True)
    user_id = Column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )

    name      = Column(String(100), nullable=True)
    is_active = Column(Boolean,     default=True, nullable=False)

    frequency        = Column(String(20), default="daily",          nullable=False)
    days_of_week     = Column(JSON,       default=lambda: [0,1,2,3,4,5,6])
    schedule_times   = Column(JSON,       default=lambda: [])
    cron_expression  = Column(String(100),nullable=True)

    video_config = Column(JSON, default=lambda: {})

    max_videos_per_day     = Column(Integer,  default=1,  nullable=False)
    videos_generated_today = Column(Integer,  default=0,  nullable=False)
    last_generated_at      = Column(DateTime, nullable=True)
    last_reset_at          = Column(DateTime, nullable=True)

    total_videos_generated = Column(Integer, default=0, nullable=False)
    total_videos_failed    = Column(Integer, default=0, nullable=False)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    user   = relationship("User",  back_populates="schedules")
    videos = relationship(
        "Video",
        back_populates="schedule",
        foreign_keys="Video.schedule_id",
    )

    def __repr__(self) -> str:
        return f"<VideoSchedule(id={self.id}, user={self.user_id}, active={self.is_active})>"

    def can_generate_today(self) -> bool:
        """
        FIX 5 — Pure read-only check. Does NOT mutate self.
        Call reset_daily_count() + db.commit() separately when needed.
        """
        if not self.is_active:
            return False
        if self.videos_generated_today >= self.max_videos_per_day:
            return False
        if self.days_of_week:
            if datetime.utcnow().weekday() not in self.days_of_week:
                return False
        return True

    def needs_daily_reset(self) -> bool:
        """Return True if the daily counter is stale and should be reset."""
        if not self.last_reset_at:
            return True
        return datetime.utcnow().date() > self.last_reset_at.date()

    def reset_daily_count(self) -> None:
        """Reset daily count. Caller must commit the session."""
        self.videos_generated_today = 0
        self.last_reset_at          = datetime.utcnow()

    def record_generated(self, success: bool = True) -> None:
        """Record a generation attempt. Caller must commit the session."""
        self.videos_generated_today += 1
        self.last_generated_at       = datetime.utcnow()
        if success:
            self.total_videos_generated += 1
        else:
            self.total_videos_failed += 1

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id":       self.id,
            "name":     self.name,
            "is_active":self.is_active,
            "frequency":self.frequency,
            "days_of_week":   self.days_of_week,
            "schedule_times": self.schedule_times,
            "max_videos_per_day":     self.max_videos_per_day,
            "videos_generated_today": self.videos_generated_today,
            "total_videos_generated": self.total_videos_generated,
            "total_videos_failed":    self.total_videos_failed,
            "last_generated_at": (
                self.last_generated_at.isoformat() if self.last_generated_at else None
            ),
            "video_config": self.video_config or {},
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
