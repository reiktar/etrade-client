"""Accounts commands."""

import typer

from etrade_client.cli.async_runner import async_command
from etrade_client.cli.client_factory import get_client
from etrade_client.cli.config import CLIConfig, OutputFormat
from etrade_client.cli.formatters import format_output, print_error

app = typer.Typer(no_args_is_help=True)


@app.command("list")
@async_command
async def list_accounts(
    ctx: typer.Context,
    output: OutputFormat = typer.Option(
        OutputFormat.TABLE,
        "--output",
        "-o",
        help="Output format.",
    ),
) -> None:
    """List all accounts."""
    config: CLIConfig = ctx.obj

    async with get_client(config) as client:
        if not client.is_authenticated:
            print_error("Not authenticated. Run 'etrade-cli auth login' first.")
            raise typer.Exit(1)

        response = await client.accounts.list_accounts()

        if not response.accounts:
            format_output([], output, title="Accounts")
            return

        # Format account data for display
        accounts_data = [
            {
                "account_id": acc.account_id_key,
                "name": acc.account_name or acc.account_desc or "",
                "type": acc.account_type or "",
                "mode": acc.account_mode or "",
                "status": acc.account_status or "",
            }
            for acc in response.accounts
        ]

        format_output(accounts_data, output, title="Accounts")


@app.command("balance")
@async_command
async def get_balance(
    ctx: typer.Context,
    account_id: str = typer.Argument(
        ...,
        help="Account ID key (from 'accounts list').",
    ),
    output: OutputFormat = typer.Option(
        OutputFormat.TABLE,
        "--output",
        "-o",
        help="Output format.",
    ),
) -> None:
    """Get account balance."""
    config: CLIConfig = ctx.obj

    async with get_client(config) as client:
        if not client.is_authenticated:
            print_error("Not authenticated. Run 'etrade-cli auth login' first.")
            raise typer.Exit(1)

        response = await client.accounts.get_balance(account_id)
        bal = response.balance

        if not bal or not bal.computed:
            print_error("Unable to retrieve balance data.")
            raise typer.Exit(1)

        computed = bal.computed
        rtv = computed.real_time_values

        # Format balance data with defensive null checks
        balance_data = {
            "account_type": bal.account_type or "",
            "total_value": f"${rtv.total_account_value:,.2f}"
            if rtv and rtv.total_account_value is not None
            else "N/A",
            "cash_available": f"${computed.cash_available_for_investment:,.2f}"
            if computed.cash_available_for_investment is not None
            else "N/A",
            "net_cash": f"${computed.net_cash:,.2f}"
            if computed.net_cash is not None
            else "N/A",
            "margin_buying_power": f"${computed.margin_buying_power:,.2f}"
            if computed.margin_buying_power is not None
            else "N/A",
        }

        format_output(balance_data, output, title="Account Balance")


@app.command("portfolio")
@async_command
async def get_portfolio(
    ctx: typer.Context,
    account_id: str = typer.Argument(
        ...,
        help="Account ID key (from 'accounts list').",
    ),
    view: str = typer.Option(
        "QUICK",
        "--view",
        "-v",
        help="View type: QUICK, PERFORMANCE, FUNDAMENTAL, COMPLETE.",
    ),
    output: OutputFormat = typer.Option(
        OutputFormat.TABLE,
        "--output",
        "-o",
        help="Output format.",
    ),
) -> None:
    """Get account portfolio positions."""
    config: CLIConfig = ctx.obj

    async with get_client(config) as client:
        if not client.is_authenticated:
            print_error("Not authenticated. Run 'etrade-cli auth login' first.")
            raise typer.Exit(1)

        portfolio = await client.accounts.get_portfolio(account_id, view=view.upper())

        if not portfolio.positions:
            format_output([], output, title="Portfolio Positions")
            return

        # Format position data
        positions_data = [
            {
                "symbol": pos.product.symbol if pos.product else "",
                "type": pos.product.security_type if pos.product else "",
                "quantity": pos.quantity or 0,
                "price": f"${pos.quick.last_trade:,.2f}" if pos.quick and pos.quick.last_trade else "N/A",
                "value": f"${pos.market_value:,.2f}" if pos.market_value else "N/A",
                "day_change": f"{pos.quick.change_pct:+.2f}%" if pos.quick and pos.quick.change_pct else "N/A",
                "total_gain": f"${pos.total_gain:,.2f}" if pos.total_gain else "N/A",
            }
            for pos in portfolio.positions
        ]

        format_output(positions_data, output, title="Portfolio Positions")
