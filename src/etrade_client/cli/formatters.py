"""Output formatters for CLI commands."""

import csv
import io
import json
from collections.abc import Sequence
from typing import Any, cast

from pydantic import BaseModel
from rich.console import Console
from rich.table import Table

from etrade_client.cli.config import OutputFormat

console = Console()
error_console = Console(stderr=True)


def format_output(
    data: BaseModel | Sequence[BaseModel] | dict[str, Any] | list[dict[str, Any]],
    output_format: OutputFormat,
    *,
    title: str | None = None,
    columns: list[str] | None = None,
) -> None:
    """Format and print output in the specified format.

    Args:
        data: Data to format (Pydantic model, list of models, or dict/list)
        output_format: Output format (table, json, csv)
        title: Optional title for table output
        columns: Optional column names to include (for table/csv)
    """
    # Convert all input types to list[dict[str, Any]]
    converted: list[dict[str, Any]]
    if isinstance(data, BaseModel):
        converted = [data.model_dump(by_alias=True, exclude_none=True)]
    elif isinstance(data, dict):
        converted = [cast(dict[str, Any], data)]  # type: ignore[redundant-cast]  # needed for ty
    elif isinstance(data, Sequence) and not isinstance(data, str):
        converted = [
            item.model_dump(by_alias=True, exclude_none=True)
            if isinstance(item, BaseModel)
            else item
            for item in data
        ]
    else:
        converted = []

    if output_format == OutputFormat.JSON:
        _format_json(converted)
    elif output_format == OutputFormat.CSV:
        _format_csv(converted, columns)
    else:
        _format_table(converted, title, columns)


def _format_json(data: list[dict[str, Any]]) -> None:
    """Format as JSON."""
    if len(data) == 1:
        console.print_json(json.dumps(data[0], default=str))
    else:
        console.print_json(json.dumps(data, default=str))


def _format_csv(data: list[dict[str, Any]], columns: list[str] | None) -> None:
    """Format as CSV."""
    if not data:
        return

    # Get all keys from first item if columns not specified
    if columns is None:
        columns = list(data[0].keys())

    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=columns, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(data)
    console.print(output.getvalue(), end="")


def _snake_to_title(s: str) -> str:
    """Convert snake_case to Title Case for table headers."""
    return " ".join(word.capitalize() for word in s.split("_"))


def _format_table(
    data: list[dict[str, Any]],
    title: str | None,
    columns: list[str] | None,
) -> None:
    """Format as rich table."""
    if not data:
        console.print("[dim]No data[/dim]")
        return

    # Get columns from first item if not specified
    if columns is None:
        columns = list(data[0].keys())

    table = Table(title=title, show_header=True, header_style="bold")

    # Convert snake_case column names to Title Case for display
    for col in columns:
        table.add_column(_snake_to_title(col))

    for row in data:
        table.add_row(*[str(row.get(col, "")) for col in columns])

    console.print(table)


def print_error(message: str) -> None:
    """Print an error message to stderr."""
    error_console.print(f"[red]Error:[/red] {message}")


def print_success(message: str) -> None:
    """Print a success message."""
    console.print(f"[green]✓[/green] {message}")


def print_warning(message: str) -> None:
    """Print a warning message."""
    console.print(f"[yellow]Warning:[/yellow] {message}")


def print_info(message: str) -> None:
    """Print an info message."""
    console.print(f"[blue]i[/blue] {message}")
