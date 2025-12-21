"""Authentication commands."""

import webbrowser

import typer

from etrade_client.auth import TokenStore
from etrade_client.cli.async_runner import async_command
from etrade_client.cli.client_factory import get_client
from etrade_client.cli.config import CLIConfig
from etrade_client.cli.formatters import console, print_error, print_info, print_success
from etrade_client.config import ETradeConfig

app = typer.Typer(no_args_is_help=True)


@app.command("login")
@async_command
async def login(
    ctx: typer.Context,
    no_browser: bool = typer.Option(
        False,
        "--no-browser",
        help="Don't open browser automatically.",
    ),
) -> None:
    """Authenticate with E*Trade OAuth.

    This command starts the OAuth flow:
    1. Opens browser for E*Trade login
    2. Prompts for verification code
    3. Saves access token for future use

    Credentials are loaded from:
    1. Config file (~/.config/etrade-cli/{sandbox,production}.json)
    2. Environment variables (override file values)
    """
    config: CLIConfig = ctx.obj

    try:
        consumer_key, consumer_secret = config.load_credentials()
    except ValueError as e:
        print_error(str(e))
        print_info(f"Create config file at: {config.credentials_path}")
        print_info("Or set ETRADE_CONSUMER_KEY and ETRADE_CONSUMER_SECRET environment variables")
        raise typer.Exit(1) from None

    # Create ETradeConfig and auth
    etrade_config = ETradeConfig(
        consumer_key=consumer_key,
        consumer_secret=consumer_secret,
        sandbox=config.sandbox,
    )

    from etrade_client.auth import ETradeAuth

    auth = ETradeAuth(etrade_config)

    # Step 1: Get request token
    print_info(f"Starting OAuth flow for {config.environment}...")
    request_token = await auth.get_request_token()

    # Step 2: Open browser or show URL
    if no_browser:
        console.print("\nOpen this URL in your browser:")
        console.print(f"[link]{request_token.authorization_url}[/link]")
    else:
        print_info("Opening browser for authorization...")
        webbrowser.open(request_token.authorization_url)
        console.print("\n[dim]If browser didn't open, visit:[/dim]")
        console.print(f"[link]{request_token.authorization_url}[/link]")

    # Step 3: Get verifier from user
    console.print()
    verifier = typer.prompt("Enter the verification code from E*Trade")

    # Step 4: Exchange for access token
    print_info("Exchanging verification code for access token...")
    access_token = await auth.get_access_token(verifier.strip())

    # Step 5: Save token to data directory
    token_store = TokenStore(path=config.token_path)
    token_store.save(access_token)

    print_success("Authenticated successfully!")
    print_info(f"Token saved to: {config.token_path}")


@app.command("status")
def status(ctx: typer.Context) -> None:
    """Check authentication status and configuration paths."""
    config: CLIConfig = ctx.obj

    token_store = TokenStore(path=config.token_path)

    console.print(f"Environment: [bold]{config.environment}[/bold]")
    console.print()
    console.print("[dim]Configuration:[/dim]")
    console.print(f"  Credentials: {config.credentials_path}")
    console.print(f"  Token: {config.token_path}")
    console.print()

    # Check credentials
    if config.has_credentials():
        print_success("Credentials found")
    else:
        print_info(f"No credentials - create {config.credentials_path} or set env vars")

    # Check token
    if token_store.has_token():
        print_success("Token found - you are authenticated")
        print_info("Note: Tokens expire at midnight US Eastern time")
    else:
        print_info("No token - run 'etrade-cli auth login' to authenticate")


@app.command("renew")
@async_command
async def renew(ctx: typer.Context) -> None:
    """Renew the current access token.

    E*Trade tokens expire at midnight US Eastern time.
    Call this to extend the token for another day.
    """
    config: CLIConfig = ctx.obj

    async with get_client(config) as client:
        if not client.is_authenticated:
            print_error("Not authenticated. Run 'etrade-cli auth login' first.")
            raise typer.Exit(1)

        print_info("Renewing access token...")
        await client.renew_token()
        client.save_token()
        print_success("Token renewed successfully!")


@app.command("logout")
@async_command
async def logout(
    ctx: typer.Context,
    revoke: bool = typer.Option(
        True,
        "--revoke/--no-revoke",
        help="Revoke token on E*Trade server before clearing.",
    ),
) -> None:
    """Log out and clear saved token.

    By default, also revokes the token on E*Trade's server.
    Use --no-revoke to only clear the local token file.
    """
    config: CLIConfig = ctx.obj

    token_store = TokenStore(path=config.token_path)

    if not token_store.has_token():
        print_info("No token to clear.")
        return

    if revoke:
        try:
            async with get_client(config) as client:
                if client.is_authenticated:
                    print_info("Revoking token on E*Trade server...")
                    await client.revoke_token()
        except Exception as e:
            print_error(f"Failed to revoke token: {e}")
            print_info("Clearing local token anyway...")

    token_store.clear()
    print_success(f"Logged out from {config.environment}.")


@app.command("paths")
def paths(ctx: typer.Context) -> None:
    """Show configuration and data paths for current environment."""
    config: CLIConfig = ctx.obj

    console.print(f"[bold]Environment:[/bold] {config.environment}")
    console.print()
    console.print("[bold]Configuration (credentials):[/bold]")
    console.print(f"  Directory: {config.config_dir}")
    console.print(f"  File: {config.credentials_path}")
    exists = "[green]exists[/green]" if config.credentials_path.exists() else "[dim]not found[/dim]"
    console.print(f"  Status: {exists}")
    console.print()
    console.print("[bold]Data (tokens):[/bold]")
    console.print(f"  Directory: {config.data_dir}")
    console.print(f"  File: {config.token_path}")
    exists = "[green]exists[/green]" if config.token_path.exists() else "[dim]not found[/dim]"
    console.print(f"  Status: {exists}")
