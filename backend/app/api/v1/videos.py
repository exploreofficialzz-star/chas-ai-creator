"""
Video generation and management API routes.
FILE: app/api/v1/videos.py

FIXES:
1. CRITICAL — Route ordering: /schedules/list and /schedules/{id} were
   defined AFTER /{video_id}. FastAPI matched "schedules" as a video_id
   and returned 404 every time. Fixed by registering all /schedules/*
   routes BEFORE /{video_id}.

2. CreateVideoRequest was missing audio_mode, voice_style, target_platforms
   fields. The frontend (smart_create_screen.dart, api_service.dart) always
   sends these — they were silently dropped, causing wrong video generation.

3. Added GET "/" route (not just "/list") — api_service.dart tries "/" first
   and falls back to "/list" only on 404/405. The old code only had "/list"
   so every video list request triggered two API calls.

4. validate_video_config() was calling check_daily_limit(user, db=None) — 
   passing None as db causes AttributeError. Function removed; validation
   is done inline in create_video() where db is available.

5. VideoType enum extended — "sound_sync" added to match AudioMode.soundSync
   from the frontend.
"""

import uuid
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
from app.models.video import (
    Video, VideoScene, VideoSchedule,
    VideoStatus, VideoType, VideoStyle,
)
from app.tasks.video_generation import generate_video_task

logger = get_logger(__name__)
router = APIRouter()


# ─── AUTH DEPENDENCY ──────────────────────────────────────────────────────────

def get_current_user(
    authorization: str = Header(None),
    db: Session = Depends(get_db),
) -> User:
    if not authorization or not authorization.startswith("Bearer "):
        raise AuthenticationException(
            "You must be logged in to perform this action."
        )
    token = authorization.split(" ")[1]
    payload = verify_token(token)
    user_id = payload.get("sub")
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise AuthenticationException(
            "Account not found. Please log in again."
        )
    return user


# ─── REQUEST / RESPONSE MODELS ────────────────────────────────────────────────

class CreateVideoRequest(BaseModel):
    niche: str
    title: Optional[str] = None
    description: Optional[str] = None
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
    # FIX 2 — fields the frontend always sends (were silently dropped before)
    audio_mode: str = "silent"          # silent | narration | sound_sync
    voice_style: str = "professional"   # professional | friendly | dramatic…
    target_platforms: List[str] = Field(default_factory=lambda: ["tiktok"])


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


# ─── TIER LIMITS ─────────────────────────────────────────────────────────────

TIER_LIMITS = {
    "free": {
        "max_duration": 30,
        "daily_limit": 2,
        "can_use_narration": False,
        "can_use_character_consistency": False,
        "can_use_scheduling": False,
        "label": "Free",
    },
    "basic": {
        "max_duration": 60,
        "daily_limit": 10,
        "can_use_narration": True,
        "can_use_character_consistency": False,
        "can_use_scheduling": True,
        "label": "Basic",
    },
    "pro": {
        "max_duration": 300,
        "daily_limit": 50,
        "can_use_narration": True,
        "can_use_character_consistency": True,
        "can_use_scheduling": True,
        "label": "Pro",
    },
}


def get_tier_limits(user: User) -> dict:
    tier = user.subscription_tier
    tier_str = tier.value if hasattr(tier, "value") else str(tier)
    return TIER_LIMITS.get(tier_str.lower(), TIER_LIMITS["free"])


def check_daily_limit(user: User, db: Session) -> int:
    today_start = datetime.utcnow().replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    return db.query(Video).filter(
        Video.user_id == user.id,
        Video.created_at >= today_start,
    ).count()


