"""Integration tests for the Alerts API."""

import pytest


pytestmark = pytest.mark.integration


class TestAlertsAPI:
    """Integration tests for AlertsAPI."""

    async def test_list_alerts(self, async_integration_client, analyze_response) -> None:
        """Should list alerts from the sandbox."""
        client = async_integration_client

        alerts_response = await client.alerts.list_alerts()

        # Analyze individual Alert models
        for alert in alerts_response.alerts:
            analyze_response(alert, "alerts/list/Alert")

        # Should have the response structure even if empty
        assert alerts_response is not None
        assert hasattr(alerts_response, "alerts")

    async def test_list_alerts_with_category_filter(self, async_integration_client, analyze_response) -> None:
        """Should filter alerts by category."""
        client = async_integration_client

        # Test stock alerts
        stock_alerts = await client.alerts.list_alerts(category="STOCK")
        assert stock_alerts is not None

        for alert in stock_alerts.alerts:
            analyze_response(alert, "alerts/list/STOCK/Alert")

        # Test account alerts
        account_alerts = await client.alerts.list_alerts(category="ACCOUNT")
        assert account_alerts is not None

        for alert in account_alerts.alerts:
            analyze_response(alert, "alerts/list/ACCOUNT/Alert")

    async def test_list_alerts_with_status_filter(self, async_integration_client, analyze_response) -> None:
        """Should filter alerts by status."""
        client = async_integration_client

        for status in ["READ", "UNREAD"]:
            alerts_response = await client.alerts.list_alerts(status=status)
            assert alerts_response is not None

            for alert in alerts_response.alerts:
                analyze_response(alert, f"alerts/list/{status}/Alert")

    async def test_get_alert_details(self, async_integration_client, analyze_response) -> None:
        """Should get alert details if alerts exist."""
        client = async_integration_client

        alerts_response = await client.alerts.list_alerts()

        if alerts_response.alerts:
            # Get details of first alert
            alert = alerts_response.alerts[0]
            detail_response = await client.alerts.get_alert_details(alert.alert_id)

            analyze_response(detail_response.alert, "alerts/details/Alert")

            assert detail_response is not None
            assert detail_response.alert is not None
