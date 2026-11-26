"""
Structured application domain exceptions for consistent JSON & HTML error responses.
"""


class AppError(Exception):
    """Base application error carrying an HTTP status code and machine-readable code."""

    def __init__(self, message: str, status_code: int = 400, code: str = "app_error") -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.code = code


class ValidationError(AppError):
    """Raised when user input or payload validation fails (HTTP 400)."""

    def __init__(self, message: str = "Invalid input.", code: str = "validation_error") -> None:
        super().__init__(message=message, status_code=400, code=code)


class UnauthorizedError(AppError):
    """Raised when authentication is required or invalid (HTTP 401)."""

    def __init__(self, message: str = "Authentication required.", code: str = "unauthorized") -> None:
        super().__init__(message=message, status_code=401, code=code)


class ForbiddenError(AppError):
    """Raised when an authenticated user lacks permission (HTTP 403)."""

    def __init__(self, message: str = "Access denied.", code: str = "forbidden") -> None:
        super().__init__(message=message, status_code=403, code=code)


class NotFoundError(AppError):
    """Raised when a requested resource does not exist (HTTP 404)."""

    def __init__(self, message: str = "Resource not found.", code: str = "not_found") -> None:
        super().__init__(message=message, status_code=404, code=code)


class RateLimitError(AppError):
    """Raised when a client exceeds rate limits (HTTP 429)."""

    def __init__(self, retry_after: int = 60, message: str = "") -> None:
        msg = message or f"Too many requests. Try again in {retry_after}s."
        super().__init__(message=msg, status_code=429, code="rate_limited")
        self.retry_after = retry_after
