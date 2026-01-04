"""Orders commands."""

from datetime import date
from decimal import Decimal
from typing import Any

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from etrade_client.builders import EquityOrderBuilder, OptionOrderBuilder
from etrade_client.cli.async_runner import async_command
from etrade_client.cli.client_factory import get_client
from etrade_client.cli.config import CLIConfig, OutputFormat
from etrade_client.cli.formatters import format_output, print_error, print_success
from etrade_client.models.market import OptionType

app = typer.Typer(no_args_is_help=True)
console = Console()


def _format_price(value: Decimal | None) -> str:
    """Format a price value for display."""
    if value is None:
        return "N/A"
    return f"${value:,.2f}"


def _display_order_preview(
    symbol: str,
    action: str,
    quantity: int,
    order_type: str,
    limit_price: float | None,
    stop_price: float | None,
    term: str,
    session: str,
    preview: Any,
    is_option: bool = False,
) -> None:
    """Display a formatted order preview to the console."""
    # Order details table
    details_table = Table(show_header=False, box=None, padding=(0, 2))
    details_table.add_column("Field", style="dim")
    details_table.add_column("Value", style="bold")

    details_table.add_row("Symbol", symbol)

    if is_option:
        details_table.add_row("Action", f"{action} {quantity} contracts")
    else:
        details_table.add_row("Action", f"{action} {quantity} shares")

    # Format order type with prices
    type_str = order_type
    if limit_price and order_type in ("LIMIT", "STOP_LIMIT"):
        type_str += f" @ ${limit_price:,.2f}"
    if stop_price and order_type in ("STOP", "STOP_LIMIT"):
        if order_type == "STOP_LIMIT":
            type_str += f" (stop: ${stop_price:,.2f})"
        else:
            type_str += f" @ ${stop_price:,.2f}"

    details_table.add_row("Type", type_str)
    details_table.add_row("Term", term)
    details_table.add_row("Session", session)

    console.print(Panel(details_table, title="Order Preview", border_style="blue"))

    # Estimated costs table
    costs_table = Table(show_header=False, box=None, padding=(0, 2))
    costs_table.add_column("Field", style="dim")
    costs_table.add_column("Value", style="bold green")

    costs_table.add_row("Order Value", _format_price(preview.total_order_value))
    costs_table.add_row("Commission", _format_price(preview.estimated_commission))
    costs_table.add_row("Total", _format_price(preview.estimated_total_amount))

    console.print(Panel(costs_table, title="Estimated Costs", border_style="green"))


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


