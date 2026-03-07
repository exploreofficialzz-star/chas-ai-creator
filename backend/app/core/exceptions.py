"""Custom exceptions for the application."""

from typing import Optional


class APIException(Exception):
    """Base API exception."""
    
    def __init__(
        self,
        message: str,
        status_code: int = 500,
        error_code: Optional[str] = None,
    ):
        self.message = message
        self.status_code = status_code
        self.error_code = error_code or "INTERNAL_ERROR"
        super().__init__(self.message)


class NotFoundException(APIException):
    """Resource not found exception."""
    
    def __init__(self, message: str = "Resource not found"):
        super().__init__(message, status_code=404, error_code="NOT_FOUND")


class ValidationException(APIException):
    """Validation error exception."""
    
    def __init__(self, message: str = "Validation error"):
        super().__init__(message, status_code=400, error_code="VALIDATION_ERROR")


class AuthenticationException(APIException):
    """Authentication error exception."""
    
    def __init__(self, message: str = "Authentication failed"):
        super().__init__(message, status_code=401, error_code="AUTHENTICATION_ERROR")


class AuthorizationException(APIException):
    """Authorization error exception."""
    
    def __init__(self, message: str = "Not authorized"):
        super().__init__(message, status_code=403, error_code="AUTHORIZATION_ERROR")


class RateLimitException(APIException):
    """Rate limit exceeded exception."""
    
    def __init__(self, message: str = "Rate limit exceeded"):
        super().__init__(message, status_code=429, error_code="RATE_LIMIT_EXCEEDED")


class PaymentException(APIException):
    """Payment error exception."""
    
    def __init__(self, message: str = "Payment failed"):
        super().__init__(message, status_code=400, error_code="PAYMENT_ERROR")


class AIServiceException(APIException):
    """AI service error exception."""
    
    def __init__(self, message: str = "AI service error"):
        super().__init__(message, status_code=503, error_code="AI_SERVICE_ERROR")


class VideoGenerationException(APIException):
    """Video generation error exception."""
    
    def __init__(self, message: str = "Video generation failed"):
        super().__init__(message, status_code=500, error_code="VIDEO_GENERATION_ERROR")
