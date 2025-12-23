"""Double-entry bookkeeping commands."""

from collections import defaultdict
from datetime import date
from decimal import Decimal

import typer
from rich.console import Console
from rich.table import Table
from rich.text import Text

from etrade_client.cli.async_runner import async_command
from etrade_client.cli.client_factory import get_client
from etrade_client.cli.config import CLIConfig, OutputFormat
from etrade_client.cli.formatters import format_output, print_error, print_info
from etrade_client.doubleentry import TransactionMapper, list_all_accounts
from etrade_client.doubleentry.chart import CHART_OF_ACCOUNTS
from etrade_client.doubleentry.models import JournalEntry

app = typer.Typer(no_args_is_help=True)
console = Console()


def _format_amount(amount: Decimal, width: int = 12) -> str:
    """Format an amount with commas and proper alignment."""
    if amount == 0:
        return ""
    return f"${abs(amount):>,.2f}"


def _print_journal_entry(entry: JournalEntry) -> None:
    """Print a single journal entry in ledger format."""
    # Header line: date and description
    date_str = entry.date.strftime("%Y-%m-%d")
    console.print(f"[bold]{date_str}[/bold]  [cyan]{entry.description}[/cyan]")

    # Postings
    for posting in entry.postings:
        account_name = posting.account.name
        if posting.is_debit:
            # Debit - left aligned account, amount on left
            amount_str = _format_amount(posting.amount)
            console.print(f"    {account_name:<40} {amount_str:>14}")
        else:
            # Credit - indented account, amount on right
            amount_str = _format_amount(-posting.amount)
            console.print(f"        {account_name:<36} {' ':>14}{amount_str:>14}")

        # Print memo if present
        if posting.memo:
            console.print(f"            [dim]; {posting.memo}[/dim]")

    console.print()  # Blank line between entries


@app.command("journal")
@async_command
async def journal(
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
    ytd: bool = typer.Option(
        False,
        "--ytd",
        help="Year to date (Jan 1 to today).",
    ),
    alltime: bool = typer.Option(
        False,
        "--alltime",
        help="All transactions (full history).",
    ),
    symbol: str | None = typer.Option(
        None,
        "--symbol",
        "-s",
        help="Filter by symbol.",
    ),
    limit: int | None = typer.Option(
        None,
        "--limit",
        "-n",
        help="Maximum entries to show.",
    ),
    warnings: bool = typer.Option(
        False,
        "--warnings",
        "-w",
        help="Show mapping warnings.",
    ),
) -> None:
    """Show transactions as double-entry journal entries.

    Each transaction is displayed as a balanced journal entry with
    debits and credits. This format clearly shows money flow between
    accounts.

    Example:
        2025-01-15  Dividend - MSTY
            Assets:Cash:Settlement             $125.50
                Income:Dividends:MSTY                      $125.50
    """
    config: CLIConfig = ctx.obj

    # Parse dates
    start_date = None
    end_date = None
    today = date.today()

    # Validate mutually exclusive date options
    date_options_count = sum([ytd, alltime, bool(from_date or to_date)])
    if date_options_count > 1:
        print_error("Options --ytd, --alltime, and --from/--to are mutually exclusive.")
        raise typer.Exit(1)

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

        # Collect transactions
        transactions = []
        async for tx in client.accounts.iter_transactions(
            account_id,
            start_date=start_date,
            end_date=end_date,
            sort_order="ASC",  # Chronological for journal
            limit=None,
        ):
            # Filter by symbol if specified
            if symbol:
                tx_symbol = tx.symbol
                if not tx_symbol or tx_symbol.upper() != symbol.upper():
                    continue

            transactions.append(tx)

        if not transactions:
            print_info("No transactions found.")
            return

        # Map to journal entries
        mapper = TransactionMapper()
        entries, all_warnings = mapper.map_transactions(transactions)

        # Apply limit
        if limit and len(entries) > limit:
            entries = entries[:limit]

        # Print header
        console.print()
        console.print(f"[bold]Journal Entries[/bold] ({len(entries)} entries)")
        console.print("=" * 70)
        console.print()

        # Print each entry
        for entry in entries:
            _print_journal_entry(entry)

        # Print warnings if requested
        if warnings and all_warnings:
            console.print()
            console.print("[yellow]Warnings:[/yellow]")
            for w in all_warnings:
                console.print(f"  [dim]- {w}[/dim]")


