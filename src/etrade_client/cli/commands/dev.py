"""Developer tools for data collection and analysis."""

import json
from datetime import date, datetime
from pathlib import Path
from typing import Any

import typer

from etrade_client.cli.async_runner import async_command
from etrade_client.cli.client_factory import get_client
from etrade_client.cli.config import CLIConfig
from etrade_client.cli.formatters import print_error, print_success

app = typer.Typer(no_args_is_help=True)


class ManifestManager:
    """Manages the collection manifest file."""

    def __init__(self, data_dir: Path) -> None:
        self.data_dir = data_dir
        self.manifest_path = data_dir / "manifest.json"

    def load(self) -> dict[str, Any]:
        """Load existing manifest or create empty one."""
        if self.manifest_path.exists():
            return json.loads(self.manifest_path.read_text())
        return {
            "version": "1.0",
            "created_at": datetime.now().isoformat(),
            "last_updated": datetime.now().isoformat(),
            "collections": [],
            "summary": {
                "total_accounts": 0,
                "total_transactions": 0,
                "total_pages": 0,
                "environments": [],
            },
        }

    def save(self, manifest: dict[str, Any]) -> None:
        """Save manifest to disk."""
        manifest["last_updated"] = datetime.now().isoformat()
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.manifest_path.write_text(json.dumps(manifest, indent=2))

    def find_collection(
        self, manifest: dict[str, Any], environment: str, account_id_key: str
    ) -> dict[str, Any] | None:
        """Find existing collection for account."""
        for collection in manifest.get("collections", []):
            if (
                collection.get("environment") == environment
                and collection.get("account_id_key") == account_id_key
            ):
                return collection
        return None

    def get_collected_ranges(
        self, manifest: dict[str, Any], environment: str, account_id_key: str
    ) -> list[tuple[date, date]]:
        """Get list of already collected date ranges for an account."""
        collection = self.find_collection(manifest, environment, account_id_key)
        if not collection:
            return []

        ranges = []
        for dr in collection.get("date_ranges", []):
            start = date.fromisoformat(dr["start_date"])
            end = date.fromisoformat(dr["end_date"])
            ranges.append((start, end))
        return ranges


class RawTransactionCollector:
    """Collects raw transaction API responses."""

    def __init__(
        self,
        data_dir: Path,
        environment: str,
        verbose: bool = False,
    ) -> None:
        self.data_dir = data_dir
        self.environment = environment
        self.verbose = verbose
        self.manifest_manager = ManifestManager(data_dir)

    async def collect_account(
        self,
        client: Any,
        account_id_key: str,
        account_description: str,
        start_date: date,
        end_date: date,
    ) -> dict[str, Any]:
        """Collect all transactions for an account in date range.

        Returns collection summary.
        """
        # Create output directory
        chunk_dir = (
            self.data_dir
            / self.environment
            / f"account_{account_id_key}"
            / f"{start_date.isoformat()}_{end_date.isoformat()}"
        )
        chunk_dir.mkdir(parents=True, exist_ok=True)

        # Collect pages
        pages_info = []
        total_transactions = 0
        page_num = 0
        marker = None
        expected_total: int | None = None  # Captured from first page

        while True:
            page_num += 1

            # Build params for raw API call
            params: dict[str, Any] = {
                "count": 50,
                "sortOrder": "DESC",
            }
            if start_date:
                params["startDate"] = start_date.strftime("%m%d%Y")
            if end_date:
                params["endDate"] = end_date.strftime("%m%d%Y")
            if marker:
                params["marker"] = marker

            # Get raw JSON response (before Pydantic parsing)
            raw_response = await client.accounts._get(
                f"/accounts/{account_id_key}/transactions.json",
                params=params,
            )

            # Add metadata
            page_data = {
                "_metadata": {
                    "captured_at": datetime.now().isoformat(),
                    "page_number": page_num,
                    "marker_used": marker,
                    "params": params,
                },
                **raw_response,
            }

            # Save page
            page_file = chunk_dir / f"page_{page_num:03d}.json"
            page_file.write_text(json.dumps(page_data, indent=2, default=str))

            # Extract transaction info
            tx_response = raw_response.get("TransactionListResponse", {})
            tx_list = tx_response.get("Transaction", [])
            if isinstance(tx_list, dict):
                tx_list = [tx_list]

            tx_count = len(tx_list)
            total_transactions += tx_count

            pages_info.append(
                {
                    "page_number": page_num,
                    "file": page_file.name,
                    "transaction_count": tx_count,
                    "marker": marker,
                }
            )

            if self.verbose:
                print(f"    Page {page_num}: {tx_count} transactions")

            # Check for more pages
            # Note: E*Trade API sometimes returns moreTransactions=false incorrectly
            # Capture totalCount from first page (subsequent pages may have different values)
            # Use totalCount comparison as the reliable indicator
            marker = tx_response.get("marker")
            if expected_total is None:
                expected_total = tx_response.get("totalCount", 0)

            if not marker or total_transactions >= expected_total:
                break

        # Save chunk summary
        summary = {
            "environment": self.environment,
            "account_id_key": account_id_key,
            "account_description": account_description,
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "collected_at": datetime.now().isoformat(),
            "pages": pages_info,
            "total_transactions": total_transactions,
            "total_pages": page_num,
        }
        summary_file = chunk_dir / "summary.json"
        summary_file.write_text(json.dumps(summary, indent=2))

        return summary