@app.command("place-equity")
@async_command
async def place_equity(
    ctx: typer.Context,
    account_id: str = typer.Argument(
        ...,
        help="Account ID key.",
    ),
    symbol: str = typer.Argument(
        ...,
        help="Stock symbol (e.g., AAPL).",
    ),
    # Action options (mutually exclusive)
    buy: int | None = typer.Option(
        None,
        "--buy",
        help="Buy quantity.",
    ),
    sell: int | None = typer.Option(
        None,
        "--sell",
        help="Sell quantity.",
    ),
    sell_short: int | None = typer.Option(
        None,
        "--sell-short",
        help="Short sell quantity.",
    ),
    buy_to_cover: int | None = typer.Option(
        None,
        "--buy-to-cover",
        help="Buy to cover quantity.",
    ),
    # Price options
    limit_price: float | None = typer.Option(
        None,
        "--limit",
        help="Limit price for limit or stop-limit orders.",
    ),
    stop_price: float | None = typer.Option(
        None,
        "--stop",
        help="Stop price for stop or stop-limit orders.",
    ),
    # Order term options (mutually exclusive)
    gtc: bool = typer.Option(
        False,
        "--gtc",
        help="Good until cancel (default: good for day).",
    ),
    ioc: bool = typer.Option(
        False,
        "--ioc",
        help="Immediate or cancel.",
    ),
    fok: bool = typer.Option(
        False,
        "--fok",
        help="Fill or kill.",
    ),
    # Other options
    extended: bool = typer.Option(
        False,
        "--extended",
        help="Extended hours session.",
    ),
    all_or_none: bool = typer.Option(
        False,
        "--all-or-none",
        help="All or none flag.",
    ),
    yes: bool = typer.Option(
        False,
        "--yes",
        "-y",
        help="Skip confirmation prompt.",
    ),
) -> None:
    """Place an equity order.

    Examples:
        etrade-cli orders place-equity ABC123 AAPL --buy 100
        etrade-cli orders place-equity ABC123 AAPL --sell 50 --limit 150.00 --gtc
    """
    config: CLIConfig = ctx.obj

    # Validate action - exactly one must be specified
    actions = [
        ("BUY", buy),
        ("SELL", sell),
        ("SELL_SHORT", sell_short),
        ("BUY_TO_COVER", buy_to_cover),
    ]
    specified_actions = [(name, qty) for name, qty in actions if qty is not None]

    if len(specified_actions) == 0:
        print_error("Must specify one action: --buy, --sell, --sell-short, or --buy-to-cover")
        raise typer.Exit(1)
    if len(specified_actions) > 1:
        print_error("Only one action can be specified.")
        raise typer.Exit(1)

    action_name, quantity = specified_actions[0]

    # Validate order term - at most one
    term_options = [gtc, ioc, fok]
    if sum(term_options) > 1:
        print_error("Only one order term can be specified: --gtc, --ioc, or --fok")
        raise typer.Exit(1)

    # Determine order type based on price options
    if limit_price is not None and stop_price is not None:
        order_type = "STOP_LIMIT"
    elif limit_price is not None:
        order_type = "LIMIT"
    elif stop_price is not None:
        order_type = "STOP"
    else:
        order_type = "MARKET"

    # Determine order term
    if gtc:
        term = "Good Until Cancel"
    elif ioc:
        term = "Immediate or Cancel"
    elif fok:
        term = "Fill or Kill"
    else:
        term = "Good for Day"

    session = "Extended" if extended else "Regular"

    # Build the order
    builder = EquityOrderBuilder(symbol)

    # Set action
    if action_name == "BUY":
        builder.buy(quantity)
    elif action_name == "SELL":
        builder.sell(quantity)
    elif action_name == "SELL_SHORT":
        builder.sell_short(quantity)
    elif action_name == "BUY_TO_COVER":
        builder.buy_to_cover(quantity)

    # Set price type
    if order_type == "LIMIT":
        builder.limit(limit_price)  # type: ignore
    elif order_type == "STOP":
        builder.stop(stop_price)  # type: ignore
    elif order_type == "STOP_LIMIT":
        builder.stop_limit(stop_price, limit_price)  # type: ignore

    # Set order term
    if gtc:
        builder.good_until_cancel()
    elif ioc:
        builder.immediate_or_cancel()
    elif fok:
        builder.fill_or_kill()

    # Set other options
    if extended:
        builder.extended_session()
    if all_or_none:
        builder.all_or_none()

    try:
        order = builder.build()
    except ValueError as e:
        print_error(str(e))
        raise typer.Exit(1) from None

    async with get_client(config) as client:
        if not client.is_authenticated:
            print_error("Not authenticated. Run 'etrade-cli auth login' first.")
            raise typer.Exit(1)

        # Preview the order
        try:
            preview_response = await client.orders.preview_order(account_id, order)
        except Exception as e:
            print_error(f"Failed to preview order: {e}")
            raise typer.Exit(1) from None

        preview = preview_response.preview

        # Display preview
        _display_order_preview(
            symbol=symbol.upper(),
            action=action_name,
            quantity=quantity,
            order_type=order_type,
            limit_price=limit_price,
            stop_price=stop_price,
            term=term,
            session=session,
            preview=preview,
        )

        # Confirm unless --yes
        if not yes:
            confirmed = typer.confirm("\nPlace this order?", default=False)
            if not confirmed:
                console.print("[yellow]Order cancelled.[/yellow]")
                raise typer.Exit(0)

        # Place the order
        try:
            place_response = await client.orders.place_order(
                account_id, order, preview.preview_ids_for_placement
            )
        except Exception as e:
            print_error(f"Failed to place order: {e}")
            raise typer.Exit(1) from None

        placed = place_response.order
        console.print()
        print_success("Order placed successfully!")
        console.print(f"  Order ID: [bold]{placed.order_id}[/bold]")
        if placed.order_num is not None:
            console.print(f"  Order #:  [bold]{placed.order_num}[/bold]")


