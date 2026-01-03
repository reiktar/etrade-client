"""Transactions commands."""

from datetime import date

import typer

from etrade_client.cli.async_runner import async_command
from etrade_client.cli.client_factory import get_client
from etrade_client.cli.config import CLIConfig, OutputFormat
from etrade_client.cli.formatters import format_output, print_error

app = typer.Typer(no_args_is_help=True)


@app.command("list")
@async_command
async def list_transactions(
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
    full_history: bool = typer.Option(
        False,
        "--full-history",
        help="Full history (up to 2 years).",
    ),
    limit: int | None = typer.Option(
        None,
        "--limit",
        "-n",
        help="Maximum transactions to return (default: all).",
    ),
    sort: str = typer.Option(
        "DESC",
        "--sort",
        help="Sort order: ASC or DESC.",
    ),
    output: OutputFormat = typer.Option(
        OutputFormat.TABLE,
        "--output",
        "-o",
        help="Output format.",
    ),
) -> None:
    """List transactions for an account.

    Without date filters, only recent transactions are returned.
    Use --ytd, --full-history, or --from/--to together for extended history.
    """
    config: CLIConfig = ctx.obj

    # Parse dates
    start_date = None
    end_date = None
    today = date.today()

    # Validate mutually exclusive date options
    date_options_count = sum([ytd, full_history, bool(from_date or to_date)])
    if date_options_count > 1:
        print_error("Options --ytd, --full-history, and --from/--to are mutually exclusive.")
        raise typer.Exit(1)

    # Handle convenience date options
    if ytd:
        start_date = date(today.year, 1, 1)
        end_date = today
    elif full_history:
        # E*Trade API only supports 2 years of history
        start_date = today.replace(year=today.year - 2)
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

        # Collect transactions up to limit
        transactions = []
        count = 0
        async for tx in client.accounts.iter_transactions(
            account_id,
            start_date=start_date,
            end_date=end_date,
            sort_order=sort.upper(),
            limit=None,  # We filter ourselves when symbol is specified
        ):
            # Filter by symbol if specified
            if symbol:
                tx_symbol = (
                    tx.brokerage.product.symbol if tx.brokerage and tx.brokerage.product else None
                )
                if not tx_symbol or tx_symbol.upper() != symbol.upper():
                    continue

            transactions.append(tx)
            count += 1

            # Check limit
            if limit is not None and count >= limit:
                break

        if not transactions:
            format_output([], output, title="Transactions")
            return

        # Format transaction data
        tx_data = [
            {
                "date": tx.transaction_datetime.strftime("%Y-%m-%d"),
                "type": tx.transaction_type or "",
                "description": (tx.description[:30] + "...")
                if tx.description and len(tx.description) > 30
                else (tx.description or ""),
                "symbol": tx.symbol or "",
                "quantity": tx.brokerage.quantity if tx.brokerage else 0,
                "amount": f"${tx.amount:,.2f}" if tx.amount is not None else "",
            }
            for tx in transactions
        ]

        format_output(tx_data, output, title="Transactions")
