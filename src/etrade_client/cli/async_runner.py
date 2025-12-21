"""Async command support for Typer."""

import asyncio
from collections.abc import Callable, Coroutine
from functools import wraps
from typing import Any


def async_command[T](f: Callable[..., Coroutine[Any, Any, T]]) -> Callable[..., T]:
    """Decorator to run async Typer commands.

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
        return asyncio.run(f(*args, **kwargs))

    return wrapper
