"""Basic connectivity tests for the E*Trade sandbox API."""

import pytest

pytestmark = pytest.mark.integration


class TestConnectivity:
    """Basic connectivity tests."""

    async def test_client_is_authenticated(self, async_integration_client) -> None:
        """Client should be authenticated."""
        client = async_integration_client
        assert client.is_authenticated

    async def test_sandbox_url_enforced(self, integration_config) -> None:
        """Configuration should use sandbox URL."""
        assert integration_config.sandbox is True
        assert "apisb.etrade.com" in integration_config.base_url

    async def test_token_renewal(self, async_integration_client) -> None:
        """Should be able to renew token."""
        client = async_integration_client

        # This extends the token expiry without changing the token
        await client.renew_token()

        # Should still be authenticated
        assert client.is_authenticated
