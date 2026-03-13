"""
Video generation and management API routes.
FILE: app/api/v1/videos.py

BUGS FIXED:
1. CRITICAL — video_type INSERT crash: "invalid input value for enum videotype"
   _safe_video_type() returned a VideoType enum OBJECT. String(20) column
   passes it to psycopg2 which calls str(obj) → PostgreSQL rejects it.
   Fixed: _safe_video_type() now returns .value (a plain string).
   Same fix applied to style via new _safe_style() helper.

2. CRITICAL — style INSERT crash: same psycopg2 enum-object issue.
   VideoStyle(request.style) returned a VideoStyle enum OBJECT.
   Fixed: _safe_style() always returns the .value string with fallback.

3. CRITICAL — VideoStatus.PROCESSING does not exist in VideoStatus enum.
   smart_generate_start() set video.status = VideoStatus.PROCESSING
   → AttributeError at runtime, every "start rendering" tap raised 500.
   Fixed: use VideoStatus.PENDING — generate_video_task advances through
   all intermediate statuses (SCRIPT_GENERATING → … → COMPLETED) itself.

4. target_platforms stored as JSON string '["tiktok"]' instead of a list.
   JSON/JSONB column expects a Python object. Pydantic v2 can serialise
   List[str] to a JSON string in some request-handling paths.
   Fixed: _safe_platforms() coerces to a Python list before Video().
"""

import uuid
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, Header, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.exceptions import (
    AuthenticationException,
    NotFoundException,
    RateLimitException,
    ValidationException,
)
from app.core.logging import get_logger
from app.core.security import verify_token
from app.db.base import get_db
from app.models.user import User
from app.models.video import (
    Video,
    VideoSchedule,
    VideoScene,
    VideoStatus,
    VideoStyle,
    VideoType,
)
from app.services.ai.text_generation import AIGenerationError
from app.tasks.video_generation import generate_video_task

logger = get_logger(__name__)
router = APIRouter()


# ── Auth dependency ───────────────────────────────────────────────────────────

def get_current_user(
    authorization: str = Header(None),
    db: Session = Depends(get_db),
) -> User:
    if not authorization or not authorization.startswith("Bearer "):
        raise AuthenticationException("You must be logged in to perform this action.")
    token   = authorization.split(" ")[1]
    payload = verify_token(token)
    user    = db.query(User).filter(User.id == payload.get("sub")).first()
    if not user:
        raise AuthenticationException("Account not found. Please log in again.")
    return user


# ── Request / Response models ─────────────────────────────────────────────────

class CreateVideoRequest(BaseModel):
    niche:                          str
    title:                          Optional[str]       = None
    description:                    Optional[str]       = None
    video_type:                     str                 = "silent"
    duration:                       int                 = Field(default=30, ge=10, le=300)
    aspect_ratio:                   str                 = "9:16"
    style:                          str                 = "cinematic"
    character_consistency_enabled:  bool                = False
    character_description:          Optional[str]       = None
    captions_enabled:               bool                = True
    caption_style:                  str                 = "modern"
    caption_color:                  str                 = "white"
    caption_emoji_enabled:          bool                = True
    background_music_enabled:       bool                = True
    background_music_style:         str                 = "upbeat"
    user_instructions:              Optional[str]       = None
    scene_priority_notes:           Optional[str]       = None
    audio_mode:                     str                 = "silent"
    voice_style:                    str                 = "professional"
    target_platforms:               List[str]           = Field(default_factory=lambda: ["tiktok"])


class SmartGenerateRequest(BaseModel):
    idea:                           str
    aspect_ratio:                   str                 = "9:16"
    duration:                       int                 = Field(default=30, ge=10, le=300)
    style:                          str                 = "cinematic"
    audio_mode:                     str                 = "narration"
    voice_style:                    str                 = "professional"
    target_platforms:               List[str]           = Field(default_factory=lambda: ["tiktok"])
    captions_enabled:               bool                = True
    background_music_enabled:       bool                = True
    character_consistency:          bool                = False
    reference_images:               Optional[List[str]] = None


class VideoResponse(BaseModel):
    id:             str
    title:          Optional[str]
    description:    Optional[str]
    niche:          str
    video_type:     str
    duration:       int
    aspect_ratio:   str
    style:          str
    status:         str
    progress:       int
    video_url:      Optional[str]
    thumbnail_url:  Optional[str]
    created_at:     str
    completed_at:   Optional[str]


