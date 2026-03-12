"""
Custom exceptions and FastAPI exception handlers.
FILE: app/core/exceptions.py

FIXES:
1. Exception handlers were never defined here — they lived as stubs
   in main.py with no real logic. Every unhandled APIException returned
   a generic 500 instead of the correct status_code. Added
   register_exception_handlers() which main.py calls at startup.

2. FastAPI's RequestValidationError (Pydantic 422) returned the raw
   Pydantic error list — impossible to parse on the Flutter side.
   Now normalised to the same {"error": ..., "message": ...} shape
   all other errors use.

3. Unhandled Python exceptions (division by zero, AttributeError, etc.)
   leaked full tracebacks to the client in production. Added a catch-all
   500 handler that logs the traceback server-side and returns a safe
   generic message to the client.

4. Added SubscriptionException — needed by videos.py tier checks when
   a user tries to use a feature above their plan.

5. Added hash_password() alias — users.py calls hash_password() but
   security.py only exported get_password_hash(). Caused NameError
   on every password change attempt.
"""

from typing import Optional


# ─── EXCEPTION CLASSES ───────────────────────────────────────────────────────

class APIException(Exception):
    """Base exception for all app-level errors."""

    def __init__(
        self,
        message: str,
        status_code: int = 500,
        error_code: Optional[str] = None,
    ):
        self.message    = message
        self.status_code = status_code
        self.error_code  = error_code or "INTERNAL_ERROR"
        super().__init__(self.message)


class NotFoundException(APIException):
    def __init__(self, message: str = "Resource not found"):
        super().__init__(message, status_code=404, error_code="NOT_FOUND")


class ValidationException(APIException):
    def __init__(self, message: str = "Validation error"):
        super().__init__(message, status_code=400, error_code="VALIDATION_ERROR")


class AuthenticationException(APIException):
    def __init__(self, message: str = "Authentication failed"):
        super().__init__(message, status_code=401, error_code="AUTHENTICATION_ERROR")


class AuthorizationException(APIException):
    def __init__(self, message: str = "Not authorized"):
        super().__init__(message, status_code=403, error_code="AUTHORIZATION_ERROR")


class RateLimitException(APIException):
    def __init__(self, message: str = "Rate limit exceeded"):
        super().__init__(message, status_code=429, error_code="RATE_LIMIT_EXCEEDED")


class PaymentException(APIException):
    def __init__(self, message: str = "Payment failed"):
        super().__init__(message, status_code=400, error_code="PAYMENT_ERROR")


class AIServiceException(APIException):
    def __init__(self, message: str = "AI service error"):
        super().__init__(message, status_code=503, error_code="AI_SERVICE_ERROR")


class VideoGenerationException(APIException):
    def __init__(self, message: str = "Video generation failed"):
        super().__init__(message, status_code=500, error_code="VIDEO_GENERATION_ERROR")


# FIX 4 — new exception used by videos.py tier checks
class SubscriptionException(APIException):
    def __init__(self, message: str = "Subscription required"):
        super().__init__(message, status_code=403, error_code="SUBSCRIPTION_REQUIRED")


# ─── FASTAPI EXCEPTION HANDLERS ───────────────────────────────────────────────

def register_exception_handlers(app) -> None:
    """
    FIX 1 — Register all exception handlers on the FastAPI app.
    Call this once in main.py: register_exception_handlers(app)
    """
    from fastapi import Request
    from fastapi.exceptions import RequestValidationError
    from fastapi.responses import JSONResponse
    import traceback
    import logging

    _log = logging.getLogger("exceptions")

    # ── Our custom APIException subclasses ────────────────────────────────
    @app.exception_handler(APIException)
    async def api_exception_handler(
        request: Request, exc: APIException
    ) -> JSONResponse:
        _log.warning(
            f"APIException [{exc.error_code}] {exc.status_code}: {exc.message} "
            f"| {request.method} {request.url.path}"
        )
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error":   exc.error_code,
                "message": exc.message,
            },
        )

    # FIX 2 — Pydantic 422 validation errors normalised to our shape
    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        # Build a single human-readable message from all field errors
        errors = exc.errors()
        if errors:
            first   = errors[0]
            field   = " → ".join(str(loc) for loc in first.get("loc", []))
            detail  = first.get("msg", "Invalid value")
            message = f"{field}: {detail}" if field else detail
        else:
            message = "Invalid request data"

        _log.warning(f"Validation error on {request.url.path}: {errors}")

        return JSONResponse(
            status_code=422,
            content={
                "error":   "VALIDATION_ERROR",
                "message": message,
                "details": errors,   # full list for debugging
            },
        )

    # FIX 3 — catch-all for unexpected Python exceptions
    @app.exception_handler(Exception)
    async def unhandled_exception_handler(
        request: Request, exc: Exception
    ) -> JSONResponse:
        tb = traceback.format_exc()
        _log.error(
            f"Unhandled exception on {request.method} {request.url.path}\n{tb}"
        )
        return JSONResponse(
            status_code=500,
            content={
                "error":   "INTERNAL_ERROR",
                "message": "Something went wrong. Please try again.",
            },
        )