def _ranges_overlap(r1: tuple[date, date], r2: tuple[date, date]) -> bool:
    """Check if two date ranges overlap."""
    return r1[0] <= r2[1] and r2[0] <= r1[1]


def _is_range_covered(
    target: tuple[date, date], collected: list[tuple[date, date]]
) -> bool:
    """Check if target range is fully covered by collected ranges."""
    if not collected:
        return False

    # Sort by start date
    sorted_ranges = sorted(collected)

    # Check if target is fully covered
    for coll_start, coll_end in sorted_ranges:
        if coll_start <= target[0] and coll_end >= target[1]:
            return True

    return False


@app.command("collect-transactions")
@async_command
async def collect_transactions(
    ctx: typer.Context,
    account_id: str | None = typer.Argument(
        None,
        help="Specific account ID key to collect (default: all accounts).",
    ),
    output_dir: Path = typer.Option(
        Path(".data/transactions"),
        "--output-dir",
        "-o",
        help="Output directory for collected data.",
    ),
    start_date: str | None = typer.Option(
        None,
        "--start-date",
        help="Start date (YYYY-MM-DD). Default: 2 years ago.",
    ),
    end_date: str | None = typer.Option(
        None,
        "--end-date",
        help="End date (YYYY-MM-DD). Default: today.",
    ),
    full_history: bool = typer.Option(
        False,
        "--full-history",
        help="Collect maximum 2-year history.",
    ),
    incremental: bool = typer.Option(
        True,
        "--incremental/--no-incremental",
        help="Skip already-collected date ranges.",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Preview what would be collected without saving.",
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Show detailed progress.",
    ),
) -> None:
    """Collect raw transaction API responses for analysis.

    Saves raw JSON responses before Pydantic parsing to enable
    field discovery and type analysis.

    Examples:
        # Collect all accounts, full history
        etrade-cli dev collect-transactions --full-history

        # Collect specific account
        etrade-cli dev collect-transactions ABC123 --full-history

        # Collect last 30 days
        etrade-cli dev collect-transactions --start-date 2025-12-01
    """
    config: CLIConfig = ctx.obj

    # Determine environment
    environment = "sandbox" if config.sandbox else "production"

    # Parse dates
    today = date.today()
    if full_history:
        parsed_start = today.replace(year=today.year - 2)
        parsed_end = today
    else:
        parsed_start = (
            date.fromisoformat(start_date)
            if start_date
            else today.replace(year=today.year - 2)
        )
        parsed_end = date.fromisoformat(end_date) if end_date else today

    if verbose:
        print(f"Environment: {environment}")
        print(f"Date range: {parsed_start} to {parsed_end}")
        print(f"Output: {output_dir}")

    async with get_client(config) as client:
        if not client.is_authenticated:
            print_error("Not authenticated. Run 'etrade-cli auth login' first.")
            raise typer.Exit(1)

        # Get accounts to collect
        accounts_response = await client.accounts.list_accounts()
        accounts = accounts_response.accounts

        if account_id:
            accounts = [a for a in accounts if a.account_id_key == account_id]
            if not accounts:
                print_error(f"Account not found: {account_id}")
                raise typer.Exit(1)

        if dry_run:
            print("\n[DRY RUN] Would collect:")
            for acc in accounts:
                print(f"  - {acc.account_desc} ({acc.account_id_key})")
            print(f"\nDate range: {parsed_start} to {parsed_end}")
            print(f"Output directory: {output_dir}")
            return

        # Initialize collector
        collector = RawTransactionCollector(
            data_dir=output_dir,
            environment=environment,
            verbose=verbose,
        )

        # Load manifest for incremental collection
        manifest = collector.manifest_manager.load()

        # Track totals
        total_tx = 0
        total_pages = 0
        collected_accounts = 0

        print(f"\nCollecting transactions from {environment} environment...\n")

        for acc in accounts:
            account_desc = acc.account_desc or acc.account_name or "Unknown"
            print(f"Account: {account_desc} ({acc.account_id_key})")

            # Check if already collected (incremental mode)
            if incremental:
                collected_ranges = collector.manifest_manager.get_collected_ranges(
                    manifest, environment, acc.account_id_key
                )
                target_range = (parsed_start, parsed_end)

                if _is_range_covered(target_range, collected_ranges):
                    print("  [SKIPPED] Already collected this date range")
                    continue

            # Collect
            print(f"  Collecting {parsed_start} to {parsed_end}...")
            try:
                summary = await collector.collect_account(
                    client,
                    acc.account_id_key,
                    account_desc,
                    parsed_start,
                    parsed_end,
                )

                total_tx += summary["total_transactions"]
                total_pages += summary["total_pages"]
                collected_accounts += 1

                print(
                    f"  Saved {summary['total_transactions']} transactions "
                    f"({summary['total_pages']} pages)"
                )

                # Update manifest
                collection = collector.manifest_manager.find_collection(
                    manifest, environment, acc.account_id_key
                )
                if not collection:
                    collection = {
                        "environment": environment,
                        "account_id_key": acc.account_id_key,
                        "account_id": acc.account_id,
                        "account_description": account_desc,
                        "date_ranges": [],
                    }
                    manifest["collections"].append(collection)

                collection["date_ranges"].append(
                    {
                        "start_date": parsed_start.isoformat(),
                        "end_date": parsed_end.isoformat(),
                        "collected_at": datetime.now().isoformat(),
                        "page_count": summary["total_pages"],
                        "transaction_count": summary["total_transactions"],
                        "path": str(
                            Path(environment)
                            / f"account_{acc.account_id_key}"
                            / f"{parsed_start.isoformat()}_{parsed_end.isoformat()}"
                        ),
                    }
                )

            except Exception as e:
                print_error(f"  Failed to collect: {e}")
                if verbose:
                    import traceback

                    traceback.print_exc()

        # Update manifest summary
        manifest["summary"]["total_accounts"] = len(
            {c["account_id_key"] for c in manifest["collections"]}
        )
        manifest["summary"]["total_transactions"] = sum(
            dr["transaction_count"]
            for c in manifest["collections"]
            for dr in c.get("date_ranges", [])
        )
        manifest["summary"]["total_pages"] = sum(
            dr["page_count"]
            for c in manifest["collections"]
            for dr in c.get("date_ranges", [])
        )
        manifest["summary"]["environments"] = list(
            {c["environment"] for c in manifest["collections"]}
        )

        # Save manifest
        collector.manifest_manager.save(manifest)

        print("\nCollection complete!")
        print(f"  Accounts collected: {collected_accounts}")
        print(f"  Total transactions: {total_tx}")
        print(f"  Total pages: {total_pages}")
        print(f"  Output: {output_dir}")

        print_success(f"Manifest saved to {collector.manifest_manager.manifest_path}")


