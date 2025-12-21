# Advanced Topics

This guide covers advanced configuration and integration patterns.

## Connection Pooling

The library supports HTTP connection pooling for better performance.

### Context Manager (Recommended)

```python
async with ETradeClient(config) as client:
    # Connection pool is active
    await client.accounts.list_accounts()
    await client.market.get_quotes(["AAPL"])
# Pool closed automatically
```

### Explicit Lifecycle

```python
client = ETradeClient(config)
await client.open()  # Open pool
try:
    await client.accounts.list_accounts()
finally:
    await client.close()  # Close pool
```

### Shared HTTP Client

Share an httpx client across multiple integrations:

```python
import httpx

# Create shared client with custom settings
http_client = httpx.AsyncClient(
    timeout=httpx.Timeout(30.0),
    limits=httpx.Limits(max_connections=100),
)

# ETradeClient uses shared pool
client = ETradeClient(config, http_client=http_client)

# You manage the shared client's lifecycle
# Don't use context manager if you want to control the client externally
await client.accounts.list_accounts()

# When done with all clients
await http_client.aclose()
```

## Rate Limiting

The library includes automatic retry with exponential backoff for rate limits.

### Built-in Behavior

When E\*Trade returns a 429 (rate limit) response:
1. Library waits with exponential backoff
2. Retries the request (up to 3 times by default)
3. Raises `ETradeRateLimitError` if all retries fail

### Best Practices

```python
from etrade_client import ETradeRateLimitError

# Batch multiple symbols in single request
symbols = ["AAPL", "MSFT", "GOOGL", "AMZN", "META"]  # Up to 25
quotes = await client.market.get_quotes(symbols)

# Handle rate limit exhaustion
try:
    quotes = await client.market.get_quotes(symbols)
except ETradeRateLimitError:
    print("Rate limit exceeded, try again later")
```

## Response Caching

Add caching using the `hishel` library with the shared HTTP client pattern.

### Installation

```bash
uv add hishel
```

### Implementation

```python
import hishel
import httpx
from etrade_client import ETradeClient, ETradeConfig

# Create cache storage
storage = hishel.AsyncInMemoryStorage(ttl=60)  # 60 second TTL

# Create caching transport
transport = hishel.AsyncCacheTransport(
    transport=httpx.AsyncHTTPTransport(),
    storage=storage,
)

# Create HTTP client with caching
http_client = httpx.AsyncClient(transport=transport)

# Use with ETradeClient
config = ETradeConfig.from_env(sandbox=True)
client = ETradeClient(config, http_client=http_client)

# Subsequent requests for same data will be cached
quotes = await client.market.get_quotes(["AAPL"])
quotes = await client.market.get_quotes(["AAPL"])  # Served from cache
```

### File-Based Cache

```python
import hishel
import httpx
from pathlib import Path

# Cache to disk
storage = hishel.AsyncFileStorage(
    base_path=Path.home() / ".cache" / "etrade",
    ttl=300,  # 5 minutes
)

transport = hishel.AsyncCacheTransport(
    transport=httpx.AsyncHTTPTransport(),
    storage=storage,
)

http_client = httpx.AsyncClient(transport=transport)
client = ETradeClient(config, http_client=http_client)
```

### Cache Considerations

- **Don't cache order operations** - Always use fresh data for orders
- **Short TTL for quotes** - Market data changes frequently
- **Longer TTL for static data** - Account list, option expiry dates

## OpenTelemetry Integration

Add distributed tracing using OpenTelemetry's httpx instrumentation.

### Installation

```bash
uv add opentelemetry-instrumentation-httpx
```

### Global Instrumentation

Instrument all httpx clients:

```python
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import ConsoleSpanExporter, BatchSpanProcessor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentation
from etrade_client import ETradeClient

# Set up tracing
provider = TracerProvider()
processor = BatchSpanProcessor(ConsoleSpanExporter())
provider.add_span_processor(processor)
trace.set_tracer_provider(provider)

# Instrument all httpx clients
HTTPXClientInstrumentation().instrument()

# All ETradeClient requests will now be traced
async with ETradeClient.from_env() as client:
    await client.market.get_quotes(["AAPL"])
```

### Targeted Instrumentation

Instrument only specific clients:

```python
import httpx
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentation
from etrade_client import ETradeClient

# Create and instrument specific client
http_client = httpx.AsyncClient()
HTTPXClientInstrumentation.instrument_client(http_client)

# Only this client is traced
client = ETradeClient(config, http_client=http_client)
```

