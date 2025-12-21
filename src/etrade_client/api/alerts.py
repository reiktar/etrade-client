"""Alerts API endpoints."""

from collections.abc import AsyncIterator
from typing import Any

from etrade_client.api.base import BaseAPI
from etrade_client.models.alerts import (
    Alert,
    AlertDetailResponse,
    AlertListResponse,
    DeleteAlertsResponse,
)


class AlertsAPI(BaseAPI):
    """E*Trade Alerts API.

    Provides access to user alerts and notifications.
    """

    async def list_alerts(
        self,
        *,
        count: int | None = None,
        category: str | None = None,
        status: str | None = None,
        direction: str = "DESC",
        search: str | None = None,
    ) -> AlertListResponse:
        """List alerts for the authenticated user.

        Args:
            count: Number of alerts to return (max 300, default 25)
            category: Filter by category - "STOCK" or "ACCOUNT"
            status: Filter by status - "READ", "UNREAD", or "DELETED"
            direction: Sort direction by createDate - "ASC" or "DESC"
            search: Search string to filter by subject text

        Returns:
            AlertListResponse with list of alerts
        """
        params: dict[str, Any] = {"count": min(count, 300) if count else 300}

        if category:
            params["category"] = category
        if status:
            params["status"] = status
        if direction:
            params["direction"] = direction
        if search:
            params["search"] = search

        data = await self._get("/user/alerts.json", params=params)
        return AlertListResponse.from_api_response(data)

    async def get_alert_details(
        self,
        alert_id: int,
        *,
        html_tags: bool = False,
    ) -> AlertDetailResponse:
        """Get detailed information for a specific alert.

        Args:
            alert_id: The alert ID
            html_tags: If True, return msgText with HTML tags

        Returns:
            AlertDetailResponse with alert details
        """
        params = {"htmlTags": str(html_tags).lower()}
        data = await self._get(f"/user/alerts/{alert_id}.json", params=params)
        return AlertDetailResponse.from_api_response(data)

    async def delete_alerts(self, alert_ids: list[int]) -> DeleteAlertsResponse:
        """Delete one or more alerts.

        Args:
            alert_ids: List of alert IDs to delete

        Returns:
            DeleteAlertsResponse with result status
        """
        id_list = ",".join(str(id) for id in alert_ids)
        data = await self._delete(f"/user/alerts/{id_list}.json")
        return DeleteAlertsResponse.from_api_response(data)

    async def iter_alerts(
        self,
        *,
        category: str | None = None,
        status: str | None = None,
        direction: str = "DESC",
        search: str | None = None,
        limit: int | None = None,
    ) -> AsyncIterator[Alert]:
        """Iterate over alerts matching the filters.

        Yields individual alerts. Provides a consistent interface with
        iter_transactions() and iter_orders().

        Note: The E*Trade Alerts API returns up to 300 alerts in a single
        call with no pagination. This method provides interface consistency.

        Args:
            category: Filter by category - "STOCK" or "ACCOUNT"
            status: Filter by status - "READ", "UNREAD", or "DELETED"
            direction: Sort direction by createDate - "ASC" or "DESC"
            search: Search string to filter by subject text
            limit: Maximum alerts to yield (None = unlimited)

        Yields:
            Individual Alert objects
        """
        # Fetch all alerts (API returns up to 300, no pagination)
        response = await self.list_alerts(
            count=300,
            category=category,
            status=status,
            direction=direction,
            search=search,
        )

        yielded = 0
        for alert in response.alerts:
            if limit is not None and yielded >= limit:
                return
            yield alert
            yielded += 1
