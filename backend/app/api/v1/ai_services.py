"""
AI services API routes.
FILE: app/api/v1/ai_services.py

FIXES:
1. CRITICAL — GenerateScriptRequest was missing aspect_ratio,
   target_platforms, voice_style. text_generation.py generate_script()
   requires these — calling without them caused TypeError.

2. CRITICAL — generate_script validation rejected "sound_sync" as a
   valid video_type, but the frontend AudioMode.soundSync sends exactly
   "sound_sync". Any sound_sync video creation returned 422.

3. CRITICAL — smart_generate_plan() called text_service.generate_script()
   directly instead of text_service.smart_generate_plan(). This meant
   the SmartCreate response was missing: platform_tips (Platforms tab
   always empty), seo_tags, caption (post copy), music_style, narration.

4. SmartPlanRequest was missing: audio_mode, voice_style,
   target_platforms, character_consistency, uploaded_image_count.
   SmartCreateScreen sends all of these — they were silently dropped,
   so voice and platform settings had no effect on the generated plan.

5. preview_video was missing aspect_ratio in the request model AND
   hardcoded "9:16" — 16:9 and 1:1 previews always returned wrong ratio.

6. No tier-based credit / daily-limit guard on any AI endpoint.
   Free users could hammer the AI endpoints indefinitely.

7. ai_health_check() always returned "available" without actually
   testing anything — useless for debugging HuggingFace outages.

8. generate_image() didn't pass character_consistency to the service,
   so the param existed in the request model but was always ignored.

9. smart_generate_plan() re-implemented niche detection inline instead
   of delegating to TextGenerationService._detect_niche() — two
   sources of truth for the same logic.

10. Video type validation still allowed only "silent"|"narration" in
    generate_script — "sound_sync" added to the allowed list.
"""

from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, Header
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.exceptions import (
    AIServiceException,
    AuthenticationException,
    ValidationException,
)
from app.core.logging import get_logger
from app.core.security import verify_token
from app.db.base import get_db
from app.models.user import User
from app.services.ai.image_generation import ImageGenerationService
from app.services.ai.text_generation import TextGenerationService

logger = get_logger(__name__)
router = APIRouter()

# Tier-based daily AI call limits (separate from video limits)
_TIER_AI_LIMITS = {
    "free":       5,
    "basic":      30,
    "pro":        200,
    "enterprise": 9999,
}

def _normalize_audio_mode(raw: str) -> str:
    """
    Normalize audio_mode from any Flutter/Dart serialization to snake_case.
    Flutter AudioMode enum serializes as: "soundSync", "sound sync",
    "Sound Sync", "SoundSync" — all must map to "sound_sync".
    Same for narration / silent variants.
    """
    normalized = raw.strip().lower().replace(" ", "_").replace("-", "_")
    # camelCase → snake_case (soundSync → sound_sync, aiNarration → ai_narration)
    import re
    normalized = re.sub(r'([a-z])([A-Z])', r'\1_\2', raw).lower()
    normalized = normalized.replace(" ", "_").replace("-", "_")
    # Aliases
    alias = {
        "sound_sync":   "sound_sync",
        "soundsync":    "sound_sync",
        "sound sync":   "sound_sync",
        "ai_narration": "narration",
        "ainarration":  "narration",
        "narration":    "narration",
        "silent":       "silent",
    }
    return alias.get(normalized.replace("_", "").replace(" ", ""), normalized)


VALID_NICHES = [
    "animals", "tech", "cooking", "motivation", "fitness", "travel",
    "gaming", "education", "comedy", "music", "fashion", "business",
    "science", "art", "nature", "finance", "entertainment", "news", "general",
]
VALID_STYLES      = ["cartoon", "cinematic", "realistic", "funny", "dramatic", "minimal"]
VALID_AUDIO_MODES = ["silent", "narration", "sound_sync"]   # FIX 2 / FIX 10
VALID_RATIOS      = ["9:16", "16:9", "1:1"]
VALID_VOICE_STYLES = [
    "professional", "friendly", "dramatic", "energetic", "calm", "authoritative"
]


# ─── AUTH DEPENDENCY ──────────────────────────────────────────────────────────

