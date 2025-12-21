# etrade-client

A fully typed, async Python client library for E\*Trade's APIs.

[![Python 3.14+](https://img.shields.io/badge/python-3.14+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## Features

- **Fully typed** - Pydantic models for all API responses with strict validation
- **Async/await** - Built on httpx for modern async Python
- **OAuth 1.0a** - Complete authentication flow with token persistence
- **Connection pooling** - Efficient HTTP connection reuse
- **Auto-retry** - Automatic retry with backoff on rate limits
- **Type-safe builders** - Fluent order builders for equity and options
- **Pagination iterators** - Async generators for paginated endpoints
- **CLI included** - Full-featured command-line interface

## Installation

```bash
# Library only
uv add etrade-client

# With CLI
uv add etrade-client[cli]

# Development
uv add etrade-client[dev]
```

## Quick Start: Library

```python
import asyncio
from etrade_client import ETradeClient

async def main():
    async with ETradeClient.from_env(sandbox=True) as client:
        # First time: authenticate via OAuth
        if not client.load_token():
            request_token = await client.auth.get_request_token()
            print(f"Visit: {request_token.authorization_url}")
            verifier = input("Enter verifier code: ")
            await client.auth.get_access_token(verifier)
            client.save_token()
        else:
            await client.renew_token()

        # List accounts
        accounts = await client.accounts.list_accounts()
        for account in accounts.accounts:
            print(f"{account.account_id_key}: {account.account_desc}")

        # Get quotes
        quotes = await client.market.get_quotes(["AAPL", "MSFT"])
        for quote in quotes.quotes:
            all_data = quote.all_data
            print(f"{quote.product.symbol}: ${all_data.last_trade:,.2f}")

asyncio.run(main())
```

## Quick Start: CLI

```bash
# Create config file for sandbox
mkdir -p ~/.config/etrade-cli
cat > ~/.config/etrade-cli/sandbox.json << 'EOF'
{
    "consumer_key": "your_sandbox_key",
    "consumer_secret": "your_sandbox_secret"
}
EOF

# Authenticate
etrade-cli auth login

# List accounts
etrade-cli accounts list

# Get quotes
etrade-cli market quote AAPL MSFT GOOGL

# View portfolio
etrade-cli accounts portfolio <account-id>

# List orders
etrade-cli orders list <account-id>
```

## Configuration

### Library

```bash
export ETRADE_CONSUMER_KEY="your_consumer_key"
export ETRADE_CONSUMER_SECRET="your_consumer_secret"
```

Or create `~/.config/etrade-client/config.json`:

```json
{
    "consumer_key": "your_consumer_key",
    "consumer_secret": "your_consumer_secret"
}
```

### CLI

The CLI uses environment-specific config files:

```
~/.config/etrade-cli/sandbox.json      # Sandbox credentials
~/.config/etrade-cli/production.json   # Production credentials
```

Environment variables (`ETRADE_CONSUMER_KEY`, `ETRADE_CONSUMER_SECRET`) override config file values. See [CLI Reference](docs/cli/README.md) for details.

## Documentation

| Documentation | Description |
|--------------|-------------|
| [API Reference](docs/api/README.md) | Complete library API documentation |
| [CLI Reference](docs/cli/README.md) | Command-line interface guide |
| [Contributing](CONTRIBUTING.md) | Development and contribution guide |

## API Overview

### Accounts

```python
# List accounts
accounts = await client.accounts.list_accounts()

# Get balance
balance = await client.accounts.get_balance(account_id)

# Get portfolio
portfolio = await client.accounts.get_portfolio(account_id)

# Iterate transactions (pagination handled automatically)
async for tx in client.accounts.iter_transactions(account_id):
    print(f"{tx.transaction_date}: {tx.description}")
```

### Market Data

```python
# Get quotes (up to 25 symbols)
quotes = await client.market.get_quotes(["AAPL", "MSFT"])

# Get option expiration dates
expires = await client.market.get_option_expire_dates("AAPL")

# Get options chain
chain = await client.market.get_option_chains("AAPL", expires[0].expiry_date)

# Symbol lookup
results = await client.market.lookup("Apple")
```

### Orders

```python
from etrade_client import EquityOrderBuilder, OptionOrderBuilder, OptionType

# Build equity order with fluent API
order = (
    EquityOrderBuilder("AAPL")
    .buy(100)
    .limit(150.00)
    .good_until_cancel()
    .build()
)

# Preview and place
preview = await client.orders.preview_order(account_id, order)
result = await client.orders.place_order(account_id, order, preview.preview_ids)

# Build option order
option_order = (
    OptionOrderBuilder("AAPL", "2025-01-17", 150.00, OptionType.CALL)
    .buy_to_open(5)
    .limit(2.50)
    .build()
)

# List and cancel orders
orders = await client.orders.list_orders(account_id)
await client.orders.cancel_order(account_id, order_id)
```

### Alerts

```python
# List alerts
alerts = await client.alerts.list_alerts(count=25)

# Get alert details
details = await client.alerts.get_alert_details(alert_id)

# Delete alerts
await client.alerts.delete_alerts([alert_id1, alert_id2])
```

## CLI Overview

```
etrade-cli [OPTIONS] COMMAND

Commands:
  auth          Authentication commands
  accounts      Account information
  market        Market data and quotes
  orders        Order management
  alerts        Alert management
  transactions  Transaction history

Options:
  --sandbox / --production  Use sandbox or production environment
  --verbose                 Enable verbose output
  --config-dir PATH         Config directory
```

## License

MIT
