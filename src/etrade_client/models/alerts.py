"""Alert-related models."""

from __future__ import annotations

from enum import StrEnum
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from datetime import datetime


class AlertStatus(StrEnum):
    """Alert status values."""

    READ = "READ"
    UNREAD = "UNREAD"
    DELETED = "DELETED"


class AlertCategory(StrEnum):
    """Alert category values."""

    STOCK = "STOCK"
    ACCOUNT = "ACCOUNT"


class Alert(BaseModel):
    """Individual alert from the list."""

    alert_id: int = Field(alias="id")
    create_time: datetime = Field(alias="createTime")
    subject: str
    status: AlertStatus

    model_config = {"populate_by_name": True}


class AlertDetail(BaseModel):
    """Detailed alert with message body."""

    alert_id: int = Field(alias="id")
    create_time: datetime = Field(alias="createTime")
    subject: str
    msg_text: str = Field(alias="msgText")
    read_time: datetime | None = Field(default=None, alias="readTime")
    delete_time: datetime | None = Field(default=None, alias="deleteTime")
    symbol: str | None = Field(default=None)

    model_config = {"populate_by_name": True}


class AlertListResponse(BaseModel):
    """Response from list alerts endpoint."""

    alerts: list[Alert] = Field(default_factory=list)
    total_alerts: int = Field(default=0, alias="totalAlerts")

    model_config = {"populate_by_name": True}

    @classmethod
    def from_api_response(cls, data: dict[str, Any]) -> AlertListResponse:
        """Parse from raw API response."""
        alert_response = data.get("AlertsResponse", {})
        alert_list = alert_response.get("Alert", [])

        # Handle E*Trade's single-item-as-dict quirk
        if isinstance(alert_list, dict):
            alert_list = [alert_list]

        return cls(
            alerts=[Alert.model_validate(a) for a in alert_list],
            total_alerts=alert_response.get("totalAlerts", len(alert_list)),
        )


class AlertDetailResponse(BaseModel):
    """Response from get alert details endpoint."""

    alert: AlertDetail

    @classmethod
    def from_api_response(cls, data: dict[str, Any]) -> AlertDetailResponse:
        """Parse from raw API response."""
        alert_data = data.get("AlertDetailsResponse", {})
        return cls(alert=AlertDetail.model_validate(alert_data))


class DeleteAlertsResponse(BaseModel):
    """Response from delete alerts endpoint."""

    result: str  # SUCCESS or error message

    @classmethod
    def from_api_response(cls, data: dict[str, Any]) -> DeleteAlertsResponse:
        """Parse from raw API response."""
        result = data.get("AlertsResponse", {}).get("result", "UNKNOWN")
        return cls(result=result)
