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


# ─── AUTH DEPENDENCY ─────────────────────────────────────────────────────────

def get_current_user(
    authorization: str = Header(None),
    db: Session = Depends(get_db),
) -> User:
    if not authorization or not authorization.startswith("Bearer "):
        raise AuthenticationException("You must be logged in to perform this action.")

    token = authorization.split(" ")[1]
    payload = verify_token(token)
    user_id = payload.get("sub")

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise AuthenticationException("Account not found. Please log in again.")

    return user


# ─── REQUEST / RESPONSE MODELS ───────────────────────────────────────────────

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


# ─── HELPERS ─────────────────────────────────────────────────────────────────

# Subscription tier limits
TIER_LIMITS = {
    "free": {
        "max_duration": 30,
        "daily_limit": 2,
        "can_use_narration": False,
        "can_use_character_consistency": False,
        "label": "Free",
    },
    "basic": {
        "max_duration": 60,
        "daily_limit": 10,
        "can_use_narration": True,
        "can_use_character_consistency": False,
        "label": "Basic",
    },
    "pro": {
        "max_duration": 300,
        "daily_limit": 50,
        "can_use_narration": True,
        "can_use_character_consistency": True,
        "label": "Pro",
    },
}

def get_tier_limits(user: User) -> dict:
    """Get limits for a user's subscription tier."""
    tier = user.subscription_tier
    # Handle both string and enum values
    tier_str = tier.value if hasattr(tier, "value") else str(tier)
    return TIER_LIMITS.get(tier_str.lower(), TIER_LIMITS["free"])


def check_daily_limit(user: User, db: Session) -> int:
    """Return number of videos created today by user."""
    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    return db.query(Video).filter(
        Video.user_id == user.id,
        Video.created_at >= today_start
    ).count()


def validate_video_config(request: CreateVideoRequest, user: User) -> None:
    """Validate video configuration with friendly error messages."""
    limits = get_tier_limits(user)
    tier_label = limits["label"]

    # ── Duration check ──────────────────────────────────────────────────────
    max_duration = limits["max_duration"]
    if request.duration > max_duration:
        if tier_label == "Free":
            raise ValidationException(
                f"⏱️ Free plan videos are limited to {max_duration} seconds. "
                f"Upgrade to Basic (60s) or Pro (5 mins) to create longer videos!"
            )
        elif tier_label == "Basic":
            raise ValidationException(
                f"⏱️ Basic plan videos are limited to {max_duration} seconds. "
                f"Upgrade to Pro to create videos up to 5 minutes long!"
            )
        else:
            raise ValidationException(
                f"⏱️ Maximum video duration is {max_duration} seconds."
            )

    # ── Daily limit check ───────────────────────────────────────────────────
    videos_today = check_daily_limit(user, db=None)  # will be called separately
    daily_limit = limits["daily_limit"]
    if videos_today >= daily_limit:
        if tier_label == "Free":
            raise RateLimitException(
                f"📅 You've used all {daily_limit} free videos for today. "
                f"Come back tomorrow or upgrade to Pro for up to 50 videos per day!"
            )
        else:
            raise RateLimitException(
                f"📅 You've reached your daily limit of {daily_limit} videos. "
                f"Your limit resets at midnight UTC."
            )

    # ── Narration check ─────────────────────────────────────────────────────
    if request.video_type == "narration" and not limits["can_use_narration"]:
        raise ValidationException(
            "🎙️ Narration videos are not available on the Free plan. "
            "Upgrade to Basic or Pro to add AI voiceover to your videos!"
        )

    # ── Character consistency check ─────────────────────────────────────────
    if request.character_consistency_enabled and not limits["can_use_character_consistency"]:
        raise ValidationException(
            "🎭 Character Consistency is a Pro-only feature. "
            "Upgrade to Pro to keep consistent characters across all your scenes!"
        )

    # ── Aspect ratio check ──────────────────────────────────────────────────
    valid_ratios = ["16:9", "9:16", "1:1"]
    if request.aspect_ratio not in valid_ratios:
        raise ValidationException(
            f"📐 Invalid aspect ratio '{request.aspect_ratio}'. "
            f"Please choose one of: {', '.join(valid_ratios)}."
        )

    # ── Style check ─────────────────────────────────────────────────────────
    valid_styles = ["cartoon", "cinematic", "realistic", "funny", "dramatic", "minimal"]
    if request.style not in valid_styles:
        raise ValidationException(
            f"🎨 Invalid style '{request.style}'. "
            f"Please choose one of: {', '.join(valid_styles)}."
        )

    # ── Video type check ────────────────────────────────────────────────────
    if request.video_type not in ["silent", "narration"]:
        raise ValidationException(
            "🎬 Invalid video type. Please select either 'Silent' or 'Narration'."
        )

    # ── Niche check ─────────────────────────────────────────────────────────
    if not request.niche or len(request.niche.strip()) == 0:
        raise ValidationException(
            "📌 Please select a content niche before creating your video."
        )


# ─── VIDEO ROUTES ─────────────────────────────────────────────────────────────

