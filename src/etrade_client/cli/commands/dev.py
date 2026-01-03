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


class FieldTypeAnalyzer:
    """Analyzes field types and coverage for model design decisions."""

    def __init__(
        self,
        transactions: list[dict[str, Any]],
        by_type: dict[str, list[dict[str, Any]]],
    ) -> None:
        self.transactions = transactions
        self.by_type = by_type
        self.total_count = len(transactions)
        self.type_names = sorted(by_type.keys())
        self.num_types = len(self.type_names)

    def get_json_type(self, value: Any) -> str:
        """Get JSON-compatible type name for a value."""
        if value is None:
            return "null"
        elif isinstance(value, bool):  # Must check before int (bool is subclass of int)
            return "bool"
        elif isinstance(value, int):
            return "int"
        elif isinstance(value, float):
            return "float"
        elif isinstance(value, str):
            return "str" if value else "str(empty)"
        elif isinstance(value, list):
            return "list" if value else "list(empty)"
        elif isinstance(value, dict):
            return "dict" if value else "dict(empty)"
        else:
            return type(value).__name__

    def extract_field_types(
        self, obj: dict[str, Any], prefix: str = ""
    ) -> dict[str, str]:
        """Extract all field paths and their types from an object."""
        result: dict[str, str] = {}
        for key, value in obj.items():
            path = f"{prefix}.{key}" if prefix else key
            result[path] = self.get_json_type(value)

            # Recurse into non-empty dicts
            if isinstance(value, dict) and value:
                result.update(self.extract_field_types(value, path))

        return result

    def analyze_global(self) -> dict[str, dict[str, int]]:
        """Analyze field types across all transactions.

        Returns: {field_path: {type: count}}
        """
        field_types: dict[str, dict[str, int]] = {}

        for tx in self.transactions:
            for field, ftype in self.extract_field_types(tx).items():
                if field not in field_types:
                    field_types[field] = {}
                field_types[field][ftype] = field_types[field].get(ftype, 0) + 1

        return field_types

    def analyze_per_type(self) -> dict[str, dict[str, dict[str, int]]]:
        """Analyze field types per transaction type.

        Returns: {tx_type: {field_path: {type: count}}}
        """
        result: dict[str, dict[str, dict[str, int]]] = {}

        for tx_type, txs in self.by_type.items():
            field_types: dict[str, dict[str, int]] = {}
            for tx in txs:
                for field, ftype in self.extract_field_types(tx).items():
                    if field not in field_types:
                        field_types[field] = {}
                    field_types[field][ftype] = field_types[field].get(ftype, 0) + 1
            result[tx_type] = field_types

        return result

    def get_dominant_type(self, type_counts: dict[str, int]) -> str:
        """Get the most common type from counts, preferring non-null."""
        # Filter out null for dominance check if there are other types
        non_null = {t: c for t, c in type_counts.items() if t != "null"}
        if non_null:
            return max(non_null.keys(), key=lambda t: non_null[t])
        return max(type_counts.keys(), key=lambda t: type_counts[t])

    def analyze_cross_type_coverage(
        self,
        global_analysis: dict[str, dict[str, int]],
        per_type_analysis: dict[str, dict[str, dict[str, int]]],
    ) -> dict[str, Any]:
        """Analyze field coverage across transaction types.

        Categorizes fields into:
        - base_class: present in ALL types with same datatype (100% coverage)
        - base_class_with_variance: present in ALL types but different datatypes
        - subclass_specific: present in SOME types only
        - type_variance: fields with multiple datatypes (needs attention)
        """
        all_type_names = set(self.type_names)

        base_class: dict[str, Any] = {}
        base_class_with_variance: dict[str, Any] = {}
        subclass_specific: dict[str, Any] = {}
        type_variance: dict[str, Any] = {}

        for field, type_counts in sorted(global_analysis.items()):
            total_present = sum(type_counts.values())
            coverage_pct = (total_present / self.total_count) * 100

            # Which transaction types have this field?
            types_with_field: set[str] = set()
            type_info: dict[str, dict[str, int]] = {}

            for tx_type in self.type_names:
                if field in per_type_analysis.get(tx_type, {}):
                    types_with_field.add(tx_type)
                    type_info[tx_type] = per_type_analysis[tx_type][field]

            types_present = len(types_with_field)
            type_coverage_pct = (types_present / self.num_types) * 100

            # Check for datatype variance
            all_types_found = list(type_counts.keys())
            has_variance = len(all_types_found) > 1

            # Get dominant type per transaction type
            dominant_per_tx_type: dict[str, str] = {}
            for tx_type, counts in type_info.items():
                dominant_per_tx_type[tx_type] = self.get_dominant_type(counts)

            unique_dominants = set(dominant_per_tx_type.values())
            same_type_across_all = len(unique_dominants) == 1

            field_info = {
                "global_types": type_counts,
                "coverage_pct": round(coverage_pct, 1),
                "type_coverage": f"{types_present}/{self.num_types}",
                "type_coverage_pct": round(type_coverage_pct, 1),
                "types_with_field": sorted(types_with_field),
                "dominant_type": self.get_dominant_type(type_counts),
            }

            if has_variance:
                field_info["has_variance"] = True
                field_info["dominant_per_tx_type"] = dominant_per_tx_type
                type_variance[field] = field_info.copy()

            # Categorize based on type coverage
            if types_with_field == all_type_names:
                # Present in ALL transaction types
                if same_type_across_all and not has_variance:
                    base_class[field] = field_info
                else:
                    field_info["dominant_per_tx_type"] = dominant_per_tx_type
                    base_class_with_variance[field] = field_info
            else:
                # Present in SOME transaction types
                field_info["missing_from"] = sorted(all_type_names - types_with_field)
                subclass_specific[field] = field_info

        return {
            "base_class": base_class,
            "base_class_with_variance": base_class_with_variance,
            "subclass_specific": subclass_specific,
            "type_variance": type_variance,
        }

    def analyze_within_type_coverage(
        self, per_type_analysis: dict[str, dict[str, dict[str, int]]]
    ) -> dict[str, dict[str, dict[str, Any]]]:
        """Analyze field coverage WITHIN each transaction type.

        For each type, calculates:
        - What percentage of transactions have each field (coverage)
        - What percentage of present values are null (null rate)
        - Whether the field needs to allow None in Python

        Returns: {
            tx_type: {
                field: {
                    "count": int,           # times field is present
                    "total": int,           # total transactions of this type
                    "coverage_pct": float,  # presence percentage
                    "null_count": int,      # times field value is null
                    "null_pct": float,      # null percentage of present values
                    "non_null_count": int,  # times field has actual value
                    "status": "required" | "optional" | "absent",
                    "nullable": bool,       # True if nulls observed
                    "needs_none": bool,     # True if Python type needs | None
                    "dominant_type": str,   # most common non-null type
                    "types": dict[str, int],
                    "python_type": str,     # recommended Python annotation
                }
            }
        }
        """
        result: dict[str, dict[str, dict[str, Any]]] = {}

        # Collect all fields across all types
        all_fields: set[str] = set()
        for fields in per_type_analysis.values():
            all_fields.update(fields.keys())

        for tx_type in self.type_names:
            type_total = len(self.by_type[tx_type])
            type_fields = per_type_analysis.get(tx_type, {})
            result[tx_type] = {}

            for field in sorted(all_fields):
                if field in type_fields:
                    type_counts = type_fields[field]
                    count = sum(type_counts.values())
                    coverage_pct = (count / type_total) * 100

                    # Extract null count
                    null_count = type_counts.get("null", 0)
                    non_null_count = count - null_count
                    null_pct = (null_count / count * 100) if count > 0 else 0.0

                    # Determine status
                    if coverage_pct == 100.0:
                        status = "required"
                    elif coverage_pct > 0:
                        status = "optional"
                    else:
                        status = "absent"

                    # Determine if field needs | None in Python
                    # Needs None if: field can be absent OR field can be null
                    nullable = null_count > 0
                    needs_none = coverage_pct < 100.0 or nullable

                    # Get Python type annotation
                    python_type = self.get_python_type_for_field(
                        type_counts, needs_none
                    )

                    result[tx_type][field] = {
                        "count": count,
                        "total": type_total,
                        "coverage_pct": round(coverage_pct, 1),
                        "null_count": null_count,
                        "null_pct": round(null_pct, 1),
                        "non_null_count": non_null_count,
                        "status": status,
                        "nullable": nullable,
                        "needs_none": needs_none,
                        "dominant_type": self.get_dominant_type(type_counts),
                        "types": type_counts,
                        "python_type": python_type,
                    }
                else:
                    result[tx_type][field] = {
                        "count": 0,
                        "total": type_total,
                        "coverage_pct": 0.0,
                        "null_count": 0,
                        "null_pct": 0.0,
                        "non_null_count": 0,
                        "status": "absent",
                        "nullable": False,
                        "needs_none": True,  # Absent fields need None
                        "dominant_type": None,
                        "types": {},
                        "python_type": "None",
                    }

        return result

    def get_python_type_for_field(
        self, type_counts: dict[str, int], needs_none: bool
    ) -> str:
        """Generate Python type annotation for a field.

        Args:
            type_counts: Dict of {json_type: count}
            needs_none: Whether the type needs | None (absent or nullable)

        Returns:
            Python type annotation string like "str", "Decimal", "str | None"
        """
        types = set(type_counts.keys())

        # Remove null - handled by needs_none
        types.discard("null")

        # Normalize empty variants to their base types
        if "str(empty)" in types:
            types.discard("str(empty)")
            types.add("str")
        if "list(empty)" in types:
            types.discard("list(empty)")
            types.add("list")
        if "dict(empty)" in types:
            types.discard("dict(empty)")
            types.add("dict")

        if not types:
            return "None"

        # Map JSON types to Python types
        type_mapping = {
            "str": "str",
            "int": "int",
            "float": "Decimal",
            "bool": "bool",
            "list": "list[Any]",
            "dict": "dict[str, Any]",
        }

        # Single type
        if len(types) == 1:
            t = next(iter(types))
            python_type = type_mapping.get(t, t)
        # Mixed int/float -> Decimal
        elif types <= {"int", "float"}:
            python_type = "Decimal"
        else:
            # Multiple types - create union
            python_types = sorted(type_mapping.get(t, t) for t in types)
            python_type = " | ".join(python_types)

        # Add | None if needed
        if needs_none:
            return f"{python_type} | None"
        return python_type

    def generate_per_type_breakdown(
        self, within_type_coverage: dict[str, dict[str, dict[str, Any]]]
    ) -> dict[str, dict[str, list[str]]]:
        """Generate per-type field breakdown categorized by status.

        Returns: {
            tx_type: {
                "required": [field: python_type, ...],  # 100% coverage
                "optional": [field: python_type (coverage%, null%), ...],
                "absent": [field, ...]  # 0% coverage
            }
        }
        """
        result: dict[str, dict[str, list[str]]] = {}

        for tx_type in self.type_names:
            required: list[str] = []
            optional: list[str] = []
            absent: list[str] = []

            for field, info in sorted(within_type_coverage[tx_type].items()):
                status = info["status"]
                python_type = info["python_type"]

                if status == "required":
                    # Show null% if field has null values even at 100% coverage
                    null_pct = info.get("null_pct", 0.0)
                    if null_pct > 0:
                        required.append(f"{field}: {python_type} (null: {null_pct}%)")
                    else:
                        required.append(f"{field}: {python_type}")
                elif status == "optional":
                    cov_pct = info["coverage_pct"]
                    null_pct = info.get("null_pct", 0.0)
                    # Show coverage and null% for optional fields
                    if null_pct > 0:
                        optional.append(
                            f"{field}: {python_type} (cov: {cov_pct}%, null: {null_pct}%)"
                        )
                    else:
                        optional.append(f"{field}: {python_type} (cov: {cov_pct}%)")
                else:
                    absent.append(field)

            result[tx_type] = {
                "required": required,
                "optional": optional,
                "absent": absent,
            }

        return result

    def generate_coverage_matrix(
        self, within_type_coverage: dict[str, dict[str, dict[str, Any]]]
    ) -> list[dict[str, Any]]:
        """Generate a coverage percentage matrix across all transaction types.

        Returns list of rows with Python type annotations and coverage info.
        """
        # Collect all fields
        all_fields: set[str] = set()
        for tx_type in self.type_names:
            all_fields.update(within_type_coverage[tx_type].keys())

        rows: list[dict[str, Any]] = []
        for field in sorted(all_fields):
            row: dict[str, Any] = {"field": field}
            types_with_100pct = 0
            types_with_any = 0
            types_needing_none = 0

            for tx_type in self.type_names:
                info = within_type_coverage[tx_type].get(field, {})
                pct = info.get("coverage_pct", 0.0)
                python_type = info.get("python_type", "-")
                needs_none = info.get("needs_none", True)

                if pct == 100.0:
                    null_pct = info.get("null_pct", 0.0)
                    if null_pct > 0:
                        row[tx_type] = f"{python_type} (n:{null_pct:.0f}%)"
                    else:
                        row[tx_type] = f"{python_type} ✓"
                    types_with_100pct += 1
                    types_with_any += 1
                elif pct > 0:
                    row[tx_type] = f"{python_type} ({pct:.0f}%)"
                    types_with_any += 1
                else:
                    row[tx_type] = "-"

                if needs_none:
                    types_needing_none += 1

            row["required_in"] = f"{types_with_100pct}/{self.num_types}"
            row["present_in"] = f"{types_with_any}/{self.num_types}"
            row["needs_none"] = f"{types_needing_none}/{self.num_types}"
            rows.append(row)

        return rows

    def generate_field_matrix(
        self, per_type_analysis: dict[str, dict[str, dict[str, int]]]
    ) -> list[dict[str, Any]]:
        """Generate a field presence matrix across all transaction types.

        Returns list of rows: [{field, type1, type2, ..., total_types}]
        """
        # Collect all fields
        all_fields: set[str] = set()
        for fields in per_type_analysis.values():
            all_fields.update(fields.keys())

        rows: list[dict[str, Any]] = []
        for field in sorted(all_fields):
            row: dict[str, Any] = {"field": field}
            types_present = 0

            for tx_type in self.type_names:
                if field in per_type_analysis.get(tx_type, {}):
                    type_counts = per_type_analysis[tx_type][field]
                    dominant = self.get_dominant_type(type_counts)
                    total = sum(type_counts.values())
                    row[tx_type] = f"{dominant}({total})"
                    types_present += 1
                else:
                    row[tx_type] = "-"

            row["total_types"] = f"{types_present}/{self.num_types}"
            rows.append(row)

        return rows

    def get_recommended_python_type(self, type_counts: dict[str, int]) -> str:
        """Recommend a Python type annotation based on observed types."""
        types = set(type_counts.keys())

        # Remove null - we'll handle optionality separately
        has_null = "null" in types
        types.discard("null")

        # Handle empty variants
        types.discard("str(empty)")
        types.discard("list(empty)")
        types.discard("dict(empty)")
        if "str(empty)" in type_counts:
            types.add("str")
        if "list(empty)" in type_counts:
            types.add("list")
        if "dict(empty)" in type_counts:
            types.add("dict")

        if not types:
            return "None"

        # Single type
        if len(types) == 1:
            t = next(iter(types))
            mapping = {
                "str": "str",
                "int": "int",
                "float": "Decimal",  # Financial data should use Decimal
                "bool": "bool",
                "list": "list[Any]",
                "dict": "dict[str, Any]",
            }
            base = mapping.get(t, t)
            return f"{base} | None" if has_null else base

        # Mixed numeric - prefer Decimal for financial accuracy
        if types <= {"int", "float"}:
            return "Decimal | None" if has_null else "Decimal"

        # Mixed types - use union
        type_strs = sorted(types)
        base = " | ".join(type_strs)
        return f"{base} | None" if has_null else base


