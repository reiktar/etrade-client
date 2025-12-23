"""Tests for rate limit auto-retry functionality."""

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from etrade_client import ETradeClient, ETradeConfig
from etrade_client.exceptions import ETradeAPIError, ETradeRateLimitError


@pytest.fixture
def config() -> ETradeConfig:
    """Create a test configuration."""
    return ETradeConfig(
        consumer_key="test_key",
        consumer_secret="test_secret",
        sandbox=True,
    )


def make_response(
    status_code: int, json_data: dict | None = None, headers: dict | None = None
) -> httpx.Response:
    """Create a mock httpx.Response."""
    response = MagicMock(spec=httpx.Response)
    response.status_code = status_code
    response.headers = headers or {}
    response.json.return_value = json_data or {}
    return response


class TestRateLimitRetry:
    """Tests for automatic retry on rate limit errors."""

    async def test_retries_on_rate_limit_and_succeeds(self, config: ETradeConfig) -> None:
        """Should retry when rate limit (429) is returned and succeed after."""
        call_count = 0

        def mock_request(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                return make_response(429, headers={"Retry-After": "1"})
            return make_response(200, {"AccountListResponse": {"Accounts": {"Account": []}}})

        async with ETradeClient(config) as client:
            with patch.object(client.accounts.auth, "sign_request", return_value={}):
                with patch.object(client._http_client, "request", side_effect=mock_request):
                    with patch("tenacity.nap.sleep", new_callable=AsyncMock):
                        result = await client.accounts.list_accounts()

        # Should have retried 3 times (2 failures + 1 success)
        assert call_count == 3
        assert result.accounts == []

    async def test_retries_with_retry_after_header(self, config: ETradeConfig) -> None:
        """Should successfully retry when Retry-After header is provided."""
        call_count = 0

        def mock_request(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return make_response(429, headers={"Retry-After": "7"})
            return make_response(200, {"AccountListResponse": {"Accounts": {"Account": []}}})

        async with ETradeClient(config) as client:
            with patch.object(client.accounts.auth, "sign_request", return_value={}):
                with patch.object(client._http_client, "request", side_effect=mock_request):
                    with patch("tenacity.nap.sleep", new_callable=AsyncMock):
                        result = await client.accounts.list_accounts()

        # Should have retried once and succeeded
        assert call_count == 2
        assert result.accounts == []

    async def test_retries_without_retry_after_header(self, config: ETradeConfig) -> None:
        """Should retry using exponential backoff when no Retry-After header."""
        call_count = 0

        def mock_request(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                return make_response(429)  # No Retry-After header
            return make_response(200, {"AccountListResponse": {"Accounts": {"Account": []}}})

        async with ETradeClient(config) as client:
            with patch.object(client.accounts.auth, "sign_request", return_value={}):
                with patch.object(client._http_client, "request", side_effect=mock_request):
                    with patch("tenacity.nap.sleep", new_callable=AsyncMock):
                        result = await client.accounts.list_accounts()

        # Should have retried and succeeded
        assert call_count == 3
        assert result.accounts == []

    async def test_raises_after_max_retries(self, config: ETradeConfig) -> None:
        """Should raise ETradeRateLimitError after max retries exhausted."""
        call_count = 0

        def always_rate_limit(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            return make_response(429)

        async with ETradeClient(config) as client:
            with patch.object(client.accounts.auth, "sign_request", return_value={}):
                with patch.object(client._http_client, "request", side_effect=always_rate_limit):
                    with patch("tenacity.nap.sleep", new_callable=AsyncMock):
                        with pytest.raises(ETradeRateLimitError):
                            await client.accounts.list_accounts()

        # Should have attempted 5 times (max retries)
        assert call_count == 5

    async def test_does_not_retry_other_errors(self, config: ETradeConfig) -> None:
        """Should not retry on non-rate-limit errors."""
        call_count = 0

        def mock_request(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            return make_response(500, {"Error": {"message": "Server error"}})

        async with ETradeClient(config) as client:
            with patch.object(client.accounts.auth, "sign_request", return_value={}):
                with patch.object(client._http_client, "request", side_effect=mock_request):
                    with pytest.raises(ETradeAPIError) as exc_info:
                        await client.accounts.list_accounts()

        # Should only be called once (no retry for 500 errors)
        assert call_count == 1
        assert exc_info.value.status_code == 500

    async def test_does_not_retry_auth_errors(self, config: ETradeConfig) -> None:
        """Should not retry on 401 authentication errors."""
        call_count = 0

        def mock_request(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            return make_response(401, {"Error": {"message": "Unauthorized"}})

        async with ETradeClient(config) as client:
            with patch.object(client.accounts.auth, "sign_request", return_value={}):
                with patch.object(client._http_client, "request", side_effect=mock_request):
                    with pytest.raises(ETradeAPIError) as exc_info:
                        await client.accounts.list_accounts()

        # Should only be called once (no retry for 401 errors)
        assert call_count == 1
        assert exc_info.value.status_code == 401
