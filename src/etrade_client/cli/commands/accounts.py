"""Accounts commands."""

from datetime import date
from decimal import Decimal

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


@app.command("dividends")
@async_command
async def list_dividends(
    ctx: typer.Context,
    account_id: str = typer.Argument(
        ...,
        help="Account ID key.",
    ),
    symbol: str | None = typer.Option(
        None,
        "--symbol",
        "-s",
        help="Filter by symbol.",
    ),
    from_date: str | None = typer.Option(
        None,
        "--from",
        help="Start date (YYYY-MM-DD). Requires --to.",
    ),
    to_date: str | None = typer.Option(
        None,
        "--to",
        help="End date (YYYY-MM-DD). Requires --from.",
    ),
    ytd: bool = typer.Option(
        False,
        "--ytd",
        help="Year to date (Jan 1 to today).",
    ),
    alltime: bool = typer.Option(
        False,
        "--alltime",
        help="All dividends (full history).",
    ),
    limit: int | None = typer.Option(
        None,
        "--limit",
        "-n",
        help="Maximum dividends to return (default: all).",
    ),
    output: OutputFormat = typer.Option(
        OutputFormat.TABLE,
        "--output",
        "-o",
        help="Output format.",
    ),
) -> None:
    """List dividend transactions for an account.

    Without date filters, only recent dividends are returned.
    Use --ytd, --alltime, or --from/--to together for full history.

    Shows both cash dividends and DRIP (dividend reinvestment) transactions.
    DRIP transactions show as negative amounts with shares purchased.
    """
    config: CLIConfig = ctx.obj

    # Parse dates
    start_date = None
    end_date = None
    today = date.today()

    # Handle convenience date options
    if ytd:
        start_date = date(today.year, 1, 1)
        end_date = today
    elif alltime:
        start_date = date(2010, 1, 1)
        end_date = today
    elif from_date or to_date:
        if from_date:
            try:
                start_date = date.fromisoformat(from_date)
            except ValueError:
                print_error("Invalid from date format. Use YYYY-MM-DD.")
                raise typer.Exit(1) from None
        if to_date:
            try:
                end_date = date.fromisoformat(to_date)
            except ValueError:
                print_error("Invalid to date format. Use YYYY-MM-DD.")
                raise typer.Exit(1) from None

    async with get_client(config) as client:
        if not client.is_authenticated:
            print_error("Not authenticated. Run 'etrade-cli auth login' first.")
            raise typer.Exit(1)

        # Collect dividend transactions, grouping by date/symbol/amount
        # to combine dividend + reinvestment pairs into single rows
        from collections import defaultdict

        # Key: (date_str, symbol, abs_amount) -> list of transactions
        dividend_groups: dict[tuple[str, str, Decimal], list] = defaultdict(list)

        async for tx in client.accounts.iter_transactions(
            account_id,
            start_date=start_date,
            end_date=end_date,
            limit=None,  # We'll filter and limit ourselves
        ):
            # Only include dividend transactions
            if tx.transaction_type != "Dividend":
                continue

            # Filter by symbol if specified
            tx_symbol = tx.symbol
            if symbol and (not tx_symbol or tx_symbol.upper() != symbol.upper()):
                continue

            # Group by date, symbol, and absolute amount
            date_str = tx.transaction_date.strftime("%Y-%m-%d") if tx.transaction_date else ""
            key = (date_str, tx_symbol or "", abs(tx.amount))
            dividend_groups[key].append(tx)

        if not dividend_groups:
            format_output([], output, title="Dividends")
            return

        # Process groups into consolidated rows
        dividend_data = []
        total_dividends = Decimal("0")
        total_reinvested = Decimal("0")

        # Sort by date descending
        sorted_keys = sorted(dividend_groups.keys(), key=lambda k: k[0], reverse=True)

        for key in sorted_keys:
            txs = dividend_groups[key]
            date_str, tx_symbol, amount = key

            # Find the cash dividend (positive) and reinvestment (negative)
            cash_tx = None
            reinvest_tx = None
            for tx in txs:
                if tx.amount > 0:
                    cash_tx = tx
                elif tx.amount < 0 or "REINVESTMENT" in (tx.description or "").upper():
                    reinvest_tx = tx

            # Build the row
            is_drip = reinvest_tx is not None
            total_dividends += amount

            if is_drip:
                total_reinvested += amount

            row = {
                "date": date_str,
                "symbol": tx_symbol,
                "amount": f"${amount:,.2f}",
                "drip": "Yes" if is_drip else "",
                "shares": "",
                "price": "",
            }

            # Add DRIP details from reinvestment transaction
            if reinvest_tx and reinvest_tx.brokerage:
                if reinvest_tx.brokerage.quantity:
                    row["shares"] = f"{reinvest_tx.brokerage.quantity:.3f}"
                if reinvest_tx.brokerage.price:
                    row["price"] = f"${reinvest_tx.brokerage.price:,.2f}"

            dividend_data.append(row)

            # Check limit
            if limit is not None and len(dividend_data) >= limit:
                break

        # Add summary row for table output
        if output == OutputFormat.TABLE and len(dividend_data) > 1:
            dividend_data.append({
                "date": "---",
                "symbol": "TOTAL",
                "amount": f"${total_dividends:,.2f}",
                "drip": f"(${total_reinvested:,.2f} reinvested)",
                "shares": "",
                "price": "",
            })

        format_output(dividend_data, output, title="Dividends")