@app.command("place-option")
@async_command
async def place_option(
    ctx: typer.Context,
    account_id: str = typer.Argument(
        ...,
        help="Account ID key.",
    ),
    symbol: str = typer.Argument(
        ...,
        help="Underlying stock symbol (e.g., AAPL).",
    ),
    # Option contract details
    expiry: str = typer.Option(
        ...,
        "--expiry",
        help="Expiration date (YYYY-MM-DD).",
    ),
    strike: float = typer.Option(
        ...,
        "--strike",
        help="Strike price.",
    ),
    call: bool = typer.Option(
        False,
        "--call",
        help="Call option (mutually exclusive with --put).",
    ),
    put: bool = typer.Option(
        False,
        "--put",
        help="Put option (mutually exclusive with --call).",
    ),
    # Action options (mutually exclusive)
    buy_open: int | None = typer.Option(
        None,
        "--buy-open",
        help="Buy to open quantity.",
    ),
    sell_open: int | None = typer.Option(
        None,
        "--sell-open",
        help="Sell to open quantity.",
    ),
    buy_close: int | None = typer.Option(
        None,
        "--buy-close",
        help="Buy to close quantity.",
    ),
    sell_close: int | None = typer.Option(
        None,
        "--sell-close",
        help="Sell to close quantity.",
    ),
    # Price options
    limit_price: float | None = typer.Option(
        None,
        "--limit",
        help="Limit price for limit or stop-limit orders.",
    ),
    stop_price: float | None = typer.Option(
        None,
        "--stop",
        help="Stop price for stop or stop-limit orders.",
    ),
    # Order term options (mutually exclusive)
    gtc: bool = typer.Option(
        False,
        "--gtc",
        help="Good until cancel (default: good for day).",
    ),
    ioc: bool = typer.Option(
        False,
        "--ioc",
        help="Immediate or cancel.",
    ),
    fok: bool = typer.Option(
        False,
        "--fok",
        help="Fill or kill.",
    ),
    # Other options
    extended: bool = typer.Option(
        False,
        "--extended",
        help="Extended hours session.",
    ),
    all_or_none: bool = typer.Option(
        False,
        "--all-or-none",
        help="All or none flag.",
    ),
    yes: bool = typer.Option(
        False,
        "--yes",
        "-y",
        help="Skip confirmation prompt.",
    ),
) -> None:
    """Place an option order.

    Examples:
        etrade-cli orders place-option ABC123 AAPL --expiry 2025-01-17 --strike 150 --call --buy-open 5 --limit 2.50
        etrade-cli orders place-option ABC123 AAPL --expiry 2025-01-17 --strike 145 --put --sell-close 10 --limit 1.00
    """
    config: CLIConfig = ctx.obj

    # Validate option type - exactly one must be specified
    if call and put:
        print_error("Cannot specify both --call and --put.")
        raise typer.Exit(1)
    if not call and not put:
        print_error("Must specify --call or --put.")
        raise typer.Exit(1)

    option_type = OptionType.CALL if call else OptionType.PUT

    # Validate expiry date format
    try:
        # Validate format by parsing
        date.fromisoformat(expiry)
    except ValueError:
        print_error("Invalid expiry date format. Use YYYY-MM-DD.")
        raise typer.Exit(1) from None

    # Validate action - exactly one must be specified
    actions = [
        ("BUY_OPEN", buy_open),
        ("SELL_OPEN", sell_open),
        ("BUY_CLOSE", buy_close),
        ("SELL_CLOSE", sell_close),
    ]
    specified_actions = [(name, qty) for name, qty in actions if qty is not None]

    if len(specified_actions) == 0:
        print_error(
            "Must specify one action: --buy-open, --sell-open, --buy-close, or --sell-close"
        )
        raise typer.Exit(1)
    if len(specified_actions) > 1:
        print_error("Only one action can be specified.")
        raise typer.Exit(1)

    action_name, quantity = specified_actions[0]

    # Validate order term - at most one
    term_options = [gtc, ioc, fok]
    if sum(term_options) > 1:
        print_error("Only one order term can be specified: --gtc, --ioc, or --fok")
        raise typer.Exit(1)

    # Determine order type based on price options
    if limit_price is not None and stop_price is not None:
        order_type = "STOP_LIMIT"
    elif limit_price is not None:
        order_type = "LIMIT"
    elif stop_price is not None:
        order_type = "STOP"
    else:
        order_type = "MARKET"

    # Determine order term
    if gtc:
        term = "Good Until Cancel"
    elif ioc:
        term = "Immediate or Cancel"
    elif fok:
        term = "Fill or Kill"
    else:
        term = "Good for Day"

    session = "Extended" if extended else "Regular"

    # Build the order
    builder = OptionOrderBuilder(symbol, expiry, strike, option_type)

    # Set action
    if action_name == "BUY_OPEN":
        builder.buy_to_open(quantity)
    elif action_name == "SELL_OPEN":
        builder.sell_to_open(quantity)
    elif action_name == "BUY_CLOSE":
        builder.buy_to_close(quantity)
    elif action_name == "SELL_CLOSE":
        builder.sell_to_close(quantity)

    # Set price type
    if order_type == "LIMIT":
        builder.limit(limit_price)  # type: ignore
    elif order_type == "STOP":
        builder.stop(stop_price)  # type: ignore
    elif order_type == "STOP_LIMIT":
        builder.stop_limit(stop_price, limit_price)  # type: ignore

    # Set order term
    if gtc:
        builder.good_until_cancel()
    elif ioc:
        builder.immediate_or_cancel()
    elif fok:
        builder.fill_or_kill()

    # Set other options
    if extended:
        builder.extended_session()
    if all_or_none:
        builder.all_or_none()

    try:
        order = builder.build()
    except ValueError as e:
        print_error(str(e))
        raise typer.Exit(1) from None

    # Build display symbol
    option_type_str = "CALL" if call else "PUT"
    display_symbol = f"{symbol.upper()} {expiry} ${strike:.2f} {option_type_str}"

    async with get_client(config) as client:
        if not client.is_authenticated:
            print_error("Not authenticated. Run 'etrade-cli auth login' first.")
            raise typer.Exit(1)

        # Preview the order
        try:
            preview_response = await client.orders.preview_order(account_id, order)
        except Exception as e:
            print_error(f"Failed to preview order: {e}")
            raise typer.Exit(1) from None

        preview = preview_response.preview

        # Display preview
        _display_order_preview(
            symbol=display_symbol,
            action=action_name,
            quantity=quantity,
            order_type=order_type,
            limit_price=limit_price,
            stop_price=stop_price,
            term=term,
            session=session,
            preview=preview,
            is_option=True,
        )

        # Confirm unless --yes
        if not yes:
            confirmed = typer.confirm("\nPlace this order?", default=False)
            if not confirmed:
                console.print("[yellow]Order cancelled.[/yellow]")
                raise typer.Exit(0)

        # Place the order
        try:
            place_response = await client.orders.place_order(
                account_id, order, preview.preview_ids_for_placement
            )
        except Exception as e:
            print_error(f"Failed to place order: {e}")
            raise typer.Exit(1) from None

        placed = place_response.order
        console.print()
        print_success("Order placed successfully!")
        console.print(f"  Order ID: [bold]{placed.order_id}[/bold]")
        if placed.order_num is not None:
            console.print(f"  Order #:  [bold]{placed.order_num}[/bold]")


