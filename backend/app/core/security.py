"""
Security utilities.
FILE: app/core/security.py

FIXES:
1. CRITICAL — users.py calls hash_password() but this file only exported
   get_password_hash(). Every password change raised NameError.
   Fixed: hash_password() added as the canonical name; get_password_hash()
   kept as an alias for backwards compatibility.

2. verify_token() compared datetime.utcnow() > datetime.fromtimestamp(exp)
   — datetime.fromtimestamp() uses LOCAL time, but JWTs use UTC epoch.
   In Nigeria (WAT = UTC+1) every token appeared expired 1 hour before
   it actually was. Fixed: datetime.utcfromtimestamp(exp).

3. verify_token() re-implemented expiry checking manually AFTER calling
   decode_token() which already calls jwt.decode() — python-jose's
   jwt.decode() validates expiry automatically and raises JWTError if
   expired. The manual check was redundant and had the timezone bug above.
   Kept it as a safety net but fixed the timezone comparison.

4. decode_token() caught ALL JWTError exceptions with the same generic
   "Invalid token" message — callers (Flutter app) couldn't distinguish
   "token expired" from "token tampered". Added specific error codes.

5. create_refresh_token() didn't accept expires_delta — if a future
   "remember me" feature needs longer refresh tokens, the signature
   was inflexible. Added optional expires_delta param.

6. Missing generate_reset_token() and verify_reset_token() — referenced
   in auth.py for password reset flow (forgot password screen).

7. Missing generate_email_verification_token() — referenced in auth.py
   for email verification after registration.
"""

import secrets
import hashlib
from datetime import datetime, timedelta
from typing import Optional

from jose import ExpiredSignatureError, JWTError, jwt
from passlib.context import CryptContext

from app.core.exceptions import AuthenticationException

# Lazy import of settings to avoid circular import at module level
def _settings():
    from app.config import settings
    return settings

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


# ─── PASSWORDS ────────────────────────────────────────────────────────────────

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain password against its bcrypt hash."""
    plain_password = plain_password[:72]   # bcrypt 72-byte limit
    return pwd_context.verify(plain_password, hashed_password)


def hash_password(password: str) -> str:
    """
    Hash a password with bcrypt.
    FIX 1 — canonical name (users.py calls hash_password, not get_password_hash).
    """
    password = password[:72]
    return pwd_context.hash(password)


def get_password_hash(password: str) -> str:
    """Alias for hash_password() — kept for backwards compatibility."""
    return hash_password(password)


# ─── JWT TOKENS ───────────────────────────────────────────────────────────────

def create_access_token(
    data: dict,
    expires_delta: Optional[timedelta] = None,
) -> str:
    """Create a short-lived JWT access token."""
    cfg = _settings()
    to_encode = data.copy()
    expire = datetime.utcnow() + (
        expires_delta
        if expires_delta
        else timedelta(minutes=cfg.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode.update({"exp": expire, "type": "access"})
    return jwt.encode(to_encode, cfg.SECRET_KEY, algorithm="HS256")


def create_refresh_token(
    data: dict,
    expires_delta: Optional[timedelta] = None,   # FIX 5
) -> str:
    """Create a long-lived JWT refresh token."""
    cfg = _settings()
    to_encode = data.copy()
    expire = datetime.utcnow() + (
        expires_delta
        if expires_delta
        else timedelta(minutes=cfg.REFRESH_TOKEN_EXPIRE_MINUTES)
    )
    to_encode.update({"exp": expire, "type": "refresh"})
    return jwt.encode(to_encode, cfg.SECRET_KEY, algorithm="HS256")


def decode_token(token: str) -> dict:
    """
    Decode and validate a JWT token.
    FIX 4 — raises specific error messages for expired vs invalid tokens.
    """
    cfg = _settings()
    try:
        payload = jwt.decode(token, cfg.SECRET_KEY, algorithms=["HS256"])
        return payload
    except ExpiredSignatureError:
        raise AuthenticationException("Your session has expired. Please log in again.")
    except JWTError:
        raise AuthenticationException("Invalid token. Please log in again.")


def verify_token(token: str, token_type: str = "access") -> dict:
    """
    Verify a JWT token's type and expiry.
    Returns the payload dict if valid.
    """
    payload = decode_token(token)   # raises if expired or invalid

    if payload.get("type") != token_type:
        raise AuthenticationException(
            f"Invalid token type — expected '{token_type}'. Please log in again."
        )

    # FIX 2 / FIX 3 — safety net with correct UTC comparison
    exp = payload.get("exp")
    if exp:
        expiry_dt = datetime.utcfromtimestamp(exp)   # FIX 2
        if datetime.utcnow() > expiry_dt:
            raise AuthenticationException(
                "Your session has expired. Please log in again."
            )

    return payload


# ─── RESET / VERIFICATION TOKENS ─────────────────────────────────────────────

def generate_reset_token(user_id: str, email: str) -> str:
    """
    FIX 6 — Generate a short-lived password-reset token (15 min).
    Stored as a signed JWT so it can be verified without a DB lookup.
    """
    cfg = _settings()
    payload = {
        "sub":   user_id,
        "email": email,
        "type":  "password_reset",
        "exp":   datetime.utcnow() + timedelta(minutes=15),
    }
    return jwt.encode(payload, cfg.SECRET_KEY, algorithm="HS256")


def verify_reset_token(token: str) -> dict:
    """
    FIX 6 — Verify a password-reset token.
    Returns {"sub": user_id, "email": email} if valid.
    """
    try:
        cfg     = _settings()
        payload = jwt.decode(token, cfg.SECRET_KEY, algorithms=["HS256"])
        if payload.get("type") != "password_reset":
            raise AuthenticationException("Invalid reset token.")
        return payload
    except ExpiredSignatureError:
        raise AuthenticationException("Reset link has expired. Please request a new one.")
    except JWTError:
        raise AuthenticationException("Invalid reset token.")


def generate_email_verification_token(user_id: str, email: str) -> str:
    """
    FIX 7 — Generate an email verification token (24 hours).
    """
    cfg = _settings()
    payload = {
        "sub":   user_id,
        "email": email,
        "type":  "email_verification",
        "exp":   datetime.utcnow() + timedelta(hours=24),
    }
    return jwt.encode(payload, cfg.SECRET_KEY, algorithm="HS256")


def verify_email_verification_token(token: str) -> dict:
    """
    FIX 7 — Verify an email-verification token.
    Returns {"sub": user_id, "email": email} if valid.
    """
    try:
        cfg     = _settings()
        payload = jwt.decode(token, cfg.SECRET_KEY, algorithms=["HS256"])
        if payload.get("type") != "email_verification":
            raise AuthenticationException("Invalid verification token.")
        return payload
    except ExpiredSignatureError:
        raise AuthenticationException("Verification link has expired. Please request a new one.")
    except JWTError:
        raise AuthenticationException("Invalid verification token.")


def generate_secure_token(length: int = 32) -> str:
    """Generate a cryptographically secure random token (for CSRF, webhooks, etc.)."""
    return secrets.token_urlsafe(length)


def hash_token(token: str) -> str:
    """SHA-256 hash a token for safe storage (e.g. refresh token in DB)."""
    return hashlib.sha256(token.encode()).hexdigest()
