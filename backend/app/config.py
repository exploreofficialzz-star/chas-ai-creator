"""
Application configuration settings.
FILE: app/config.py

BUGS FIXED:
1. Missing GROQ_API_KEY, GEMINI_API_KEY, OPENAI_API_KEY,
   REPLICATE_API_KEY, SEGMIND_API_KEY — text_generation.py and
   video_generation.py reference these but they were never in config.
   Every provider except HuggingFace silently got empty string and
   was skipped → single point of failure.

2. VIDEO_RESOLUTIONS as a bare dict crashed pydantic-settings on startup
   with "value is not a valid dict" validation error. Replaced with
   a ClassVar so pydantic ignores it.

3. Missing BASIC tier limits — videos.py TIER_LIMITS has a "basic" key
   but config had no BASIC_TIER_* constants, causing KeyError on
   Basic-plan users.

4. TEXT_MODEL was "Qwen/Qwen2-7B-Instruct" — the correct HuggingFace
   model ID is "Qwen/Qwen2.5-7B-Instruct" (with .5). The old ID
   returns 404 on every request.

5. VIDEO_MODEL was "cerspense/zeroscope_v2_576w" — this is a
   text-to-video model but VideoGenerationService was calling it as
   an img2vid model (SVD). Separated TEXT_TO_VIDEO_MODEL and
   IMG_TO_VIDEO_MODEL so each service uses the right endpoint.

6. SECRET_KEY was hardcoded — moved to env with a safe fallback
   so production uses the .env value.
"""

