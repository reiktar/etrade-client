"""Tests for connection pooling functionality."""

from unittest.mock import AsyncMock, patch

import httpx
import pytest

from etrade_client import ETradeClient, ETradeConfig


@pytest.fixture
def config() -> ETradeConfig:
    """Create a test configuration."""
    return ETradeConfig(
        consumer_key="test_key",
        consumer_secret="test_secret",
        sandbox=True,
    )


class TestContextManager:
    """Tests for async context manager usage."""

    async def test_context_manager_creates_http_client(self, config: ETradeConfig) -> None:
        """Context manager should create an http client on entry."""
        async with ETradeClient(config) as client:
            assert client._http_client is not None
            assert isinstance(client._http_client, httpx.AsyncClient)

    async def test_context_manager_closes_http_client(self, config: ETradeConfig) -> None:
        """Context manager should close http client on exit."""
        async with ETradeClient(config) as client:
            http_client = client._http_client
            assert http_client is not None

        # After exiting, client should be None
        assert client._http_client is None

    async def test_context_manager_propagates_to_api_modules(self, config: ETradeConfig) -> None:
        """Context manager should set http client on all API modules."""
        async with ETradeClient(config) as client:
            http_client = client._http_client
            assert client.accounts._http_client is http_client
            assert client.alerts._http_client is http_client
            assert client.market._http_client is http_client
            assert client.orders._http_client is http_client


class TestExternalHttpClient:
    """Tests for external http client usage."""

    async def test_external_client_is_used(self, config: ETradeConfig) -> None:
        """External http client should be used by API modules."""
        external_client = httpx.AsyncClient(timeout=60.0)
        try:
            client = ETradeClient(config, http_client=external_client)

            assert client._http_client is external_client
            assert client.accounts._http_client is external_client
            assert client.alerts._http_client is external_client
            assert client.market._http_client is external_client
            assert client.orders._http_client is external_client
        finally:
            await external_client.aclose()

    async def test_external_client_not_closed_by_context_manager(
        self, config: ETradeConfig
    ) -> None:
        """External http client should NOT be closed when exiting context manager."""
        external_client = httpx.AsyncClient(timeout=60.0)
        try:
            async with ETradeClient(config, http_client=external_client) as client:
                assert client._http_client is external_client

            # External client should still be open (not closed by context manager)
            # We verify by checking it's not None on the ETradeClient
            # and that we can still use the external client
            assert not external_client.is_closed
        finally:
            await external_client.aclose()

    async def test_external_client_not_closed_by_close_method(self, config: ETradeConfig) -> None:
        """External http client should NOT be closed by explicit close() call."""
        external_client = httpx.AsyncClient(timeout=60.0)
        try:
            client = ETradeClient(config, http_client=external_client)
            await client.close()

            # External client should still be open
            assert not external_client.is_closed
        finally:
            await external_client.aclose()


class TestExplicitLifecycle:
    """Tests for explicit open/close lifecycle."""

    async def test_open_creates_http_client(self, config: ETradeConfig) -> None:
        """open() should create an http client."""
        client = ETradeClient(config)
        assert client._http_client is None

        await client.open()
        assert client._http_client is not None
        assert isinstance(client._http_client, httpx.AsyncClient)

        await client.close()

    async def test_close_closes_http_client(self, config: ETradeConfig) -> None:
        """close() should close the http client."""
        client = ETradeClient(config)
        await client.open()

        http_client = client._http_client
        assert http_client is not None

        await client.close()
        assert client._http_client is None

    async def test_open_propagates_to_api_modules(self, config: ETradeConfig) -> None:
        """open() should set http client on all API modules."""
        client = ETradeClient(config)
        await client.open()

        try:
            http_client = client._http_client
            assert client.accounts._http_client is http_client
            assert client.alerts._http_client is http_client
            assert client.market._http_client is http_client
            assert client.orders._http_client is http_client
        finally:
            await client.close()

    async def test_close_clears_api_modules(self, config: ETradeConfig) -> None:
        """close() should clear http client on all API modules."""
        client = ETradeClient(config)
        await client.open()
        await client.close()

        assert client.accounts._http_client is None
        assert client.alerts._http_client is None
        assert client.market._http_client is None
        assert client.orders._http_client is None

    async def test_multiple_open_calls_are_idempotent(self, config: ETradeConfig) -> None:
        """Multiple open() calls should not create multiple clients."""
        client = ETradeClient(config)
        await client.open()
        first_http_client = client._http_client

        await client.open()
        assert client._http_client is first_http_client

        await client.close()


class TestFallbackBehavior:
    """Tests for fallback to per-request connections."""

    async def test_no_pooling_without_open(self, config: ETradeConfig) -> None:
        """Without open() or context manager, http_client should be None."""
        client = ETradeClient(config)
        assert client._http_client is None
        assert client.accounts._http_client is None

    async def test_api_modules_work_without_pooling(self, config: ETradeConfig) -> None:
        """API modules should work without pooling (per-request connections)."""
        client = ETradeClient(config)

        # Mock the _request method to verify it works
        with patch.object(client.accounts, "_request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = {"AccountListResponse": {"Accounts": {"Account": []}}}

            # This should work even without open() - uses per-request connection
            await client.accounts.list_accounts()
            mock_request.assert_called_once()


class TestOwnershipTracking:
    """Tests for http client ownership tracking."""

    async def test_owns_client_when_no_external(self, config: ETradeConfig) -> None:
        """Client should own http client when none provided externally."""
        client = ETradeClient(config)
        assert client._owns_http_client is True

    async def test_does_not_own_external_client(self, config: ETradeConfig) -> None:
        """Client should not own externally provided http client."""
        external_client = httpx.AsyncClient()
        try:
            client = ETradeClient(config, http_client=external_client)
            assert client._owns_http_client is False
        finally:
            await external_client.aclose()
