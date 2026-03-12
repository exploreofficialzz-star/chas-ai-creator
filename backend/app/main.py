"""
chAs AI Creator - Main FastAPI Application
FILE: app/main.py

FIXES:
1. CORS — allow_credentials=True + allow_origins=["*"] is invalid.
   Browsers reject it with "Cannot use wildcard in Access-Control-Allow-Origin
   when credentials flag is true". Fixed: credentials=False for wildcard.

2. sys.path — was going 2 dirs above project root. Removed entirely;
   Render sets PYTHONPATH via Procfile / render.yaml. If you need it,
   set PYTHONPATH=. in Render env vars instead.

3. @app.on_event("startup") is deprecated and conflicts with lifespan.
   Moved config validation into lifespan so there's one startup handler.

4. Fallback router now shows the real error so it's diagnosable in prod.
"""

import os
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.core.exceptions import APIException
from app.core.logging import setup_logging, get_logger
from app.core.exceptions import register_exception_handlers
register_exception_handlers(app)

from app.models.payment import seed_default_plans, seed_default_packages
from app.db.base import get_db

async with lifespan:
    create_tables()
    db = next(get_db())
    seed_default_plans(db)
    seed_default_packages(db)
   
setup_logging()
logger = get_logger(__name__)

# Store router load error so fallback endpoint can expose it
_router_load_error: str = ""



from app.db.base import create_tables, health_check

@asynccontextmanager
async def lifespan(app):
    create_tables()          # ← add this
    db_ok = health_check()   # ← and this
    if not db_ok:
        logger.warning("⚠️ Database unreachable at startup")
    yield
    # ── Config validation (moved from @on_event — avoids duplicate handler) ──
    errors = []
    if not settings.SECRET_KEY or len(settings.SECRET_KEY) < 32:
        errors.append("SECRET_KEY must be at least 32 characters")
    if not settings.DATABASE_URL:
        errors.append("DATABASE_URL is required")
    if not settings.PAYSTACK_SECRET_KEY:
        logger.warning("⚠️ PAYSTACK_SECRET_KEY not set — payments disabled")
    if not settings.CLOUDINARY_CLOUD_NAME:
        logger.warning("⚠️ Cloudinary not configured — file storage disabled")
    if errors:
        logger.error(f"❌ Config errors: {errors}")
        if settings.ENVIRONMENT == "production":
            raise RuntimeError(f"Invalid configuration: {errors}")
    else:
        logger.info("✅ Configuration validated")

    # ── Database ──────────────────────────────────────────────────────────────
    try:
        from app.db.base import engine, Base
        Base.metadata.create_all(bind=engine)
        logger.info("✅ Database tables created/verified")
    except Exception as e:
        logger.error(f"❌ Database initialization failed: {e}")
        logger.warning("⚠️ Continuing without database — check DATABASE_URL")

    # ── AI services (lazy — don't crash startup if HF key missing) ───────────
    app.state.ai_services = {}
    try:
        if settings.HUGGINGFACE_API_KEY:
            from app.services.ai.text_generation  import TextGenerationService
            from app.services.ai.image_generation import ImageGenerationService
            from app.services.ai.video_generation import VideoGenerationService

            app.state.ai_services["text"]  = TextGenerationService()
            app.state.ai_services["image"] = ImageGenerationService()
            app.state.ai_services["video"] = VideoGenerationService()
            logger.info("✅ AI services initialized")
        else:
            logger.warning(
                "⚠️ HUGGINGFACE_API_KEY not set — AI services disabled"
            )
    except Exception as e:
        logger.warning(f"⚠️ AI services init failed: {e}")

    logger.info("✅ chAs AI Creator is ready!")

    yield  # ── app is running ──

    # ── Shutdown ──────────────────────────────────────────────────────────────
    logger.info("🛑 chAs AI Creator shutting down...")
    for name, service in getattr(app.state, "ai_services", {}).items():
        try:
            if hasattr(service, "cleanup"):
                await service.cleanup()
        except Exception as e:
            logger.error(f"Error cleaning up {name}: {e}")


