"""
Application configuration settings.
Created by: chAs
"""

from functools import lru_cache
from typing import List, Optional

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # Application - chAs AI Creator
    APP_NAME: str = "chAs AI Creator"
    APP_VERSION: str = "1.0.0"
    APP_CREATOR: str = "chAs"
    DEBUG: bool = False
    ENVIRONMENT: str = "production"
    
    # Server
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    
    # Database - Supabase PostgreSQL (production)
    DATABASE_URL: str = "postgresql://postgres:[YOUR-PASSWORD]@db.[YOUR-PROJECT-REF].supabase.co:5432/postgres"
    DATABASE_POOL_SIZE: int = 20
    DATABASE_MAX_OVERFLOW: int = 10
    
    # Supabase
    SUPABASE_URL: str = "https://[YOUR-PROJECT-REF].supabase.co"
    SUPABASE_ANON_KEY: str = ""
    SUPABASE_SERVICE_ROLE_KEY: Optional[str] = None  # Optional: for admin operations
    
    # Redis (Optional - disable if not available)
    REDIS_URL: Optional[str] = None
    
    # AI Services - HuggingFace (works in Nigeria ✓)
    HUGGINGFACE_API_KEY: Optional[str] = None
    HUGGINGFACE_API_URL: str = "https://api-inference.huggingface.co/models"
    
    # AI Model Configuration
    TEXT_MODEL: str = "Qwen/Qwen2-7B-Instruct"
    IMAGE_MODEL: str = "stabilityai/stable-diffusion-xl-base-1.0"
    VIDEO_MODEL: str = "cerspense/zeroscope_v2_576w"
    VOICE_MODEL: str = "piper"
    
    # Video Processing
    FFMPEG_PATH: str = "ffmpeg"
    MAX_VIDEO_DURATION: int = 300  # 5 minutes
    DEFAULT_VIDEO_FPS: int = 24
    VIDEO_RESOLUTIONS: dict = {
        "16:9": {"width": 1920, "height": 1080},
        "9:16": {"width": 1080, "height": 1920},
        "1:1": {"width": 1080, "height": 1080},
    }
    
    # Payments - Paystack (Nigeria ✓)
    PAYSTACK_SECRET_KEY: str = ""
    PAYSTACK_PUBLIC_KEY: str = ""
    PAYSTACK_BASE_URL: str = "https://api.paystack.co"
    
    # Storage - Cloudinary (Global ✓)
    CLOUDINARY_CLOUD_NAME: str = ""
    CLOUDINARY_API_KEY: str = ""
    CLOUDINARY_API_SECRET: str = ""
    
    # Ads - Unity Ads (Nigeria ✓)
    UNITY_GAME_ID_IOS: str = "6060849"
    UNITY_GAME_ID_ANDROID: str = "6060848"
    UNITY_PLACEMENT_ID: str = "rewardedVideo"
    UNITY_ENABLED: bool = True
    
    # Limits - chAs AI Creator Tiers
    FREE_TIER_DAILY_VIDEOS: int = 2
    PRO_TIER_DAILY_VIDEOS: int = 20
    ENTERPRISE_TIER_DAILY_VIDEOS: int = 100
    
    FREE_TIER_MAX_VIDEO_LENGTH: int = 30
    PRO_TIER_MAX_VIDEO_LENGTH: int = 120
    ENTERPRISE_TIER_MAX_VIDEO_LENGTH: int = 300
    
    # Ad Configuration
    ADS_ENABLED: bool = True
    ADS_FREQUENCY_VIDEOS: int = 2
    ADS_FREQUENCY_SCREEN_VIEWS: int = 5
    
    # Scheduling
    SCHEDULER_ENABLED: bool = True
    MAX_SCHEDULED_VIDEOS_PER_DAY: int = 10
    
    # Security
    SECRET_KEY: str = "d8f7a9e2b4c6d1f3e5b8a9c0d2e4f6a8b0c2d4e6f8a0b2c4d6e8f0a2b4c6d8"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days
    REFRESH_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 30  # 30 days
    
    # CORS (Render + local development)
    CORS_ORIGINS: List[str] = [
        "https://chas-ai-creator-2.onrender.com",  # Update with your actual Render URL
        "http://localhost:3000",
        "http://localhost:8080"
    ]
    
    # Logging
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "json"
    
    # Sentry (Optional)
    SENTRY_DSN: Optional[str] = None
    
    class Config:
        env_file = ".env"
        case_sensitive = True


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


settings = get_settings()