@app.command("show-manifest")
def show_manifest(
    data_dir: Path = typer.Option(
        Path(".data/transactions"),
        "--data-dir",
        "-d",
        help="Data directory containing manifest.",
    ),
) -> None:
    """Show collection manifest summary."""
    manifest_path = data_dir / "manifest.json"

    if not manifest_path.exists():
        print_error(f"No manifest found at {manifest_path}")
        print("Run 'etrade-cli dev collect-transactions' first.")
        raise typer.Exit(1)

    manifest = json.loads(manifest_path.read_text())

    print("\n=== Collection Manifest ===\n")
    print(f"Created: {manifest.get('created_at', 'Unknown')}")
    print(f"Last updated: {manifest.get('last_updated', 'Unknown')}")

    summary = manifest.get("summary", {})
    print("\nSummary:")
    print(f"  Accounts: {summary.get('total_accounts', 0)}")
    print(f"  Transactions: {summary.get('total_transactions', 0)}")
    print(f"  Pages: {summary.get('total_pages', 0)}")
    print(f"  Environments: {', '.join(summary.get('environments', []))}")

    print("\nCollections:")
    for collection in manifest.get("collections", []):
        env = collection.get("environment", "unknown")
        account = collection.get("account_description", collection.get("account_id_key"))
        print(f"\n  [{env}] {account}")

        for dr in collection.get("date_ranges", []):
            print(
                f"    {dr['start_date']} to {dr['end_date']}: "
                f"{dr['transaction_count']} transactions ({dr['page_count']} pages)"
            )


