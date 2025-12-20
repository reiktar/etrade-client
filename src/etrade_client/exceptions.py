"""Typed exceptions for E*Trade API client."""

from typing import Any


class ETradeError(Exception):
    """Base exception for all E*Trade client errors."""

    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)


class ETradeAuthError(ETradeError):
    """Authentication or authorization error."""

    def __init__(self, message: str, *, stage: str | None = None) -> None:
        self.stage = stage  # e.g., "request_token", "access_token", "renewal"
        super().__init__(message)


class ETradeAPIError(ETradeError):
    """API request error with status code and response details."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int,
        error_code: str | None = None,
        response_body: dict[str, Any] | None = None,
    ) -> None:
        self.status_code = status_code
        self.error_code = error_code
        self.response_body = response_body
        super().__init__(message)


class ETradeRateLimitError(ETradeAPIError):
    """Rate limit exceeded - includes retry information."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int = 429,
        retry_after: int | None = None,
    ) -> None:
        self.retry_after = retry_after  # seconds until retry is allowed
        super().__init__(message, status_code=status_code)


class ETradeValidationError(ETradeError):
    """Request validation error before sending to API."""

    def __init__(self, message: str, *, field: str | None = None) -> None:
        self.field = field
        super().__init__(message)


class ETradeTokenError(ETradeAuthError):
    """Token-specific errors (missing, expired, invalid)."""

    def __init__(
        self,
        message: str,
        *,
        token_type: str = "access",  # "request" | "access"
        expired: bool = False,
    ) -> None:
        self.token_type = token_type
        self.expired = expired
        super().__init__(message, stage="token_validation")
