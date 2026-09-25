from typing import Optional


class ConversionError(Exception):
    """Mirrors the Java @ServiceErrorAnnotation(message=...) pattern: a user-facing
    message plus the original cause, surfaced as a structured JSON error response
    by the global handler registered in app.main."""

    def __init__(self, message: str, cause: Optional[Exception] = None, status_code: int = 422):
        super().__init__(message)
        self.message = message
        self.cause = cause
        self.status_code = status_code
