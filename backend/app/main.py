"""
AI Creator Automation - Main FastAPI Application
Created by: chAs
Copyright (c) 2024 chAs. All rights reserved.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
import time

from app.api.v1 import auth, users, videos, ai_services, payments
from app.config import settings
from app.core.exceptions import APIException
from app.core.logging import setup_logging, get_logger
from app.db.base import engine, Base

# Setup logging
setup_logging()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events."""
    logger.info("🚀 chAs AI Creator starting up...")
    
    # Startup
    try:
        # Create database tables
        Base.metadata.create_all(bind=engine)
        logger.info("✅ Database tables created")
    except Exception as e:
        logger.error(f"❌ Database initialization failed: {e}")
        raise
    
    # Initialize AI services
    try:
        from app.services.ai.text_generation import TextGenerationService
        from app.services.ai.image_generation import ImageGenerationService
        from app.services.ai.video_generation import VideoGenerationService
        
        app.state.text_service = TextGenerationService()
        app.state.image_service = ImageGenerationService()
        app.state.video_service = VideoGenerationService()
        logger.info("✅ AI services initialized")
    except Exception as e:
        logger.warning(f"⚠️ Some AI services failed to initialize: {e}")
    
    logger.info("✅ chAs AI Creator is ready!")
    
    yield
    
    # Shutdown
    logger.info("🛑 chAs AI Creator shutting down...")


# Create FastAPI app
app = FastAPI(
    title="chAs AI Creator",
    version=settings.APP_VERSION,
    description="🎬 AI-powered video content automation platform by chAs",
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
    lifespan=lifespan,
)

# Add middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(GZipMiddleware, minimum_size=1000)


# Request timing middleware
@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    response.headers["X-Process-Time"] = str(process_time)
    return response


# Exception handler
@app.exception_handler(APIException)
async def api_exception_handler(request: Request, exc: APIException):
    """Handle API exceptions."""
    logger.error(f"API Exception: {exc.message}", code=exc.error_code)
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": exc.message, 
            "code": exc.error_code,
            "success": False
        },
    )


# General exception handler
@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Handle general exceptions."""
    logger.error(f"Unhandled exception: {str(exc)}")
    return JSONResponse(
        status_code=500,
        content={
            "error": "An unexpected error occurred. Please try again.",
            "code": "INTERNAL_ERROR",
            "success": False
        },
    )


# Health check
@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy", 
        "version": settings.APP_VERSION,
        "app": "chAs AI Creator",
        "creator": "chAs"
    }


# Root endpoint
@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "app": "chAs AI Creator",
        "version": settings.APP_VERSION,
        "creator": "chAs",
        "description": "AI-powered video content automation platform",
        "docs": "/docs" if settings.DEBUG else None,
        "health": "/health"
    }


# Include routers
app.include_router(auth.router, prefix="/api/v1/auth", tags=["🔐 Authentication"])
app.include_router(users.router, prefix="/api/v1/users", tags=["👤 Users"])
app.include_router(videos.router, prefix="/api/v1/videos", tags=["🎬 Videos"])
app.include_router(ai_services.router, prefix="/api/v1/ai", tags=["🤖 AI Services"])
app.include_router(payments.router, prefix="/api/v1/payments", tags=["💳 Payments"])


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
      )