def _video_to_response(v: Video) -> VideoResponse:
    """Convert Video ORM object to VideoResponse."""
    return VideoResponse(
        id=v.id,
        title=v.title,
        description=v.description,
        niche=v.niche,
        video_type=v.video_type.value
                   if hasattr(v.video_type, "value") else v.video_type,
        duration=v.duration,
        aspect_ratio=v.aspect_ratio,
        style=v.style.value if hasattr(v.style, "value") else v.style,
        status=v.status.value if hasattr(v.status, "value") else v.status,
        progress=v.progress,
        video_url=v.video_url,
        thumbnail_url=v.thumbnail_url,
        created_at=v.created_at.isoformat(),
        completed_at=v.completed_at.isoformat() if v.completed_at else None,
    )


def _schedule_to_response(s: VideoSchedule) -> ScheduleResponse:
    return ScheduleResponse(
        id=s.id,
        name=s.name,
        is_active=s.is_active,
        frequency=s.frequency,
        days_of_week=s.days_of_week or [],
        schedule_times=s.schedule_times or [],
        max_videos_per_day=s.max_videos_per_day,
        videos_generated_today=s.videos_generated_today,
        total_videos_generated=s.total_videos_generated,
        created_at=s.created_at.isoformat(),
    )


# ─── VALID VALUES ─────────────────────────────────────────────────────────────

VALID_RATIOS      = ["16:9", "9:16", "1:1"]
VALID_STYLES      = ["cartoon", "cinematic", "realistic",
                     "funny", "dramatic", "minimal"]
VALID_VIDEO_TYPES = ["silent", "narration", "sound_sync"]
VALID_AUDIO_MODES = ["silent", "narration", "sound_sync"]


# ─────────────────────────────────────────────────────────────────────────────
# IMPORTANT — route ordering:
# FIX 1: All /schedules/* routes MUST be registered before /{video_id}.
#         FastAPI matches routes in registration order. Without this,
#         GET /schedules/list was matched by /{video_id} with video_id=
#         "schedules", then the DB lookup for that ID returned 404.
# ─────────────────────────────────────────────────────────────────────────────


# ─── SCHEDULE ROUTES (registered first — before /{video_id}) ─────────────────

