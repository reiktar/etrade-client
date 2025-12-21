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
        help="Start date (YYYY-MM-DD).",
    ),
    to_date: str | None = typer.Option(
        None,
        "--to",
        help="End date (YYYY-MM-DD).",
    ),
    limit: int = typer.Option(
        25,
        "--limit",
        "-n",
        help="Maximum orders to return.",
    ),
    output: OutputFormat = typer.Option(
        OutputFormat.TABLE,
        "--output",
        "-o",
        help="Output format.",
    ),
) -> None:
    """List orders for an account."""
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

        response = await client.orders.list_orders(
            account_id,
            status=status.upper() if status else None,
            symbol=symbol.upper() if symbol else None,
            from_date=start_date,
            to_date=end_date,
            count=limit,
        )

        if not response.orders:
            format_output([], output, title="Orders")
            return

        # Format order data
        orders_data = []
        for order in response.orders:
            # Get first order detail for basic info
            detail = order.order_details[0] if order.order_details else None
            instrument = detail.instruments[0] if detail and detail.instruments else None
            product = instrument.product if instrument else None

            orders_data.append({
                "order_id": order.order_id or "",
                "symbol": product.symbol if product else "",
                "action": instrument.order_action if instrument else "",
                "quantity": instrument.quantity if instrument else "",
                "type": detail.order_type if detail else "",
                "status": detail.status if detail else "",
                "price": f"${detail.limit_price:,.2f}" if detail and detail.limit_price else "MKT",
            })

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
