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
            "net_cash": f"${computed.net_cash:,.2f}" if computed.net_cash is not None else "N/A",
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
                "qty": pos.quantity or 0,
                "price": f"${pos.quick.last_trade:,.2f}"
                if pos.quick and pos.quick.last_trade
                else "N/A",
                "value": f"${pos.market_value:,.2f}" if pos.market_value else "N/A",
                "cost_basis": f"${pos.total_cost:,.2f}" if pos.total_cost else "N/A",
                "cost/share": f"${pos.cost_per_share:,.2f}" if pos.cost_per_share else "N/A",
                "gain": f"${pos.total_gain:+,.2f}" if pos.total_gain is not None else "N/A",
                "gain%": f"{pos.total_gain_pct:+.2f}%" if pos.total_gain_pct is not None else "N/A",
            }
            for pos in portfolio.positions
        ]

        # Add summary row for TABLE output
        if output == OutputFormat.TABLE and len(positions_data) > 1:
            total_value = sum(pos.market_value for pos in portfolio.positions if pos.market_value)
            total_cost = sum(pos.total_cost for pos in portfolio.positions if pos.total_cost)
            total_gain = sum(
                pos.total_gain for pos in portfolio.positions if pos.total_gain is not None
            )
            total_gain_pct = (
                (total_value - total_cost) / total_cost * 100 if total_cost else Decimal("0")
            )

            positions_data.append(
                {
                    "symbol": "TOTAL",
                    "qty": "",
                    "price": "",
                    "value": f"${total_value:,.2f}",
                    "cost_basis": f"${total_cost:,.2f}",
                    "cost/share": "",
                    "gain": f"${total_gain:+,.2f}",
                    "gain%": f"{total_gain_pct:+.2f}%",
                }
            )

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
    full_history: bool = typer.Option(
        False,
        "--full-history",
        help="Full history (up to 2 years).",
    ),
    by_symbol: bool = typer.Option(
        False,
        "--by-symbol",
        help="Group totals by symbol.",
    ),
    by_month: bool = typer.Option(
        False,
        "--by-month",
        help="Group totals by year-month.",
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
    debug: bool = typer.Option(
        False,
        "--debug",
        help="Show matching details for dividend/DRIP correlation.",
    ),
) -> None:
    """List dividend transactions for an account.

    Without date filters, only recent dividends are returned.
    Use --ytd, --full-history, or --from/--to together for extended history.

    Shows both cash dividends and DRIP (dividend reinvestment) transactions.
    DRIP transactions show as negative amounts with shares purchased.

    Use --by-symbol and/or --by-month to group and summarize dividends.
    Use --debug to inspect transaction fields for correlation analysis.
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

        # Collect dividend transactions and their reinvestments
        # E*Trade records DRIP inconsistently - reinvestments may be:
        # - Type "Dividend" with negative amount
        # - Type "Bought" with "DIVIDEND REINVESTMENT" in description
        from collections import defaultdict

        # Collect cash dividends and reinvestments separately by (date, symbol)
        # Key: (date_str, symbol) -> {"dividends": [...], "reinvestments": [...]}
        by_date_symbol: dict[tuple[str, str], dict[str, list]] = defaultdict(
            lambda: {"dividends": [], "reinvestments": []}
        )

        async for tx in client.accounts.iter_transactions(
            account_id,
            start_date=start_date,
            end_date=end_date,
            limit=None,  # We'll filter and limit ourselves
        ):
            tx_symbol = tx.symbol
            desc_upper = (tx.description or "").upper()

            # Filter by symbol if specified
            if symbol and (not tx_symbol or tx_symbol.upper() != symbol.upper()):
                continue

            date_str = tx.transaction_date.strftime("%Y-%m-%d") if tx.transaction_date else ""
            key = (date_str, tx_symbol or "")

            # Identify dividend transactions
            if tx.transaction_type == "Dividend":
                if tx.amount > 0:
                    # Cash dividend received
                    by_date_symbol[key]["dividends"].append(tx)
                else:
                    # Reinvestment (negative dividend)
                    by_date_symbol[key]["reinvestments"].append(tx)
            elif tx.transaction_type == "Bought" and "DIVIDEND REINVESTMENT" in desc_upper:
                # E*Trade sometimes categorizes DRIP as "Bought"
                by_date_symbol[key]["reinvestments"].append(tx)

        if not by_date_symbol:
            title = "Dividends"
            if by_symbol and by_month:
                title = "Dividends by Month and Symbol"
            elif by_symbol:
                title = "Dividends by Symbol"
            elif by_month:
                title = "Dividends by Month"
            format_output([], output, title=title)
            return

        # Process into consolidated rows, matching dividends with reinvestments
        # Also track data for grouping
        dividend_rows: list[dict] = []
        total_dividends = Decimal("0")
        total_reinvested = Decimal("0")

        # For grouping: track amounts by group key
        # Key format depends on grouping: (month,), (symbol,), or (month, symbol)
        group_totals: dict[tuple, dict] = defaultdict(
            lambda: {
                "amount": Decimal("0"),
                "reinvested": Decimal("0"),
                "cash": Decimal("0"),
                "count": 0,
            }
        )

        # Sort by date descending
        sorted_keys = sorted(by_date_symbol.keys(), key=lambda k: k[0], reverse=True)

        for key in sorted_keys:
            date_str, tx_symbol = key
            group = by_date_symbol[key]
            dividends = group["dividends"]
            reinvestments = group["reinvestments"]

            # Extract year-month for grouping
            year_month = date_str[:7] if date_str else ""  # "YYYY-MM"

            # Match each dividend with a reinvestment by closest amount
            # (E*Trade reinvestment amounts may differ slightly due to rounding)
            used_reinvestments: set[str] = set()

            for div_tx in dividends:
                div_amount = div_tx.amount
                total_dividends += div_amount

                # Find best matching reinvestment (closest amount, not yet used)
                best_match = None
                best_diff = Decimal("999999")
                for reinv_tx in reinvestments:
                    if reinv_tx.transaction_id in used_reinvestments:
                        continue
                    diff = abs(div_amount - abs(reinv_tx.amount))
                    if diff < best_diff:
                        best_diff = diff
                        best_match = reinv_tx

                # Consider it a match if amounts are within 10% or $0.10
                is_drip = False
                match_method = None
                if best_match is not None:
                    threshold = max(div_amount * Decimal("0.10"), Decimal("0.10"))
                    if best_diff <= threshold:
                        is_drip = True
                        used_reinvestments.add(best_match.transaction_id)
                        total_reinvested += div_amount
                        match_method = "exact" if best_diff == 0 else "threshold"

                # Debug output: show transaction fields for correlation analysis
                if debug:
                    print(f"\n--- Dividend: {tx_symbol} ${div_amount:,.2f} on {date_str} ---")
                    print(f"  tx_id: {div_tx.transaction_id}")
                    print(f"  order_no: {div_tx.brokerage.order_no if div_tx.brokerage else None}")
                    print(f"  description: {div_tx.description}")
                    print(f"  description2: {div_tx.description2}")
                    print(f"  inst_type: {div_tx.inst_type}")
                    if is_drip and best_match:
                        print(f"  MATCHED reinvestment ({match_method}, diff=${best_diff:.4f}):")
                        print(f"    reinv_tx_id: {best_match.transaction_id}")
                        reinv_brok = best_match.brokerage
                        print(f"    reinv_order_no: {reinv_brok.order_no if reinv_brok else None}")
                        print(f"    reinv_amount: ${abs(best_match.amount):,.2f}")
                        print(f"    reinv_description: {best_match.description}")
                        print(f"    reinv_description2: {best_match.description2}")
                    elif best_match:
                        print(f"  NO MATCH (diff=${best_diff:.4f} > threshold=${threshold:.4f})")
                    else:
                        print("  NO MATCH (no reinvestment candidates)")

                # Update group totals
                if by_symbol and by_month:
                    group_key = (year_month, tx_symbol)
                elif by_month:
                    group_key = (year_month,)
                elif by_symbol:
                    group_key = (tx_symbol,)
                else:
                    group_key = None

                if group_key is not None:
                    group_totals[group_key]["amount"] += div_amount
                    group_totals[group_key]["count"] += 1
                    if is_drip:
                        group_totals[group_key]["reinvested"] += div_amount
                    else:
                        group_totals[group_key]["cash"] += div_amount

                # Build individual row (for non-grouped output)
                reinvested_amt = div_amount if is_drip else Decimal("0")
                cash_amt = Decimal("0") if is_drip else div_amount
                # Format DRIP boolean based on output format
                if output == OutputFormat.CSV:
                    drip_val = "true" if is_drip else "false"
                else:
                    drip_val = "Yes" if is_drip else ""
                row = {
                    "date": date_str,
                    "symbol": tx_symbol,
                    "amount": f"${div_amount:,.2f}",
                    "reinvested": f"${reinvested_amt:,.2f}",
                    "cash": f"${cash_amt:,.2f}",
                    "drip": drip_val,
                    "shares": "",
                    "price": "",
                }

                # Add DRIP details from matched reinvestment
                if is_drip and best_match and best_match.brokerage:
                    if best_match.brokerage.quantity:
                        row["shares"] = f"{best_match.brokerage.quantity:.3f}"
                    if best_match.brokerage.price:
                        row["price"] = f"${best_match.brokerage.price:,.2f}"

                dividend_rows.append(row)

                # Check limit (only for non-grouped output)
                if not (by_symbol or by_month):
                    if limit is not None and len(dividend_rows) >= limit:
                        break

            if not (by_symbol or by_month):
                if limit is not None and len(dividend_rows) >= limit:
                    break

        # Output based on grouping mode
        if by_symbol or by_month:
            # Build grouped output
            grouped_data: list[dict] = []

            if by_symbol and by_month:
                # Group by month, then symbol within month
                # Sort by month desc, then symbol asc
                sorted_group_keys = sorted(
                    group_totals.keys(),
                    key=lambda k: (k[0], k[1]),  # (month, symbol)
                    reverse=True,
                )
                # Re-sort to have symbols in ascending order within each month
                sorted_group_keys = sorted(
                    sorted_group_keys,
                    key=lambda k: (-int(k[0].replace("-", "")), k[1]),  # month desc, symbol asc
                )

                current_month = None
                month_total = Decimal("0")
                month_reinvested = Decimal("0")
                month_cash = Decimal("0")

                for gkey in sorted_group_keys:
                    month, sym = gkey
                    totals = group_totals[gkey]

                    # Add month subtotal when month changes
                    if current_month is not None and month != current_month:
                        if output == OutputFormat.TABLE:
                            grouped_data.append(
                                {
                                    "month": "",
                                    "symbol": f"  {current_month} Total",
                                    "amount": f"${month_total:,.2f}",
                                    "reinvested": f"${month_reinvested:,.2f}",
                                    "cash": f"${month_cash:,.2f}",
                                    "count": "",
                                }
                            )
                        month_total = Decimal("0")
                        month_reinvested = Decimal("0")
                        month_cash = Decimal("0")

                    current_month = month
                    month_total += totals["amount"]
                    month_reinvested += totals["reinvested"]
                    month_cash += totals["cash"]

                    grouped_data.append(
                        {
                            "month": month,
                            "symbol": sym,
                            "amount": f"${totals['amount']:,.2f}",
                            "reinvested": f"${totals['reinvested']:,.2f}",
                            "cash": f"${totals['cash']:,.2f}",
                            "count": totals["count"],
                        }
                    )

                # Add final month subtotal
                if current_month is not None and output == OutputFormat.TABLE:
                    grouped_data.append(
                        {
                            "month": "",
                            "symbol": f"  {current_month} Total",
                            "amount": f"${month_total:,.2f}",
                            "reinvested": f"${month_reinvested:,.2f}",
                            "cash": f"${month_cash:,.2f}",
                            "count": "",
                        }
                    )

                # Add grand total
                total_cash = total_dividends - total_reinvested
                if output == OutputFormat.TABLE and len(grouped_data) > 1:
                    grouped_data.append(
                        {
                            "month": "---",
                            "symbol": "TOTAL",
                            "amount": f"${total_dividends:,.2f}",
                            "reinvested": f"${total_reinvested:,.2f}",
                            "cash": f"${total_cash:,.2f}",
                            "count": "",
                        }
                    )

                format_output(grouped_data, output, title="Dividends by Month and Symbol")

            elif by_month:
                # Group by month only
                sorted_group_keys = sorted(group_totals.keys(), reverse=True)

                for gkey in sorted_group_keys:
                    (month,) = gkey
                    totals = group_totals[gkey]
                    grouped_data.append(
                        {
                            "month": month,
                            "amount": f"${totals['amount']:,.2f}",
                            "reinvested": f"${totals['reinvested']:,.2f}",
                            "cash": f"${totals['cash']:,.2f}",
                            "count": totals["count"],
                        }
                    )

                # Add total row
                total_cash = total_dividends - total_reinvested
                if output == OutputFormat.TABLE and len(grouped_data) > 1:
                    grouped_data.append(
                        {
                            "month": "TOTAL",
                            "amount": f"${total_dividends:,.2f}",
                            "reinvested": f"${total_reinvested:,.2f}",
                            "cash": f"${total_cash:,.2f}",
                            "count": "",
                        }
                    )

                format_output(grouped_data, output, title="Dividends by Month")

            else:  # by_symbol only
                # Group by symbol only - sort by total amount descending
                sorted_group_keys = sorted(
                    group_totals.keys(),
                    key=lambda k: group_totals[k]["amount"],
                    reverse=True,
                )

                for gkey in sorted_group_keys:
                    (sym,) = gkey
                    totals = group_totals[gkey]
                    grouped_data.append(
                        {
                            "symbol": sym,
                            "amount": f"${totals['amount']:,.2f}",
                            "reinvested": f"${totals['reinvested']:,.2f}",
                            "cash": f"${totals['cash']:,.2f}",
                            "count": totals["count"],
                        }
                    )

                # Add total row
                total_cash = total_dividends - total_reinvested
                if output == OutputFormat.TABLE and len(grouped_data) > 1:
                    grouped_data.append(
                        {
                            "symbol": "TOTAL",
                            "amount": f"${total_dividends:,.2f}",
                            "reinvested": f"${total_reinvested:,.2f}",
                            "cash": f"${total_cash:,.2f}",
                            "count": "",
                        }
                    )

                format_output(grouped_data, output, title="Dividends by Symbol")

        else:
            # Non-grouped output (original behavior)
            # Add summary row for table output
            if output == OutputFormat.TABLE and len(dividend_rows) > 1:
                dividend_rows.append(
                    {
                        "date": "---",
                        "symbol": "TOTAL",
                        "amount": f"${total_dividends:,.2f}",
                        "drip": f"(${total_reinvested:,.2f} reinvested)",
                        "shares": "",
                        "price": "",
                    }
                )

            format_output(dividend_rows, output, title="Dividends")
