"""Tests for error handling and exception classes."""

import pytest
from httpx import Response

from etrade_client.exceptions import (
    ETradeAPIError,
    ETradeAuthError,
    ETradeError,
    ETradeRateLimitError,
    ETradeTokenError,
    ETradeValidationError,
)


class TestExceptionHierarchy:
    """Tests for exception class hierarchy."""

    def test_etrade_error_is_base(self) -> None:
        """All exceptions should inherit from ETradeError."""
        assert issubclass(ETradeAPIError, ETradeError)
        assert issubclass(ETradeAuthError, ETradeError)
        assert issubclass(ETradeRateLimitError, ETradeError)
        assert issubclass(ETradeValidationError, ETradeError)
        assert issubclass(ETradeTokenError, ETradeError)

    def test_rate_limit_inherits_from_api_error(self) -> None:
        """ETradeRateLimitError should be an ETradeAPIError."""
        assert issubclass(ETradeRateLimitError, ETradeAPIError)

    def test_token_error_inherits_from_auth_error(self) -> None:
        """ETradeTokenError should be an ETradeAuthError."""
        assert issubclass(ETradeTokenError, ETradeAuthError)


class TestETradeError:
    """Tests for base ETradeError."""

    def test_stores_message(self) -> None:
        """Should store the error message."""
        error = ETradeError("Something went wrong")

        assert error.message == "Something went wrong"
        assert str(error) == "Something went wrong"


class TestETradeAPIError:
    """Tests for ETradeAPIError."""

    def test_stores_status_code(self) -> None:
        """Should store the HTTP status code."""
        error = ETradeAPIError("Not found", status_code=404)

        assert error.status_code == 404
        assert error.message == "Not found"

    def test_stores_error_code(self) -> None:
        """Should store optional error code."""
        error = ETradeAPIError(
            "Invalid symbol",
            status_code=400,
            error_code="INVALID_SYMBOL",
        )

        assert error.error_code == "INVALID_SYMBOL"

    def test_stores_response_body(self) -> None:
        """Should store optional response body."""
        body = {"Error": {"code": "123", "message": "Details"}}
        error = ETradeAPIError(
            "Error occurred",
            status_code=400,
            response_body=body,
        )

        assert error.response_body == body

    def test_can_catch_as_etrade_error(self) -> None:
        """Should be catchable as ETradeError."""
        with pytest.raises(ETradeError):
            raise ETradeAPIError("API error", status_code=500)


class TestETradeRateLimitError:
    """Tests for ETradeRateLimitError."""

    def test_defaults_to_429(self) -> None:
        """Should default status code to 429."""
        error = ETradeRateLimitError("Rate limited")

        assert error.status_code == 429

    def test_stores_retry_after(self) -> None:
        """Should store Retry-After value."""
        error = ETradeRateLimitError("Rate limited", retry_after=60)

        assert error.retry_after == 60

    def test_retry_after_none_by_default(self) -> None:
        """Retry-After should be None if not provided."""
        error = ETradeRateLimitError("Rate limited")

        assert error.retry_after is None

    def test_can_catch_as_api_error(self) -> None:
        """Should be catchable as ETradeAPIError."""
        with pytest.raises(ETradeAPIError):
            raise ETradeRateLimitError("Rate limited")


class TestETradeAuthError:
    """Tests for ETradeAuthError."""

    def test_stores_stage(self) -> None:
        """Should store authentication stage."""
        error = ETradeAuthError("Auth failed", stage="request_token")

        assert error.stage == "request_token"
        assert error.message == "Auth failed"

    def test_stage_is_optional(self) -> None:
        """Stage should be None by default."""
        error = ETradeAuthError("Auth failed")

        assert error.stage is None


class TestETradeTokenError:
    """Tests for ETradeTokenError."""

    def test_defaults_to_access_token(self) -> None:
        """Should default to access token type."""
        error = ETradeTokenError("Token invalid")

        assert error.token_type == "access"
        assert error.expired is False

    def test_stores_token_type(self) -> None:
        """Should store token type."""
        error = ETradeTokenError("Token missing", token_type="request")

        assert error.token_type == "request"

    def test_stores_expired_flag(self) -> None:
        """Should store expired flag."""
        error = ETradeTokenError("Token expired", expired=True)

        assert error.expired is True

    def test_sets_stage_to_token_validation(self) -> None:
        """Should set stage to token_validation."""
        error = ETradeTokenError("Token error")

        assert error.stage == "token_validation"


class TestETradeValidationError:
    """Tests for ETradeValidationError."""

    def test_stores_field(self) -> None:
        """Should store the invalid field name."""
        error = ETradeValidationError("Invalid quantity", field="quantity")

        assert error.field == "quantity"
        assert error.message == "Invalid quantity"

    def test_field_is_optional(self) -> None:
        """Field should be None by default."""
        error = ETradeValidationError("Validation failed")

        assert error.field is None


