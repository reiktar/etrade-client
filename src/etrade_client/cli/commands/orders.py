"""Orders commands."""

from datetime import date

import typer

from etrade_client.cli.async_runner import async_command
from etrade_client.cli.client_factory import get_client
from etrade_client.cli.config import CLIConfig, OutputFormat
from etrade_client.cli.formatters import format_output, print_error, print_success

app = typer.Typer(no_args_is_help=True)


@app.command("list")
@async_command
async def list_orders(
    ctx: typer.Context,
    account_id: str = typer.Argument(
        ...,
        help="Account ID key.",
    ),
    status: str | None = typer.Option(
        None,
        "--status",
        "-s",
        help="Filter by status: OPEN, EXECUTED, CANCELLED, EXPIRED, REJECTED.",
    ),
    symbol: str | None = typer.Option(
        None,
        "--symbol",
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
        help="Maximum orders to return (default: all).",
    ),
    output: OutputFormat = typer.Option(
        OutputFormat.TABLE,
        "--output",
        "-o",
        help="Output format.",
    ),
) -> None:
    """List orders for an account.

    Without date filters, only recent orders are returned.
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

        # Collect orders using pagination iterator
        orders = []
        async for order in client.orders.iter_orders(
            account_id,
            status=status.upper() if status else None,
            symbol=symbol.upper() if symbol else None,
            from_date=start_date,
            to_date=end_date,
            limit=limit,
        ):
            orders.append(order)

        if not orders:
            format_output([], output, title="Orders")
            return

        # Format order data
        orders_data = []
        for order in orders:
            # Get first order detail for basic info
            detail = order.order_details[0] if order.order_details else None
            instrument = detail.instruments[0] if detail and detail.instruments else None
            product = instrument.product if instrument else None

            # Determine limit/stop price to display
            order_price = ""
            if detail:
                if detail.order_type in ("LIMIT", "STOP_LIMIT") and detail.limit_price:
                    order_price = f"${detail.limit_price:,.2f}"
                elif detail.order_type in ("STOP", "STOP_LIMIT") and detail.stop_price:
                    order_price = f"${detail.stop_price:,.2f}"

            # Execution price (for filled orders)
            exec_price = ""
            if instrument and instrument.average_execution_price:
                exec_price = f"${instrument.average_execution_price:,.2f}"

            orders_data.append(
                {
                    "order_id": order.order_id or "",
                    "symbol": product.symbol if product else "",
                    "action": instrument.order_action if instrument else "",
                    "qty": instrument.quantity if instrument else "",
                    "type": detail.order_type if detail else "",
                    "status": detail.status if detail else "",
                    "limit/stop": order_price,
                    "exec_price": exec_price,
                }
            )

        format_output(orders_data, output, title="Orders")


@app.command("cancel")
@async_command
async def cancel_order(
    ctx: typer.Context,
    account_id: str = typer.Argument(
        ...,
        help="Account ID key.",
    ),
    order_id: int = typer.Argument(
        ...,
        help="Order ID to cancel.",
    ),
) -> None:
    """Cancel an open order.

    Note: This is a write operation. Use with caution.
    """
    config: CLIConfig = ctx.obj

    async with get_client(config) as client:
        if not client.is_authenticated:
            print_error("Not authenticated. Run 'etrade-cli auth login' first.")
            raise typer.Exit(1)

        result = await client.orders.cancel_order(account_id, order_id)

        # Check result
        cancel_response = result.get("CancelOrderResponse", {})
        if cancel_response.get("orderId"):
            print_success(f"Order {order_id} cancelled successfully.")
        else:
            print_error(f"Failed to cancel order: {result}")
            raise typer.Exit(1)
