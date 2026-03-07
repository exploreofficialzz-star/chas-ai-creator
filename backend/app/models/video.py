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
    Integer,
    String,
    Text,
    JSON,
    Float,
)
from sqlalchemy.orm import relationship

from app.db.base import Base


class VideoStatus(str, Enum):
    """Video generation status."""
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
    """Video type options."""
    SILENT = "silent"
    NARRATION = "narration"


class VideoStyle(str, Enum):
    """Video style presets."""
    CARTOON = "cartoon"
    CINEMATIC = "cinematic"
    REALISTIC = "realistic"
    FUNNY = "funny"
    DRAMATIC = "dramatic"
    MINIMAL = "minimal"


class Video(Base):
    """Video model for generated content."""
    
    __tablename__ = "videos"
    
    id = Column(String(36), primary_key=True, index=True)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    
    # Basic Info
    title = Column(String(200), nullable=True)
    description = Column(Text, nullable=True)
    niche = Column(String(50), nullable=False)
    
    # Video Configuration
    video_type = Column(SQLEnum(VideoType), default=VideoType.SILENT)
    duration = Column(Integer, default=30)  # seconds
    aspect_ratio = Column(String(10), default="9:16")  # 16:9, 9:16, 1:1
    style = Column(SQLEnum(VideoStyle), default=VideoStyle.CINEMATIC)
    
    # Character Consistency
    character_consistency_enabled = Column(Boolean, default=False)
    character_description = Column(Text, nullable=True)
    
    # Captions
    captions_enabled = Column(Boolean, default=True)
    caption_style = Column(String(50), default="modern")
    caption_color = Column(String(20), default="white")
    caption_emoji_enabled = Column(Boolean, default=True)
    
    # Background Music
    background_music_enabled = Column(Boolean, default=True)
    background_music_url = Column(String(500), nullable=True)
    background_music_style = Column(String(50), default="upbeat")
    
    # User Instructions
    user_instructions = Column(Text, nullable=True)
    scene_priority_notes = Column(Text, nullable=True)
    
    # Generated Content
    script = Column(JSON, nullable=True)  # Full script with scenes
    narration_text = Column(Text, nullable=True)
    hashtags = Column(JSON, default=list)
    
    # Status & Progress
    status = Column(SQLEnum(VideoStatus), default=VideoStatus.PENDING)
    progress = Column(Integer, default=0)  # 0-100
    error_message = Column(Text, nullable=True)
    
    # File URLs
    video_url = Column(String(500), nullable=True)
    thumbnail_url = Column(String(500), nullable=True)
    
    # Metadata
    file_size = Column(Integer, nullable=True)  # bytes
    resolution = Column(String(20), nullable=True)  # e.g., "1080x1920"
    fps = Column(Integer, default=24)
    
    # Analytics
    view_count = Column(Integer, default=0)
    download_count = Column(Integer, default=0)
    
    # Scheduling
    is_scheduled = Column(Boolean, default=False)
    scheduled_for = Column(DateTime, nullable=True)
    schedule_id = Column(String(36), ForeignKey("video_schedules.id"), nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    
    # Relationships
    user = relationship("User", back_populates="videos")
    scenes = relationship("VideoScene", back_populates="video", cascade="all, delete-orphan")
    schedule = relationship("VideoSchedule", back_populates="videos")
    
    def __repr__(self) -> str:
        return f"<Video(id={self.id}, status={self.status}, user_id={self.user_id})>"
    
    @property
    def is_completed(self) -> bool:
        """Check if video generation is completed."""
        return self.status == VideoStatus.COMPLETED
    
    @property
    def is_failed(self) -> bool:
        """Check if video generation failed."""
        return self.status == VideoStatus.FAILED
    
    @property
    def is_processing(self) -> bool:
        """Check if video is currently being processed."""
        return self.status in [
            VideoStatus.SCRIPT_GENERATING,
            VideoStatus.IMAGES_GENERATING,
            VideoStatus.VIDEO_GENERATING,
            VideoStatus.AUDIO_GENERATING,
            VideoStatus.COMPOSING,
        ]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert video to dictionary."""
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
            "progress": self.progress,
            "video_url": self.video_url,
            "thumbnail_url": self.thumbnail_url,
            "resolution": self.resolution,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }


class VideoScene(Base):
    """Individual scene within a video."""
    
    __tablename__ = "video_scenes"
    
    id = Column(String(36), primary_key=True, index=True)
    video_id = Column(String(36), ForeignKey("videos.id"), nullable=False, index=True)
    
    # Scene Order
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
    duration = Column(Float, default=3.0)  # seconds
    start_time = Column(Float, nullable=True)  # seconds from video start
    end_time = Column(Float, nullable=True)  # seconds from video start
    
    # Status
    status = Column(String(20), default="pending")  # pending, generating, completed, failed
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    video = relationship("Video", back_populates="scenes")
    
    def __repr__(self) -> str:
        return f"<VideoScene(video_id={self.video_id}, scene={self.scene_number})>"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert scene to dictionary."""
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
            "status": self.status,
        }


class VideoSchedule(Base):
    """Scheduled video generation tasks."""
    
    __tablename__ = "video_schedules"
    
    id = Column(String(36), primary_key=True, index=True)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    
    # Schedule Configuration
    name = Column(String(100), nullable=True)
    is_active = Column(Boolean, default=True)
    
    # Frequency
    frequency = Column(String(20), default="daily")  # daily, weekly, custom
    days_of_week = Column(JSON, default=list)  # [0, 1, 2, 3, 4, 5, 6] for Mon-Sun
    
    # Times (cron-style or specific times)
    schedule_times = Column(JSON, default=list)  # ["09:00", "15:00", "20:00"]
    cron_expression = Column(String(100), nullable=True)
    
    # Video Configuration (overrides user defaults)
    video_config = Column(JSON, default=dict)  # Video generation settings
    
    # Limits
    max_videos_per_day = Column(Integer, default=1)
    videos_generated_today = Column(Integer, default=0)
    last_generated_at = Column(DateTime, nullable=True)
    
    # Statistics
    total_videos_generated = Column(Integer, default=0)
    total_videos_failed = Column(Integer, default=0)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user = relationship("User", back_populates="schedules")
    videos = relationship("Video", back_populates="schedule")
    
    def __repr__(self) -> str:
        return f"<VideoSchedule(user_id={self.user_id}, active={self.is_active})>"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert schedule to dictionary."""
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
            "video_config": self.video_config,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
    
    def can_generate_today(self) -> bool:
        """Check if schedule can generate more videos today."""
        if not self.is_active:
            return False
        if self.videos_generated_today >= self.max_videos_per_day:
            return False
        
        # Check if today is in allowed days
        if self.days_of_week:
            today = datetime.utcnow().weekday()
            if today not in self.days_of_week:
                return False
        
        return True
    
    def reset_daily_count(self) -> None:
        """Reset daily video count."""
        self.videos_generated_today = 0
