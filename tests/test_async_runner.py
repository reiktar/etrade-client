"""Tests for async_runner module."""

from etrade_client.cli.async_runner import _is_token_invalid_error
from etrade_client.exceptions import ETradeAPIError


class TestTokenInvalidDetection:
    """Tests for token invalid detection (expired or rejected)."""

    def test_detects_token_expired_message(self) -> None:
        """Should detect token_expired in error message."""
        error = ETradeAPIError(
            message="oauth_problem=token_expired",
            status_code=401,
        )
        assert _is_token_invalid_error(error) is True

    def test_detects_token_rejected_message(self) -> None:
        """Should detect token_rejected in error message."""
        error = ETradeAPIError(
            message="oauth_problem=token_rejected",
            status_code=401,
        )
        assert _is_token_invalid_error(error) is True

    def test_detects_token_expired_case_insensitive(self) -> None:
        """Should detect TOKEN_EXPIRED regardless of case."""
        error = ETradeAPIError(
            message="oauth_problem=TOKEN_EXPIRED",
            status_code=401,
        )
        assert _is_token_invalid_error(error) is True

    def test_detects_token_rejected_case_insensitive(self) -> None:
        """Should detect TOKEN_REJECTED regardless of case."""
        error = ETradeAPIError(
            message="oauth_problem=TOKEN_REJECTED",
            status_code=401,
        )
        assert _is_token_invalid_error(error) is True

    def test_ignores_other_oauth_problems(self) -> None:
        """Should not match other OAuth errors."""
        error = ETradeAPIError(
            message="oauth_problem=signature_invalid",
            status_code=401,
        )
        assert _is_token_invalid_error(error) is False

    def test_ignores_non_oauth_errors(self) -> None:
        """Should not match general errors."""
        error = ETradeAPIError(
            message="Account not found",
            status_code=404,
        )
        assert _is_token_invalid_error(error) is False