from functools import lru_cache
from typing import ClassVar, Dict, List, Optional

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings — all values loaded from .env"""

    # ── App ───────────────────────────────────────────────────────────────────
    APP_NAME:    str = "chAs AI Creator"
    APP_VERSION: str = "1.0.0"
    APP_CREATOR: str = "chAs"
    DEBUG:       bool = False
    ENVIRONMENT: str = "production"

    # ── Server ────────────────────────────────────────────────────────────────
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # ── Database (Supabase PostgreSQL) ────────────────────────────────────────
    DATABASE_URL:         str = ""
    DATABASE_POOL_SIZE:   int = 20
    DATABASE_MAX_OVERFLOW:int = 10

    # ── Supabase ──────────────────────────────────────────────────────────────
    SUPABASE_URL:              str           = ""
    SUPABASE_ANON_KEY:         str           = ""
    SUPABASE_SERVICE_ROLE_KEY: Optional[str] = None

    # ── Redis (optional — not required on Render free tier) ───────────────────
    REDIS_URL: Optional[str] = None

    # ── AI Text Generation — provider chain ───────────────────────────────────
    # FIX 1 — all four providers now configurable via .env
    HUGGINGFACE_API_KEY: Optional[str] = None
    GROQ_API_KEY:        Optional[str] = None   # FIX 1 — was missing
    GEMINI_API_KEY:      Optional[str] = None   # FIX 1 — was missing
    OPENAI_API_KEY:      Optional[str] = None   # FIX 1 — was missing

    # ── AI Image Generation ───────────────────────────────────────────────────
    HUGGINGFACE_API_URL: str = "https://api-inference.huggingface.co/models"
    # FIX 4 — corrected model ID (was Qwen2-7B, correct is Qwen2.5-7B)
    TEXT_MODEL:  str = "Qwen/Qwen2.5-7B-Instruct"
    IMAGE_MODEL: str = "stabilityai/stable-diffusion-xl-base-1.0"

    # ── AI Video Generation — provider chain ──────────────────────────────────
    # FIX 1 — Replicate and Segmind keys now configurable
    REPLICATE_API_KEY: Optional[str] = None    # FIX 1 — was missing
    SEGMIND_API_KEY:   Optional[str] = None    # FIX 1 — was missing

    # FIX 5 — split into two separate model configs so each service
    # uses the correct endpoint type
    TEXT_TO_VIDEO_MODEL: str = "cerspense/zeroscope_v2_576w"   # text → video
    IMG_TO_VIDEO_MODEL:  str = "stabilityai/stable-video-diffusion-img2vid-xt"  # img → video

    # Keep VIDEO_MODEL as alias for backwards compatibility
    VIDEO_MODEL: str = "cerspense/zeroscope_v2_576w"

    # Voice
    VOICE_MODEL: str = "piper"

    # ── Video processing ──────────────────────────────────────────────────────
    FFMPEG_PATH:          str = "ffmpeg"
    MAX_VIDEO_DURATION:   int = 300
    DEFAULT_VIDEO_FPS:    int = 24

    # FIX 2 — ClassVar so pydantic-settings ignores this (not an env var)
    VIDEO_RESOLUTIONS: ClassVar[Dict[str, Dict[str, int]]] = {
        "16:9": {"width": 1920, "height": 1080},
        "9:16": {"width": 1080, "height": 1920},
        "1:1":  {"width": 1080, "height": 1080},
    }

    # ── Payments (Paystack) ───────────────────────────────────────────────────
    PAYSTACK_SECRET_KEY: str = ""
    PAYSTACK_PUBLIC_KEY: str = ""
    PAYSTACK_BASE_URL:   str = "https://api.paystack.co"

    # ── Storage (Cloudinary) ──────────────────────────────────────────────────
    CLOUDINARY_CLOUD_NAME: str = ""
    CLOUDINARY_API_KEY:    str = ""
    CLOUDINARY_API_SECRET: str = ""

    # ── Ads (Unity) ───────────────────────────────────────────────────────────
    UNITY_GAME_ID_IOS:     str  = "6060849"
    UNITY_GAME_ID_ANDROID: str  = "6060848"
    UNITY_PLACEMENT_ID:    str  = "rewardedVideo"
    UNITY_ENABLED:         bool = True

    # ── Tier limits ───────────────────────────────────────────────────────────
    # FIX 3 — added BASIC tier (was missing, caused KeyError for Basic users)
    FREE_TIER_DAILY_VIDEOS:      int = 2
    BASIC_TIER_DAILY_VIDEOS:     int = 10   # FIX 3
    PRO_TIER_DAILY_VIDEOS:       int = 50
    ENTERPRISE_TIER_DAILY_VIDEOS:int = 200

    FREE_TIER_MAX_VIDEO_LENGTH:      int = 30
    BASIC_TIER_MAX_VIDEO_LENGTH:     int = 60   # FIX 3
    PRO_TIER_MAX_VIDEO_LENGTH:       int = 300
    ENTERPRISE_TIER_MAX_VIDEO_LENGTH:int = 600

    # ── Ads ───────────────────────────────────────────────────────────────────
    ADS_ENABLED:              bool = True
    ADS_FREQUENCY_VIDEOS:     int  = 2
    ADS_FREQUENCY_SCREEN_VIEWS:int = 5

    # ── Scheduling ────────────────────────────────────────────────────────────
    SCHEDULER_ENABLED:              bool = True
    MAX_SCHEDULED_VIDEOS_PER_DAY:   int  = 10

    # ── Security ──────────────────────────────────────────────────────────────
    # FIX 6 — loaded from .env; fallback only used in local dev
    SECRET_KEY:                    str = "change-this-in-production-env"
    ACCESS_TOKEN_EXPIRE_MINUTES:   int = 60 * 24 * 7    # 7 days
    REFRESH_TOKEN_EXPIRE_MINUTES:  int = 60 * 24 * 30   # 30 days

    # ── CORS ──────────────────────────────────────────────────────────────────
    CORS_ORIGINS: List[str] = [
        "https://chas-ai-creator-2.onrender.com",
        "http://localhost:3000",
        "http://localhost:8080",
    ]

    # ── Logging ───────────────────────────────────────────────────────────────
    LOG_LEVEL:  str = "INFO"
    LOG_FORMAT: str = "json"

    # ── Sentry (optional) ─────────────────────────────────────────────────────
    SENTRY_DSN: Optional[str] = None

    class Config:
        env_file      = ".env"
        case_sensitive = True


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