@router.post("/generate", response_model=VideoResponse)
async def create_video(
    request: CreateVideoRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create and start video generation."""
    limits = get_tier_limits(current_user)
    tier_label = limits["label"]

    # ── Daily limit ──────────────────────────────────────────────────────────
    videos_today = check_daily_limit(current_user, db)
    daily_limit = limits["daily_limit"]
    if videos_today >= daily_limit:
        if tier_label == "Free":
            raise RateLimitException(
                f"📅 You've used all {daily_limit} free videos for today. "
                f"Come back tomorrow or upgrade to Pro for up to 50 videos/day!"
            )
        else:
            raise RateLimitException(
                f"📅 Daily limit of {daily_limit} videos reached. Resets at midnight UTC."
            )

    # ── Duration ─────────────────────────────────────────────────────────────
    max_duration = limits["max_duration"]
    if request.duration > max_duration:
        if tier_label == "Free":
            raise ValidationException(
                f"⏱️ Free plan is limited to {max_duration} seconds per video. "
                f"Upgrade to Basic (60s) or Pro (5 mins) for longer videos!"
            )
        elif tier_label == "Basic":
            raise ValidationException(
                f"⏱️ Basic plan is limited to {max_duration} seconds. "
                f"Upgrade to Pro for videos up to 5 minutes!"
            )
        else:
            raise ValidationException(f"⏱️ Maximum duration is {max_duration} seconds.")

    # ── Narration ─────────────────────────────────────────────────────────────
    if request.video_type == "narration" and not limits["can_use_narration"]:
        raise ValidationException(
            "🎙️ Narration is not available on the Free plan. "
            "Upgrade to Basic or Pro to add AI voiceover to your videos!"
        )

    # ── Character consistency ─────────────────────────────────────────────────
    if request.character_consistency_enabled and not limits["can_use_character_consistency"]:
        raise ValidationException(
            "🎭 Character Consistency is a Pro-only feature. "
            "Upgrade to Pro to unlock it!"
        )

    # ── Aspect ratio ──────────────────────────────────────────────────────────
    valid_ratios = ["16:9", "9:16", "1:1"]
    if request.aspect_ratio not in valid_ratios:
        raise ValidationException(
            f"📐 Invalid aspect ratio. Choose one of: {', '.join(valid_ratios)}."
        )

    # ── Style ─────────────────────────────────────────────────────────────────
    valid_styles = ["cartoon", "cinematic", "realistic", "funny", "dramatic", "minimal"]
    if request.style not in valid_styles:
        raise ValidationException(
            f"🎨 Invalid style. Choose one of: {', '.join(valid_styles)}."
        )

    # ── Video type ────────────────────────────────────────────────────────────
    if request.video_type not in ["silent", "narration"]:
        raise ValidationException(
            "🎬 Invalid video type. Please select 'Silent' or 'Narration'."
        )

    # ── Create video record ───────────────────────────────────────────────────
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
        tier=tier_label,
    )

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
        try:
            query = query.filter(Video.status == VideoStatus(status))
        except ValueError:
            raise ValidationException(f"Invalid status filter: '{status}'.")

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
        raise NotFoundException("Video not found. It may have been deleted.")

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
        raise NotFoundException("Video not found.")

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
        raise NotFoundException("Video not found or already deleted.")

    db.delete(video)
    db.commit()

    logger.info("Video deleted", video_id=video_id, user_id=current_user.id)
    return {"message": "✅ Video deleted successfully."}


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
        raise NotFoundException("Video not found.")

    if video.status not in [VideoStatus.FAILED, VideoStatus.CANCELLED]:
        raise ValidationException(
            "⚠️ Only failed or cancelled videos can be regenerated."
        )

    # Check daily limit before regenerating
    limits = get_tier_limits(current_user)
    videos_today = check_daily_limit(current_user, db)
    if videos_today >= limits["daily_limit"]:
        raise RateLimitException(
            f"📅 Daily limit reached. You can regenerate this video tomorrow, "
            f"or upgrade your plan for a higher daily limit!"
        )

    video.status = VideoStatus.PENDING
    video.progress = 0
    video.error_message = None
    db.commit()

    background_tasks.add_task(generate_video_task, video.id)

    logger.info("Video regeneration started", video_id=video_id, user_id=current_user.id)
    return {"message": "🔄 Video regeneration started!"}


# ─── SCHEDULE ROUTES ──────────────────────────────────────────────────────────

@router.post("/schedules", response_model=ScheduleResponse)
async def create_schedule(
    request: ScheduleRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create video generation schedule."""
    limits = get_tier_limits(current_user)

    # Only Basic and Pro can use scheduling
    if limits["label"] == "Free":
        raise ValidationException(
            "📅 Video scheduling is not available on the Free plan. "
            "Upgrade to Basic or Pro to automate your content creation!"
        )

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
        raise NotFoundException("Schedule not found.")

    schedule.name = request.name
    schedule.frequency = request.frequency
    schedule.days_of_week = request.days_of_week or schedule.days_of_week
    schedule.schedule_times = request.schedule_times
    schedule.max_videos_per_day = request.max_videos_per_day
    schedule.video_config = request.video_config or schedule.video_config

    db.commit()
    db.refresh(schedule)

    logger.info("Schedule updated", schedule_id=schedule_id, user_id=current_user.id)
    return {"message": "✅ Schedule updated successfully."}


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
        raise NotFoundException("Schedule not found.")

    db.delete(schedule)
    db.commit()

    logger.info("Schedule deleted", schedule_id=schedule_id, user_id=current_user.id)
    return {"message": "✅ Schedule deleted successfully."}
