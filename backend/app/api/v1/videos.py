"""Video generation and management API routes."""

from datetime import datetime
from typing import Optional, List

from fastapi import APIRouter, Depends, Header, Query, BackgroundTasks
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.exceptions import (
    NotFoundException,
    AuthenticationException,
    ValidationException,
    RateLimitException,
)
from app.core.logging import get_logger
from app.core.security import verify_token
from app.db.base import get_db
from app.models.user import User
from app.models.video import Video, VideoScene, VideoSchedule, VideoStatus, VideoType, VideoStyle
from app.tasks.video_generation import generate_video_task

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
class CreateVideoRequest(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    niche: str
    video_type: str = "silent"
    duration: int = Field(default=30, ge=10, le=300)
    aspect_ratio: str = "9:16"
    style: str = "cinematic"
    character_consistency_enabled: bool = False
    character_description: Optional[str] = None
    captions_enabled: bool = True
    caption_style: str = "modern"
    caption_color: str = "white"
    caption_emoji_enabled: bool = True
    background_music_enabled: bool = True
    background_music_style: str = "upbeat"
    user_instructions: Optional[str] = None
    scene_priority_notes: Optional[str] = None


class VideoResponse(BaseModel):
    id: str
    title: Optional[str]
    description: Optional[str]
    niche: str
    video_type: str
    duration: int
    aspect_ratio: str
    style: str
    status: str
    progress: int
    video_url: Optional[str]
    thumbnail_url: Optional[str]
    created_at: str
    completed_at: Optional[str]


class SceneResponse(BaseModel):
    id: str
    scene_number: int
    description: str
    caption: Optional[str]
    narration: Optional[str]
    image_url: Optional[str]
    video_clip_url: Optional[str]
    duration: float
    status: str


class ScheduleRequest(BaseModel):
    name: Optional[str] = None
    frequency: str = "daily"
    days_of_week: Optional[List[int]] = None
    schedule_times: List[str]
    max_videos_per_day: int = 1
    video_config: Optional[dict] = None


class ScheduleResponse(BaseModel):
    id: str
    name: Optional[str]
    is_active: bool
    frequency: str
    days_of_week: List[int]
    schedule_times: List[str]
    max_videos_per_day: int
    videos_generated_today: int
    total_videos_generated: int
    created_at: str


# Helper functions
def check_daily_limit(user: User, db: Session) -> bool:
    """Check if user has exceeded daily video limit."""
    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    videos_today = db.query(Video).filter(
        Video.user_id == user.id,
        Video.created_at >= today_start
    ).count()
    
    return videos_today < user.daily_video_limit


def validate_video_config(request: CreateVideoRequest, user: User) -> None:
    """Validate video configuration."""
    # Check duration limit
    if request.duration > user.max_video_length:
        raise ValidationException(
            f"Duration exceeds maximum allowed ({user.max_video_length}s)"
        )
    
    # Validate aspect ratio
    valid_ratios = ["16:9", "9:16", "1:1"]
    if request.aspect_ratio not in valid_ratios:
        raise ValidationException(f"Invalid aspect ratio. Must be one of: {valid_ratios}")
    
    # Validate style
    valid_styles = ["cartoon", "cinematic", "realistic", "funny", "dramatic", "minimal"]
    if request.style not in valid_styles:
        raise ValidationException(f"Invalid style. Must be one of: {valid_styles}")
    
    # Validate video type
    if request.video_type not in ["silent", "narration"]:
        raise ValidationException("Video type must be 'silent' or 'narration'")


@router.post("/generate", response_model=VideoResponse)
async def create_video(
    request: CreateVideoRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create and start video generation."""
    # Check daily limit
    if not check_daily_limit(current_user, db):
        raise RateLimitException("Daily video limit exceeded")
    
    # Validate configuration
    validate_video_config(request, current_user)
    
    # Check narration permission
    if request.video_type == "narration" and current_user.subscription_tier.value == "free":
        raise ValidationException("Narration requires Pro subscription")
    
    # Create video record
    import uuid
    video = Video(
        id=str(uuid.uuid4()),
        user_id=current_user.id,
        title=request.title,
        description=request.description,
        niche=request.niche,
        video_type=VideoType(request.video_type),
        duration=request.duration,
        aspect_ratio=request.aspect_ratio,
        style=VideoStyle(request.style),
        character_consistency_enabled=request.character_consistency_enabled,
        character_description=request.character_description,
        captions_enabled=request.captions_enabled,
        caption_style=request.caption_style,
        caption_color=request.caption_color,
        caption_emoji_enabled=request.caption_emoji_enabled,
        background_music_enabled=request.background_music_enabled,
        background_music_style=request.background_music_style,
        user_instructions=request.user_instructions,
        scene_priority_notes=request.scene_priority_notes,
        status=VideoStatus.PENDING,
        progress=0,
    )
    
    db.add(video)
    db.commit()
    db.refresh(video)
    
    logger.info(
        "Video generation started",
        video_id=video.id,
        user_id=current_user.id,
        niche=request.niche,
    )
    
    # Queue video generation task
    background_tasks.add_task(generate_video_task, video.id)
    
    return VideoResponse(
        id=video.id,
        title=video.title,
        description=video.description,
        niche=video.niche,
        video_type=video.video_type.value,
        duration=video.duration,
        aspect_ratio=video.aspect_ratio,
        style=video.style.value,
        status=video.status.value,
        progress=video.progress,
        video_url=video.video_url,
        thumbnail_url=video.thumbnail_url,
        created_at=video.created_at.isoformat(),
        completed_at=video.completed_at.isoformat() if video.completed_at else None,
    )


@router.get("/list")
async def list_videos(
    status: Optional[str] = None,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List user's videos."""
    query = db.query(Video).filter(Video.user_id == current_user.id)
    
    if status:
        query = query.filter(Video.status == status)
    
    total = query.count()
    videos = query.order_by(Video.created_at.desc()).offset(
        (page - 1) * limit
    ).limit(limit).all()
    
    return {
        "videos": [VideoResponse(
            id=v.id,
            title=v.title,
            description=v.description,
            niche=v.niche,
            video_type=v.video_type.value,
            duration=v.duration,
            aspect_ratio=v.aspect_ratio,
            style=v.style.value,
            status=v.status.value,
            progress=v.progress,
            video_url=v.video_url,
            thumbnail_url=v.thumbnail_url,
            created_at=v.created_at.isoformat(),
            completed_at=v.completed_at.isoformat() if v.completed_at else None,
        ) for v in videos],
        "total": total,
        "page": page,
        "pages": (total + limit - 1) // limit,
    }


@router.get("/{video_id}", response_model=VideoResponse)
async def get_video(
    video_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get video details."""
    video = db.query(Video).filter(
        Video.id == video_id,
        Video.user_id == current_user.id
    ).first()
    
    if not video:
        raise NotFoundException("Video not found")
    
    return VideoResponse(
        id=video.id,
        title=video.title,
        description=video.description,
        niche=video.niche,
        video_type=video.video_type.value,
        duration=video.duration,
        aspect_ratio=video.aspect_ratio,
        style=video.style.value,
        status=video.status.value,
        progress=video.progress,
        video_url=video.video_url,
        thumbnail_url=video.thumbnail_url,
        created_at=video.created_at.isoformat(),
        completed_at=video.completed_at.isoformat() if video.completed_at else None,
    )


@router.get("/{video_id}/scenes")
async def get_video_scenes(
    video_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get video scenes."""
    video = db.query(Video).filter(
        Video.id == video_id,
        Video.user_id == current_user.id
    ).first()
    
    if not video:
        raise NotFoundException("Video not found")
    
    scenes = db.query(VideoScene).filter(
        VideoScene.video_id == video_id
    ).order_by(VideoScene.scene_number).all()
    
    return {
        "scenes": [SceneResponse(
            id=s.id,
            scene_number=s.scene_number,
            description=s.description,
            caption=s.caption,
            narration=s.narration,
            image_url=s.image_url,
            video_clip_url=s.video_clip_url,
            duration=s.duration,
            status=s.status,
        ) for s in scenes]
    }


@router.delete("/{video_id}")
async def delete_video(
    video_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Delete a video."""
    video = db.query(Video).filter(
        Video.id == video_id,
        Video.user_id == current_user.id
    ).first()
    
    if not video:
        raise NotFoundException("Video not found")
    
    # Delete from database (cascade will handle scenes)
    db.delete(video)
    db.commit()
    
    logger.info("Video deleted", video_id=video_id, user_id=current_user.id)
    
    return {"message": "Video deleted successfully"}


@router.post("/{video_id}/regenerate")
async def regenerate_video(
    video_id: str,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Regenerate a failed video."""
    video = db.query(Video).filter(
        Video.id == video_id,
        Video.user_id == current_user.id
    ).first()
    
    if not video:
        raise NotFoundException("Video not found")
    
    if video.status not in [VideoStatus.FAILED, VideoStatus.CANCELLED]:
        raise ValidationException("Only failed or cancelled videos can be regenerated")
    
    # Reset status
    video.status = VideoStatus.PENDING
    video.progress = 0
    video.error_message = None
    db.commit()
    
    # Queue regeneration
    background_tasks.add_task(generate_video_task, video.id)
    
    logger.info("Video regeneration started", video_id=video_id, user_id=current_user.id)
    
    return {"message": "Video regeneration started"}


# Schedule routes
@router.post("/schedules", response_model=ScheduleResponse)
async def create_schedule(
    request: ScheduleRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create video generation schedule."""
    import uuid
    
    schedule = VideoSchedule(
        id=str(uuid.uuid4()),
        user_id=current_user.id,
        name=request.name,
        frequency=request.frequency,
        days_of_week=request.days_of_week or [0, 1, 2, 3, 4, 5, 6],
        schedule_times=request.schedule_times,
        max_videos_per_day=request.max_videos_per_day,
        video_config=request.video_config or {},
    )
    
    db.add(schedule)
    db.commit()
    db.refresh(schedule)
    
    logger.info("Schedule created", schedule_id=schedule.id, user_id=current_user.id)
    
    return ScheduleResponse(
        id=schedule.id,
        name=schedule.name,
        is_active=schedule.is_active,
        frequency=schedule.frequency,
        days_of_week=schedule.days_of_week,
        schedule_times=schedule.schedule_times,
        max_videos_per_day=schedule.max_videos_per_day,
        videos_generated_today=schedule.videos_generated_today,
        total_videos_generated=schedule.total_videos_generated,
        created_at=schedule.created_at.isoformat(),
    )


@router.get("/schedules/list")
async def list_schedules(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List user's video schedules."""
    schedules = db.query(VideoSchedule).filter(
        VideoSchedule.user_id == current_user.id
    ).order_by(VideoSchedule.created_at.desc()).all()
    
    return {
        "schedules": [ScheduleResponse(
            id=s.id,
            name=s.name,
            is_active=s.is_active,
            frequency=s.frequency,
            days_of_week=s.days_of_week,
            schedule_times=s.schedule_times,
            max_videos_per_day=s.max_videos_per_day,
            videos_generated_today=s.videos_generated_today,
            total_videos_generated=s.total_videos_generated,
            created_at=s.created_at.isoformat(),
        ) for s in schedules]
    }


@router.put("/schedules/{schedule_id}")
async def update_schedule(
    schedule_id: str,
    request: ScheduleRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update video schedule."""
    schedule = db.query(VideoSchedule).filter(
        VideoSchedule.id == schedule_id,
        VideoSchedule.user_id == current_user.id
    ).first()
    
    if not schedule:
        raise NotFoundException("Schedule not found")
    
    # Update fields
    schedule.name = request.name
    schedule.frequency = request.frequency
    schedule.days_of_week = request.days_of_week or schedule.days_of_week
    schedule.schedule_times = request.schedule_times
    schedule.max_videos_per_day = request.max_videos_per_day
    schedule.video_config = request.video_config or schedule.video_config
    
    db.commit()
    db.refresh(schedule)
    
    logger.info("Schedule updated", schedule_id=schedule_id, user_id=current_user.id)
    
    return {"message": "Schedule updated successfully"}


@router.delete("/schedules/{schedule_id}")
async def delete_schedule(
    schedule_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Delete video schedule."""
    schedule = db.query(VideoSchedule).filter(
        VideoSchedule.id == schedule_id,
        VideoSchedule.user_id == current_user.id
    ).first()
    
    if not schedule:
        raise NotFoundException("Schedule not found")
    
    db.delete(schedule)
    db.commit()
    
    logger.info("Schedule deleted", schedule_id=schedule_id, user_id=current_user.id)
    
    return {"message": "Schedule deleted successfully"}