class TransactionAnalyzer:
    """Analyzes collected transaction data to discover types and field patterns."""

    def __init__(self, data_dir: Path) -> None:
        self.data_dir = data_dir
        self.manifest_manager = ManifestManager(data_dir)

    def load_all_transactions(self) -> list[dict[str, Any]]:
        """Load all transactions from collected data."""
        transactions: list[dict[str, Any]] = []

        # Find all page files
        for page_file in self.data_dir.rglob("page_*.json"):
            page_data = json.loads(page_file.read_text())
            tx_response = page_data.get("TransactionListResponse", {})
            tx_list = tx_response.get("Transaction", [])
            if isinstance(tx_list, dict):
                tx_list = [tx_list]
            transactions.extend(tx_list)

        return transactions

    def analyze_types(
        self, transactions: list[dict[str, Any]]
    ) -> dict[str, list[dict[str, Any]]]:
        """Group transactions by transactionType."""
        by_type: dict[str, list[dict[str, Any]]] = {}
        for tx in transactions:
            tx_type = tx.get("transactionType", "UNKNOWN")
            if tx_type not in by_type:
                by_type[tx_type] = []
            by_type[tx_type].append(tx)
        return by_type

    def analyze_fields(
        self, transactions: list[dict[str, Any]], prefix: str = ""
    ) -> dict[str, dict[str, int]]:
        """Analyze field presence across transactions.

        Returns dict of field_path -> {"present": count, "absent": count}
        """
        field_stats: dict[str, dict[str, int]] = {}
        total = len(transactions)

        # Collect all unique field paths
        all_fields: set[str] = set()
        for tx in transactions:
            all_fields.update(self._get_field_paths(tx, prefix))

        # Count presence for each field
        for field in all_fields:
            present = sum(1 for tx in transactions if self._has_field(tx, field, prefix))
            field_stats[field] = {"present": present, "absent": total - present}

        return field_stats

    def _get_field_paths(self, obj: Any, prefix: str = "") -> set[str]:
        """Recursively get all field paths from an object."""
        paths: set[str] = set()
        if isinstance(obj, dict):
            for key, value in obj.items():
                full_path = f"{prefix}.{key}" if prefix else key
                paths.add(full_path)
                paths.update(self._get_field_paths(value, full_path))
        return paths

    def _has_field(self, tx: dict[str, Any], field: str, prefix: str = "") -> bool:
        """Check if transaction has a field (handles nested paths)."""
        parts = field.split(".") if not prefix else field[len(prefix) + 1 :].split(".")
        current = tx
        for part in parts:
            if not isinstance(current, dict) or part not in current:
                return False
            current = current[part]
        return True

    def categorize_fields(
        self, field_stats: dict[str, dict[str, int]], total: int
    ) -> tuple[list[str], list[str], list[str]]:
        """Categorize fields into always/sometimes/never present."""
        always: list[str] = []
        sometimes: list[str] = []
        never: list[str] = []

        for field, stats in sorted(field_stats.items()):
            present = stats["present"]
            if present == total:
                always.append(field)
            elif present == 0:
                never.append(field)
            else:
                sometimes.append(f"{field} ({present}/{total})")

        return always, sometimes, never