def get_current_user(
    authorization: str = Header(None),
    db: Session = Depends(get_db),
) -> User:
    if not authorization or not authorization.startswith("Bearer "):
        raise AuthenticationException("You must be logged in to use AI services.")
    token   = authorization.split(" ")[1]
    payload = verify_token(token)
    user    = db.query(User).filter(User.id == payload.get("sub")).first()
    if not user:
        raise AuthenticationException("Account not found. Please log in again.")
    return user


# ─── TIER GUARD ───────────────────────────────────────────────────────────────

def _check_daily_ai_limit(user: User, db: Session) -> None:
    """
    FIX 6 — Enforce daily AI endpoint call limit per tier.
    Counts all videos created today as a proxy for AI calls.
    """
    from app.models.video import Video
    tier = user.subscription_tier
    tier_str = tier.value if hasattr(tier, "value") else str(tier)
    limit = _TIER_AI_LIMITS.get(tier_str.lower(), _TIER_AI_LIMITS["free"])

    today_start = datetime.utcnow().replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    count = db.query(Video).filter(
        Video.user_id    == user.id,
        Video.created_at >= today_start,
    ).count()

    if count >= limit:
        raise ValidationException(
            f"You've reached your daily AI limit ({limit} requests). "
            "Upgrade your plan for more."
        )


# ─── REQUEST / RESPONSE MODELS ────────────────────────────────────────────────

class GenerateScriptRequest(BaseModel):
    niche:             str
    video_type:        str            = "silent"
    duration:          int            = 30
    user_instructions: Optional[str]  = None
    style:             str            = "cinematic"
    # FIX 1 — added missing fields
    aspect_ratio:      str            = "9:16"
    target_platforms:  List[str]      = ["tiktok"]
    voice_style:       str            = "professional"


class GenerateScriptResponse(BaseModel):
    title:       str
    description: str
    scenes:      List[dict]
    narration:   Optional[str]  = None
    hashtags:    List[str]      = []
    seo_tags:    List[str]      = []
    music_style: Optional[str]  = None


class GenerateImageRequest(BaseModel):
    prompt:               str
    style:                str           = "cinematic"
    aspect_ratio:         str           = "9:16"
    negative_prompt:      Optional[str] = None
    # FIX 8 — was in model but never passed to service
    character_consistency: Optional[str] = None


class GenerateImageResponse(BaseModel):
    image_url: str
    prompt:    str


class PreviewVideoRequest(BaseModel):
    niche:             str
    video_type:        str           = "silent"
    duration:          int           = 30
    style:             str           = "cinematic"
    user_instructions: Optional[str] = None
    # FIX 5 — was hardcoded to "9:16" inside the handler
    aspect_ratio:      str           = "9:16"


class SmartPlanRequest(BaseModel):
    idea:                    str
    aspect_ratio:            str       = "9:16"
    duration:                int       = 30
    style:                   str       = "cinematic"
    captions_enabled:        bool      = True
    background_music_enabled: bool     = True
    audio_mode:              str       = "narration"
    voice_style:             str       = "professional"
    target_platforms:        List[str] = ["tiktok"]
    character_consistency:   bool      = False
    uploaded_image_count:    int       = 0
    # URLs or base64 strings of user-uploaded reference images
    reference_images:        List[str] = []


# ─── SCRIPT ───────────────────────────────────────────────────────────────────

