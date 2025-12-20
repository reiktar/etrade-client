"""E*Trade API client library.

A fully typed, async Python client for E*Trade's APIs.

Example:
    from etrade_client import ETradeClient, ETradeConfig

    # Create client from environment variables
    client = ETradeClient.from_env(sandbox=True)

    # Or with explicit config
    config = ETradeConfig(
        consumer_key="your_key",
        consumer_secret="your_secret",
        sandbox=True,
    )
    client = ETradeClient(config)

    # Authenticate (first time)
    request_token = await client.auth.get_request_token()
    print(f"Visit: {request_token.authorization_url}")
    verifier = input("Enter verifier code: ")
    await client.auth.get_access_token(verifier)
    client.save_token()

    # Subsequent runs - load saved token
    if client.load_token():
        await client.renew_token()  # Extend expiration

    # Use the client
    accounts = await client.accounts.list_accounts()
    quotes = await client.market.get_quotes(["AAPL"])
    orders = await client.orders.list_orders(accounts.accounts[0].account_id_key)
"""

from etrade_client.builders import (
    EquityOrderBuilder,
    MarketSession,
    OptionOrderBuilder,
    OptionType,
    OrderAction,
    OrderTerm,
    OrderType,
    PriceType,  # Backwards compatibility alias for OrderType
)
from etrade_client.client import ETradeClient
from etrade_client.config import ETradeConfig
from etrade_client.exceptions import (
    ETradeAPIError,
    ETradeAuthError,
    ETradeError,
    ETradeRateLimitError,
    ETradeTokenError,
    ETradeValidationError,
)

__version__ = "0.1.0"

__all__ = [
    # Builders
    "EquityOrderBuilder",
    "OptionOrderBuilder",
    # Enums (commonly used)
    "MarketSession",
    "OptionType",
    "OrderAction",
    "OrderTerm",
    "OrderType",
    "PriceType",  # Backwards compatibility alias for OrderType
    # Main client
    "ETradeClient",
    "ETradeConfig",
    # Exceptions
    "ETradeAPIError",
    "ETradeAuthError",
    "ETradeError",
    "ETradeRateLimitError",
    "ETradeTokenError",
    "ETradeValidationError",
]
