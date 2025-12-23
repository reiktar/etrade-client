"""Tests for alert model parsing."""

from datetime import datetime

from etrade_client.models.alerts import (
    Alert,
    AlertDetailResponse,
    AlertListResponse,
    DeleteAlertsResponse,
)


class TestAlertListResponse:
    """Tests for AlertListResponse.from_api_response."""

    def test_parses_multiple_alerts(self) -> None:
        """Should parse response with multiple alerts."""
        data = {
            "AlertsResponse": {
                "Alert": [
                    {
                        "id": 1001,
                        "createTime": "2025-01-15T10:30:00",
                        "subject": "Price Alert: AAPL",
                        "status": "UNREAD",
                    },
                    {
                        "id": 1002,
                        "createTime": "2025-01-16T14:00:00",
                        "subject": "Order Filled: MSFT",
                        "status": "READ",
                    },
                ],
                "totalAlerts": 2,
            }
        }

        result = AlertListResponse.from_api_response(data)

        assert len(result.alerts) == 2
        assert result.alerts[0].alert_id == 1001
        assert result.alerts[0].subject == "Price Alert: AAPL"
        assert result.alerts[0].status == "UNREAD"
        assert result.alerts[1].alert_id == 1002
        assert result.alerts[1].status == "READ"
        assert result.total_alerts == 2

    def test_parses_single_alert_as_dict(self) -> None:
        """Should handle E*Trade's single-item-as-dict quirk."""
        data = {
            "AlertsResponse": {
                "Alert": {
                    "id": 1001,
                    "createTime": "2025-01-15T10:30:00",
                    "subject": "Price Alert: AAPL",
                    "status": "UNREAD",
                },
                "totalAlerts": 1,
            }
        }

        result = AlertListResponse.from_api_response(data)

        assert len(result.alerts) == 1
        assert result.alerts[0].alert_id == 1001

    def test_parses_empty_alerts(self) -> None:
        """Should handle empty alerts list."""
        data = {"AlertsResponse": {"Alert": [], "totalAlerts": 0}}

        result = AlertListResponse.from_api_response(data)

        assert len(result.alerts) == 0
        assert result.total_alerts == 0

    def test_total_alerts_defaults_to_list_length(self) -> None:
        """Should default totalAlerts to list length if not provided."""
        data = {
            "AlertsResponse": {
                "Alert": [
                    {
                        "id": 1001,
                        "createTime": "2025-01-15T10:30:00",
                        "subject": "Alert 1",
                        "status": "UNREAD",
                    },
                    {
                        "id": 1002,
                        "createTime": "2025-01-16T14:00:00",
                        "subject": "Alert 2",
                        "status": "READ",
                    },
                ],
            }
        }

        result = AlertListResponse.from_api_response(data)

        assert result.total_alerts == 2

    def test_handles_missing_alerts_key(self) -> None:
        """Should handle missing Alert key gracefully."""
        data = {"AlertsResponse": {}}

        result = AlertListResponse.from_api_response(data)

        assert len(result.alerts) == 0
        assert result.total_alerts == 0


class TestAlertDetailResponse:
    """Tests for AlertDetailResponse.from_api_response."""

    def test_parses_full_alert_detail(self) -> None:
        """Should parse alert with all fields."""
        data = {
            "AlertDetailsResponse": {
                "id": 1001,
                "createTime": "2025-01-15T10:30:00",
                "subject": "Price Alert: AAPL",
                "msgText": "AAPL has reached your target price of $150.00",
                "readTime": "2025-01-15T11:00:00",
                "symbol": "AAPL",
            }
        }

        result = AlertDetailResponse.from_api_response(data)

        assert result.alert.alert_id == 1001
        assert result.alert.subject == "Price Alert: AAPL"
        assert result.alert.msg_text == "AAPL has reached your target price of $150.00"
        assert result.alert.symbol == "AAPL"
        assert result.alert.read_time is not None

    def test_parses_minimal_alert_detail(self) -> None:
        """Should parse alert with only required fields."""
        data = {
            "AlertDetailsResponse": {
                "id": 1001,
                "createTime": "2025-01-15T10:30:00",
                "subject": "Account Alert",
                "msgText": "Your account balance is low",
            }
        }

        result = AlertDetailResponse.from_api_response(data)

        assert result.alert.alert_id == 1001
        assert result.alert.msg_text == "Your account balance is low"
        assert result.alert.read_time is None
        assert result.alert.delete_time is None
        assert result.alert.symbol is None


class TestDeleteAlertsResponse:
    """Tests for DeleteAlertsResponse.from_api_response."""

    def test_parses_success_result(self) -> None:
        """Should parse successful delete response."""
        data = {"AlertsResponse": {"result": "SUCCESS"}}

        result = DeleteAlertsResponse.from_api_response(data)

        assert result.result == "SUCCESS"

    def test_parses_error_result(self) -> None:
        """Should parse error delete response."""
        data = {"AlertsResponse": {"result": "ALERT_NOT_FOUND"}}

        result = DeleteAlertsResponse.from_api_response(data)

        assert result.result == "ALERT_NOT_FOUND"

    def test_handles_missing_result(self) -> None:
        """Should default to UNKNOWN when result missing."""
        data = {"AlertsResponse": {}}

        result = DeleteAlertsResponse.from_api_response(data)

        assert result.result == "UNKNOWN"


class TestAlert:
    """Tests for Alert model."""

    def test_parses_with_alias(self) -> None:
        """Should parse using alias fields."""
        data = {
            "id": 1001,
            "createTime": "2025-01-15T10:30:00",
            "subject": "Test Alert",
            "status": "UNREAD",
        }

        alert = Alert.model_validate(data)

        assert alert.alert_id == 1001
        assert alert.create_time == datetime(2025, 1, 15, 10, 30, 0)
        assert alert.subject == "Test Alert"
        assert alert.status == "UNREAD"
