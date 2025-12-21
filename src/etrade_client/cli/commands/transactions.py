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
    from_date: str | None = typer.Option(
        None,
        "--from",
        help="Start date (YYYY-MM-DD).",
    ),
    to_date: str | None = typer.Option(
        None,
        "--to",
        help="End date (YYYY-MM-DD).",
    ),
    limit: int = typer.Option(
        50,
        "--limit",
        "-n",
        help="Maximum transactions to return.",
    ),
    sort: str = typer.Option(
        "DESC",
        "--sort",
        "-s",
        help="Sort order: ASC or DESC.",
    ),
    output: OutputFormat = typer.Option(
        OutputFormat.TABLE,
        "--output",
        "-o",
        help="Output format.",
    ),
) -> None:
    """List transactions for an account."""
    config: CLIConfig = ctx.obj

    # Parse dates
    start_date = None
    end_date = None
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
        async for tx in client.accounts.iter_transactions(
            account_id,
            start_date=start_date,
            end_date=end_date,
            sort_order=sort.upper(),
            limit=limit,
        ):
            transactions.append(tx)

        if not transactions:
            format_output([], output, title="Transactions")
            return

        # Format transaction data
        tx_data = [
            {
                "date": tx.transaction_date.strftime("%Y-%m-%d") if tx.transaction_date else "",
                "type": tx.transaction_type or "",
                "description": (tx.description[:30] + "...") if tx.description and len(tx.description) > 30 else (tx.description or ""),
                "symbol": (tx.brokerage.product.symbol or "") if tx.brokerage and tx.brokerage.product else "",
                "quantity": tx.brokerage.quantity if tx.brokerage and tx.brokerage.quantity else 0,
                "amount": f"${tx.amount:,.2f}" if tx.amount is not None else "",
            }
            for tx in transactions
        ]

        format_output(tx_data, output, title="Transactions")
