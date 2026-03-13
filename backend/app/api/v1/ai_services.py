"""
AI services API routes.
FILE: app/api/v1/ai_services.py

BUGS FIXED:
1. CRITICAL — AIServiceException imported from app.core.exceptions but that
   class does not exist there. This caused an ImportError at startup —
   the entire AI router failed to register, making every /ai/* endpoint 404.
   Fixed: replaced with APIException(status_code=503, ...) which is the
   correct base exception class in app.core.exceptions.

2. _normalize_audio_mode() had a local variable shadowing bug:
   'normalized' was computed twice and the first computation (using raw)
   was immediately overwritten by the second (using raw again without
   the initial lowercase/strip). The alias lookup then used
   normalized.replace("_","") which dropped underscores before matching —
   "sound_sync" became "soundsync" and missed the "sound_sync" key.
   Fixed: single clean normalisation path, aliases keyed without underscores.
"""

import re
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, Header
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.exceptions import (
    APIException,                # BUG 1 FIX — was AIServiceException (doesn't exist)
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
    BUG 2 FIX — Normalize audio_mode from any Flutter serialisation to snake_case.
    Flutter AudioMode enum may arrive as: "soundSync", "sound sync",
    "Sound Sync", "SoundSync", "sound_sync" — all must map to "sound_sync".

    Old code had two 'normalized = ...' assignments where the second one
    re-processed 'raw' (not the first result), and the alias dict used
    "sound_sync" as key but the lookup stripped underscores first so it
    looked up "soundsync" and found nothing → returned the raw value.
    """
    # camelCase → snake_case first (soundSync → sound_sync)
    snake = re.sub(r'([a-z])([A-Z])', r'\1_\2', raw.strip())
    # lowercase + normalise separators
    normalised = snake.lower().replace(" ", "_").replace("-", "_")

    # Alias table — keys are the normalised forms WITH underscores
    alias = {
        "sound_sync":   "sound_sync",
        "ai_narration": "narration",
        "narration":    "narration",
        "silent":       "silent",
    }
    # Also match squished versions: "soundsync", "ainarration"
    squished_alias = {
        "soundsync":   "sound_sync",
        "ainarration": "narration",
    }
    return alias.get(normalised) or squished_alias.get(normalised.replace("_", "")) or normalised


VALID_NICHES = [
    "animals", "tech", "cooking", "motivation", "fitness", "travel",
    "gaming", "education", "comedy", "music", "fashion", "business",
    "science", "art", "nature", "finance", "entertainment", "news", "general",
]
VALID_STYLES       = ["cartoon", "cinematic", "realistic", "funny", "dramatic", "minimal"]
VALID_AUDIO_MODES  = ["silent", "narration", "sound_sync"]
VALID_RATIOS       = ["9:16", "16:9", "1:1"]
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
    """Enforce daily AI endpoint call limit per tier."""
    from app.models.video import Video
    tier     = user.subscription_tier
    tier_str = tier.value if hasattr(tier, "value") else str(tier)
    limit    = _TIER_AI_LIMITS.get(tier_str.lower(), _TIER_AI_LIMITS["free"])

    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
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
    video_type:        str           = "silent"
    duration:          int           = 30
    user_instructions: Optional[str] = None
    style:             str           = "cinematic"
    aspect_ratio:      str           = "9:16"
    target_platforms:  List[str]     = ["tiktok"]
    voice_style:       str           = "professional"


class GenerateScriptResponse(BaseModel):
    title:       str
    description: str
    scenes:      List[dict]
    narration:   Optional[str] = None
    hashtags:    List[str]     = []
    seo_tags:    List[str]     = []
    music_style: Optional[str] = None


class GenerateImageRequest(BaseModel):
    prompt:                str
    style:                 str           = "cinematic"
    aspect_ratio:          str           = "9:16"
    negative_prompt:       Optional[str] = None
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
    aspect_ratio:      str           = "9:16"


class SmartPlanRequest(BaseModel):
    idea:                     str
    aspect_ratio:             str       = "9:16"
    duration:                 int       = 30
    style:                    str       = "cinematic"
    captions_enabled:         bool      = True
    background_music_enabled: bool      = True
    audio_mode:               str       = "narration"
    voice_style:              str       = "professional"
    target_platforms:         List[str] = ["tiktok"]
    character_consistency:    bool      = False
    uploaded_image_count:     int       = 0
    reference_images:         List[str] = []


# ─── SCRIPT ───────────────────────────────────────────────────────────────────

@router.post("/generate-script", response_model=GenerateScriptResponse)
async def generate_script(
    request: GenerateScriptRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    request.video_type = _normalize_audio_mode(request.video_type)

    if request.niche not in VALID_NICHES:
        raise ValidationException(
            f"Invalid niche '{request.niche}'. Valid options: {', '.join(VALID_NICHES)}"
        )
    if request.style not in VALID_STYLES:
        raise ValidationException(
            f"Invalid style '{request.style}'. Valid options: {', '.join(VALID_STYLES)}"
        )
    if request.video_type not in VALID_AUDIO_MODES:
        raise ValidationException(f"video_type must be one of: {', '.join(VALID_AUDIO_MODES)}")
    if request.aspect_ratio not in VALID_RATIOS:
        raise ValidationException(f"aspect_ratio must be one of: {', '.join(VALID_RATIOS)}")
    if not (10 <= request.duration <= 300):
        raise ValidationException("Duration must be between 10 and 300 seconds.")

    _check_daily_ai_limit(current_user, db)

    try:
        script = await TextGenerationService().generate_script(
            niche=request.niche,
            video_type=request.video_type,
            duration=request.duration,
            user_instructions=request.user_instructions,
            style=request.style,
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
        # BUG 1 FIX — APIException(status_code=503) instead of AIServiceException
        raise APIException(
            status_code=503,
            message="Failed to generate script. Please try again.",
            error_code="AI_SERVICE_ERROR",
        )


# ─── IMAGE ────────────────────────────────────────────────────────────────────

@router.post("/generate-image", response_model=GenerateImageResponse)
async def generate_image(
    request: GenerateImageRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not request.prompt or not request.prompt.strip():
        raise ValidationException("Image prompt cannot be empty.")
    if request.aspect_ratio not in VALID_RATIOS:
        raise ValidationException(
            f"Invalid aspect ratio. Choose one of: {', '.join(VALID_RATIOS)}"
        )

    _check_daily_ai_limit(current_user, db)

    try:
        image_url = await ImageGenerationService().generate_image(
            prompt=request.prompt,
            style=request.style,
            aspect_ratio=request.aspect_ratio,
            negative_prompt=request.negative_prompt,
            character_consistency=request.character_consistency,
        )
        logger.info(f"Image generated: {current_user.id}")
        return GenerateImageResponse(image_url=image_url, prompt=request.prompt)
    except ValidationException:
        raise
    except Exception as e:
        logger.error(f"Image generation failed: {e}")
        raise APIException(
            status_code=503,
            message="Failed to generate image. Please try again.",
            error_code="AI_SERVICE_ERROR",
        )


# ─── PREVIEW VIDEO ────────────────────────────────────────────────────────────

@router.post("/preview-video")
async def preview_video(
    request: PreviewVideoRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if request.niche not in VALID_NICHES:
        raise ValidationException(f"Invalid niche '{request.niche}'.")
    if request.aspect_ratio not in VALID_RATIOS:
        raise ValidationException(f"aspect_ratio must be one of: {', '.join(VALID_RATIOS)}")

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
            aspect_ratio=request.aspect_ratio,
        )

        sample_images = []
        for scene in script.get("scenes", [])[:3]:
            image_prompt = (
                scene.get("image_prompt")
                or scene.get("description")
                or f"{request.style} scene for {request.niche} video"
            )
            try:
                image_url = await image_service.generate_image(
                    prompt=image_prompt,
                    style=request.style,
                    aspect_ratio=request.aspect_ratio,
                )
                sample_images.append({
                    "scene_number": scene.get("scene_number", len(sample_images) + 1),
                    "caption":      scene.get("caption", ""),
                    "image_url":    image_url,
                })
            except Exception as img_err:
                logger.warning(f"Sample image failed for scene {scene.get('scene_number')}: {img_err}")
                placeholder = (
                    "https://placehold.co/720x1280/1a1a2e/ffffff?text=Preview"
                    if request.aspect_ratio == "9:16"
                    else "https://placehold.co/1280x720/1a1a2e/ffffff?text=Preview"
                )
                sample_images.append({
                    "scene_number": scene.get("scene_number", len(sample_images) + 1),
                    "caption":      scene.get("caption", ""),
                    "image_url":    placeholder,
                })

        logger.info(
            f"Video preview: {current_user.id} | niche={request.niche} | "
            f"scenes={len(script.get('scenes', []))} | ratio={request.aspect_ratio}"
        )
        return {"script": script, "sample_images": sample_images}

    except ValidationException:
        raise
    except Exception as e:
        logger.error(f"Video preview failed: {e}")
        raise APIException(
            status_code=503,
            message="Failed to generate video preview. Please try again.",
            error_code="AI_SERVICE_ERROR",
        )


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
    # BUG 2 FIX — normalise before validation
    request.audio_mode = _normalize_audio_mode(request.audio_mode)

    if not request.idea or not request.idea.strip():
        raise ValidationException("Please describe your video idea before generating a plan.")
    if len(request.idea.strip()) < 10:
        raise ValidationException("Your idea is too short. Please give a bit more detail!")
    if request.audio_mode not in VALID_AUDIO_MODES:
        raise ValidationException(f"audio_mode must be one of: {', '.join(VALID_AUDIO_MODES)}")
    if request.voice_style not in VALID_VOICE_STYLES:
        raise ValidationException(f"voice_style must be one of: {', '.join(VALID_VOICE_STYLES)}")
    if request.aspect_ratio not in VALID_RATIOS:
        raise ValidationException(f"aspect_ratio must be one of: {', '.join(VALID_RATIOS)}")

    _check_daily_ai_limit(current_user, db)

    try:
        plan = await TextGenerationService().smart_generate_plan(
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

        # Merge request fields not returned by the service
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
        from app.config import settings as _cfg
        debug = getattr(_cfg, "DEBUG", False)
        raise APIException(
            status_code=503,
            message=(
                f"Smart plan error: {type(e).__name__}: {str(e)}"
                if debug else
                "Failed to generate video plan. Please try again."
            ),
            error_code="AI_SERVICE_ERROR",
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
    return {
        "platforms": [
            {"id": "tiktok",    "name": "TikTok",      "icon": "🎵", "best_ratio": "9:16", "max_duration": 60},
            {"id": "instagram", "name": "Instagram",   "icon": "📸", "best_ratio": "9:16", "max_duration": 90},
            {"id": "youtube",   "name": "YouTube",     "icon": "▶️", "best_ratio": "16:9", "max_duration": 600},
            {"id": "facebook",  "name": "Facebook",    "icon": "👍", "best_ratio": "9:16", "max_duration": 240},
            {"id": "twitter",   "name": "X / Twitter", "icon": "🐦", "best_ratio": "16:9", "max_duration": 140},
            {"id": "linkedin",  "name": "LinkedIn",    "icon": "💼", "best_ratio": "16:9", "max_duration": 600},
        ]
    }


# ─── HEALTH CHECK ─────────────────────────────────────────────────────────────

@router.get("/health")
async def ai_health_check():
    """
    Actually tests provider connectivity instead of always returning 'available'.
    Checks HuggingFace auth, Groq key presence, and Gemini key presence
    so the frontend can show a real degraded-service warning.
    """
    from app.config import settings
    import httpx

    # ── HuggingFace ──
    hf_status  = "unconfigured"
    hf_message = "HUGGINGFACE_API_KEY not set"
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

    # ── Groq ──
    groq_status = (
        "configured" if getattr(settings, "GROQ_API_KEY", None) else "unconfigured"
    )

    # ── Gemini ──
    gemini_status = (
        "configured" if getattr(settings, "GEMINI_API_KEY", None) else "unconfigured"
    )

    # ── Storage / Payments ──
    cloudinary_status = (
        "configured"
        if all([
            getattr(settings, "CLOUDINARY_CLOUD_NAME", None),
            getattr(settings, "CLOUDINARY_API_KEY", None),
            getattr(settings, "CLOUDINARY_API_SECRET", None),
        ])
        else "unconfigured"
    )
    paystack_status = (
        "configured" if getattr(settings, "PAYSTACK_SECRET_KEY", None) else "unconfigured"
    )

    # Overall: ok only if at least one AI provider is reachable
    any_ai = hf_status == "ok" or groq_status == "configured" or gemini_status == "configured"
    overall = "ok" if any_ai else "degraded"

    return {
        "status": overall,
        "services": {
            "text_generation":  {"status": hf_status,         "message": hf_message},
            "image_generation": {"status": hf_status,         "message": hf_message},
            "voice_generation": {"status": hf_status,         "message": hf_message},
            "groq":             {"status": groq_status,        "message": "Groq LLM fallback"},
            "gemini":           {"status": gemini_status,      "message": "Gemini LLM fallback"},
            "storage":          {"status": cloudinary_status,  "message": "Cloudinary"},
            "payments":         {"status": paystack_status,    "message": "Paystack"},
        },
        "fallback_mode": hf_status != "ok",
        "fallback_note": (
            "HuggingFace is unavailable — Groq/Gemini fallbacks are active."
            if hf_status != "ok" and any_ai else
            "All AI providers unavailable — generation will fail."
            if not any_ai else None
        ),
    }
