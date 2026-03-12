"""
SQLAlchemy base configuration.
FILE: app/db/base.py

FIXES:
1. CRITICAL — create_engine() called with pool_size and max_overflow
   at module import time. If DATABASE_URL uses SQLite (common in local
   dev / CI), SQLite doesn't support connection pooling and raises:
   "Invalid argument(s) 'pool_size' for dialect sqlite"
   Fixed: only pass pool args for non-SQLite engines.

2. CRITICAL — create_engine() runs at import time, so if DATABASE_URL
   is missing or malformed (e.g. Render cold-start before env vars are
   injected), the entire app crashes on import with an unreadable error.
   Fixed: deferred engine creation inside get_engine() with a clear error.

3. CRITICAL — get_db() used a plain try/finally — on exception the
   session was closed but never rolled back. Any failed DB write left
   an uncommitted transaction open, which blocked subsequent queries on
   the same connection until the pool recycled it.
   Fixed: explicit rollback in the except branch.

4. declarative_base() from sqlalchemy.ext.declarative is deprecated
   since SQLAlchemy 1.4 and removed in 2.0. Render's python packages
   will install SQLAlchemy 2.x. Fixed: import from sqlalchemy.orm.

5. pool_pre_ping=True is correct but pool_recycle was missing.
   Render's PostgreSQL (and most managed DBs) close idle connections
   after 300 s — without pool_recycle the app gets
   "SSL connection has been closed unexpectedly" errors after idle
   periods. Fixed: pool_recycle=280 (just under the 300 s limit).

6. DATABASE_POOL_SIZE / DATABASE_MAX_OVERFLOW missing from config
   caused AttributeError. Fixed with safe getattr() fallback defaults.

7. Added create_tables() helper used by main.py lifespan to ensure
   tables exist on first deploy without running a separate migration.
   Also added health_check() for the /health endpoint.
"""

import logging
from typing import Generator, Optional

from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.logging import get_logger

logger = get_logger(__name__)

# FIX 4 — use the non-deprecated import path (SQLAlchemy 1.4+ / 2.x)
class Base(DeclarativeBase):
    pass


# Module-level singletons — populated lazily by get_engine()
_engine  = None
_Session = None


def get_engine():
    """
    FIX 2 — Deferred engine creation so import-time crashes are avoided
    and a clear error is raised if DATABASE_URL is not set.
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

    is_sqlite = url.startswith("sqlite")

    # FIX 6 — safe defaults if pool settings missing from config
    pool_size   = getattr(settings, "DATABASE_POOL_SIZE",    5)
    max_overflow = getattr(settings, "DATABASE_MAX_OVERFLOW", 10)

    if is_sqlite:
        # FIX 1 — SQLite doesn't support pool_size / max_overflow
        _engine = create_engine(
            url,
            connect_args={"check_same_thread": False},
            pool_pre_ping=True,
        )
    else:
        # FIX 5 — pool_recycle prevents stale connection errors
        _engine = create_engine(
            url,
            pool_size=pool_size,
            max_overflow=max_overflow,
            pool_pre_ping=True,
            pool_recycle=280,   # FIX 5 — recycle before managed DB closes idle conn
        )

    logger.info(f"Database engine created: {url[:30]}...")
    return _engine


def get_session_factory() -> sessionmaker:
    """Return (and lazily create) the session factory."""
    global _Session
    if _Session is None:
        _Session = sessionmaker(
            autocommit=False,
            autoflush=False,
            bind=get_engine(),
        )
    return _Session


# Convenience alias used by tasks/video_generation.py
def SessionLocal() -> Session:
    return get_session_factory()()


def get_db() -> Generator[Session, None, None]:
    """
    FastAPI dependency — yields a DB session.
    FIX 3 — rolls back on exception so the connection is returned clean.
    """
    db = get_session_factory()()
    try:
        yield db
    except Exception:
        db.rollback()    # FIX 3
        raise
    finally:
        db.close()


def create_tables() -> None:
    """
    FIX 7 — Create all tables that don't exist yet.
    Safe to call on every startup (CREATE TABLE IF NOT EXISTS).
    Called from main.py lifespan before the app starts serving.
    """
    # Import all models so their metadata is registered on Base
    import app.models.user     # noqa: F401
    import app.models.video    # noqa: F401
    import app.models.payment  # noqa: F401

    engine = get_engine()
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables verified / created.")


def health_check() -> bool:
    """
    FIX 7 — Quick connectivity check used by the /health endpoint.
    Returns True if the DB is reachable, False otherwise.
    """
    try:
        engine = get_engine()
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        return False
