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
    
    # Database - SQLite for local, PostgreSQL for production
    DATABASE_URL: str = "sqlite:///./app.db"
    DATABASE_POOL_SIZE: int = 20
    DATABASE_MAX_OVERFLOW: int = 10
    
    # Redis (Optional - can disable if not available)
    REDIS_URL: Optional[str] = "redis://localhost:6379/0"
    
    # AI Services - HuggingFace (works in Nigeria ✓)
    HUGGINGFACE_API_KEY: Optional[str] = None
    HUGGINGFACE_API_URL: str = "https://api-inference.huggingface.co/models"
    
    # REMOVE: OpenAI (blocked in Nigeria)
    # OPENAI_API_KEY: Optional[str] = None
    
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
    
    # REMOVE: Stripe (blocked in Nigeria)
    # STRIPE_SECRET_KEY: str = ""
    # STRIPE_PUBLISHABLE_KEY: str = ""
    # STRIPE_WEBHOOK_SECRET: str = ""
    # STRIPE_PRICE_ID_FREE: str = ""
    # STRIPE_PRICE_ID_PRO: str = ""
    # STRIPE_PRICE_ID_ENTERPRISE: str = ""
    
    # Storage - Cloudinary (Global ✓)
    CLOUDINARY_CLOUD_NAME: str = ""
    CLOUDINARY_API_KEY: str = ""
    CLOUDINARY_API_SECRET: str = ""
    
    # REMOVE: AWS (can use but expensive)
    # AWS_ACCESS_KEY_ID: str = ""
    # AWS_SECRET_ACCESS_KEY: str = ""
    # AWS_REGION: str = "us-east-1"
    # AWS_S3_BUCKET: str = "ai-creator-videos"
    # AWS_S3_ENDPOINT: Optional[str] = None
    
    # REMOVE: Firebase (restricted in Nigeria)
    # FIREBASE_PROJECT_ID: str = ""
    # FIREBASE_PRIVATE_KEY: str = ""
    # FIREBASE_CLIENT_EMAIL: str = ""
    # FIREBASE_DATABASE_URL: Optional[str] = None
    # FIREBASE_STORAGE_BUCKET: Optional[str] = None
    
    # Ads - Unity Ads (Nigeria ✓)
    UNITY_GAME_ID_IOS: str = "6060849"
    UNITY_GAME_ID_ANDROID: str = "6060848"
    UNITY_PLACEMENT_ID: str = "rewardedVideo"
    UNITY_ENABLED: bool = True
    
    # REMOVE: Google AdMob (replaced with Unity Ads)
    # ADMOB_APP_ID_ANDROID: str = ""
    # ADMOB_APP_ID_IOS: str = ""
    # ADMOB_BANNER_AD_UNIT_ID: str = ""
    # ADMOB_INTERSTITIAL_AD_UNIT_ID: str = ""
    # ADMOB_REWARDED_AD_UNIT_ID: str = ""
    
    # Limits - chAs AI Creator Tiers
    FREE_TIER_DAILY_VIDEOS: int = 2  # Reduced for ads support
    PRO_TIER_DAILY_VIDEOS: int = 20
    ENTERPRISE_TIER_DAILY_VIDEOS: int = 100
    
    FREE_TIER_MAX_VIDEO_LENGTH: int = 30
    PRO_TIER_MAX_VIDEO_LENGTH: int = 120
    ENTERPRISE_TIER_MAX_VIDEO_LENGTH: int = 300
    
    # Ad Configuration
    ADS_ENABLED: bool = True
    ADS_FREQUENCY_VIDEOS: int = 2  # Show ad every N videos for free users
    ADS_FREQUENCY_SCREEN_VIEWS: int = 5  # Show ad every N screen views
    
    # Scheduling
    SCHEDULER_ENABLED: bool = True
    MAX_SCHEDULED_VIDEOS_PER_DAY: int = 10
    
    # Security
    SECRET_KEY: str = "your-random-secret-key-min-32-chars-long"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days
    REFRESH_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 30  # 30 days
    
    # CORS (Update with your actual frontend URL)
    CORS_ORIGINS: List[str] = ["https://your-app.onrender.com", "http://localhost:3000"]
    
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