@app.command("analyze-transactions")
def analyze_transactions(
    data_dir: Path = typer.Option(
        Path(".data/transactions"),
        "--data-dir",
        "-d",
        help="Data directory containing collected transactions.",
    ),
    show_base_class: bool = typer.Option(
        True,
        "--show-base-class/--no-base-class",
        help="Show base class candidate fields (100% coverage, same type).",
    ),
    show_variance: bool = typer.Option(
        True,
        "--show-variance/--no-variance",
        help="Show fields with datatype variance.",
    ),
    show_subclass: bool = typer.Option(
        False,
        "--show-subclass",
        "-s",
        help="Show subclass-specific fields (not in all types).",
    ),
    show_matrix: bool = typer.Option(
        False,
        "--show-matrix",
        "-m",
        help="Show field presence matrix across all types.",
    ),
    show_per_type: bool = typer.Option(
        False,
        "--show-per-type",
        "-p",
        help="Show per-type field breakdown (required/optional/absent).",
    ),
    show_coverage_matrix: bool = typer.Option(
        False,
        "--show-coverage-matrix",
        "-c",
        help="Show coverage percentage matrix (✓=100%, X%=partial).",
    ),
    output_json: Path | None = typer.Option(
        None,
        "--output-json",
        "-o",
        help="Save full analysis results to JSON file.",
    ),
) -> None:
    """Analyze collected transactions for model design.

    Performs comprehensive field and datatype analysis:
    - Transaction type distribution
    - Field coverage analysis (which fields in which types)
    - Datatype analysis (detect type variance)
    - Base class candidates (fields in ALL types with same datatype)
    - Subclass-specific fields (fields in SOME types only)

    Examples:
        # Full analysis for model design
        etrade-cli dev analyze-transactions

        # Include field matrix across types
        etrade-cli dev analyze-transactions --show-matrix

        # Show subclass-specific fields
        etrade-cli dev analyze-transactions --show-subclass

        # Save complete analysis to JSON
        etrade-cli dev analyze-transactions -o analysis.json
    """
    manifest_path = data_dir / "manifest.json"

    if not manifest_path.exists():
        print_error(f"No manifest found at {manifest_path}")
        print("Run 'etrade-cli dev collect-transactions' first.")
        raise typer.Exit(1)

    loader = TransactionAnalyzer(data_dir)

    print("\nLoading transactions...")
    transactions = loader.load_all_transactions()

    if not transactions:
        print_error("No transactions found in collected data.")
        raise typer.Exit(1)

    # Group by type
    by_type = loader.analyze_types(transactions)

    print(f"Loaded {len(transactions)} transactions across {len(by_type)} types\n")

    # Initialize the field type analyzer
    analyzer = FieldTypeAnalyzer(transactions, by_type)

    # Run analyses
    global_analysis = analyzer.analyze_global()
    per_type_analysis = analyzer.analyze_per_type()
    cross_type = analyzer.analyze_cross_type_coverage(global_analysis, per_type_analysis)

    # === Transaction Type Distribution ===
    print("=" * 60)
    print("TRANSACTION TYPE DISTRIBUTION")
    print("=" * 60)
    type_summary: dict[str, Any] = {}
    for tx_type, txs in sorted(by_type.items(), key=lambda x: -len(x[1])):
        count = len(txs)
        pct = (count / len(transactions)) * 100
        print(f"  {tx_type}: {count} ({pct:.1f}%)")
        type_summary[tx_type] = {"count": count, "percentage": round(pct, 2)}

    # === Base Class Candidates ===
    if show_base_class:
        print("\n" + "=" * 60)
        print("BASE CLASS CANDIDATES (present in ALL types, same datatype)")
        print("=" * 60)
        print("Fields that should go in TransactionBase:\n")

        base_fields = cross_type["base_class"]
        if base_fields:
            for field, info in sorted(base_fields.items()):
                type_str = info["dominant_type"]
                python_type = analyzer.get_recommended_python_type(info["global_types"])
                print(f"  {field}: {type_str} -> {python_type}")
        else:
            print("  (none found)")

        # Also show fields in all types but with variance
        variance_in_all = cross_type["base_class_with_variance"]
        if variance_in_all:
            print("\n  --- With Type Variance (needs decision) ---")
            for field, info in sorted(variance_in_all.items()):
                types_str = ", ".join(
                    f"{t}:{c}" for t, c in info["global_types"].items()
                )
                python_type = analyzer.get_recommended_python_type(info["global_types"])
                print(f"  {field}: [{types_str}] -> {python_type}")

    # === Type Variance ===
    if show_variance:
        variance = cross_type["type_variance"]
        if variance:
            print("\n" + "=" * 60)
            print("FIELDS WITH DATATYPE VARIANCE")
            print("=" * 60)
            print("These fields have multiple datatypes across transactions:\n")

            for field, info in sorted(variance.items()):
                types_str = ", ".join(
                    f"{t}:{c}" for t, c in info["global_types"].items()
                )
                coverage = info["coverage_pct"]
                python_type = analyzer.get_recommended_python_type(info["global_types"])
                print(f"  {field}")
                print(f"    Types: {types_str}")
                print(f"    Coverage: {coverage}%")
                print(f"    Recommended: {python_type}")

    # === Subclass-Specific Fields ===
    if show_subclass:
        subclass = cross_type["subclass_specific"]
        if subclass:
            print("\n" + "=" * 60)
            print("SUBCLASS-SPECIFIC FIELDS (not in all types)")
            print("=" * 60)

            for field, info in sorted(subclass.items()):
                type_cov = info["type_coverage"]
                types_in = ", ".join(info["types_with_field"][:5])
                if len(info["types_with_field"]) > 5:
                    types_in += "..."
                dominant = info["dominant_type"]
                python_type = analyzer.get_recommended_python_type(info["global_types"])
                print(f"  {field}: {dominant} ({type_cov} types)")
                print(f"    Present in: {types_in}")
                print(f"    Recommended: {python_type}")

    # === Field Matrix ===
    if show_matrix:
        print("\n" + "=" * 60)
        print("FIELD PRESENCE MATRIX")
        print("=" * 60)

        matrix = analyzer.generate_field_matrix(per_type_analysis)

        # Determine column widths
        type_names = analyzer.type_names
        field_width = max(len(r["field"]) for r in matrix) + 2
        type_width = 12

        # Header
        header = "Field".ljust(field_width)
        for tx_type in type_names:
            # Abbreviate long type names
            abbrev = tx_type[:10] if len(tx_type) > 10 else tx_type
            header += abbrev.ljust(type_width)
        header += "Coverage"
        print(header)
        print("-" * len(header))

        # Rows
        for row in matrix:
            line = row["field"].ljust(field_width)
            for tx_type in type_names:
                val = row.get(tx_type, "-")
                # Abbreviate type info
                if val != "-":
                    val = val[:10] if len(val) > 10 else val
                line += val.ljust(type_width)
            line += row["total_types"]
            print(line)

    # Run within-type analysis for per-type breakdown and coverage matrix
    within_type_coverage = analyzer.analyze_within_type_coverage(per_type_analysis)

    # === Per-Type Field Breakdown ===
    if show_per_type:
        print("\n" + "=" * 60)
        print("PER-TYPE FIELD BREAKDOWN")
        print("=" * 60)
        print("Fields categorized as required/optional/absent within each type:\n")

        breakdown = analyzer.generate_per_type_breakdown(within_type_coverage)

        for tx_type in analyzer.type_names:
            type_count = len(by_type[tx_type])
            info = breakdown[tx_type]
            print(f"\n{tx_type} ({type_count} transactions):")

            print("  Required (100%):")
            if info["required"]:
                for field in info["required"]:
                    print(f"    - {field}")
            else:
                print("    (none)")

            if info["optional"]:
                print("  Optional (partial coverage):")
                for field in info["optional"]:
                    print(f"    - {field}")

            # Only show absent count, not full list
            if info["absent"]:
                print(f"  Absent: {len(info['absent'])} fields")

    # === Coverage Percentage Matrix ===
    if show_coverage_matrix:
        print("\n" + "=" * 60)
        print("COVERAGE PERCENTAGE MATRIX")
        print("=" * 60)
        print("✓ = 100% (required), X% = partial (optional), - = absent\n")

        coverage_matrix = analyzer.generate_coverage_matrix(within_type_coverage)

        # Determine column widths
        type_names = analyzer.type_names
        field_width = max(len(r["field"]) for r in coverage_matrix) + 2
        type_width = 10

        # Header
        header = "Field".ljust(field_width)
        for tx_type in type_names:
            abbrev = tx_type[:8] if len(tx_type) > 8 else tx_type
            header += abbrev.ljust(type_width)
        header += "Req/Pres"
        print(header)
        print("-" * len(header))

        # Rows
        for row in coverage_matrix:
            line = row["field"].ljust(field_width)
            for tx_type in type_names:
                val = row.get(tx_type, "-")
                if val != "-":
                    val = val[:8] if len(val) > 8 else val
                line += val.ljust(type_width)
            line += f"{row['required_in']} / {row['present_in']}"
            print(line)

    # === Save to JSON ===
    if output_json:
        results = {
            "total_transactions": len(transactions),
            "num_types": len(by_type),
            "type_distribution": type_summary,
            "global_field_types": {
                field: {
                    "types": types,
                    "recommended_python_type": analyzer.get_recommended_python_type(
                        types
                    ),
                }
                for field, types in global_analysis.items()
            },
            "cross_type_analysis": cross_type,
            "per_type_analysis": per_type_analysis,
            "within_type_coverage": within_type_coverage,
        }

        output_json.write_text(json.dumps(results, indent=2))
        print_success(f"\nFull analysis saved to {output_json}")