@app.command("preview-equity")
@async_command
async def preview_equity(
    ctx: typer.Context,
    account_id: str = typer.Argument(
        ...,
        help="Account ID key.",
    ),
    symbol: str = typer.Argument(
        ...,
        help="Stock symbol (e.g., AAPL).",
    ),
    # Action options (mutually exclusive)
    buy: int | None = typer.Option(
        None,
        "--buy",
        help="Buy quantity.",
    ),
    sell: int | None = typer.Option(
        None,
        "--sell",
        help="Sell quantity.",
    ),
    sell_short: int | None = typer.Option(
        None,
        "--sell-short",
        help="Sell short quantity.",
    ),
    buy_to_cover: int | None = typer.Option(
        None,
        "--buy-to-cover",
        help="Buy to cover quantity.",
    ),
    # Price options
    limit_price: float | None = typer.Option(
        None,
        "--limit",
        help="Limit price for limit or stop-limit orders.",
    ),
    stop_price: float | None = typer.Option(
        None,
        "--stop",
        help="Stop price for stop or stop-limit orders.",
    ),
    # Order term options (mutually exclusive)
    gtc: bool = typer.Option(
        False,
        "--gtc",
        help="Good until cancel (default: good for day).",
    ),
    ioc: bool = typer.Option(
        False,
        "--ioc",
        help="Immediate or cancel.",
    ),
    fok: bool = typer.Option(
        False,
        "--fok",
        help="Fill or kill.",
    ),
    # Other options
    extended: bool = typer.Option(
        False,
        "--extended",
        help="Extended hours session.",
    ),
    all_or_none: bool = typer.Option(
        False,
        "--all-or-none",
        help="All or none flag.",
    ),
) -> None:
    """Preview an equity order without placing it.

    Examples:
        etrade-cli orders preview-equity ABC123 AAPL --buy 100 --limit 150.00
        etrade-cli orders preview-equity ABC123 MSFT --sell 50 --gtc
    """
    config: CLIConfig = ctx.obj

    # Validate action - exactly one must be specified
    actions = [
        ("BUY", buy),
        ("SELL", sell),
        ("SELL_SHORT", sell_short),
        ("BUY_TO_COVER", buy_to_cover),
    ]
    specified_actions = [(name, qty) for name, qty in actions if qty is not None]

    if len(specified_actions) == 0:
        print_error("Must specify one action: --buy, --sell, --sell-short, or --buy-to-cover")
        raise typer.Exit(1)
    if len(specified_actions) > 1:
        print_error("Only one action can be specified.")
        raise typer.Exit(1)

    action_name, quantity = specified_actions[0]

    # Validate order term - at most one
    term_options = [gtc, ioc, fok]
    if sum(term_options) > 1:
        print_error("Only one order term can be specified: --gtc, --ioc, or --fok")
        raise typer.Exit(1)

    # Determine order type based on price options
    if limit_price is not None and stop_price is not None:
        order_type = "STOP_LIMIT"
    elif limit_price is not None:
        order_type = "LIMIT"
    elif stop_price is not None:
        order_type = "STOP"
    else:
        order_type = "MARKET"

    # Determine order term
    if gtc:
        term = "Good Until Cancel"
    elif ioc:
        term = "Immediate or Cancel"
    elif fok:
        term = "Fill or Kill"
    else:
        term = "Good for Day"

    session = "Extended" if extended else "Regular"

    # Build the order
    builder = EquityOrderBuilder(symbol)

    # Set action
    if action_name == "BUY":
        builder.buy(quantity)
    elif action_name == "SELL":
        builder.sell(quantity)
    elif action_name == "SELL_SHORT":
        builder.sell_short(quantity)
    elif action_name == "BUY_TO_COVER":
        builder.buy_to_cover(quantity)

    # Set price type
    if order_type == "LIMIT":
        builder.limit(limit_price)  # type: ignore
    elif order_type == "STOP":
        builder.stop(stop_price)  # type: ignore
    elif order_type == "STOP_LIMIT":
        builder.stop_limit(stop_price, limit_price)  # type: ignore

    # Set order term
    if gtc:
        builder.good_until_cancel()
    elif ioc:
        builder.immediate_or_cancel()
    elif fok:
        builder.fill_or_kill()

    # Set other options
    if extended:
        builder.extended_session()
    if all_or_none:
        builder.all_or_none()

    try:
        order = builder.build()
    except ValueError as e:
        print_error(str(e))
        raise typer.Exit(1) from None

    async with get_client(config) as client:
        if not client.is_authenticated:
            print_error("Not authenticated. Run 'etrade-cli auth login' first.")
            raise typer.Exit(1)

        # Preview the order
        try:
            preview_response = await client.orders.preview_order(account_id, order)
        except Exception as e:
            print_error(f"Failed to preview order: {e}")
            raise typer.Exit(1) from None

        preview = preview_response.preview

        # Display preview
        _display_order_preview(
            symbol=symbol.upper(),
            action=action_name,
            quantity=quantity,
            order_type=order_type,
            limit_price=limit_price,
            stop_price=stop_price,
            term=term,
            session=session,
            preview=preview,
        )

        console.print("\n[dim]Preview only - order not placed.[/dim]")


