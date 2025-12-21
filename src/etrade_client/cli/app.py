"""Main Typer application."""

import os
from pathlib import Path

import typer

from etrade_client.cli.config import CLIConfig

# Create main app
app = typer.Typer(
    name="etrade-cli",
    help="E*Trade API command-line interface.",
    no_args_is_help=True,
)


def _get_config_dir() -> Path:
    """Get XDG-compliant config directory for CLI."""
    xdg_config = os.environ.get("XDG_CONFIG_HOME")
    if xdg_config:
        return Path(xdg_config) / "etrade-cli"
    return Path.home() / ".config" / "etrade-cli"


@app.callback()
def main(
    ctx: typer.Context,
    sandbox: bool = typer.Option(
        True,
        "--sandbox/--production",
        "-s/-p",
        help="Use sandbox (default) or production environment.",
        envvar="ETRADE_SANDBOX",
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Enable verbose output.",
    ),
    config_dir: Path | None = typer.Option(
        None,
        "--config-dir",
        "-c",
        help="Config directory (default: ~/.config/etrade-cli).",
        envvar="ETRADE_CLI_CONFIG_DIR",
    ),
) -> None:
    """E*Trade API command-line interface.

    Use --production to connect to the live E*Trade API.
    Default is sandbox mode for testing.
    """
    ctx.obj = CLIConfig(
        sandbox=sandbox,
        verbose=verbose,
        config_dir=config_dir or _get_config_dir(),
    )
