"""Main Typer application."""

from pathlib import Path

import typer

from etrade_client.cli.config import CLIConfig, _default_config_dir, _default_data_dir

# Create main app
app = typer.Typer(
    name="etrade-cli",
    help="E*Trade API command-line interface.",
    no_args_is_help=True,
)


@app.callback()
def main(
    ctx: typer.Context,
    sandbox: bool = typer.Option(
        False,
        "--sandbox/--production",
        "-s/-p",
        help="Use sandbox or production (default) environment.",
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
        help="Config directory for credentials (default: ~/.config/etrade-cli).",
        envvar="ETRADE_CLI_CONFIG_DIR",
    ),
    data_dir: Path | None = typer.Option(
        None,
        "--data-dir",
        "-d",
        help="Data directory for tokens (default: ~/.local/share/etrade-cli).",
        envvar="ETRADE_CLI_DATA_DIR",
    ),
) -> None:
    """E*Trade API command-line interface.

    Use --production to connect to the live E*Trade API.
    Default is sandbox mode for testing.

    Configuration files are stored in XDG-compliant locations:
    - Credentials: ~/.config/etrade-cli/{sandbox,production}.json
    - Tokens: ~/.local/share/etrade-cli/{sandbox,production}-token.json

    Environment variables (ETRADE_CONSUMER_KEY, ETRADE_CONSUMER_SECRET)
    override values from config files.
    """
    ctx.obj = CLIConfig(
        sandbox=sandbox,
        verbose=verbose,
        config_dir=config_dir or _default_config_dir(),
        data_dir=data_dir or _default_data_dir(),
    )