class SceneResponse(BaseModel):
    id:             str
    scene_number:   int
    description:    str
    caption:        Optional[str]
    narration:      Optional[str]
    image_url:      Optional[str]
    video_clip_url: Optional[str]
    duration:       float
    status:         str


class ScheduleRequest(BaseModel):
    name:               Optional[str]       = None
    frequency:          str                 = "daily"
    days_of_week:       Optional[List[int]] = None
    schedule_times:     List[str]
    max_videos_per_day: int                 = 1
    video_config:       Optional[dict]      = None


class ScheduleResponse(BaseModel):
    id:                      str
    name:                    Optional[str]
    is_active:               bool
    frequency:               str
    days_of_week:            List[int]
    schedule_times:          List[str]
    max_videos_per_day:      int
    videos_generated_today:  int
    total_videos_generated:  int
    created_at:              str


# ── Tier limits ───────────────────────────────────────────────────────────────

TIER_LIMITS = {
    "free":       {"max_duration": 30,  "daily_limit": 2,   "can_use_narration": False, "can_use_character_consistency": False, "can_use_scheduling": False, "label": "Free"},
    "basic":      {"max_duration": 60,  "daily_limit": 10,  "can_use_narration": True,  "can_use_character_consistency": False, "can_use_scheduling": True,  "label": "Basic"},
    "pro":        {"max_duration": 300, "daily_limit": 50,  "can_use_narration": True,  "can_use_character_consistency": True,  "can_use_scheduling": True,  "label": "Pro"},
    "enterprise": {"max_duration": 600, "daily_limit": 200, "can_use_narration": True,  "can_use_character_consistency": True,  "can_use_scheduling": True,  "label": "Enterprise"},
}


def get_tier_limits(user: User) -> dict:
    tier = user.subscription_tier
    t    = tier.value if hasattr(tier, "value") else str(tier)
    return TIER_LIMITS.get(t.lower(), TIER_LIMITS["free"])


def check_daily_limit(user: User, db: Session) -> int:
    today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    return db.query(Video).filter(
        Video.user_id    == user.id,
        Video.created_at >= today,
    ).count()


# ── Column value helpers — ALWAYS return plain strings, never enum objects ────

def _safe_video_type(value: str) -> str:
    """
    BUG 1 FIX — String(20) DB column requires a plain string.
    The old code returned VideoType(value) — an enum object.
    psycopg2 has no adapter for VideoType so it calls str(obj) which
    produces "<VideoType.SILENT: 'silent'>" → PostgreSQL rejects it.
    """
    valid = {e.value for e in VideoType}
    return value if value in valid else VideoType.SILENT.value


def _safe_style(value: str) -> str:
    """
    BUG 2 FIX — String(50) DB column requires a plain string.
    Old code: VideoStyle(request.style) → enum object → same crash.
    """
    valid = {e.value for e in VideoStyle}
    return value if value in valid else VideoStyle.CINEMATIC.value


def _safe_platforms(value) -> list:
    """
    BUG 4 FIX — JSONB column requires a Python list, not a pre-serialised
    string. Pydantic v2 can serialise List[str] to '["tiktok"]' in some
    request-handling paths; this coerces it back to a native list.
    """
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        import json as _json
        try:
            parsed = _json.loads(value)
            return parsed if isinstance(parsed, list) else [value]
        except Exception:
            return [value]
    return ["tiktok"]