@app.command("preview-option")
@async_command
async def preview_option(
    ctx: typer.Context,
    account_id: str = typer.Argument(
        ...,
        help="Account ID key.",
    ),
    symbol: str = typer.Argument(
        ...,
        help="Underlying stock symbol (e.g., AAPL).",
    ),
    # Option contract details
    expiry: str = typer.Option(
        ...,
        "--expiry",
        help="Expiration date (YYYY-MM-DD).",
    ),
    strike: float = typer.Option(
        ...,
        "--strike",
        help="Strike price.",
    ),
    call: bool = typer.Option(
        False,
        "--call",
        help="Call option (mutually exclusive with --put).",
    ),
    put: bool = typer.Option(
        False,
        "--put",
        help="Put option (mutually exclusive with --call).",
    ),
    # Action options (mutually exclusive)
    buy_open: int | None = typer.Option(
        None,
        "--buy-open",
        help="Buy to open quantity.",
    ),
    sell_open: int | None = typer.Option(
        None,
        "--sell-open",
        help="Sell to open quantity.",
    ),
    buy_close: int | None = typer.Option(
        None,
        "--buy-close",
        help="Buy to close quantity.",
    ),
    sell_close: int | None = typer.Option(
        None,
        "--sell-close",
        help="Sell to close quantity.",
    ),
    # Price options
    limit_price: float | None = typer.Option(
        None,
        "--limit",
        help="Limit price for limit or stop-limit orders.",
    ),
    stop_price: float | None = typer.Option(
        None,
        "--stop",
        help="Stop price for stop or stop-limit orders.",
    ),
    # Order term options (mutually exclusive)
    gtc: bool = typer.Option(
        False,
        "--gtc",
        help="Good until cancel (default: good for day).",
    ),
    ioc: bool = typer.Option(
        False,
        "--ioc",
        help="Immediate or cancel.",
    ),
    fok: bool = typer.Option(
        False,
        "--fok",
        help="Fill or kill.",
    ),
    # Other options
    extended: bool = typer.Option(
        False,
        "--extended",
        help="Extended hours session.",
    ),
    all_or_none: bool = typer.Option(
        False,
        "--all-or-none",
        help="All or none flag.",
    ),
) -> None:
    """Preview an option order without placing it.

    Examples:
        etrade-cli orders preview-option ABC123 AAPL --expiry 2025-01-17 --strike 150 --call --buy-open 5 --limit 2.50
        etrade-cli orders preview-option ABC123 AAPL --expiry 2025-01-17 --strike 145 --put --sell-close 10
    """
    config: CLIConfig = ctx.obj

    # Validate option type - exactly one must be specified
    if call and put:
        print_error("Cannot specify both --call and --put.")
        raise typer.Exit(1)
    if not call and not put:
        print_error("Must specify --call or --put.")
        raise typer.Exit(1)

    option_type = OptionType.CALL if call else OptionType.PUT

    # Validate expiry date format
    try:
        # Validate format by parsing
        date.fromisoformat(expiry)
    except ValueError:
        print_error("Invalid expiry date format. Use YYYY-MM-DD.")
        raise typer.Exit(1) from None

    # Validate action - exactly one must be specified
    actions = [
        ("BUY_OPEN", buy_open),
        ("SELL_OPEN", sell_open),
        ("BUY_CLOSE", buy_close),
        ("SELL_CLOSE", sell_close),
    ]
    specified_actions = [(name, qty) for name, qty in actions if qty is not None]

    if len(specified_actions) == 0:
        print_error(
            "Must specify one action: --buy-open, --sell-open, --buy-close, or --sell-close"
        )
        raise typer.Exit(1)
    if len(specified_actions) > 1:
        print_error("Only one action can be specified.")
        raise typer.Exit(1)

    action_name, quantity = specified_actions[0]

    # Validate order term - at most one
    term_options = [gtc, ioc, fok]
    if sum(term_options) > 1:
        print_error("Only one order term can be specified: --gtc, --ioc, or --fok")
        raise typer.Exit(1)

    # Determine order type based on price options
    if limit_price is not None and stop_price is not None:
        order_type = "STOP_LIMIT"
    elif limit_price is not None:
        order_type = "LIMIT"
    elif stop_price is not None:
        order_type = "STOP"
    else:
        order_type = "MARKET"

    # Determine order term
    if gtc:
        term = "Good Until Cancel"
    elif ioc:
        term = "Immediate or Cancel"
    elif fok:
        term = "Fill or Kill"
    else:
        term = "Good for Day"

    session = "Extended" if extended else "Regular"

    # Build the order
    builder = OptionOrderBuilder(symbol, expiry, strike, option_type)

    # Set action
    if action_name == "BUY_OPEN":
        builder.buy_to_open(quantity)
    elif action_name == "SELL_OPEN":
        builder.sell_to_open(quantity)
    elif action_name == "BUY_CLOSE":
        builder.buy_to_close(quantity)
    elif action_name == "SELL_CLOSE":
        builder.sell_to_close(quantity)

    # Set price type
    if order_type == "LIMIT":
        builder.limit(limit_price)  # type: ignore
    elif order_type == "STOP":
        builder.stop(stop_price)  # type: ignore
    elif order_type == "STOP_LIMIT":
        builder.stop_limit(stop_price, limit_price)  # type: ignore

    # Set order term
    if gtc:
        builder.good_until_cancel()
    elif ioc:
        builder.immediate_or_cancel()
    elif fok:
        builder.fill_or_kill()

    # Set other options
    if extended:
        builder.extended_session()
    if all_or_none:
        builder.all_or_none()

    try:
        order = builder.build()
    except ValueError as e:
        print_error(str(e))
        raise typer.Exit(1) from None

    # Build display symbol
    option_type_str = "CALL" if call else "PUT"
    display_symbol = f"{symbol.upper()} {expiry} ${strike:.2f} {option_type_str}"

    async with get_client(config) as client:
        if not client.is_authenticated:
            print_error("Not authenticated. Run 'etrade-cli auth login' first.")
            raise typer.Exit(1)

        # Preview the order
        try:
            preview_response = await client.orders.preview_order(account_id, order)
        except Exception as e:
            print_error(f"Failed to preview order: {e}")
            raise typer.Exit(1) from None

        preview = preview_response.preview

        # Display preview
        _display_order_preview(
            symbol=display_symbol,
            action=action_name,
            quantity=quantity,
            order_type=order_type,
            limit_price=limit_price,
            stop_price=stop_price,
            term=term,
            session=session,
            preview=preview,
            is_option=True,
        )

        console.print("\n[dim]Preview only - order not placed.[/dim]")
