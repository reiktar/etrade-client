"""E*Trade CLI - Command-line interface for E*Trade API."""

from etrade_client.cli.app import app

# Import command modules to register them with the app
from etrade_client.cli.commands import accounts, alerts, auth, dev, market, orders, transactions

# Register sub-apps
app.add_typer(auth.app, name="auth", help="Authentication commands.")
app.add_typer(accounts.app, name="accounts", help="Account information.")
app.add_typer(market.app, name="market", help="Market data and quotes.")
app.add_typer(orders.app, name="orders", help="Order management.")
app.add_typer(alerts.app, name="alerts", help="Alert management.")
app.add_typer(transactions.app, name="transactions", help="Transaction history.")
app.add_typer(dev.app, name="dev", help="Developer tools for data collection and analysis.")


def main() -> None:
    """Entry point for the CLI."""
    app()


__all__ = ["app", "main"]
