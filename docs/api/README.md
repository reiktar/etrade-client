# etrade-client API Reference

This documentation covers the Python library for programmatic access to E\*Trade's APIs.

## Table of Contents

1. [Getting Started](#getting-started)
2. [Authentication](authentication.md)
3. [Accounts API](accounts.md)
4. [Market Data API](market.md)
5. [Orders API](orders.md)
6. [Alerts API](alerts.md)
7. [Advanced Topics](advanced.md)

## Getting Started

### Installation

```bash
uv add etrade-client
```

### Prerequisites

You need E\*Trade API credentials:

1. Log in to [E\*Trade Developer](https://developer.etrade.com)
2. Create an application to get your Consumer Key and Secret
3. Note: Sandbox and Production use different credentials

### Configuration

**Option 1: Environment Variables (Recommended)**

```bash
export ETRADE_CONSUMER_KEY="your_consumer_key"
export ETRADE_CONSUMER_SECRET="your_consumer_secret"
```

**Option 2: Config File**

Create `~/.config/etrade-client/config.json`:

```json
{
    "consumer_key": "your_consumer_key",
    "consumer_secret": "your_consumer_secret"
}
```

**Option 3: Explicit Configuration**

```python
from etrade_client import ETradeClient, ETradeConfig

config = ETradeConfig(
    consumer_key="your_key",
    consumer_secret="your_secret",
    sandbox=True,  # False for production
)
client = ETradeClient(config)
```

### Basic Usage

```python
import asyncio
from etrade_client import ETradeClient

async def main():
    # Use context manager for connection pooling
    async with ETradeClient.from_env(sandbox=True) as client:
        # Handle authentication
        if not client.load_token():
            request_token = await client.auth.get_request_token()
            print(f"Visit: {request_token.authorization_url}")
            verifier = input("Enter verifier code: ")
            await client.auth.get_access_token(verifier)
            client.save_token()
        else:
            # Renew existing token
            await client.renew_token()

        # Now use the APIs
        accounts = await client.accounts.list_accounts()
        quotes = await client.market.get_quotes(["AAPL"])

asyncio.run(main())
```

## Client Lifecycle

### Context Manager (Recommended)

The context manager handles connection pooling automatically:

```python
async with ETradeClient(config) as client:
    # Connection pool is open
    await client.accounts.list_accounts()
# Connection pool is closed
```

### Explicit Lifecycle

```python
client = ETradeClient(config)
await client.open()  # Open connection pool
try:
    await client.accounts.list_accounts()
finally:
    await client.close()  # Close connection pool
```

### Shared HTTP Client

For integrations with other httpx-based libraries:

```python
import httpx

# Create shared client
http_client = httpx.AsyncClient(timeout=30.0)

# ETradeClient uses shared pool, doesn't close it
client = ETradeClient(config, http_client=http_client)
await client.accounts.list_accounts()

# You manage the shared client's lifecycle
await http_client.aclose()
```

## Error Handling

All exceptions inherit from `ETradeError`:

```python
from etrade_client import (
    ETradeError,
    ETradeAPIError,
    ETradeAuthError,
    ETradeRateLimitError,
    ETradeTokenError,
    ETradeValidationError,
)

try:
    await client.market.get_quotes(["AAPL"])
except ETradeRateLimitError:
    # Automatic retry with backoff is built-in
    # This only raises if all retries exhausted
    pass
except ETradeAuthError:
    # Token expired or invalid
    await client.auth.get_request_token()  # Re-authenticate
except ETradeAPIError as e:
    # Other API errors
    print(f"API error: {e.code} - {e.message}")
except ETradeError:
    # Base exception for all library errors
    pass
```

## API Modules

The client provides access to four API modules:

| Module | Description |
|--------|-------------|
| `client.accounts` | Account balances, portfolios, transactions |
| `client.market` | Quotes, option chains, symbol lookup |
| `client.orders` | Order preview, placement, cancellation |
| `client.alerts` | Alert listing, details, deletion |

See individual documentation pages for complete method references.

## Sandbox vs Production

```python
# Sandbox (default) - for development and testing
client = ETradeClient.from_env(sandbox=True)

# Production - real money, real trades
client = ETradeClient.from_env(sandbox=False)
```

Use sandbox for development. Production credentials are different and require additional E\*Trade approval.

## Next Steps

- [Authentication Guide](authentication.md) - OAuth flow details
- [Accounts API](accounts.md) - Account data access
- [Market Data API](market.md) - Quotes and options
- [Orders API](orders.md) - Trading operations
- [Advanced Topics](advanced.md) - Caching, telemetry, connection pooling
