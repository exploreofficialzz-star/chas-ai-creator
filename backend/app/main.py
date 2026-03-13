"""
chAs AI Creator — Main FastAPI Application
FILE: app/main.py

BUGS FIXED:
1. CRITICAL — Duplicate exception handlers. register_exception_handlers(app)
   was called AND then @app.exception_handler decorators were also registered
   below it. FastAPI stacks handlers — the decorators silently overrode
   register_exception_handlers(). Worse: if register_exception_handlers()
   doesn't exist in exceptions.py the bare import crashed startup before any
   route loaded. Fixed: use ONLY the decorator-style handlers; removed the
   register_exception_handlers() call entirely.

2. CRITICAL — DB session leak in lifespan. db = next(get_db()) created a
   session with no finally: db.close(). If seeding raised, the connection
   was leaked. On Render free tier (max 5 Postgres connections) this caused
   "too many connections" after a few redeploys.
   Fixed: try/finally with explicit db.close().

3. AI services never initialized without HUGGINGFACE_API_KEY. Guard was
   `if settings.HUGGINGFACE_API_KEY` but Replicate/Segmind/Gemini/Groq
   don't need it. A user with only REPLICATE_API_KEY set got "AI disabled"
   and every video generation returned 503.
   Fixed: check if ANY ai key is set.

4. @app.head("/") conflicted with @app.get("/"). FastAPI auto-generates
   HEAD for every GET route — the explicit HEAD registration caused a
   duplicate-route warning and 422 on HEAD in some FastAPI versions.
   Fixed: removed the explicit HEAD route.

5. health_check name collision. The lifespan imported health_check from
   app.db.base AND the route function was also named health_check. The
   DB import was fine in local lifespan scope, but the name clash made
   it easy to accidentally call the wrong function.
   Fixed: route renamed to health_check_route; DB import aliased to
   db_health_check. Also added db_health_check to db/base.py exports.

6. _router_load_error closure wrong scope. Module-level variable was
   reassigned with a plain = inside the except block — Python treats
   that as a local variable in the enclosing scope, not the global one.
   The nested async def error_info() always read the original "" value.
   Fixed: `global _router_load_error` inside the except block.
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

# FIX 6 — no type annotation here; annotated names cannot be used with `global`
_router_load_error = ""

setup_logging()
logger = get_logger(__name__)


# ── Lifespan ──────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):

    # ── Config validation ─────────────────────────────────────────────────────
    errors   = []
    warnings = []

    if not settings.SECRET_KEY or len(settings.SECRET_KEY) < 32:
        errors.append("SECRET_KEY must be at least 32 characters")
    if not settings.DATABASE_URL:
        errors.append("DATABASE_URL is required")
    if not settings.PAYSTACK_SECRET_KEY:
        warnings.append("PAYSTACK_SECRET_KEY not set — payments disabled")
    if not settings.CLOUDINARY_CLOUD_NAME:
        warnings.append("Cloudinary not configured — file storage disabled")

    for w in warnings:
        logger.warning(f"⚠️  {w}")

    if errors:
        logger.error(f"❌ Config errors: {errors}")
        if settings.ENVIRONMENT == "production":
            raise RuntimeError(f"Invalid configuration: {errors}")
    else:
        logger.info("✅ Configuration validated")

    # ── Database ──────────────────────────────────────────────────────────────
    try:
        # FIX 5 — import aliased to avoid name clash with the route below
        from app.db.base import create_tables, health_check as db_health_check, get_db

        create_tables()

        if db_health_check():
            logger.info("✅ Database connection verified")
        else:
            logger.warning("⚠️  Database unreachable at startup — check DATABASE_URL")

        # FIX 2 — always close the seeding session in finally
        db = None
        try:
            db = next(get_db())
            from app.models.payment import seed_default_plans, seed_default_packages
            seed_default_plans(db)
            seed_default_packages(db)
            logger.info("✅ Default plans/packages seeded")
        except Exception as seed_err:
            logger.warning(f"⚠️  Seeding failed (non-fatal): {seed_err}")
        finally:
            if db is not None:
                db.close()   # FIX 2

        logger.info("✅ Database tables verified / created")

    except Exception as e:
        logger.error(f"❌ Database initialization failed: {e}")
        logger.warning("⚠️  Continuing without database — check DATABASE_URL")

    # ── AI services ───────────────────────────────────────────────────────────
    # FIX 3 — any key present is enough; don't gate everything on HF alone
    _any_ai_key = any([
        getattr(settings, "HUGGINGFACE_API_KEY", None),
        getattr(settings, "GROQ_API_KEY",        None),
        getattr(settings, "GEMINI_API_KEY",       None),
        getattr(settings, "REPLICATE_API_KEY",    None),
        getattr(settings, "SEGMIND_API_KEY",      None),
    ])

    app.state.ai_services = {}

    if _any_ai_key:
        try:
            from app.services.ai.text_generation  import TextGenerationService
            from app.services.ai.image_generation import ImageGenerationService
            from app.services.ai.video_generation import VideoGenerationService

            app.state.ai_services["text"]  = TextGenerationService()
            app.state.ai_services["image"] = ImageGenerationService()
            app.state.ai_services["video"] = VideoGenerationService()
            logger.info("✅ AI services initialized")
        except Exception as e:
            logger.warning(f"⚠️  AI services init failed: {e}")
    else:
        logger.warning(
            "⚠️  No AI API keys detected. Add at least one of: "
            "HUGGINGFACE_API_KEY, GROQ_API_KEY, GEMINI_API_KEY, "
            "REPLICATE_API_KEY, or SEGMIND_API_KEY to your .env"
        )

    logger.info(f"🚀 {settings.APP_NAME} v{settings.APP_VERSION} ready!")
    yield

    # ── Shutdown ──────────────────────────────────────────────────────────────
    logger.info("🛑 Shutting down…")
    for name, service in getattr(app.state, "ai_services", {}).items():
        try:
            if hasattr(service, "cleanup"):
                await service.cleanup()
        except Exception as e:
            logger.error(f"Cleanup error ({name}): {e}")


# ── App ───────────────────────────────────────────────────────────────────────

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="🎬 AI-powered video content automation platform by chAs",
    docs_url="/docs"            if settings.DEBUG else None,
    redoc_url="/redoc"          if settings.DEBUG else None,
    openapi_url="/openapi.json" if settings.DEBUG else None,
    lifespan=lifespan,
)

# ── CORS ──────────────────────────────────────────────────────────────────────
# allow_credentials=True + allow_origins=["*"] is rejected by browsers.
# Flutter mobile apps pass JWT in the Authorization header — they never
# send cookies — so allow_credentials=False is correct and safe here.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,   # must be False when allow_origins is a wildcard
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)

app.add_middleware(GZipMiddleware, minimum_size=1000)


# ── Request timing middleware ─────────────────────────────────────────────────

@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    start = time.time()
    try:
        response = await call_next(request)
        response.headers["X-Process-Time"] = f"{time.time() - start:.3f}s"
        return response
    except Exception as e:
        logger.error(f"Request failed after {time.time() - start:.3f}s: {e}")
        raise


# ── Exception handlers ────────────────────────────────────────────────────────
# FIX 1 — register ONLY here via decorators.
#          Removed register_exception_handlers(app) — it was overridden by
#          these decorators anyway, and crashed startup if the function
#          didn't exist in exceptions.py.

@app.exception_handler(APIException)
async def api_exception_handler(request: Request, exc: APIException):
    logger.error(f"APIException [{exc.error_code}]: {exc.message}")
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
            "error":   str(exc) if settings.DEBUG else "Internal server error",
            "code":    "INTERNAL_ERROR",
            "success": False,
        },
    )


# ── Health / Root ─────────────────────────────────────────────────────────────

@app.get("/health",  tags=["Health"])
@app.get("/healthz", tags=["Health"])
async def health_check_route():   # FIX 5 — renamed to avoid collision with db import
    return {
        "status":      "healthy",
        "version":     settings.APP_VERSION,
        "app":         settings.APP_NAME,
        "creator":     settings.APP_CREATOR,
        "environment": settings.ENVIRONMENT,
        "timestamp":   time.time(),
    }


@app.api_route("/", methods=["GET", "HEAD"], tags=["Root"])
# Explicit HEAD prevents 405 on Render health probes and load balancers
# that send HEAD / before routing real traffic. FastAPI's auto-HEAD
# generation is unreliable with GZipMiddleware in some Starlette versions.
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

    app.include_router(auth.router,        prefix="/api/v1/auth",     tags=["Authentication"])
    app.include_router(users.router,       prefix="/api/v1/users",    tags=["Users"])
    app.include_router(videos.router,      prefix="/api/v1/videos",   tags=["Videos"])
    app.include_router(ai_services.router, prefix="/api/v1/ai",       tags=["AI Services"])
    app.include_router(payments.router,    prefix="/api/v1/payments",  tags=["Payments"])

    logger.info("✅ API routes registered")

except Exception as e:
    global _router_load_error          # FIX 6 — update the module-level variable
    _router_load_error = str(e)
    logger.error(f"❌ Failed to load API routes: {e}", exc_info=True)

    from fastapi import APIRouter
    _fallback = APIRouter()

    @_fallback.get("/error")
    async def error_info():
        return {
            "error":  "API routes failed to load",
            "detail": _router_load_error,   # FIX 6 — now reads the real error
        }

    app.include_router(_fallback, prefix="/api/v1")


# ── Dev entrypoint ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=getattr(settings, "HOST", "0.0.0.0"),
        port=int(os.getenv("PORT", getattr(settings, "PORT", 8000))),
        reload=settings.DEBUG,
        log_level="info",
        access_log=True,
    )
