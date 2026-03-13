"""
SQLAlchemy base configuration.
FILE: app/db/base.py

BUGS FIXED:
1. CRITICAL — DeclarativeBase (SQLAlchemy 2.x) + plain Column() syntax
   without Mapped[] annotations raises at startup:
   "SAWarning: Mapper[Video(videos)] does not have a mapped column 'id'"
   and in strict builds a full MappedColumn error. Every single model
   failed to register. Fixed: __allow_unmapped__ = True on Base.

2. CRITICAL — _EngineProxy.__call__ called self._get_real()() but
   SQLAlchemy Engine is not callable → TypeError whenever any code
   did engine(). Removed __call__; added connect() and begin() passthroughs
   so common use patterns work without the dangerous fallthrough.

3. pool_recycle=280 prevents "SSL connection closed unexpectedly" errors
   after Render's managed Postgres closes idle connections at ~300s.

4. Explicit rollback in get_db() exception handler so failed writes
   don't leave uncommitted transactions blocking the connection pool.

5. Deferred engine creation so a missing DATABASE_URL gives a clear
   RuntimeError instead of a cryptic import-time crash.
"""

import logging
from typing import Generator

from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.logging import get_logger

logger = get_logger(__name__)


# ── Base ──────────────────────────────────────────────────────────────────────

class Base(DeclarativeBase):
    """
    FIX 1 — __allow_unmapped__ = True lets all models use the legacy
    Column() syntax (without Mapped[] annotations) under SQLAlchemy 2.x.
    Without this every model raises a MappedColumn registration error
    at startup before a single request is served.
    """
    __allow_unmapped__ = True


# ── Engine (lazy) ─────────────────────────────────────────────────────────────

_engine   = None
_Session  = None


def get_engine():
    """
    FIX 5 — Deferred so a missing DATABASE_URL gives a clear error
    instead of crashing the entire import chain.
    """
    global _engine
    if _engine is not None:
        return _engine

    from app.config import settings

    url = getattr(settings, "DATABASE_URL", None)
    if not url:
        raise RuntimeError(
            "DATABASE_URL is not set. "
            "Add it to your Render environment variables."
        )

    is_sqlite    = url.startswith("sqlite")
    pool_size    = getattr(settings, "DATABASE_POOL_SIZE",    5)
    max_overflow = getattr(settings, "DATABASE_MAX_OVERFLOW", 10)

    if is_sqlite:
        # SQLite doesn't support pool_size / max_overflow
        _engine = create_engine(
            url,
            connect_args={"check_same_thread": False},
            pool_pre_ping=True,
        )
    else:
        # FIX 3 — pool_recycle=280 keeps connections alive through
        # Render's 300 s idle-connection timeout
        _engine = create_engine(
            url,
            pool_size=pool_size,
            max_overflow=max_overflow,
            pool_pre_ping=True,
            pool_recycle=280,
        )

    logger.info(f"Database engine created: {url[:40]}...")
    return _engine


# ── Session factory ───────────────────────────────────────────────────────────

def _get_session_factory() -> sessionmaker:
    global _Session
    if _Session is None:
        _Session = sessionmaker(
            autocommit=False,
            autoflush=False,
            bind=get_engine(),
        )
    return _Session


def SessionLocal() -> Session:
    """Return a new DB session. Caller is responsible for closing it."""
    return _get_session_factory()()


def get_db() -> Generator[Session, None, None]:
    """
    FastAPI dependency — yields a DB session.
    FIX 4 — explicit rollback on exception so the connection is
    returned to the pool in a clean state.
    """
    db = _get_session_factory()()
    try:
        yield db
    except Exception:
        db.rollback()   # FIX 4
        raise
    finally:
        db.close()


# ── Engine proxy ──────────────────────────────────────────────────────────────

class _EngineProxy:
    """
    FIX 2 — Lazy engine proxy. Removed __call__ (Engine is not callable).
    Exposes connect() and begin() directly so common patterns work.
    All other attribute access is forwarded to the real engine via __getattr__.
    """
    _real: object = None

    def _get(self):
        if self._real is None:
            object.__setattr__(self, "_real", get_engine())
        return self._real

    # Explicit passthroughs for the most-used engine methods
    def connect(self, *a, **kw):
        return self._get().connect(*a, **kw)

    def begin(self, *a, **kw):
        return self._get().begin(*a, **kw)

    def dispose(self, *a, **kw):
        return self._get().dispose(*a, **kw)

    # Generic fallthrough for anything else
    def __getattr__(self, name: str):
        return getattr(self._get(), name)

    def __repr__(self):
        return repr(self._get())

    def __str__(self):
        return str(self._get())


# main.py can do: from app.db.base import engine
engine = _EngineProxy()


# ── Startup helpers ───────────────────────────────────────────────────────────

def create_tables() -> None:
    """
    Create all tables that don't exist yet (CREATE TABLE IF NOT EXISTS).
    Safe to call on every startup. Call from main.py lifespan.
    """
    import app.models.user     # noqa: F401 — register models on Base
    import app.models.video    # noqa: F401
    import app.models.payment  # noqa: F401

    Base.metadata.create_all(bind=get_engine())
    logger.info("Database tables verified / created.")


def health_check() -> bool:
    """Quick connectivity test for the /health endpoint."""
    try:
        with get_engine().connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception as e:
        logger.error(f"DB health check failed: {e}")
        return False