### Jaeger Export

```python
from opentelemetry.exporter.jaeger.thrift import JaegerExporter
from opentelemetry.sdk.trace.export import BatchSpanProcessor

exporter = JaegerExporter(
    agent_host_name="localhost",
    agent_port=6831,
)
provider.add_span_processor(BatchSpanProcessor(exporter))
```

## Custom Token Storage

Store tokens in a database or secrets manager instead of files.

### Token Store Interface

```python
from etrade_client.auth import TokenStore
from etrade_client.models.auth import AccessToken

class DatabaseTokenStore:
    """Store tokens in a database."""

    def __init__(self, db_connection):
        self.db = db_connection

    def save(self, token: AccessToken) -> None:
        self.db.execute(
            "INSERT OR REPLACE INTO tokens (id, token, secret) VALUES (1, ?, ?)",
            (token.token, token.token_secret),
        )
        self.db.commit()

    def load(self) -> AccessToken | None:
        row = self.db.execute("SELECT token, secret FROM tokens WHERE id = 1").fetchone()
        if row:
            return AccessToken(token=row[0], token_secret=row[1])
        return None

    def clear(self) -> None:
        self.db.execute("DELETE FROM tokens WHERE id = 1")
        self.db.commit()

    def has_token(self) -> bool:
        return self.load() is not None

# Use custom token store
token_store = DatabaseTokenStore(db_connection)
client = ETradeClient(config, token_store=token_store)
```

### AWS Secrets Manager

```python
import boto3
import json
from etrade_client.models.auth import AccessToken

class SecretsManagerTokenStore:
    """Store tokens in AWS Secrets Manager."""

    def __init__(self, secret_name: str):
        self.client = boto3.client("secretsmanager")
        self.secret_name = secret_name

    def save(self, token: AccessToken) -> None:
        self.client.put_secret_value(
            SecretId=self.secret_name,
            SecretString=json.dumps({
                "token": token.token,
                "token_secret": token.token_secret,
            }),
        )

    def load(self) -> AccessToken | None:
        try:
            response = self.client.get_secret_value(SecretId=self.secret_name)
            data = json.loads(response["SecretString"])
            return AccessToken(token=data["token"], token_secret=data["token_secret"])
        except self.client.exceptions.ResourceNotFoundException:
            return None

    def clear(self) -> None:
        try:
            self.client.delete_secret(SecretId=self.secret_name, ForceDeleteWithoutRecovery=True)
        except self.client.exceptions.ResourceNotFoundException:
            pass

    def has_token(self) -> bool:
        return self.load() is not None
```

## Logging

The library uses Python's standard logging:

```python
import logging

# Enable debug logging for the library
logging.getLogger("etrade_client").setLevel(logging.DEBUG)

# Add a handler
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s"))
logging.getLogger("etrade_client").addHandler(handler)
```

## Testing with Mocks

Use httpx's mock transport for testing:

```python
import httpx
from etrade_client import ETradeClient, ETradeConfig

def mock_handler(request: httpx.Request) -> httpx.Response:
    if "quote" in str(request.url):
        return httpx.Response(
            200,
            json={
                "QuoteResponse": {
                    "QuoteData": [
                        {
                            "Product": {"symbol": "AAPL"},
                            "All": {"lastTrade": 150.0},
                        }
                    ]
                }
            },
        )
    return httpx.Response(404)

# Create mock transport
transport = httpx.MockTransport(mock_handler)
http_client = httpx.AsyncClient(transport=transport)

# Use in tests
config = ETradeConfig(
    consumer_key="test",
    consumer_secret="test",
    sandbox=True,
)
client = ETradeClient(config, http_client=http_client)

# This will use the mock
quotes = await client.market.get_quotes(["AAPL"])
```

## Concurrent Requests

Make multiple API calls concurrently:

```python
import asyncio

async with ETradeClient.from_env() as client:
    # Load token
    client.load_token()
    await client.renew_token()

    # Make concurrent requests
    accounts_task = client.accounts.list_accounts()
    quotes_task = client.market.get_quotes(["AAPL", "MSFT"])

    accounts, quotes = await asyncio.gather(accounts_task, quotes_task)
```

## Environment Variables

| Variable | Description |
|----------|-------------|
| `ETRADE_CONSUMER_KEY` | OAuth consumer key |
| `ETRADE_CONSUMER_SECRET` | OAuth consumer secret |
| `ETRADE_SANDBOX` | Set to `0` for production |
