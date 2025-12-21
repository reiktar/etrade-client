# Alerts API

The Alerts API provides access to account and stock alerts.

## Quick Reference

| Method | Description |
|--------|-------------|
| `list_alerts()` | List alerts |
| `get_alert_details(alert_id)` | Get alert details |
| `delete_alerts(alert_ids)` | Delete one or more alerts |

## List Alerts

```python
response = await client.alerts.list_alerts(
    count=25,
    category="STOCK",  # STOCK, ACCOUNT
    status="UNREAD",   # READ, UNREAD, DELETED
    search="AAPL",     # Search in subject
)

for alert in response.alerts:
    print(f"[{alert.alert_id}] {alert.subject}")
    print(f"  Status: {alert.status}")
    print(f"  Created: {alert.create_time}")
```

### Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `count` | `int` | No | `25` | Max alerts (up to 300) |
| `category` | `str` | No | - | STOCK or ACCOUNT |
| `status` | `str` | No | - | READ, UNREAD, DELETED |
| `search` | `str` | No | - | Search in subject |
| `direction` | `str` | No | `"DESC"` | Sort direction |

### Alert Fields

| Field | Type | Description |
|-------|------|-------------|
| `alert_id` | `int` | Unique alert ID |
| `subject` | `str` | Alert subject line |
| `status` | `str` | READ, UNREAD, DELETED |
| `create_time` | `datetime` | Creation timestamp |

## Get Alert Details

```python
response = await client.alerts.get_alert_details(alert_id)
alert = response.alert

print(f"Subject: {alert.subject}")
print(f"Message: {alert.msg_text}")
print(f"Symbol: {alert.symbol}")
print(f"Created: {alert.create_time}")
```

### Detail Fields

| Field | Type | Description |
|-------|------|-------------|
| `alert_id` | `int` | Unique alert ID |
| `subject` | `str` | Alert subject |
| `msg_text` | `str` | Full message text |
| `symbol` | `str` | Related symbol (if applicable) |
| `create_time` | `datetime` | Creation timestamp |

## Delete Alerts

```python
# Delete single alert
response = await client.alerts.delete_alerts([alert_id])

# Delete multiple alerts
response = await client.alerts.delete_alerts([12345, 12346, 12347])

if response.result == "SUCCESS":
    print("Alerts deleted successfully")
```

### Response

| Field | Type | Description |
|-------|------|-------------|
| `result` | `str` | SUCCESS or error message |

## Examples

### Process Unread Alerts

```python
async def process_unread_alerts():
    """Read and mark unread alerts."""
    response = await client.alerts.list_alerts(status="UNREAD")

    for alert in response.alerts:
        # Get full details
        details = await client.alerts.get_alert_details(alert.alert_id)

        print(f"Alert: {details.alert.subject}")
        print(f"  {details.alert.msg_text}")

        # Could mark as read by getting details
        # E*Trade marks alerts as read when details are fetched
```

### Monitor Price Alerts

```python
async def check_price_alerts():
    """Check for stock price alerts."""
    response = await client.alerts.list_alerts(
        category="STOCK",
        status="UNREAD",
    )

    for alert in response.alerts:
        if "price" in (alert.subject or "").lower():
            details = await client.alerts.get_alert_details(alert.alert_id)
            print(f"Price Alert: {details.alert.symbol}")
            print(f"  {details.alert.msg_text}")
```

### Clean Up Old Alerts

```python
async def cleanup_old_alerts(days_old: int = 30):
    """Delete alerts older than specified days."""
    from datetime import datetime, timedelta

    cutoff = datetime.now() - timedelta(days=days_old)

    response = await client.alerts.list_alerts(count=300, status="READ")

    old_alert_ids = [
        alert.alert_id
        for alert in response.alerts
        if alert.create_time and alert.create_time < cutoff
    ]

    if old_alert_ids:
        await client.alerts.delete_alerts(old_alert_ids)
        print(f"Deleted {len(old_alert_ids)} old alerts")
```

## Notes

- Alerts are created by E\*Trade for price triggers, account events, etc.
- Viewing alert details marks the alert as read
- Deleted alerts may still appear with DELETED status temporarily
