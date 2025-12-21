"""Client factory for CLI commands."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

from etrade_client.auth import TokenStore
from etrade_client.client import ETradeClient
from etrade_client.config import ETradeConfig

if TYPE_CHECKING:
    from etrade_client.cli.config import CLIConfig


@asynccontextmanager
async def get_client(config: CLIConfig) -> AsyncGenerator[ETradeClient]:
    """Create and configure an ETradeClient for CLI use.

    This context manager:
    1. Loads credentials from environment or config file
    2. Uses environment-specific token storage
    3. Manages connection pooling lifecycle

    Usage:
        async with get_client(cli_config) as client:
            result = await client.accounts.list_accounts()
    """
    # Load credentials (env takes precedence over file)
    etrade_config = ETradeConfig.load(sandbox=config.sandbox)

    # Use CLI's token path (environment-specific)
    token_store = TokenStore(path=config.token_path)

    # Create client with token store
    client = ETradeClient(etrade_config, token_store=token_store)

    # Load any saved token
    client.load_token()

    async with client:
        yield client
