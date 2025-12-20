# etrade-client

A fully typed, async Python client library for E*Trade's APIs.

## Features

- **Fully typed** - Pydantic models for all API responses
- **Async/await** - Built on httpx for modern async Python
- **OAuth 1.0a** - Complete authentication flow with token persistence
- **Comprehensive** - Accounts, Market Data, and Orders APIs

## Installation

```bash
uv add etrade-client
```

## Quick Start

```python
import asyncio
from etrade_client import ETradeClient

async def main():
    # Create client (reads from ETRADE_CONSUMER_KEY and ETRADE_CONSUMER_SECRET)
    client = ETradeClient.from_env(sandbox=True)

    # First time: authenticate via OAuth
    if not client.load_token():
        request_token = await client.auth.get_request_token()
        print(f"Visit: {request_token.authorization_url}")
        verifier = input("Enter verifier code: ")
        await client.auth.get_access_token(verifier)
        client.save_token()
    else:
        # Token loaded, renew it
        await client.renew_token()

    # List accounts
    accounts = await client.accounts.list_accounts()
    for account in accounts.accounts:
        print(f"{account.account_id}: {account.account_desc}")

    # Get quotes
    quotes = await client.market.get_quotes(["AAPL", "MSFT"])
    for quote in quotes.quotes:
        print(f"{quote.symbol}: ${quote.last_trade}")

asyncio.run(main())
```

## Configuration

Set environment variables:

```bash
export ETRADE_CONSUMER_KEY="your_consumer_key"
export ETRADE_CONSUMER_SECRET="your_consumer_secret"
```

Or create a config file at `~/.config/etrade-client/config.json`:

```json
{
    "consumer_key": "your_consumer_key",
    "consumer_secret": "your_consumer_secret"
}
```

## API Reference

### Accounts

```python
# List all accounts
accounts = await client.accounts.list_accounts()

# Get account balance
balance = await client.accounts.get_balance(account_id_key)

# Get portfolio positions
portfolio = await client.accounts.get_portfolio(account_id_key)
```

### Market Data

```python
# Get quotes (up to 25 symbols)
quotes = await client.market.get_quotes(["AAPL", "MSFT", "GOOGL"])

# Get option expiration dates
expires = await client.market.get_option_expire_dates("AAPL")

# Get options chain
chain = await client.market.get_option_chains("AAPL", expires[0].expiry_date)
```

### Orders

```python
# List orders
orders = await client.orders.list_orders(account_id_key)

# Build and preview an order
order = client.orders.build_equity_order(
    symbol="AAPL",
    action="BUY",
    quantity=10,
    order_type="LIMIT",
    limit_price=150.00,
)
preview = await client.orders.preview_order(account_id_key, order)

# Place the order
result = await client.orders.place_order(
    account_id_key,
    order,
    [{"previewId": pid} for pid in preview.preview.preview_id_values],
)

# Cancel an order
await client.orders.cancel_order(account_id_key, order_id)
```

## Development

```bash
# Install dependencies
uv sync --all-extras

# Format code
uv run ruff format .

# Lint code
uv run ruff check --fix .

# Type check
uv run ty check src/
```

## License

MIT