@app.command("ledger")
@async_command
async def ledger(
    ctx: typer.Context,
    account_id: str = typer.Argument(
        ...,
        help="Account ID key.",
    ),
    account_name: str = typer.Argument(
        ...,
        help="Account name to show (e.g., 'Assets:Cash:Settlement', 'Income:Dividends:MSTY').",
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
    ytd: bool = typer.Option(
        False,
        "--ytd",
        help="Year to date (Jan 1 to today).",
    ),
    alltime: bool = typer.Option(
        False,
        "--alltime",
        help="All transactions (full history).",
    ),
) -> None:
    """Show ledger for a specific account.

    Displays all activity for one account with running balance.

    Example:
        etrade-cli doubleentry ledger ACCOUNT_ID Assets:Cash:Settlement --ytd
        etrade-cli doubleentry ledger ACCOUNT_ID Income:Dividends:MSTY --ytd
    """
    config: CLIConfig = ctx.obj

    # Parse dates
    start_date = None
    end_date = None
    today = date.today()

    date_options_count = sum([ytd, alltime, bool(from_date or to_date)])
    if date_options_count > 1:
        print_error("Options --ytd, --alltime, and --from/--to are mutually exclusive.")
        raise typer.Exit(1)

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

        # Collect transactions
        transactions = []
        async for tx in client.accounts.iter_transactions(
            account_id,
            start_date=start_date,
            end_date=end_date,
            sort_order="ASC",
            limit=None,
        ):
            transactions.append(tx)

        if not transactions:
            print_info("No transactions found.")
            return

        # Map to journal entries
        mapper = TransactionMapper()
        entries, _ = mapper.map_transactions(transactions)

        # Filter to entries affecting the specified account
        account_name_lower = account_name.lower()
        relevant_entries: list[tuple[JournalEntry, Decimal]] = []

        for entry in entries:
            for posting in entry.postings:
                if posting.account.name.lower() == account_name_lower:
                    relevant_entries.append((entry, posting.amount))
                    break

        if not relevant_entries:
            print_info(f"No activity found for account: {account_name}")
            return

        # Build table
        table = Table(title=f"Ledger: {account_name}")
        table.add_column("Date", style="cyan")
        table.add_column("Description")
        table.add_column("Debit", justify="right", style="green")
        table.add_column("Credit", justify="right", style="red")
        table.add_column("Balance", justify="right", style="bold")

        balance = Decimal(0)

        for entry, amount in relevant_entries:
            balance += amount

            debit_str = _format_amount(amount) if amount > 0 else ""
            credit_str = _format_amount(-amount) if amount < 0 else ""
            balance_str = f"${balance:,.2f}"

            table.add_row(
                entry.date.strftime("%Y-%m-%d"),
                entry.description[:40],
                debit_str,
                credit_str,
                balance_str,
            )

        console.print()
        console.print(table)
        console.print()
        console.print(f"[bold]Final Balance: ${balance:,.2f}[/bold]")


@app.command("trial-balance")
@async_command
async def trial_balance(
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
    ytd: bool = typer.Option(
        False,
        "--ytd",
        help="Year to date (Jan 1 to today).",
    ),
    alltime: bool = typer.Option(
        False,
        "--alltime",
        help="All transactions (full history).",
    ),
    output: OutputFormat = typer.Option(
        OutputFormat.TABLE,
        "--output",
        "-o",
        help="Output format.",
    ),
) -> None:
    """Show trial balance with all account totals.

    The trial balance shows the sum of all debits and credits
    for each account. In a balanced system, total debits equal
    total credits.
    """
    config: CLIConfig = ctx.obj

    # Parse dates
    start_date = None
    end_date = None
    today = date.today()

    date_options_count = sum([ytd, alltime, bool(from_date or to_date)])
    if date_options_count > 1:
        print_error("Options --ytd, --alltime, and --from/--to are mutually exclusive.")
        raise typer.Exit(1)

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

        # Collect transactions
        transactions = []
        async for tx in client.accounts.iter_transactions(
            account_id,
            start_date=start_date,
            end_date=end_date,
            sort_order="ASC",
            limit=None,
        ):
            transactions.append(tx)

        if not transactions:
            print_info("No transactions found.")
            return

        # Map to journal entries
        mapper = TransactionMapper()
        entries, _ = mapper.map_transactions(transactions)

        # Aggregate by account
        account_balances: dict[str, Decimal] = defaultdict(Decimal)

        for entry in entries:
            for posting in entry.postings:
                account_balances[posting.account.name] += posting.amount

        # Sort accounts by name
        sorted_accounts = sorted(account_balances.items())

        # Calculate totals
        total_debits = sum(bal for bal in account_balances.values() if bal > 0)
        total_credits = sum(-bal for bal in account_balances.values() if bal < 0)

        if output == OutputFormat.TABLE:
            # Build table
            table = Table(title="Trial Balance")
            table.add_column("Account", style="cyan")
            table.add_column("Debit", justify="right", style="green")
            table.add_column("Credit", justify="right", style="red")

            for account_name, balance in sorted_accounts:
                if balance == 0:
                    continue

                debit_str = _format_amount(balance) if balance > 0 else ""
                credit_str = _format_amount(-balance) if balance < 0 else ""

                table.add_row(account_name, debit_str, credit_str)

            # Totals row
            table.add_row("", "", "", style="dim")
            table.add_row(
                "[bold]TOTALS[/bold]",
                f"[bold]${total_debits:,.2f}[/bold]",
                f"[bold]${total_credits:,.2f}[/bold]",
            )

            console.print()
            console.print(table)
            console.print()

            # Check balance
            diff = total_debits - total_credits
            if abs(diff) < Decimal("0.01"):
                console.print("[green]Balanced[/green]")
            else:
                console.print(f"[red]Imbalance: ${diff:,.2f}[/red]")
        else:
            # JSON/CSV output
            data = [
                {
                    "account": name,
                    "debit": float(bal) if bal > 0 else 0,
                    "credit": float(-bal) if bal < 0 else 0,
                    "balance": float(bal),
                }
                for name, bal in sorted_accounts
                if bal != 0
            ]
            format_output(data, output, title="Trial Balance")


@app.command("accounts")
def list_accounts_cmd(
    output: OutputFormat = typer.Option(
        OutputFormat.TABLE,
        "--output",
        "-o",
        help="Output format.",
    ),
) -> None:
    """List the chart of accounts.

    Shows all predefined and dynamically created accounts
    used for double-entry bookkeeping.
    """
    accounts = list_all_accounts()

    if output == OutputFormat.TABLE:
        table = Table(title="Chart of Accounts")
        table.add_column("Account", style="cyan")
        table.add_column("Type", style="yellow")
        table.add_column("Description")

        for account in accounts:
            # Indent based on depth
            indent = "  " * account.depth
            name = indent + account.short_name

            table.add_row(name, account.account_type.value, account.description)

        console.print()
        console.print(table)
    else:
        data = [
            {
                "name": a.name,
                "type": a.account_type.value,
                "description": a.description,
            }
            for a in accounts
        ]
        format_output(data, output, title="Chart of Accounts")