# ── App ───────────────────────────────────────────────────────────────────────

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="🎬 AI-powered video content automation platform by chAs",
    docs_url="/docs"         if settings.DEBUG else None,
    redoc_url="/redoc"       if settings.DEBUG else None,
    openapi_url="/openapi.json" if settings.DEBUG else None,
    lifespan=lifespan,
)

# ── CORS ──────────────────────────────────────────────────────────────────────
# FIX 1 — allow_credentials=True + allow_origins=["*"] is browser-rejected.
# Using allow_credentials=False so the wildcard origin is valid.
# Flutter mobile apps don't send credentials in CORS preflight anyway —
# they pass the JWT in the Authorization header which is always allowed.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,   # FIX — was True, invalid with wildcard origin
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)

app.add_middleware(GZipMiddleware, minimum_size=1000)


# ── Request timing middleware ─────────────────────────────────────────────────

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


# ── Exception handlers ────────────────────────────────────────────────────────

@app.exception_handler(APIException)
async def api_exception_handler(request: Request, exc: APIException):
    logger.error(f"API Exception [{exc.error_code}]: {exc.message}")
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error":   exc.message,
            "code":    exc.error_code,
            "success": False,
        },
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    logger.exception(f"Unhandled exception: {exc}")
    return JSONResponse(
        status_code=500,
        content={
            "error":   "Internal server error"
                       if not settings.DEBUG else str(exc),
            "code":    "INTERNAL_ERROR",
            "success": False,
        },
    )


# ── Health / Root ─────────────────────────────────────────────────────────────

@app.get("/health",  tags=["Health"])
@app.get("/healthz", tags=["Health"])
async def health_check():
    """Health check for Render."""
    return {
        "status":      "healthy",
        "version":     settings.APP_VERSION,
        "app":         settings.APP_NAME,
        "creator":     settings.APP_CREATOR,
        "environment": settings.ENVIRONMENT,
        "timestamp":   time.time(),
    }


@app.get("/",  tags=["Root"])
@app.head("/", include_in_schema=False)
async def root():
    return {
        "app":         settings.APP_NAME,
        "version":     settings.APP_VERSION,
        "creator":     settings.APP_CREATOR,
        "description": "AI-powered video content automation platform",
        "environment": settings.ENVIRONMENT,
        "docs":        "/docs" if settings.DEBUG else None,
        "health":      "/health",
    }


# ── Routers ───────────────────────────────────────────────────────────────────

try:
    from app.api.v1 import auth, users, videos, ai_services, payments

    app.include_router(
        auth.router,        prefix="/api/v1/auth",     tags=["Authentication"])
    app.include_router(
        users.router,       prefix="/api/v1/users",    tags=["Users"])
    app.include_router(
        videos.router,      prefix="/api/v1/videos",   tags=["Videos"])
    app.include_router(
        ai_services.router, prefix="/api/v1/ai",       tags=["AI Services"])
    app.include_router(
        payments.router,    prefix="/api/v1/payments", tags=["Payments"])

    logger.info("✅ API routes registered")

except Exception as e:
    _router_load_error = str(e)
    logger.error(f"❌ Failed to load API routes: {e}")

    from fastapi import APIRouter
    _fallback = APIRouter()

    @_fallback.get("/error")
    async def error_info():
        # FIX 4 — expose the real error so it's diagnosable
        return {
            "error":  "API routes failed to load",
            "detail": _router_load_error,
        }

    app.include_router(_fallback, prefix="/api/v1")


# ── Dev entrypoint ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", getattr(settings, "PORT", 8000)))
    uvicorn.run(
        "app.main:app",
        host=getattr(settings, "HOST", "0.0.0.0"),
        port=port,
        reload=settings.DEBUG,
        log_level="info",
        access_log=True,
    )
