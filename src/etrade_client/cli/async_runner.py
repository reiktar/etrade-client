"""Async command support for Typer."""

import asyncio
from collections.abc import Callable, Coroutine
from functools import wraps
from typing import Any

import typer

from etrade_client.exceptions import ETradeAPIError


def _is_token_invalid_error(e: ETradeAPIError) -> bool:
    """Check if the error is due to an invalid token (expired or rejected)."""
    msg = str(e.message).lower()
    return "token_expired" in msg or "token_rejected" in msg


async def _handle_token_invalid(ctx: typer.Context) -> None:
    """Handle invalid token by prompting for re-authentication."""
    from etrade_client.cli.formatters import console, print_error, print_info

    print_error("Your session is invalid or has expired.")
    print_info("E*Trade tokens expire at midnight US Eastern time.")
    console.print()

    # Ask if user wants to re-authenticate
    re_auth = typer.confirm("Would you like to re-authenticate now?", default=True)

    if re_auth:
        # Import and run login flow
        # login is wrapped by @async_command, access the original async fn via __wrapped__
        from etrade_client.cli.commands.auth import login

        console.print()
        # Run login with the same context (use __wrapped__ to get the async function)
        await login.__wrapped__(ctx, no_browser=False)
    else:
        print_info("Run 'etrade-cli auth login' when ready to re-authenticate.")
        raise typer.Exit(1)


def async_command[T](f: Callable[..., Coroutine[Any, Any, T]]) -> Callable[..., T]:
    """Decorator to run async Typer commands.

    Handles token expiration errors by prompting for re-authentication.

    Usage:
        @app.command()
        @async_command
        async def my_command(ctx: typer.Context):
            async with get_client(ctx.obj) as client:
                result = await client.accounts.list_accounts()
                ...
    """

    @wraps(f)
    def wrapper(*args: Any, **kwargs: Any) -> T:
        async def run_with_error_handling() -> T:
            try:
                return await f(*args, **kwargs)
            except ETradeAPIError as e:
                if _is_token_invalid_error(e):
                    # Find the typer.Context in args or kwargs
                    ctx = None
                    for arg in args:
                        if isinstance(arg, typer.Context):
                            ctx = arg
                            break
                    if ctx is None:
                        # Check kwargs (typer passes ctx as keyword arg)
                        ctx = kwargs.get("ctx")
                    if ctx is not None:
                        await _handle_token_invalid(ctx)
                        # If we get here, user re-authenticated successfully
                        # Re-run the original command
                        return await f(*args, **kwargs)
                # Re-raise if not token expired or no context found
                raise

        return asyncio.run(run_with_error_handling())

    return wrapper
