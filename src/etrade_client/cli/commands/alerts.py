"""Alerts commands."""

import typer

from etrade_client.cli.async_runner import async_command
from etrade_client.cli.client_factory import get_client
from etrade_client.cli.config import CLIConfig, OutputFormat
from etrade_client.cli.formatters import format_output, print_error, print_success

app = typer.Typer(no_args_is_help=True)


@app.command("list")
@async_command
async def list_alerts(
    ctx: typer.Context,
    category: str | None = typer.Option(
        None,
        "--category",
        "-c",
        help="Filter by category: STOCK, ACCOUNT.",
    ),
    status: str | None = typer.Option(
        None,
        "--status",
        "-s",
        help="Filter by status: READ, UNREAD, DELETED.",
    ),
    search: str | None = typer.Option(
        None,
        "--search",
        help="Search in alert subject.",
    ),
    limit: int | None = typer.Option(
        None,
        "--limit",
        "-n",
        help="Maximum alerts to return (default: all, max 300).",
    ),
    output: OutputFormat = typer.Option(
        OutputFormat.TABLE,
        "--output",
        "-o",
        help="Output format.",
    ),
) -> None:
    """List alerts."""
    config: CLIConfig = ctx.obj

    async with get_client(config) as client:
        if not client.is_authenticated:
            print_error("Not authenticated. Run 'etrade-cli auth login' first.")
            raise typer.Exit(1)

        response = await client.alerts.list_alerts(
            count=limit,
            category=category.upper() if category else None,
            status=status.upper() if status else None,
            search=search,
        )

        if not response.alerts:
            format_output([], output, title="Alerts")
            return

        # Format alert data
        alerts_data = [
            {
                "id": alert.alert_id,
                "subject": (alert.subject[:40] + "...") if alert.subject and len(alert.subject) > 40 else (alert.subject or ""),
                "status": alert.status or "",
                "created": alert.create_time.strftime("%Y-%m-%d %H:%M") if alert.create_time else "",
            }
            for alert in response.alerts
        ]

        format_output(alerts_data, output, title="Alerts")


@app.command("get")
@async_command
async def get_alert(
    ctx: typer.Context,
    alert_id: int = typer.Argument(
        ...,
        help="Alert ID.",
    ),
    output: OutputFormat = typer.Option(
        OutputFormat.TABLE,
        "--output",
        "-o",
        help="Output format.",
    ),
) -> None:
    """Get alert details."""
    config: CLIConfig = ctx.obj

    async with get_client(config) as client:
        if not client.is_authenticated:
            print_error("Not authenticated. Run 'etrade-cli auth login' first.")
            raise typer.Exit(1)

        response = await client.alerts.get_alert_details(alert_id)

        if not response.alert:
            print_error(f"Alert {alert_id} not found.")
            raise typer.Exit(1)

        alert = response.alert
        alert_data = {
            "id": alert.alert_id,
            "subject": alert.subject or "",
            "message": alert.msg_text or "",
            "symbol": alert.symbol or "",
            "created": alert.create_time.strftime("%Y-%m-%d %H:%M") if alert.create_time else "",
        }

        format_output(alert_data, output, title=f"Alert {alert_id}")


@app.command("delete")
@async_command
async def delete_alerts(
    ctx: typer.Context,
    alert_ids: list[int] = typer.Argument(
        ...,
        help="Alert ID(s) to delete.",
    ),
) -> None:
    """Delete one or more alerts.

    Note: This is a write operation. Use with caution.
    """
    config: CLIConfig = ctx.obj

    async with get_client(config) as client:
        if not client.is_authenticated:
            print_error("Not authenticated. Run 'etrade-cli auth login' first.")
            raise typer.Exit(1)

        response = await client.alerts.delete_alerts(alert_ids)

        if response.result == "SUCCESS":
            print_success(f"Deleted {len(alert_ids)} alert(s).")
        else:
            print_error(f"Failed to delete alerts: {response.result}")
            raise typer.Exit(1)