def _video_to_response(v: Video) -> VideoResponse:
    return VideoResponse(
        id=v.id,
        title=v.title,
        description=v.description,
        niche=v.niche,
        video_type=v.video_type.value if hasattr(v.video_type, "value") else str(v.video_type),
        duration=v.duration,
        aspect_ratio=v.aspect_ratio,
        style=v.style.value if hasattr(v.style, "value") else str(v.style),
        status=v.status.value if hasattr(v.status, "value") else str(v.status),
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


VALID_RATIOS      = ["16:9", "9:16", "1:1"]
VALID_STYLES      = ["cartoon", "cinematic", "realistic", "funny", "dramatic", "minimal"]
VALID_AUDIO_MODES = ["silent", "narration", "sound_sync"]


# ── Background task wrapper ───────────────────────────────────────────────────

async def _run_generation(video_id: str, db_factory):
    """
    Wraps generate_video_task so any error marks the video FAILED
    in the DB instead of leaving it stuck in PENDING forever.
    """
    db: Session = db_factory()
    try:
        await generate_video_task(video_id)
    except AIGenerationError as e:
        logger.error(f"AIGenerationError for video {video_id}: {e}")
        video = db.query(Video).filter(Video.id == video_id).first()
        if video:
            video.status        = VideoStatus.FAILED
            video.progress      = 0
            video.error_message = (
                "AI generation failed — all providers are currently unavailable. "
                "Please try again in a few minutes."
            )
            db.commit()
    except Exception as e:
        logger.error(f"Unexpected error for video {video_id}: {e}", exc_info=True)
        video = db.query(Video).filter(Video.id == video_id).first()
        if video:
            video.status        = VideoStatus.FAILED
            video.progress      = 0
            video.error_message = f"Generation failed: {str(e)[:200]}"
            db.commit()
    finally:
        db.close()


# ─────────────────────────────────────────────────────────────────────────────
# ROUTE ORDER: /schedules/* and /smart-generate MUST come before /{video_id}
# ─────────────────────────────────────────────────────────────────────────────


# ── Schedule routes ───────────────────────────────────────────────────────────

@router.post("/schedules", response_model=ScheduleResponse)
async def create_schedule(
    request: ScheduleRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    limits = get_tier_limits(current_user)
    if not limits["can_use_scheduling"]:
        raise ValidationException(
            "📅 Video scheduling is not available on the Free plan. "
            "Upgrade to Basic or Pro to automate your content!"
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
    schedule = db.query(VideoSchedule).filter(
        VideoSchedule.id == schedule_id,
        VideoSchedule.user_id == current_user.id,
    ).first()
    if not schedule:
        raise NotFoundException("Schedule not found.")
    schedule.name               = request.name
    schedule.frequency          = request.frequency
    schedule.days_of_week       = request.days_of_week or schedule.days_of_week
    schedule.schedule_times     = request.schedule_times
    schedule.max_videos_per_day = request.max_videos_per_day
    schedule.video_config       = request.video_config or schedule.video_config
    db.commit()
    db.refresh(schedule)
    return {"message": "✅ Schedule updated successfully."}


@router.delete("/schedules/{schedule_id}")
async def delete_schedule(
    schedule_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    schedule = db.query(VideoSchedule).filter(
        VideoSchedule.id == schedule_id,
        VideoSchedule.user_id == current_user.id,
    ).first()
    if not schedule:
        raise NotFoundException("Schedule not found.")
    db.delete(schedule)
    db.commit()
    return {"message": "✅ Schedule deleted successfully."}


# ── Smart generate ─────────────────────────────────────────────────────────────

@router.post("/smart-generate")
async def smart_generate(
    request: SmartGenerateRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Step 1 of 2 — generates the AI plan and saves scenes.
    Returns immediately so the frontend can display the scene list.
    """
    limits     = get_tier_limits(current_user)
    tier_label = limits["label"]

    if request.audio_mode == "narration" and not limits["can_use_narration"]:
        raise ValidationException(
            "🎙️ Narration is not available on the Free plan. "
            "Upgrade to Basic or Pro!"
        )
    if request.character_consistency and not limits["can_use_character_consistency"]:
        raise ValidationException(
            "🎭 Character Consistency is a Pro-only feature. Upgrade to unlock!"
        )
    if request.duration > limits["max_duration"]:
        raise ValidationException(
            f"⏱️ {tier_label} plan is limited to {limits['max_duration']}s per video."
        )
    if check_daily_limit(current_user, db) >= limits["daily_limit"]:
        raise RateLimitException(
            f"📅 Daily limit of {limits['daily_limit']} videos reached. "
            "Resets at midnight UTC."
        )

    from app.services.ai.text_generation import TextGenerationService
    try:
        plan = await TextGenerationService().smart_generate_plan(
            idea=request.idea,
            aspect_ratio=request.aspect_ratio,
            duration=request.duration,
            style=request.style,
            audio_mode=request.audio_mode,
            voice_style=request.voice_style,
            target_platforms=request.target_platforms,
            captions_enabled=request.captions_enabled,
            background_music_enabled=request.background_music_enabled,
            character_consistency=request.character_consistency,
            reference_images=request.reference_images,
        )
    except AIGenerationError as e:
        logger.error(f"Smart generate AI error: {e}")
        raise ValidationException(str(e))

    # BUG 1 + 2 + 4 FIX — plain strings and Python list, never enum objects
    video = Video(
        id=str(uuid.uuid4()),
        user_id=current_user.id,
        title=plan.get("title", request.idea[:60]),
        description=plan.get("description", ""),
        niche=plan.get("niche", "general"),
        video_type=_safe_video_type(request.audio_mode),           # BUG 1 FIX
        duration=request.duration,
        aspect_ratio=request.aspect_ratio,
        style=_safe_style(request.style),                          # BUG 2 FIX
        character_consistency_enabled=request.character_consistency,
        captions_enabled=request.captions_enabled,
        background_music_enabled=request.background_music_enabled,
        audio_mode=request.audio_mode,
        voice_style=request.voice_style,
        target_platforms=_safe_platforms(request.target_platforms), # BUG 4 FIX
        user_instructions=request.idea,
        status=VideoStatus.PENDING,
        progress=0,
    )
    db.add(video)
    db.flush()

    for i, sd in enumerate(plan.get("scenes", [])):
        db.add(VideoScene(
            id=str(uuid.uuid4()),
            video_id=video.id,
            scene_number=sd.get("scene_number", i + 1),
            description=sd.get("description", ""),
            caption=sd.get("caption"),
            narration=sd.get("narration"),
            image_prompt=sd.get("image_prompt", ""),
            duration=sd.get("duration", 3.0),
            status="pending",
        ))

    db.commit()
    db.refresh(video)
    logger.info(
        f"Smart plan: video={video.id} "
        f"idea='{request.idea[:40]}' scenes={len(plan.get('scenes', []))}"
    )
    return {"video": _video_to_response(video), "plan": plan}


@router.post("/smart-generate/start/{video_id}")
async def smart_generate_start(
    video_id: str,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Step 2 of 2 — starts the actual rendering pipeline in the background."""
    video = db.query(Video).filter(
        Video.id      == video_id,
        Video.user_id == current_user.id,
    ).first()
    if not video:
        raise NotFoundException("Video not found.")
    if video.status not in [VideoStatus.PENDING, VideoStatus.FAILED]:
        raise ValidationException("Video is already processing or completed.")

    # BUG 3 FIX — VideoStatus.PROCESSING does not exist.
    # Keep PENDING — generate_video_task advances through all intermediate
    # states (SCRIPT_GENERATING → IMAGES_GENERATING → … → COMPLETED) itself.
    video.status   = VideoStatus.PENDING
    video.progress = 0
    db.commit()

    from app.db.base import SessionLocal
    background_tasks.add_task(_run_generation, video.id, SessionLocal)

    logger.info(f"Video rendering started: {video.id}")
    return {"message": "🎬 Video generation started!", "video_id": video.id}


# ── Standard video routes ─────────────────────────────────────────────────────

@router.post("/generate", response_model=VideoResponse)
async def create_video(
    request: CreateVideoRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Standard video creation (non-smart route)."""
    limits     = get_tier_limits(current_user)
    tier_label = limits["label"]

    if not request.niche or not request.niche.strip():
        raise ValidationException("📌 Please select a content niche.")
    if request.aspect_ratio not in VALID_RATIOS:
        raise ValidationException(f"📐 Invalid aspect ratio. Choose: {', '.join(VALID_RATIOS)}.")
    if request.style not in VALID_STYLES:
        raise ValidationException(f"🎨 Invalid style. Choose: {', '.join(VALID_STYLES)}.")

    effective_type = request.audio_mode or request.video_type
    if effective_type not in VALID_AUDIO_MODES:
        raise ValidationException("🎬 Invalid audio mode. Choose: silent, narration, or sound_sync.")
    if request.duration > limits["max_duration"]:
        raise ValidationException(
            f"⏱️ {tier_label} plan is limited to {limits['max_duration']}s per video."
        )
    if check_daily_limit(current_user, db) >= limits["daily_limit"]:
        raise RateLimitException(
            f"📅 Daily limit of {limits['daily_limit']} videos reached. "
            "Resets at midnight UTC."
        )
    if effective_type == "narration" and not limits["can_use_narration"]:
        raise ValidationException(
            "🎙️ Narration is not available on the Free plan. Upgrade to Basic or Pro!"
        )
    if request.character_consistency_enabled and not limits["can_use_character_consistency"]:
        raise ValidationException("🎭 Character Consistency is a Pro-only feature.")

    # BUG 1 + 2 + 4 FIX
    video = Video(
        id=str(uuid.uuid4()),
        user_id=current_user.id,
        title=request.title,
        description=request.description,
        niche=request.niche.strip(),
        video_type=_safe_video_type(effective_type),               # BUG 1 FIX
        duration=request.duration,
        aspect_ratio=request.aspect_ratio,
        style=_safe_style(request.style),                          # BUG 2 FIX
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
        audio_mode=request.audio_mode,
        voice_style=request.voice_style,
        target_platforms=_safe_platforms(request.target_platforms), # BUG 4 FIX
        status=VideoStatus.PENDING,
        progress=0,
    )
    db.add(video)
    db.commit()
    db.refresh(video)

    from app.db.base import SessionLocal
    background_tasks.add_task(_run_generation, video.id, SessionLocal)

    logger.info(
        f"Video created: {video.id} | user={current_user.id} | "
        f"niche={request.niche} | audio={request.audio_mode}"
    )
    return _video_to_response(video)


@router.get("/")
async def list_videos_root(
    status:   Optional[str] = None,
    page:     int           = Query(1, ge=1),
    limit:    int           = Query(20, ge=1, le=100),
    per_page: int           = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return await _list_videos(status, page, max(limit, per_page), current_user, db)


@router.get("/list")
async def list_videos_fallback(
    status: Optional[str] = None,
    page:   int           = Query(1, ge=1),
    limit:  int           = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return await _list_videos(status, page, limit, current_user, db)


async def _list_videos(
    status: Optional[str], page: int, limit: int,
    current_user: User, db: Session,
):
    query = db.query(Video).filter(Video.user_id == current_user.id)
    if status:
        try:
            query = query.filter(Video.status == VideoStatus(status))
        except ValueError:
            raise ValidationException(f"Invalid status filter: '{status}'.")
    total  = query.count()
    videos = query.order_by(Video.created_at.desc()).offset((page - 1) * limit).limit(limit).all()
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
    video = db.query(Video).filter(
        Video.id == video_id, Video.user_id == current_user.id
    ).first()
    if not video:
        raise NotFoundException("Video not found.")
    return _video_to_response(video)


@router.get("/{video_id}/scenes")
async def get_video_scenes(
    video_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    video = db.query(Video).filter(
        Video.id == video_id, Video.user_id == current_user.id
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
                status=s.status if isinstance(s.status, str) else s.status.value,
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
    video = db.query(Video).filter(
        Video.id == video_id, Video.user_id == current_user.id
    ).first()
    if not video:
        raise NotFoundException("Video not found or already deleted.")
    db.delete(video)
    db.commit()
    logger.info(f"Video deleted: {video_id}")
    return {"message": "✅ Video deleted successfully."}


@router.post("/{video_id}/regenerate")
async def regenerate_video(
    video_id: str,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    video = db.query(Video).filter(
        Video.id == video_id, Video.user_id == current_user.id
    ).first()
    if not video:
        raise NotFoundException("Video not found.")
    if video.status not in [VideoStatus.FAILED, VideoStatus.CANCELLED]:
        raise ValidationException("⚠️ Only failed or cancelled videos can be regenerated.")
    limits = get_tier_limits(current_user)
    if check_daily_limit(current_user, db) >= limits["daily_limit"]:
        raise RateLimitException("📅 Daily limit reached. Try again tomorrow.")

    video.status        = VideoStatus.PENDING
    video.progress      = 0
    video.error_message = None
    db.commit()

    from app.db.base import SessionLocal
    background_tasks.add_task(_run_generation, video.id, SessionLocal)

    logger.info(f"Video regeneration started: {video_id}")
    return {"message": "🔄 Video regeneration started!", "video_id": video_id}