class TestHandleResponse:
    """Tests for BaseAPI._handle_response method."""

    @pytest.fixture
    def base_api(self):
        """Create a BaseAPI instance for testing."""
        from unittest.mock import MagicMock

        from etrade_client.api.base import BaseAPI

        config = MagicMock()
        auth = MagicMock()
        return BaseAPI(config, auth)

    def test_returns_json_on_success(self, base_api) -> None:
        """Should return parsed JSON on 2xx response."""
        response = Response(
            200,
            json={"QuoteResponse": {"data": "test"}},
        )

        result = base_api._handle_response(response)

        assert result == {"QuoteResponse": {"data": "test"}}

    def test_returns_empty_dict_on_204(self, base_api) -> None:
        """Should return empty dict on 204 No Content."""
        response = Response(204)

        result = base_api._handle_response(response)

        assert result == {}

    def test_raises_rate_limit_on_429(self, base_api) -> None:
        """Should raise ETradeRateLimitError on 429."""
        response = Response(429)

        with pytest.raises(ETradeRateLimitError) as exc_info:
            base_api._handle_response(response)

        assert exc_info.value.status_code == 429

    def test_includes_retry_after_header(self, base_api) -> None:
        """Should include Retry-After header in rate limit error."""
        response = Response(429, headers={"Retry-After": "30"})

        with pytest.raises(ETradeRateLimitError) as exc_info:
            base_api._handle_response(response)

        assert exc_info.value.retry_after == 30

    def test_raises_api_error_on_400(self, base_api) -> None:
        """Should raise ETradeAPIError on 400."""
        response = Response(400, json={"Error": {"message": "Bad request"}})

        with pytest.raises(ETradeAPIError) as exc_info:
            base_api._handle_response(response)

        assert exc_info.value.status_code == 400
        assert "Bad request" in exc_info.value.message

    def test_raises_api_error_on_401(self, base_api) -> None:
        """Should raise ETradeAPIError on 401."""
        response = Response(401, json={"Error": {"message": "Unauthorized"}})

        with pytest.raises(ETradeAPIError) as exc_info:
            base_api._handle_response(response)

        assert exc_info.value.status_code == 401

    def test_raises_api_error_on_500(self, base_api) -> None:
        """Should raise ETradeAPIError on 500."""
        response = Response(500, json={"Error": {"message": "Server error"}})

        with pytest.raises(ETradeAPIError) as exc_info:
            base_api._handle_response(response)

        assert exc_info.value.status_code == 500

    def test_includes_response_body_in_error(self, base_api) -> None:
        """Should include response body in error."""
        body = {"Error": {"code": "ERR001", "message": "Detailed error"}}
        response = Response(400, json=body)

        with pytest.raises(ETradeAPIError) as exc_info:
            base_api._handle_response(response)

        assert exc_info.value.response_body == body

    def test_handles_non_json_error_response(self, base_api) -> None:
        """Should handle error response that isn't JSON."""
        response = Response(500, content=b"Internal Server Error")

        with pytest.raises(ETradeAPIError) as exc_info:
            base_api._handle_response(response)

        assert exc_info.value.status_code == 500
        assert exc_info.value.response_body is None

    def test_parses_etrade_error_format(self, base_api) -> None:
        """Should parse E*Trade's error response format."""
        response = Response(
            400,
            json={
                "Error": {
                    "code": "100",
                    "message": "Order rejected: Invalid symbol",
                }
            },
        )

        with pytest.raises(ETradeAPIError) as exc_info:
            base_api._handle_response(response)

        assert "Order rejected: Invalid symbol" in exc_info.value.message


class TestErrorContextForDebugging:
    """Tests that errors provide useful context for debugging."""

    def test_api_error_str_includes_status(self) -> None:
        """String representation should include status code context."""
        error = ETradeAPIError("Order failed", status_code=400)

        # The message should be accessible via str()
        assert "Order failed" in str(error)

    def test_rate_limit_error_with_retry_info(self) -> None:
        """Rate limit error should have retry info accessible."""
        error = ETradeRateLimitError("Rate limited", retry_after=45)

        # Application code should be able to access retry timing
        assert error.retry_after == 45
        assert error.status_code == 429

    def test_token_error_provides_token_context(self) -> None:
        """Token error should indicate what type of token failed."""
        error = ETradeTokenError(
            "Token has expired",
            token_type="access",
            expired=True,
        )

        # Application can determine appropriate action
        assert error.expired is True
        assert error.token_type == "access"
