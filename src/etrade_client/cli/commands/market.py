"""Market data commands."""

from datetime import date

import typer

from etrade_client.cli.async_runner import async_command
from etrade_client.cli.client_factory import get_client
from etrade_client.cli.config import CLIConfig, OutputFormat
from etrade_client.cli.formatters import format_output, print_error

app = typer.Typer(no_args_is_help=True)


@app.command("quote")
@async_command
async def get_quote(
    ctx: typer.Context,
    symbols: list[str] = typer.Argument(
        ...,
        help="One or more ticker symbols (max 25).",
    ),
    detail: str = typer.Option(
        "ALL",
        "--detail",
        "-d",
        help="Detail level: ALL, FUNDAMENTAL, INTRADAY, OPTIONS, WEEK_52.",
    ),
    output: OutputFormat = typer.Option(
        OutputFormat.TABLE,
        "--output",
        "-o",
        help="Output format.",
    ),
) -> None:
    """Get quotes for one or more symbols."""
    config: CLIConfig = ctx.obj

    if len(symbols) > 25:
        print_error("Maximum 25 symbols per request.")
        raise typer.Exit(1)

    async with get_client(config) as client:
        if not client.is_authenticated:
            print_error("Not authenticated. Run 'etrade-cli auth login' first.")
            raise typer.Exit(1)

        response = await client.market.get_quotes(symbols, detail_flag=detail.upper())

        # Format quote data
        quotes_data = [
            {
                "symbol": quote.product.symbol if quote.product else "",
                "last": f"${quote.all_data.last_trade:,.2f}" if quote.all_data and quote.all_data.last_trade else "N/A",
                "change": f"{quote.all_data.change_close:+,.2f}" if quote.all_data and quote.all_data.change_close else "N/A",
                "change_pct": f"{quote.all_data.change_close_pct:+.2f}%" if quote.all_data and quote.all_data.change_close_pct else "N/A",
                "bid": f"${quote.all_data.bid:,.2f}" if quote.all_data and quote.all_data.bid else "N/A",
                "ask": f"${quote.all_data.ask:,.2f}" if quote.all_data and quote.all_data.ask else "N/A",
                "volume": f"{quote.all_data.total_volume:,}" if quote.all_data and quote.all_data.total_volume else "N/A",
            }
            for quote in response.quotes
        ]

        format_output(quotes_data, output, title="Quotes")


@app.command("lookup")
@async_command
async def lookup(
    ctx: typer.Context,
    search: str = typer.Argument(
        ...,
        help="Company name or partial symbol to search.",
    ),
    output: OutputFormat = typer.Option(
        OutputFormat.TABLE,
        "--output",
        "-o",
        help="Output format.",
    ),
) -> None:
    """Look up securities by name or symbol."""
    config: CLIConfig = ctx.obj

    async with get_client(config) as client:
        if not client.is_authenticated:
            print_error("Not authenticated. Run 'etrade-cli auth login' first.")
            raise typer.Exit(1)

        results = await client.market.lookup(search)

        # Format lookup results
        lookup_data = [
            {
                "symbol": r.get("symbol", ""),
                "description": r.get("description", ""),
                "type": r.get("type", ""),
            }
            for r in results
        ]

        format_output(lookup_data, output, title="Lookup Results")


@app.command("options-dates")
@async_command
async def options_dates(
    ctx: typer.Context,
    symbol: str = typer.Argument(
        ...,
        help="Underlying symbol.",
    ),
    expiry_type: str | None = typer.Option(
        None,
        "--type",
        "-t",
        help="Expiry type: ALL, MONTHLY, WEEKLY.",
    ),
    output: OutputFormat = typer.Option(
        OutputFormat.TABLE,
        "--output",
        "-o",
        help="Output format.",
    ),
) -> None:
    """Get available option expiration dates."""
    config: CLIConfig = ctx.obj

    async with get_client(config) as client:
        if not client.is_authenticated:
            print_error("Not authenticated. Run 'etrade-cli auth login' first.")
            raise typer.Exit(1)

        dates = await client.market.get_option_expire_dates(
            symbol,
            expiry_type=expiry_type.upper() if expiry_type else None,
        )

        # Format dates
        dates_data = [
            {
                "expiry_date": d.expiry_date.isoformat() if d.expiry_date else "",
                "type": d.expiry_type or "",
            }
            for d in dates
        ]

        format_output(dates_data, output, title=f"Option Expiry Dates for {symbol.upper()}")


@app.command("options-chain")
@async_command
async def options_chain(
    ctx: typer.Context,
    symbol: str = typer.Argument(
        ...,
        help="Underlying symbol.",
    ),
    expiry: str = typer.Argument(
        ...,
        help="Expiry date (YYYY-MM-DD).",
    ),
    chain_type: str = typer.Option(
        "CALLPUT",
        "--type",
        "-t",
        help="Chain type: CALL, PUT, CALLPUT.",
    ),
    strikes: int | None = typer.Option(
        None,
        "--strikes",
        "-n",
        help="Number of strikes to return.",
    ),
    output: OutputFormat = typer.Option(
        OutputFormat.TABLE,
        "--output",
        "-o",
        help="Output format.",
    ),
) -> None:
    """Get options chain for a symbol and expiry date."""
    config: CLIConfig = ctx.obj

    try:
        expiry_date = date.fromisoformat(expiry)
    except ValueError:
        print_error("Invalid date format. Use YYYY-MM-DD.")
        raise typer.Exit(1) from None

    async with get_client(config) as client:
        if not client.is_authenticated:
            print_error("Not authenticated. Run 'etrade-cli auth login' first.")
            raise typer.Exit(1)

        chain = await client.market.get_option_chains(
            symbol,
            expiry_date,
            chain_type=chain_type.upper(),
            no_of_strikes=strikes,
        )

        if not chain.option_pairs:
            format_output([], output, title="Options Chain")
            return

        # Format chain data
        chain_data = []
        for pair in chain.option_pairs:
            if pair.call:
                chain_data.append({
                    "type": "CALL",
                    "strike": f"${pair.call.strike_price:,.2f}" if pair.call.strike_price else "N/A",
                    "bid": f"${pair.call.bid:,.2f}" if pair.call.bid else "N/A",
                    "ask": f"${pair.call.ask:,.2f}" if pair.call.ask else "N/A",
                    "last": f"${pair.call.last_price:,.2f}" if pair.call.last_price else "N/A",
                    "volume": pair.call.volume or 0,
                    "open_interest": pair.call.open_interest or 0,
                })
            if pair.put:
                chain_data.append({
                    "type": "PUT",
                    "strike": f"${pair.put.strike_price:,.2f}" if pair.put.strike_price else "N/A",
                    "bid": f"${pair.put.bid:,.2f}" if pair.put.bid else "N/A",
                    "ask": f"${pair.put.ask:,.2f}" if pair.put.ask else "N/A",
                    "last": f"${pair.put.last_price:,.2f}" if pair.put.last_price else "N/A",
                    "volume": pair.put.volume or 0,
                    "open_interest": pair.put.open_interest or 0,
                })

        format_output(chain_data, output, title=f"Options Chain: {symbol.upper()} {expiry}")