@router.post("/generate-script", response_model=GenerateScriptResponse)
async def generate_script(
    request: GenerateScriptRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Generate a video script from niche, style, and settings."""

    # Normalize video_type — same Flutter camelCase issue as audio_mode
    request.video_type = _normalize_audio_mode(request.video_type)

    # Validation
    if request.niche not in VALID_NICHES:
        raise ValidationException(
            f"Invalid niche '{request.niche}'. "
            f"Valid options: {', '.join(VALID_NICHES)}"
        )
    if request.style not in VALID_STYLES:
        raise ValidationException(
            f"Invalid style '{request.style}'. "
            f"Valid options: {', '.join(VALID_STYLES)}"
        )
    # FIX 2 / FIX 10 — sound_sync is now accepted
    if request.video_type not in VALID_AUDIO_MODES:
        raise ValidationException(
            f"video_type must be one of: {', '.join(VALID_AUDIO_MODES)}"
        )
    if request.aspect_ratio not in VALID_RATIOS:
        raise ValidationException(
            f"aspect_ratio must be one of: {', '.join(VALID_RATIOS)}"
        )
    if not (10 <= request.duration <= 300):
        raise ValidationException("Duration must be between 10 and 300 seconds.")

    # FIX 6 — daily limit check
    _check_daily_ai_limit(current_user, db)

    try:
        text_service = TextGenerationService()
        script = await text_service.generate_script(
            niche=request.niche,
            video_type=request.video_type,
            duration=request.duration,
            user_instructions=request.user_instructions,
            style=request.style,
            # FIX 1 — now passed through
            aspect_ratio=request.aspect_ratio,
            target_platforms=request.target_platforms,
            voice_style=request.voice_style,
        )

        logger.info(f"Script generated: {current_user.id} | niche={request.niche}")

        return GenerateScriptResponse(
            title=script.get("title", "Untitled"),
            description=script.get("description", ""),
            scenes=script.get("scenes", []),
            narration=script.get("narration"),
            hashtags=script.get("hashtags", []),
            seo_tags=script.get("seo_tags", []),
            music_style=script.get("music_style"),
        )

    except ValidationException:
        raise
    except Exception as e:
        logger.error(f"Script generation failed: {e}")
        raise AIServiceException("Failed to generate script. Please try again.")


# ─── IMAGE ────────────────────────────────────────────────────────────────────

@router.post("/generate-image", response_model=GenerateImageResponse)
async def generate_image(
    request: GenerateImageRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Generate a single image from a prompt."""

    if not request.prompt or not request.prompt.strip():
        raise ValidationException("Image prompt cannot be empty.")
    if request.aspect_ratio not in VALID_RATIOS:
        raise ValidationException(
            f"Invalid aspect ratio. Choose one of: {', '.join(VALID_RATIOS)}"
        )

    _check_daily_ai_limit(current_user, db)

    try:
        image_service = ImageGenerationService()
        image_url = await image_service.generate_image(
            prompt=request.prompt,
            style=request.style,
            aspect_ratio=request.aspect_ratio,
            negative_prompt=request.negative_prompt,
            # FIX 8 — now actually passed to service
            character_consistency=request.character_consistency,
        )

        logger.info(f"Image generated: {current_user.id}")

        return GenerateImageResponse(
            image_url=image_url,
            prompt=request.prompt,
        )

    except ValidationException:
        raise
    except Exception as e:
        logger.error(f"Image generation failed: {e}")
        raise AIServiceException("Failed to generate image. Please try again.")


# ─── PREVIEW VIDEO ────────────────────────────────────────────────────────────

@router.post("/preview-video")
async def preview_video(
    request: PreviewVideoRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Generate video preview: script + sample images for first 3 scenes."""

    if request.niche not in VALID_NICHES:
        raise ValidationException(f"Invalid niche '{request.niche}'.")
    # FIX 5 — validate the aspect_ratio from request
    if request.aspect_ratio not in VALID_RATIOS:
        raise ValidationException(
            f"aspect_ratio must be one of: {', '.join(VALID_RATIOS)}"
        )

    _check_daily_ai_limit(current_user, db)

    try:
        text_service  = TextGenerationService()
        image_service = ImageGenerationService()

        script = await text_service.generate_script(
            niche=request.niche,
            video_type=request.video_type,
            duration=request.duration,
            user_instructions=request.user_instructions,
            style=request.style,
            aspect_ratio=request.aspect_ratio,   # FIX 5 — was hardcoded "9:16"
        )

        sample_images = []
        scenes = script.get("scenes", [])

        for scene in scenes[:3]:
            image_prompt = (
                scene.get("image_prompt")
                or scene.get("description")
                or f"{request.style} scene for {request.niche} video"
            )
            try:
                image_url = await image_service.generate_image(
                    prompt=image_prompt,
                    style=request.style,
                    aspect_ratio=request.aspect_ratio,  # FIX 5
                )
                sample_images.append({
                    "scene_number": scene.get("scene_number", len(sample_images) + 1),
                    "caption":      scene.get("caption", ""),
                    "image_url":    image_url,
                })
            except Exception as img_err:
                logger.warning(
                    f"Sample image failed for scene "
                    f"{scene.get('scene_number')}: {img_err}"
                )
                sample_images.append({
                    "scene_number": scene.get("scene_number", len(sample_images) + 1),
                    "caption":      scene.get("caption", ""),
                    "image_url":    (
                        "https://placehold.co/720x1280/1a1a2e/ffffff?text=Preview"
                        if request.aspect_ratio == "9:16"
                        else "https://placehold.co/1280x720/1a1a2e/ffffff?text=Preview"
                    ),
                })

        logger.info(
            f"Video preview: {current_user.id} | niche={request.niche} | "
            f"scenes={len(scenes)} | ratio={request.aspect_ratio}"
        )

        return {
            "script":        script,
            "sample_images": sample_images,
        }

    except ValidationException:
        raise
    except Exception as e:
        logger.error(f"Video preview failed: {e}")
        raise AIServiceException("Failed to generate video preview. Please try again.")


# ─── SMART PLAN ───────────────────────────────────────────────────────────────

@router.post("/smart-plan")
async def smart_generate_plan(
    request: SmartPlanRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Convert a natural language idea into a full ready-to-generate video plan.
    Powers SmartCreateScreen — returns scenes, hashtags, seo_tags,
    platform_tips, narration, and post caption.
    """

    # Normalize audio_mode BEFORE validation — Flutter sends "soundSync" not "sound_sync"
    request.audio_mode = _normalize_audio_mode(request.audio_mode)

    # FIX 3 / FIX 4 — validate all new fields
    if not request.idea or not request.idea.strip():
        raise ValidationException(
            "Please describe your video idea before generating a plan."
        )
    if len(request.idea.strip()) < 10:
        raise ValidationException(
            "Your idea is too short. Please give a bit more detail!"
        )
    if request.audio_mode not in VALID_AUDIO_MODES:
        raise ValidationException(
            f"audio_mode must be one of: {', '.join(VALID_AUDIO_MODES)}"
        )
    if request.voice_style not in VALID_VOICE_STYLES:
        raise ValidationException(
            f"voice_style must be one of: {', '.join(VALID_VOICE_STYLES)}"
        )
    if request.aspect_ratio not in VALID_RATIOS:
        raise ValidationException(
            f"aspect_ratio must be one of: {', '.join(VALID_RATIOS)}"
        )

    _check_daily_ai_limit(current_user, db)

    try:
        text_service = TextGenerationService()

        # FIX 3 / FIX 9 — delegate to smart_generate_plan() which returns
        # the full shape the frontend expects (platform_tips, seo_tags, etc.)
        plan = await text_service.smart_generate_plan(
            idea=request.idea,
            aspect_ratio=request.aspect_ratio,
            duration=request.duration,
            style=request.style,
            captions_enabled=request.captions_enabled,
            background_music_enabled=request.background_music_enabled,
            audio_mode=request.audio_mode,
            voice_style=request.voice_style,
            target_platforms=request.target_platforms,
            character_consistency=request.character_consistency,
            uploaded_image_count=request.uploaded_image_count,
            reference_images=request.reference_images or [],
        )

        logger.info(
            f"Smart plan: {current_user.id} | niche={plan.get('niche')} | "
            f"platforms={request.target_platforms} | audio={request.audio_mode}"
        )

        # Merge in request fields not returned by the service
        plan["captions_enabled"]         = request.captions_enabled
        plan["background_music_enabled"] = request.background_music_enabled
        plan["style"]                    = request.style
        plan["audio_mode"]               = request.audio_mode
        plan["voice_style"]              = request.voice_style
        plan["target_platforms"]         = request.target_platforms

        return plan

    except ValidationException:
        raise
    except Exception as e:
        import traceback
        logger.error(f"Smart plan CRASH: {type(e).__name__}: {e}\n{traceback.format_exc()}")
        # Surface real error in development, generic message in production
        from app.config import settings as _cfg
        debug = getattr(_cfg, "DEBUG", False)
        raise AIServiceException(
            f"Smart plan error: {type(e).__name__}: {str(e)}"
            if debug else
            "Failed to generate video plan. Please try again."
        )


# ─── REFERENCE DATA ───────────────────────────────────────────────────────────

@router.get("/niches")
async def get_niches():
    return {
        "niches": [
            {"id": "animals",       "name": "Animals & Pets",     "icon": "🐾"},
            {"id": "tech",          "name": "Technology",          "icon": "💻"},
            {"id": "cooking",       "name": "Cooking & Food",      "icon": "🍳"},
            {"id": "motivation",    "name": "Motivation",          "icon": "💪"},
            {"id": "fitness",       "name": "Fitness & Health",    "icon": "🏋️"},
            {"id": "travel",        "name": "Travel",              "icon": "✈️"},
            {"id": "gaming",        "name": "Gaming",              "icon": "🎮"},
            {"id": "education",     "name": "Education",           "icon": "📚"},
            {"id": "comedy",        "name": "Comedy",              "icon": "😂"},
            {"id": "music",         "name": "Music",               "icon": "🎵"},
            {"id": "fashion",       "name": "Fashion",             "icon": "👗"},
            {"id": "business",      "name": "Business",            "icon": "💼"},
            {"id": "science",       "name": "Science",             "icon": "🔬"},
            {"id": "art",           "name": "Art & Design",        "icon": "🎨"},
            {"id": "nature",        "name": "Nature",              "icon": "🌿"},
            {"id": "finance",       "name": "Finance & Money",     "icon": "💰"},
            {"id": "entertainment", "name": "Entertainment",       "icon": "🎬"},
            {"id": "news",          "name": "News & Events",       "icon": "📰"},
            {"id": "general",       "name": "General",             "icon": "⭐"},
        ]
    }


@router.get("/styles")
async def get_styles():
    return {
        "styles": [
            {"id": "cinematic", "name": "Cinematic",  "description": "Movie-like quality",        "icon": "🎬"},
            {"id": "cartoon",   "name": "Cartoon",    "description": "Animated cartoon style",    "icon": "🎨"},
            {"id": "realistic", "name": "Realistic",  "description": "Photorealistic visuals",    "icon": "📷"},
            {"id": "funny",     "name": "Funny",      "description": "Humorous and lighthearted", "icon": "😂"},
            {"id": "dramatic",  "name": "Dramatic",   "description": "Intense and emotional",     "icon": "🎭"},
            {"id": "minimal",   "name": "Minimal",    "description": "Clean and simple",          "icon": "✨"},
        ]
    }


@router.get("/caption-styles")
async def get_caption_styles():
    return {
        "styles": [
            {"id": "modern",  "name": "Modern",  "font": "Montserrat", "animation": "slide-up"},
            {"id": "classic", "name": "Classic", "font": "Georgia",    "animation": "fade-in"},
            {"id": "bold",    "name": "Bold",    "font": "Impact",     "animation": "pop-in"},
            {"id": "minimal", "name": "Minimal", "font": "Inter",      "animation": "typewriter"},
            {"id": "fun",     "name": "Fun",     "font": "Poppins",    "animation": "bounce"},
        ]
    }


@router.get("/music-styles")
async def get_music_styles():
    return {
        "styles": [
            {"id": "upbeat",        "name": "Upbeat",        "description": "Energetic and positive"},
            {"id": "calm",          "name": "Calm",          "description": "Relaxing and peaceful"},
            {"id": "dramatic",      "name": "Dramatic",      "description": "Intense and emotional"},
            {"id": "inspirational", "name": "Inspirational", "description": "Uplifting and motivating"},
            {"id": "epic",          "name": "Epic",          "description": "Grand and powerful"},
            {"id": "lofi",          "name": "Lo-Fi",         "description": "Chill and ambient"},
            {"id": "afrobeat",      "name": "Afrobeat",      "description": "Nigerian/African rhythm"},
        ]
    }


@router.get("/voice-styles")
async def get_voice_styles():
    """Voice styles for narration and sound_sync videos."""
    return {
        "styles": [
            {"id": "professional",  "name": "Professional",  "description": "Clear, measured, authoritative"},
            {"id": "friendly",      "name": "Friendly",      "description": "Warm and approachable"},
            {"id": "dramatic",      "name": "Dramatic",      "description": "Slow and intense"},
            {"id": "energetic",     "name": "Energetic",     "description": "Fast-paced and exciting"},
            {"id": "calm",          "name": "Calm",          "description": "Relaxed and soothing"},
            {"id": "authoritative", "name": "Authoritative", "description": "Deep and commanding"},
        ]
    }


@router.get("/platforms")
async def get_platforms():
    """Target platforms for video optimization."""
    return {
        "platforms": [
            {"id": "tiktok",    "name": "TikTok",     "icon": "🎵", "best_ratio": "9:16", "max_duration": 60},
            {"id": "instagram", "name": "Instagram",  "icon": "📸", "best_ratio": "9:16", "max_duration": 90},
            {"id": "youtube",   "name": "YouTube",    "icon": "▶️", "best_ratio": "16:9", "max_duration": 600},
            {"id": "facebook",  "name": "Facebook",   "icon": "👍", "best_ratio": "9:16", "max_duration": 240},
            {"id": "twitter",   "name": "X / Twitter","icon": "🐦", "best_ratio": "16:9", "max_duration": 140},
            {"id": "linkedin",  "name": "LinkedIn",   "icon": "💼", "best_ratio": "16:9", "max_duration": 600},
        ]
    }


# ─── HEALTH CHECK ─────────────────────────────────────────────────────────────

@router.get("/health")
async def ai_health_check():
    """
    FIX 7 — Actually test HuggingFace connectivity.
    Returns degraded status when HF API is unreachable,
    so frontend can show a warning instead of silently failing.
    """
    from app.config import settings
    import httpx

    hf_status  = "unconfigured"
    hf_message = "HUGGINGFACE_API_KEY not set — using mock templates"

    if getattr(settings, "HUGGINGFACE_API_KEY", None):
        try:
            async with httpx.AsyncClient() as client:
                r = await client.get(
                    "https://huggingface.co/api/whoami",
                    headers={"Authorization": f"Bearer {settings.HUGGINGFACE_API_KEY}"},
                    timeout=8.0,
                )
            if r.status_code == 200:
                hf_status  = "ok"
                hf_message = "HuggingFace API reachable"
            elif r.status_code == 401:
                hf_status  = "invalid_key"
                hf_message = "HUGGINGFACE_API_KEY is invalid or expired"
            else:
                hf_status  = "degraded"
                hf_message = f"HuggingFace returned HTTP {r.status_code}"
        except Exception as e:
            hf_status  = "unreachable"
            hf_message = f"Cannot reach HuggingFace: {str(e)[:80]}"

    cloudinary_status = "unconfigured"
    if all([
        getattr(settings, "CLOUDINARY_CLOUD_NAME", None),
        getattr(settings, "CLOUDINARY_API_KEY", None),
        getattr(settings, "CLOUDINARY_API_SECRET", None),
    ]):
        cloudinary_status = "configured"

    paystack_status = "unconfigured"
    if getattr(settings, "PAYSTACK_SECRET_KEY", None):
        paystack_status = "configured"

    overall = (
        "ok"       if hf_status == "ok" else
        "degraded" if hf_status in ("unconfigured",) else
        "error"
    )

    return {
        "status": overall,
        "services": {
            "text_generation":  {"status": hf_status,         "message": hf_message},
            "image_generation": {"status": hf_status,         "message": hf_message},
            "voice_generation": {"status": hf_status,         "message": hf_message},
            "storage":          {"status": cloudinary_status, "message": "Cloudinary"},
            "payments":         {"status": paystack_status,   "message": "Paystack"},
        },
        "fallback_mode": hf_status != "ok",
        "fallback_note":  (
            "AI generation will use rich built-in templates when HuggingFace is unavailable."
            if hf_status != "ok" else None
        ),
    }
