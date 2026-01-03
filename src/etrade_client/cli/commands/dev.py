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


class ModelGenerator:
    """Generates Python model code from transaction analysis results."""

    def __init__(
        self,
        cross_type: dict[str, Any],
        within_type_coverage: dict[str, dict[str, dict[str, Any]]],
        type_counts: dict[str, int],
    ) -> None:
        self.cross_type = cross_type
        self.within_type_coverage = within_type_coverage
        self.type_counts = type_counts
        self.type_names = sorted(type_counts.keys())

    def _sanitize_class_name(self, tx_type: str) -> str:
        """Convert transaction type to valid Python class name."""
        # Remove spaces, capitalize words
        words = tx_type.replace("-", " ").split()
        return "".join(word.capitalize() for word in words) + "Transaction"

    def _sanitize_enum_name(self, tx_type: str) -> str:
        """Convert transaction type to valid Python enum member name."""
        # Convert to SCREAMING_SNAKE_CASE
        result = tx_type.upper().replace(" ", "_").replace("-", "_")
        # Handle special chars
        result = "".join(c if c.isalnum() or c == "_" else "_" for c in result)
        return result

    def _get_field_python_type(
        self, field_info: dict[str, Any], for_base: bool = False
    ) -> str:
        """Get Python type annotation for a field."""
        python_type = field_info.get("python_type", "Any")
        # For base class, we might want stricter types
        if for_base and python_type == "None":
            return "Any"
        return python_type

    def _is_nested_field(self, field: str) -> bool:
        """Check if field is a nested path like brokerage.fee."""
        return "." in field

    def _get_top_level_fields(
        self, field_infos: dict[str, dict[str, Any]]
    ) -> dict[str, dict[str, Any]]:
        """Extract only top-level (non-nested) fields."""
        return {f: info for f, info in field_infos.items() if not self._is_nested_field(f)}

    def _get_nested_fields(
        self, field_infos: dict[str, dict[str, Any]], prefix: str
    ) -> dict[str, dict[str, Any]]:
        """Extract fields nested under a prefix (e.g., 'brokerage.')."""
        result = {}
        prefix_dot = prefix + "."
        for field, info in field_infos.items():
            if field.startswith(prefix_dot):
                # Remove the prefix to get the relative field name
                relative = field[len(prefix_dot) :]
                # Only include direct children (not further nested)
                if "." not in relative:
                    result[relative] = info
        return result

    def _collect_base_fields(self) -> dict[str, dict[str, Any]]:
        """Collect fields that belong in the base class."""
        base_fields: dict[str, dict[str, Any]] = {}

        # From base_class (present in all types, same datatype)
        for field, info in self.cross_type.get("base_class", {}).items():
            python_type = self._compute_python_type(info["global_types"], is_required=True)
            base_fields[field] = {
                "python_type": python_type,
                "is_required": True,
                "source": "base_class",
            }

        # From base_class_with_variance (present in all types, varying datatype)
        for field, info in self.cross_type.get("base_class_with_variance", {}).items():
            python_type = self._compute_python_type(info["global_types"], is_required=True)
            base_fields[field] = {
                "python_type": python_type,
                "is_required": True,
                "source": "base_class_with_variance",
            }

        return base_fields

    def _compute_python_type(
        self, type_counts: dict[str, int], is_required: bool
    ) -> str:
        """Compute Python type from type counts."""
        types = set(type_counts.keys())

        # Handle null
        has_null = "null" in types
        types.discard("null")

        # Normalize empty variants
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

        type_mapping = {
            "str": "str",
            "int": "int",
            "float": "Decimal",
            "bool": "bool",
            "list": "list[Any]",
            "dict": "dict[str, Any]",
        }

        if len(types) == 1:
            t = next(iter(types))
            python_type = type_mapping.get(t, t)
        elif types <= {"int", "float"}:
            python_type = "Decimal"
        else:
            python_types = sorted(type_mapping.get(t, t) for t in types)
            python_type = " | ".join(python_types)

        # Add None if nullable or not required
        needs_none = has_null or not is_required
        if needs_none:
            return f"{python_type} | None"
        return python_type

    def _collect_type_specific_fields(
        self, tx_type: str, base_fields: dict[str, dict[str, Any]]
    ) -> dict[str, dict[str, Any]]:
        """Collect fields specific to a transaction type (not in base)."""
        type_coverage = self.within_type_coverage.get(tx_type, {})
        specific_fields: dict[str, dict[str, Any]] = {}

        for field, info in type_coverage.items():
            # Skip if in base class
            if field in base_fields:
                continue

            # Skip absent fields
            if info["status"] == "absent":
                continue

            specific_fields[field] = {
                "python_type": info["python_type"],
                "is_required": info["status"] == "required",
                "coverage_pct": info["coverage_pct"],
            }

        return specific_fields

    def generate_pydantic_models(self) -> str:
        """Generate Pydantic model code."""
        lines: list[str] = []

        # Header and imports
        lines.append('"""Auto-generated transaction models from API analysis."""')
        lines.append("")
        lines.append("from decimal import Decimal")
        lines.append("from typing import Annotated, Any, Literal, Union")
        lines.append("")
        lines.append("from pydantic import BaseModel, Field")
        lines.append("from pydantic.functional_validators import Tag")
        lines.append("from pydantic import Discriminator")
        lines.append("")
        lines.append("")

        # TransactionType enum
        lines.append("class TransactionType:")
        lines.append('    """Known transaction type values from E*Trade API."""')
        lines.append("")
        for tx_type in self.type_names:
            enum_name = self._sanitize_enum_name(tx_type)
            lines.append(f'    {enum_name} = "{tx_type}"')
        lines.append("")
        lines.append("")

        # Collect base class fields
        base_fields = self._collect_base_fields()

        # Generate nested models (Product, BrokerageWithProduct, BrokerageWithoutProduct)
        nested_lines, types_with_product, _ = self._generate_pydantic_nested_models()
        lines.extend(nested_lines)

        # Generate TransactionBase (without brokerage - varies by subclass)
        lines.extend(self._generate_pydantic_base_class(base_fields))

        # Generate subclasses for each transaction type
        for tx_type in self.type_names:
            lines.extend(
                self._generate_pydantic_subclass(tx_type, base_fields, types_with_product)
            )

        # Generate discriminated union
        lines.extend(self._generate_pydantic_union())

        return "\n".join(lines)

    def _analyze_nested_field_requirements(
        self, parent_field: str, child_prefix: str
    ) -> dict[str, bool]:
        """Analyze if child fields are always present when parent is non-empty.

        Returns dict of {child_field: is_required_when_parent_present}
        """
        requirements: dict[str, bool] = {}

        for tx_type in self.type_names:
            type_coverage = self.within_type_coverage.get(tx_type, {})

            # Get parent field info
            parent_info = type_coverage.get(parent_field, {})
            parent_types = parent_info.get("types", {})

            # Count non-empty parent occurrences (dict vs dict(empty))
            non_empty_parent_count = parent_types.get("dict", 0)

            if non_empty_parent_count == 0:
                continue  # No non-empty parents in this type

            # Check each child field
            for field, info in type_coverage.items():
                if not field.startswith(child_prefix):
                    continue

                rel_field = field[len(child_prefix) :]
                if "." in rel_field:  # Skip nested children
                    continue

                child_count = info.get("count", 0)

                # If child count matches non-empty parent count, it's required
                if rel_field not in requirements:
                    requirements[rel_field] = True

                if child_count != non_empty_parent_count:
                    requirements[rel_field] = False

        return requirements

    def _categorize_types_by_product(self) -> tuple[list[str], list[str]]:
        """Categorize transaction types by whether they have brokerage.product.

        Returns (types_with_product, types_without_product)
        """
        with_product: list[str] = []
        without_product: list[str] = []

        for tx_type in self.type_names:
            type_coverage = self.within_type_coverage.get(tx_type, {})
            product_info = type_coverage.get("brokerage.product", {})
            product_types = product_info.get("types", {})

            non_empty = product_types.get("dict", 0)
            empty = product_types.get("dict(empty)", 0)

            if non_empty > 0 and empty == 0:
                with_product.append(tx_type)
            else:
                without_product.append(tx_type)

        return with_product, without_product

    def _get_brokerage_field_requirements(
        self, tx_types: list[str]
    ) -> dict[str, dict[str, Any]]:
        """Get brokerage field requirements for a subset of transaction types.

        Returns field info with is_required based on coverage within those types.
        """
        field_stats: dict[str, dict[str, Any]] = {}

        for tx_type in tx_types:
            type_coverage = self.within_type_coverage.get(tx_type, {})
            type_count = self.type_counts.get(tx_type, 0)

            for field, info in type_coverage.items():
                if not field.startswith("brokerage."):
                    continue
                # Only direct brokerage children (not brokerage.product.X)
                rel_field = field[len("brokerage.") :]
                if "." in rel_field:
                    continue

                if rel_field not in field_stats:
                    field_stats[rel_field] = {
                        "total_count": 0,
                        "total_transactions": 0,
                        "python_type": info.get("python_type", "Any"),
                        "types": {},
                    }

                field_stats[rel_field]["total_count"] += info.get("count", 0)
                field_stats[rel_field]["total_transactions"] += type_count

                # Merge type counts
                for t, c in info.get("types", {}).items():
                    field_stats[rel_field]["types"][t] = (
                        field_stats[rel_field]["types"].get(t, 0) + c
                    )

        # Determine if required (100% coverage within these types)
        result: dict[str, dict[str, Any]] = {}
        for field, stats in field_stats.items():
            coverage = (
                stats["total_count"] / stats["total_transactions"] * 100
                if stats["total_transactions"] > 0
                else 0
            )
            base_type = stats["python_type"].replace(" | None", "")
            result[field] = {
                "python_type": base_type if coverage == 100 else f"{base_type} | None",
                "is_required": coverage == 100,
                "coverage_pct": coverage,
            }

        return result

    def _generate_pydantic_nested_models(self) -> tuple[list[str], list[str], list[str]]:
        """Generate nested Pydantic models (Product, BrokerageWithProduct, BrokerageWithoutProduct).

        Returns (lines, types_with_product, types_without_product)
        """
        lines: list[str] = []

        # Categorize transaction types
        types_with_product, types_without_product = self._categorize_types_by_product()

        # Analyze if product fields are required when product is present
        product_requirements = self._analyze_nested_field_requirements(
            "brokerage.product", "brokerage.product."
        )

        # Collect product fields from types that have product
        all_product_fields: dict[str, dict[str, Any]] = {}
        for tx_type in types_with_product:
            type_coverage = self.within_type_coverage.get(tx_type, {})
            for field, info in type_coverage.items():
                if field.startswith("brokerage.product.") and info["status"] != "absent":
                    rel_field = field.replace("brokerage.product.", "")
                    if "." not in rel_field and rel_field not in all_product_fields:
                        all_product_fields[rel_field] = info

        # Generate Product model
        if all_product_fields:
            lines.append("class Product(BaseModel):")
            lines.append('    """Product information within a brokerage transaction."""')
            lines.append("")

            required_fields = []
            optional_fields = []

            for field, info in sorted(all_product_fields.items()):
                python_type = info.get("python_type", "Any")
                base_type = python_type.replace(" | None", "")
                is_required = product_requirements.get(field, False)

                if is_required:
                    required_fields.append((field, base_type))
                else:
                    optional_fields.append((field, base_type))

            for field, python_type in required_fields:
                lines.append(f"    {field}: {python_type}")
            for field, python_type in optional_fields:
                lines.append(f"    {field}: {python_type} | None = None")

            lines.append("")
            lines.append("")

        # Get brokerage field requirements for each category
        with_product_fields = self._get_brokerage_field_requirements(types_with_product)
        without_product_fields = self._get_brokerage_field_requirements(types_without_product)

        # Generate BrokerageWithProduct
        lines.append("class BrokerageWithProduct(BaseModel):")
        lines.append('    """Brokerage details for transactions with product info."""')
        lines.append("")

        # Required fields first
        for field, info in sorted(with_product_fields.items()):
            if field == "product":
                continue
            if info["is_required"]:
                lines.append(f"    {field}: {info['python_type']}")

        # Optional fields
        for field, info in sorted(with_product_fields.items()):
            if field == "product":
                continue
            if not info["is_required"]:
                python_type = info["python_type"]
                if "| None" not in python_type:
                    python_type = f"{python_type} | None"
                lines.append(f"    {field}: {python_type} = None")

        # Product is required in this variant
        lines.append("    product: Product")
        lines.append("")
        lines.append("")

        # Generate BrokerageWithoutProduct
        lines.append("class BrokerageWithoutProduct(BaseModel):")
        lines.append('    """Brokerage details for transactions without product info."""')
        lines.append("")

        # Required fields first
        for field, info in sorted(without_product_fields.items()):
            if field == "product":
                continue
            if info["is_required"]:
                lines.append(f"    {field}: {info['python_type']}")

        # Optional fields
        for field, info in sorted(without_product_fields.items()):
            if field == "product":
                continue
            if not info["is_required"]:
                python_type = info["python_type"]
                if "| None" not in python_type:
                    python_type = f"{python_type} | None"
                lines.append(f"    {field}: {python_type} = None")

        lines.append("")
        lines.append("")

        return lines, types_with_product, types_without_product

    def _generate_pydantic_base_class(
        self, base_fields: dict[str, dict[str, Any]]
    ) -> list[str]:
        """Generate Pydantic base class (without brokerage - varies by subclass)."""
        lines: list[str] = []

        lines.append("class TransactionBase(BaseModel):")
        lines.append('    """Base class for all transaction types.')
        lines.append("")
        lines.append("    Note: brokerage field is defined in subclasses with the")
        lines.append("    appropriate type (BrokerageWithProduct or BrokerageWithoutProduct).")
        lines.append('    """')
        lines.append("")

        # Add top-level fields (exclude nested ones and brokerage)
        top_level = self._get_top_level_fields(base_fields)

        for field, info in sorted(top_level.items()):
            # Skip brokerage - it's defined in subclasses
            if field == "brokerage":
                continue

            python_type = info.get("python_type", "Any")

            # Use Field with alias for camelCase fields
            snake_field = self._to_snake_case(field)
            if snake_field != field:
                lines.append(
                    f'    {snake_field}: {python_type} = Field(alias="{field}")'
                )
            else:
                lines.append(f"    {field}: {python_type}")

        lines.append("")
        lines.append("    @property")
        lines.append("    def is_pending(self) -> bool:")
        lines.append('        """Check if transaction is pending (post_date is epoch)."""')
        lines.append("        return self.post_date == 0 if hasattr(self, 'post_date') else False")
        lines.append("")
        lines.append("")

        return lines

    def _generate_pydantic_subclass(
        self,
        tx_type: str,
        base_fields: dict[str, dict[str, Any]],
        types_with_product: list[str],
    ) -> list[str]:
        """Generate Pydantic subclass for a transaction type."""
        lines: list[str] = []

        class_name = self._sanitize_class_name(tx_type)
        specific_fields = self._collect_type_specific_fields(tx_type, base_fields)
        top_level_specific = self._get_top_level_fields(specific_fields)

        # Determine brokerage type
        has_product = tx_type in types_with_product
        brokerage_type = "BrokerageWithProduct" if has_product else "BrokerageWithoutProduct"

        lines.append(f"class {class_name}(TransactionBase):")
        lines.append(f'    """Transaction type: {tx_type}"""')
        lines.append("")

        # Add literal type for discriminator
        lines.append(f'    transaction_type: Literal["{tx_type}"] = Field(')
        lines.append(f'        default="{tx_type}", alias="transactionType"')
        lines.append("    )")

        # Add brokerage with appropriate type
        lines.append(f"    brokerage: {brokerage_type}")

        # Add type-specific fields
        if top_level_specific:
            lines.append("")
            for field, info in sorted(top_level_specific.items()):
                python_type = info.get("python_type", "Any")
                snake_field = self._to_snake_case(field)

                is_required = info.get("is_required", False)
                if is_required:
                    if snake_field != field:
                        lines.append(
                            f'    {snake_field}: {python_type} = Field(alias="{field}")'
                        )
                    else:
                        lines.append(f"    {field}: {python_type}")
                else:
                    if "| None" not in python_type:
                        python_type = f"{python_type} | None"
                    if snake_field != field:
                        lines.append(
                            f'    {snake_field}: {python_type} = Field(default=None, alias="{field}")'
                        )
                    else:
                        lines.append(f"    {field}: {python_type} = None")

        lines.append("")
        lines.append("")

        return lines

    def _generate_pydantic_union(self) -> list[str]:
        """Generate discriminated union type for all transaction types."""
        lines: list[str] = []

        lines.append("# Discriminated union of all transaction types")
        lines.append("Transaction = Annotated[")
        lines.append("    Union[")

        for tx_type in self.type_names:
            class_name = self._sanitize_class_name(tx_type)
            lines.append(f'        Annotated[{class_name}, Tag("{tx_type}")],')

        lines.append("    ],")
        lines.append('    Discriminator("transaction_type"),')
        lines.append("]")
        lines.append("")

        return lines

    def generate_dataclass_models(self) -> str:
        """Generate dataclass model code."""
        lines: list[str] = []

        # Header and imports
        lines.append('"""Auto-generated transaction models from API analysis."""')
        lines.append("")
        lines.append("from dataclasses import dataclass, field")
        lines.append("from decimal import Decimal")
        lines.append("from typing import Any, Literal, Union")
        lines.append("")
        lines.append("")

        # TransactionType constants
        lines.append("class TransactionType:")
        lines.append('    """Known transaction type values from E*Trade API."""')
        lines.append("")
        for tx_type in self.type_names:
            enum_name = self._sanitize_enum_name(tx_type)
            lines.append(f'    {enum_name} = "{tx_type}"')
        lines.append("")
        lines.append("")

        # Collect base class fields
        base_fields = self._collect_base_fields()

        # Generate nested dataclasses (Product, BrokerageWithProduct, BrokerageWithoutProduct)
        nested_lines, types_with_product, _ = self._generate_dataclass_nested_models()
        lines.extend(nested_lines)

        # Generate base dataclass
        lines.extend(self._generate_dataclass_base(base_fields))

        # Generate subclasses for each transaction type
        for tx_type in self.type_names:
            lines.extend(
                self._generate_dataclass_subclass(tx_type, base_fields, types_with_product)
            )

        # Generate union type alias
        lines.extend(self._generate_dataclass_union())

        return "\n".join(lines)

    def _generate_dataclass_nested_models(self) -> tuple[list[str], list[str], list[str]]:
        """Generate nested dataclass models (Product, BrokerageWithProduct, BrokerageWithoutProduct).

        Returns (lines, types_with_product, types_without_product)
        """
        lines: list[str] = []

        # Categorize transaction types
        types_with_product, types_without_product = self._categorize_types_by_product()

        # Analyze if product fields are required when product is present
        product_requirements = self._analyze_nested_field_requirements(
            "brokerage.product", "brokerage.product."
        )

        # Collect product fields from types that have product
        all_product_fields: dict[str, dict[str, Any]] = {}
        for tx_type in types_with_product:
            type_coverage = self.within_type_coverage.get(tx_type, {})
            for fld, info in type_coverage.items():
                if fld.startswith("brokerage.product.") and info["status"] != "absent":
                    rel_field = fld.replace("brokerage.product.", "")
                    if "." not in rel_field and rel_field not in all_product_fields:
                        all_product_fields[rel_field] = info

        # Generate Product dataclass
        if all_product_fields:
            lines.append("@dataclass")
            lines.append("class Product:")
            lines.append('    """Product information within a brokerage transaction."""')
            lines.append("")

            required_fields = []
            optional_fields = []

            for fld, info in sorted(all_product_fields.items()):
                python_type = info.get("python_type", "Any")
                base_type = python_type.replace(" | None", "")
                is_required = product_requirements.get(fld, False)

                if is_required:
                    required_fields.append((fld, base_type))
                else:
                    optional_fields.append((fld, base_type))

            for fld, python_type in required_fields:
                lines.append(f"    {fld}: {python_type}")
            for fld, python_type in optional_fields:
                lines.append(f"    {fld}: {python_type} | None = None")

            lines.append("")
            lines.append("")

        # Get brokerage field requirements for each category
        with_product_fields = self._get_brokerage_field_requirements(types_with_product)
        without_product_fields = self._get_brokerage_field_requirements(types_without_product)

        # Generate BrokerageWithProduct
        lines.append("@dataclass")
        lines.append("class BrokerageWithProduct:")
        lines.append('    """Brokerage details for transactions with product info."""')
        lines.append("")

        # Required fields first
        for fld, info in sorted(with_product_fields.items()):
            if fld == "product":
                continue
            if info["is_required"]:
                lines.append(f"    {fld}: {info['python_type']}")

        # Optional fields
        for fld, info in sorted(with_product_fields.items()):
            if fld == "product":
                continue
            if not info["is_required"]:
                python_type = info["python_type"]
                if "| None" not in python_type:
                    python_type = f"{python_type} | None"
                lines.append(f"    {fld}: {python_type} = None")

        # Product is required in this variant
        lines.append("    product: Product = field(default_factory=Product)")
        lines.append("")
        lines.append("")

        # Generate BrokerageWithoutProduct
        lines.append("@dataclass")
        lines.append("class BrokerageWithoutProduct:")
        lines.append('    """Brokerage details for transactions without product info."""')
        lines.append("")

        # Required fields first
        for fld, info in sorted(without_product_fields.items()):
            if fld == "product":
                continue
            if info["is_required"]:
                lines.append(f"    {fld}: {info['python_type']}")

        # Optional fields
        for fld, info in sorted(without_product_fields.items()):
            if fld == "product":
                continue
            if not info["is_required"]:
                python_type = info["python_type"]
                if "| None" not in python_type:
                    python_type = f"{python_type} | None"
                lines.append(f"    {fld}: {python_type} = None")

        lines.append("")
        lines.append("")

        return lines, types_with_product, types_without_product

    def _generate_dataclass_base(
        self, base_fields: dict[str, dict[str, Any]]
    ) -> list[str]:
        """Generate base dataclass (without brokerage - varies by subclass)."""
        lines: list[str] = []

        lines.append("@dataclass")
        lines.append("class TransactionBase:")
        lines.append('    """Base class for all transaction types.')
        lines.append("")
        lines.append("    Note: brokerage field is defined in subclasses with the")
        lines.append("    appropriate type (BrokerageWithProduct or BrokerageWithoutProduct).")
        lines.append('    """')
        lines.append("")

        top_level = self._get_top_level_fields(base_fields)

        # Required fields first (exclude brokerage - it's defined in subclasses)
        for fld, info in sorted(top_level.items()):
            if fld == "brokerage":
                continue
            if info.get("is_required", True):
                python_type = info.get("python_type", "Any")
                snake = self._to_snake_case(fld)
                lines.append(f"    {snake}: {python_type}")

        # Optional fields with defaults
        for fld, info in sorted(top_level.items()):
            if fld == "brokerage":
                continue
            if not info.get("is_required", True):
                python_type = info.get("python_type", "Any")
                if "| None" not in python_type:
                    python_type = f"{python_type} | None"
                snake = self._to_snake_case(fld)
                lines.append(f"    {snake}: {python_type} = None")

        lines.append("")
        lines.append("    @property")
        lines.append("    def is_pending(self) -> bool:")
        lines.append('        """Check if transaction is pending."""')
        lines.append("        return self.post_date == 0 if hasattr(self, 'post_date') else False")
        lines.append("")
        lines.append("")

        return lines

    def _generate_dataclass_subclass(
        self,
        tx_type: str,
        base_fields: dict[str, dict[str, Any]],
        types_with_product: list[str],
    ) -> list[str]:
        """Generate dataclass subclass for a transaction type."""
        lines: list[str] = []

        class_name = self._sanitize_class_name(tx_type)
        specific_fields = self._collect_type_specific_fields(tx_type, base_fields)
        top_level_specific = self._get_top_level_fields(specific_fields)

        # Determine brokerage type based on whether this type has product
        has_product = tx_type in types_with_product
        brokerage_type = "BrokerageWithProduct" if has_product else "BrokerageWithoutProduct"

        lines.append("@dataclass")
        lines.append(f"class {class_name}(TransactionBase):")
        lines.append(f'    """Transaction type: {tx_type}"""')
        lines.append("")

        # Discriminator field
        lines.append(f'    transaction_type: Literal["{tx_type}"] = "{tx_type}"')

        # Brokerage field with appropriate type (uses field(default=None) since base class fields come first)
        lines.append(f"    brokerage: {brokerage_type} = field(default=None)  # type: ignore")

        # Required type-specific fields
        required_fields = [
            (f, i) for f, i in sorted(top_level_specific.items()) if i.get("is_required")
        ]
        for fld, info in required_fields:
            python_type = info.get("python_type", "Any")
            snake = self._to_snake_case(fld)
            lines.append(f"    {snake}: {python_type} = field(default=None)  # type: ignore")

        # Optional fields
        optional_fields = [
            (f, i) for f, i in sorted(top_level_specific.items()) if not i.get("is_required")
        ]
        for fld, info in optional_fields:
            python_type = info.get("python_type", "Any")
            if "| None" not in python_type:
                python_type = f"{python_type} | None"
            snake = self._to_snake_case(fld)
            lines.append(f"    {snake}: {python_type} = None")

        lines.append("")
        lines.append("")

        return lines

    def _generate_dataclass_union(self) -> list[str]:
        """Generate union type alias for dataclasses."""
        lines: list[str] = []

        class_names = [self._sanitize_class_name(t) for t in self.type_names]
        lines.append("# Union type of all transaction types")
        lines.append("Transaction = Union[")
        for name in class_names:
            lines.append(f"    {name},")
        lines.append("]")
        lines.append("")

        return lines

    def _to_snake_case(self, name: str) -> str:
        """Convert camelCase to snake_case."""
        result = []
        prev_was_upper = False
        for i, char in enumerate(name):
            if char.isupper():
                # Add underscore before uppercase if:
                # - Not at start
                # - Previous char wasn't uppercase (avoid URI -> u_r_i)
                # - OR next char is lowercase (handle XMLParser -> xml_parser)
                if (i > 0 and not prev_was_upper) or (
                    i > 0
                    and prev_was_upper
                    and i + 1 < len(name)
                    and name[i + 1].islower()
                ):
                    result.append("_")
                result.append(char.lower())
                prev_was_upper = True
            else:
                result.append(char)
                prev_was_upper = False
        return "".join(result)


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
    generate_models: bool = typer.Option(
        False,
        "--generate-models",
        "-g",
        help="Generate recommended Python model code from analysis.",
    ),
    model_format: str = typer.Option(
        "pydantic",
        "--model-format",
        help="Model format: 'pydantic' or 'dataclass'.",
    ),
    output_models: Path | None = typer.Option(
        None,
        "--output-models",
        help="Save generated models to a Python file.",
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

        # Generate Pydantic models
        etrade-cli dev analyze-transactions --generate-models

        # Generate and save dataclass models to file
        etrade-cli dev analyze-transactions -g --model-format dataclass --output-models models.py
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

    # === Generate Models ===
    if generate_models or output_models:
        # Build type counts for the generator
        type_counts = {tx_type: len(txs) for tx_type, txs in by_type.items()}

        generator = ModelGenerator(
            cross_type=cross_type,
            within_type_coverage=within_type_coverage,
            type_counts=type_counts,
        )

        # Validate format
        if model_format not in ("pydantic", "dataclass"):
            print_error(f"Unknown model format: {model_format}")
            print("Supported formats: pydantic, dataclass")
            raise typer.Exit(1)

        # Generate code
        if model_format == "pydantic":
            model_code = generator.generate_pydantic_models()
        else:
            model_code = generator.generate_dataclass_models()

        # Output
        if output_models:
            output_models.write_text(model_code)
            print_success(f"\nGenerated {model_format} models saved to {output_models}")
        else:
            print("\n" + "=" * 60)
            print(f"GENERATED {model_format.upper()} MODELS")
            print("=" * 60)
            print(model_code)