@app.command("analyze-transactions")
def analyze_transactions(
    data_dir: Path = typer.Option(
        Path(".data/transactions"),
        "--data-dir",
        "-d",
        help="Data directory containing collected transactions.",
    ),
    show_fields: bool = typer.Option(
        False,
        "--show-fields",
        "-f",
        help="Show field presence analysis for each type.",
    ),
    output_json: Path | None = typer.Option(
        None,
        "--output-json",
        "-o",
        help="Save analysis results to JSON file.",
    ),
) -> None:
    """Analyze collected transactions to discover types and field patterns.

    Reads all collected raw transaction data and produces:
    - Transaction type distribution (count per type)
    - Field presence analysis per type (always/sometimes/never present)

    Examples:
        # Basic type distribution
        etrade-cli dev analyze-transactions

        # Include field analysis
        etrade-cli dev analyze-transactions --show-fields

        # Save to JSON for further processing
        etrade-cli dev analyze-transactions -o analysis.json
    """
    manifest_path = data_dir / "manifest.json"

    if not manifest_path.exists():
        print_error(f"No manifest found at {manifest_path}")
        print("Run 'etrade-cli dev collect-transactions' first.")
        raise typer.Exit(1)

    analyzer = TransactionAnalyzer(data_dir)

    print("\nLoading transactions...")
    transactions = analyzer.load_all_transactions()

    if not transactions:
        print_error("No transactions found in collected data.")
        raise typer.Exit(1)

    print(f"Loaded {len(transactions)} transactions\n")

    # Analyze by type
    by_type = analyzer.analyze_types(transactions)

    print("=== Transaction Type Distribution ===\n")
    type_summary: dict[str, Any] = {}
    for tx_type, txs in sorted(by_type.items(), key=lambda x: -len(x[1])):
        count = len(txs)
        pct = (count / len(transactions)) * 100
        print(f"  {tx_type}: {count} ({pct:.1f}%)")
        type_summary[tx_type] = {"count": count, "percentage": round(pct, 2)}

    if show_fields:
        print("\n=== Field Presence by Type ===")

        field_analysis: dict[str, Any] = {}
        for tx_type, txs in sorted(by_type.items()):
            print(f"\n{tx_type} ({len(txs)} transactions):")

            field_stats = analyzer.analyze_fields(txs)
            always, sometimes, never = analyzer.categorize_fields(field_stats, len(txs))

            field_analysis[tx_type] = {
                "always_present": always,
                "sometimes_present": sometimes,
                "never_present": never,
            }

            print("  Always present:")
            for field in always:
                print(f"    - {field}")

            if sometimes:
                print("  Sometimes present:")
                for field in sometimes:
                    print(f"    - {field}")

    if output_json:
        results = {
            "total_transactions": len(transactions),
            "type_distribution": type_summary,
        }
        if show_fields:
            results["field_analysis"] = field_analysis

        output_json.write_text(json.dumps(results, indent=2))
        print_success(f"\nAnalysis saved to {output_json}")