@router.post("/schedules", response_model=ScheduleResponse)
async def create_schedule(
    request: ScheduleRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create a video generation schedule."""
    limits = get_tier_limits(current_user)

    if not limits["can_use_scheduling"]:
        raise ValidationException(
            "📅 Video scheduling is not available on the Free plan. "
            "Upgrade to Basic or Pro to automate your content creation!"
        )

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

    logger.info(f"Schedule created: {schedule.id} for user {current_user.id}")
    return _schedule_to_response(schedule)


@router.get("/schedules/list")
async def list_schedules(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List user's video schedules."""
    schedules = db.query(VideoSchedule).filter(
        VideoSchedule.user_id == current_user.id
    ).order_by(VideoSchedule.created_at.desc()).all()

    return {"schedules": [_schedule_to_response(s) for s in schedules]}


@router.put("/schedules/{schedule_id}")
async def update_schedule(
    schedule_id: str,
    request: ScheduleRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update a video schedule."""
    schedule = db.query(VideoSchedule).filter(
        VideoSchedule.id == schedule_id,
        VideoSchedule.user_id == current_user.id,
    ).first()

    if not schedule:
        raise NotFoundException("Schedule not found.")

    schedule.name             = request.name
    schedule.frequency        = request.frequency
    schedule.days_of_week     = request.days_of_week or schedule.days_of_week
    schedule.schedule_times   = request.schedule_times
    schedule.max_videos_per_day = request.max_videos_per_day
    schedule.video_config     = request.video_config or schedule.video_config

    db.commit()
    db.refresh(schedule)

    logger.info(f"Schedule updated: {schedule_id}")
    return {"message": "✅ Schedule updated successfully."}


@router.delete("/schedules/{schedule_id}")
async def delete_schedule(
    schedule_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Delete a video schedule."""
    schedule = db.query(VideoSchedule).filter(
        VideoSchedule.id == schedule_id,
        VideoSchedule.user_id == current_user.id,
    ).first()

    if not schedule:
        raise NotFoundException("Schedule not found.")

    db.delete(schedule)
    db.commit()

    logger.info(f"Schedule deleted: {schedule_id}")
    return {"message": "✅ Schedule deleted successfully."}


# ─── VIDEO ROUTES ─────────────────────────────────────────────────────────────

@router.post("/generate", response_model=VideoResponse)
async def create_video(
    request: CreateVideoRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create and start video generation."""
    limits    = get_tier_limits(current_user)
    tier_label = limits["label"]

    # ── Niche ────────────────────────────────────────────────────────────────
    if not request.niche or not request.niche.strip():
        raise ValidationException(
            "📌 Please select a content niche before creating your video."
        )

    # ── Aspect ratio ─────────────────────────────────────────────────────────
    if request.aspect_ratio not in VALID_RATIOS:
        raise ValidationException(
            f"📐 Invalid aspect ratio. Choose one of: {', '.join(VALID_RATIOS)}."
        )

    # ── Style ────────────────────────────────────────────────────────────────
    if request.style not in VALID_STYLES:
        raise ValidationException(
            f"🎨 Invalid style. Choose one of: {', '.join(VALID_STYLES)}."
        )

    # ── Video type ────────────────────────────────────────────────────────────
    # FIX 2 — use audio_mode as primary source of truth; video_type is derived
    effective_type = request.audio_mode or request.video_type
    if effective_type not in VALID_AUDIO_MODES:
        raise ValidationException(
            "🎬 Invalid audio mode. Choose: silent, narration, or sound_sync."
        )

    # ── Duration ──────────────────────────────────────────────────────────────
    max_dur = limits["max_duration"]
    if request.duration > max_dur:
        if tier_label == "Free":
            raise ValidationException(
                f"⏱️ Free plan is limited to {max_dur}s per video. "
                "Upgrade to Basic (60s) or Pro (5 mins) for longer videos!"
            )
        elif tier_label == "Basic":
            raise ValidationException(
                f"⏱️ Basic plan is limited to {max_dur}s. "
                "Upgrade to Pro for videos up to 5 minutes!"
            )
        else:
            raise ValidationException(
                f"⏱️ Maximum duration is {max_dur} seconds."
            )

    # ── Daily limit ───────────────────────────────────────────────────────────
    videos_today = check_daily_limit(current_user, db)
    daily_limit  = limits["daily_limit"]
    if videos_today >= daily_limit:
        if tier_label == "Free":
            raise RateLimitException(
                f"📅 You've used all {daily_limit} free videos today. "
                "Come back tomorrow or upgrade to Pro for up to 50/day!"
            )
        else:
            raise RateLimitException(
                f"📅 Daily limit of {daily_limit} reached. "
                "Resets at midnight UTC."
            )

    # ── Narration gating ──────────────────────────────────────────────────────
    if effective_type == "narration" and not limits["can_use_narration"]:
        raise ValidationException(
            "🎙️ Narration videos are not available on the Free plan. "
            "Upgrade to Basic or Pro to add AI voiceover!"
        )

    # ── Character consistency gating ──────────────────────────────────────────
    if (request.character_consistency_enabled
            and not limits["can_use_character_consistency"]):
        raise ValidationException(
            "🎭 Character Consistency is a Pro-only feature. "
            "Upgrade to Pro to unlock it!"
        )

    # ── Create video record ───────────────────────────────────────────────────
    # Map audio_mode → VideoType enum value
    video_type_value = effective_type  # "silent" | "narration" | "sound_sync"

    video = Video(
        id=str(uuid.uuid4()),
        user_id=current_user.id,
        title=request.title,
        description=request.description,
        niche=request.niche.strip(),
        video_type=VideoType(video_type_value)
                   if video_type_value in [e.value for e in VideoType]
                   else VideoType("silent"),
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
        # FIX 2 — store the new fields
        audio_mode=request.audio_mode,
        voice_style=request.voice_style,
        target_platforms=request.target_platforms,
        status=VideoStatus.PENDING,
        progress=0,
    )

    db.add(video)
    db.commit()
    db.refresh(video)

    logger.info(
        f"Video generation started: {video.id} | "
        f"user={current_user.id} | niche={request.niche} | "
        f"tier={tier_label} | audio={request.audio_mode}"
    )

    background_tasks.add_task(generate_video_task, video.id)

    return _video_to_response(video)


# FIX 3 — Added GET "/" so api_service.dart doesn't always need the fallback
@router.get("/")
async def list_videos_root(
    status: Optional[str] = None,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    per_page: int = Query(20, ge=1, le=100),  # accept per_page alias from frontend
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List user's videos (primary endpoint)."""
    return await _list_videos(status, page, max(limit, per_page), current_user, db)


@router.get("/list")
async def list_videos_fallback(
    status: Optional[str] = None,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List user's videos (fallback endpoint for compatibility)."""
    return await _list_videos(status, page, limit, current_user, db)


async def _list_videos(
    status: Optional[str],
    page: int,
    limit: int,
    current_user: User,
    db: Session,
):
    query = db.query(Video).filter(Video.user_id == current_user.id)

    if status:
        try:
            query = query.filter(Video.status == VideoStatus(status))
        except ValueError:
            raise ValidationException(f"Invalid status filter: '{status}'.")

    total  = query.count()
    videos = query.order_by(Video.created_at.desc()).offset(
        (page - 1) * limit
    ).limit(limit).all()

    return {
        "videos": [_video_to_response(v) for v in videos],
        "total":  total,
        "page":   page,
        "pages":  (total + limit - 1) // limit,
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
        Video.user_id == current_user.id,
    ).first()
    if not video:
        raise NotFoundException("Video not found. It may have been deleted.")
    return _video_to_response(video)


@router.get("/{video_id}/scenes")
async def get_video_scenes(
    video_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get video scenes."""
    video = db.query(Video).filter(
        Video.id == video_id,
        Video.user_id == current_user.id,
    ).first()
    if not video:
        raise NotFoundException("Video not found.")

    scenes = db.query(VideoScene).filter(
        VideoScene.video_id == video_id
    ).order_by(VideoScene.scene_number).all()

    return {
        "scenes": [
            SceneResponse(
                id=s.id,
                scene_number=s.scene_number,
                description=s.description or "",
                caption=s.caption,
                narration=s.narration,
                image_url=s.image_url,
                video_clip_url=s.video_clip_url,
                duration=s.duration,
                status=s.status if isinstance(s.status, str)
                       else s.status.value,
            )
            for s in scenes
        ]
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
        Video.user_id == current_user.id,
    ).first()
    if not video:
        raise NotFoundException("Video not found or already deleted.")

    db.delete(video)
    db.commit()

    logger.info(f"Video deleted: {video_id} by user {current_user.id}")
    return {"message": "✅ Video deleted successfully."}


@router.post("/{video_id}/regenerate")
async def regenerate_video(
    video_id: str,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Regenerate a failed or cancelled video."""
    video = db.query(Video).filter(
        Video.id == video_id,
        Video.user_id == current_user.id,
    ).first()
    if not video:
        raise NotFoundException("Video not found.")

    failed_statuses = [VideoStatus.FAILED, VideoStatus.CANCELLED]
    if video.status not in failed_statuses:
        raise ValidationException(
            "⚠️ Only failed or cancelled videos can be regenerated."
        )

    limits = get_tier_limits(current_user)
    if check_daily_limit(current_user, db) >= limits["daily_limit"]:
        raise RateLimitException(
            "📅 Daily limit reached. You can regenerate this video tomorrow, "
            "or upgrade for a higher daily limit!"
        )

    video.status        = VideoStatus.PENDING
    video.progress      = 0
    video.error_message = None
    db.commit()

    background_tasks.add_task(generate_video_task, video.id)

    logger.info(f"Video regeneration started: {video_id}")
    return {"message": "🔄 Video regeneration started!"}
