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
    1. Loads credentials from config file with env var overrides
    2. Uses environment-specific token storage (XDG_DATA_HOME)
    3. Manages connection pooling lifecycle

    Credential loading priority:
    1. Environment-specific config file (~/.config/etrade-cli/{sandbox,production}.json)
    2. Environment variables override file values (ETRADE_CONSUMER_KEY, ETRADE_CONSUMER_SECRET)

    Usage:
        async with get_client(cli_config) as client:
            result = await client.accounts.list_accounts()
    """
    # Load credentials using CLI config (file + env var overrides)
    consumer_key, consumer_secret = config.load_credentials()

    # Create ETradeConfig with loaded credentials
    etrade_config = ETradeConfig(
        consumer_key=consumer_key,
        consumer_secret=consumer_secret,
        sandbox=config.sandbox,
    )

    # Use CLI's token path (environment-specific, in XDG_DATA_HOME)
    token_store = TokenStore(path=config.token_path)

    # Create client with token store
    client = ETradeClient(etrade_config, token_store=token_store)

    # Load any saved token
    client.load_token()

    async with client:
        yield client
