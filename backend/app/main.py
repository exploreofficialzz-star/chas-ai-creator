"""
AI Creator Automation - Main FastAPI Application
Created by: chAs
Copyright (c) 2024 chAs. All rights reserved.
"""

import os
import sys
import time
from contextlib import asynccontextmanager

# Add project root to path (for Render)
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(current_dir))
sys.path.insert(0, project_root)

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse

# Use absolute imports for Render compatibility
from app.config import settings
from app.core.exceptions import APIException
from app.core.logging import setup_logging, get_logger

# Setup logging first
setup_logging()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events."""
    logger.info("🚀 chAs AI Creator starting up...")
    
    # Database initialization
    try:
        from app.db.base import engine, Base
        Base.metadata.create_all(bind=engine)
        logger.info("✅ Database tables created/verified")
    except Exception as e:
        logger.error(f"❌ Database initialization failed: {e}")
        # Don't raise - let app start anyway for debugging
        logger.warning("⚠️ Continuing without database...")
    
    # Initialize AI services (lazy load to avoid startup crashes)
    app.state.ai_services = {}
    try:
        # Only import if HuggingFace key is configured
        if settings.HUGGINGFACE_API_KEY:
            from app.services.ai.text_generation import TextGenerationService
            from app.services.ai.image_generation import ImageGenerationService
            from app.services.ai.video_generation import VideoGenerationService
            
            app.state.ai_services['text'] = TextGenerationService()
            app.state.ai_services['image'] = ImageGenerationService()
            app.state.ai_services['video'] = VideoGenerationService()
            logger.info("✅ AI services initialized")
        else:
            logger.warning("⚠️ HUGGINGFACE_API_KEY not set - AI services disabled")
    except Exception as e:
        logger.warning(f"⚠️ AI services initialization failed: {e}")
        logger.info("💡 App will run without AI generation capabilities")
    
    logger.info("✅ chAs AI Creator is ready!")
    
    yield
    
    # Cleanup on shutdown
    logger.info("🛑 chAs AI Creator shutting down...")
    # Cleanup AI services if needed
    for service_name, service in getattr(app.state, 'ai_services', {}).items():
        try:
            if hasattr(service, 'cleanup'):
                await service.cleanup()
        except Exception as e:
            logger.error(f"Error cleaning up {service_name}: {e}")


# Create FastAPI app
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="🎬 AI-powered video content automation platform by chAs",
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
    openapi_url="/openapi.json" if settings.DEBUG else None,  # Hide schema in prod
    lifespan=lifespan,
)

# CORS - Critical for Flutter frontend - PERMISSIVE VERSION
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow ALL origins temporarily for testing
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)

app.add_middleware(GZipMiddleware, minimum_size=1000)


# Request timing middleware
@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    start_time = time.time()
    try:
        response = await call_next(request)
        process_time = time.time() - start_time
        response.headers["X-Process-Time"] = f"{process_time:.3f}s"
        return response
    except Exception as e:
        process_time = time.time() - start_time
        logger.error(f"Request failed after {process_time:.3f}s: {e}")
        raise


# Exception handlers
@app.exception_handler(APIException)
async def api_exception_handler(request: Request, exc: APIException):
    """Handle custom API exceptions."""
    logger.error(f"API Exception [{exc.error_code}]: {exc.message}")
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": exc.message,
            "code": exc.error_code,
            "success": False
        },
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Handle unexpected exceptions."""
    logger.exception(f"Unhandled exception: {str(exc)}")
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error" if not settings.DEBUG else str(exc),
            "code": "INTERNAL_ERROR",
            "success": False
        },
    )


# Health check - Render requires this
@app.get("/health", tags=["Health"])
@app.get("/healthz", tags=["Health"])  # Alternative path some platforms use
async def health_check():
    """Health check endpoint for Render."""
    return {
        "status": "healthy",
        "version": settings.APP_VERSION,
        "app": settings.APP_NAME,
        "creator": settings.APP_CREATOR,
        "environment": settings.ENVIRONMENT,
        "timestamp": time.time()
    }


# Root endpoint - Supports both GET and HEAD (Render requires HEAD)
@app.get("/", tags=["Root"])
@app.head("/", include_in_schema=False)
async def root():
    """Root endpoint."""
    return {
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "creator": settings.APP_CREATOR,
        "description": "AI-powered video content automation platform",
        "environment": settings.ENVIRONMENT,
        "docs": "/docs" if settings.DEBUG else None,
        "health": "/health"
    }


# Import and include routers (with error handling)
try:
    from app.api.v1 import auth, users, videos, ai_services, payments
    
    app.include_router(auth.router, prefix="/api/v1/auth", tags=["Authentication"])
    app.include_router(users.router, prefix="/api/v1/users", tags=["Users"])
    app.include_router(videos.router, prefix="/api/v1/videos", tags=["Videos"])
    app.include_router(ai_services.router, prefix="/api/v1/ai", tags=["AI Services"])
    app.include_router(payments.router, prefix="/api/v1/payments", tags=["Payments"])
    
    logger.info("✅ API routes registered")
except Exception as e:
    logger.error(f"❌ Failed to load API routes: {e}")
    # Create fallback router
    from fastapi import APIRouter
    fallback_router = APIRouter()
    
    @fallback_router.get("/error")
    async def error_info():
        return {"error": "API routes failed to load", "detail": str(e)}
    
    app.include_router(fallback_router, prefix="/api/v1")


# Startup validation
@app.on_event("startup")
async def validate_config():
    """Validate critical configuration on startup."""
    errors = []
    
    if not settings.SECRET_KEY or len(settings.SECRET_KEY) < 32:
        errors.append("SECRET_KEY must be at least 32 characters")
    
    if not settings.DATABASE_URL:
        errors.append("DATABASE_URL is required")
    
    if not settings.PAYSTACK_SECRET_KEY:
        logger.warning("⚠️ PAYSTACK_SECRET_KEY not set - payments disabled")
    
    if not settings.CLOUDINARY_CLOUD_NAME:
        logger.warning("⚠️ Cloudinary not configured - file storage disabled")
    
    if errors:
        logger.error(f"❌ Configuration errors: {errors}")
        if settings.ENVIRONMENT == "production":
            raise RuntimeError(f"Invalid configuration: {errors}")
    else:
        logger.info("✅ Configuration validated")


if __name__ == "__main__":
    import uvicorn
    
    # Render uses PORT env var, fallback to settings
    port = int(os.getenv("PORT", settings.PORT))
    
    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=port,
        reload=settings.DEBUG,
        log_level="info",
        access_log=True,
    )
