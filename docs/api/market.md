# Market Data API

The Market Data API provides access to quotes, option chains, and symbol lookup.

## Quick Reference

| Method | Description |
|--------|-------------|
| `get_quotes(symbols)` | Get quotes for up to 25 symbols |
| `get_option_expire_dates(symbol)` | Get option expiration dates |
| `get_option_chains(symbol, expiry)` | Get options chain |
| `lookup(search)` | Search for securities |

## Get Quotes

```python
response = await client.market.get_quotes(
    ["AAPL", "MSFT", "GOOGL"],
    detail_flag="ALL",  # ALL, FUNDAMENTAL, INTRADAY, OPTIONS, WEEK_52
)

for quote in response.quotes:
    product = quote.product
    all_data = quote.all_data

    print(f"{product.symbol}: ${all_data.last_trade:,.2f}")
    print(f"  Change: {all_data.change_close:+,.2f} ({all_data.change_close_pct:+.2f}%)")
    print(f"  Bid: ${all_data.bid:,.2f} x {all_data.bid_size}")
    print(f"  Ask: ${all_data.ask:,.2f} x {all_data.ask_size}")
    print(f"  Volume: {all_data.total_volume:,}")
    print(f"  52-Week Range: ${all_data.low_52:,.2f} - ${all_data.high_52:,.2f}")
```

### Detail Flags

| Flag | Description |
|------|-------------|
| `ALL` | Complete quote data (default) |
| `FUNDAMENTAL` | P/E, EPS, dividend info |
| `INTRADAY` | Intraday trading data |
| `OPTIONS` | Option-specific data |
| `WEEK_52` | 52-week high/low data |

### Quote Fields

| Field | Type | Description |
|-------|------|-------------|
| `product.symbol` | `str` | Ticker symbol |
| `product.security_type` | `str` | EQ, OPTN, MF, etc. |
| `all_data.last_trade` | `float` | Last trade price |
| `all_data.change_close` | `float` | Change from close |
| `all_data.change_close_pct` | `float` | Change percentage |
| `all_data.bid` | `float` | Bid price |
| `all_data.ask` | `float` | Ask price |
| `all_data.bid_size` | `int` | Bid size |
| `all_data.ask_size` | `int` | Ask size |
| `all_data.total_volume` | `int` | Trading volume |
| `all_data.open` | `float` | Open price |
| `all_data.high` | `float` | Day high |
| `all_data.low` | `float` | Day low |
| `all_data.previous_close` | `float` | Previous close |
| `all_data.high_52` | `float` | 52-week high |
| `all_data.low_52` | `float` | 52-week low |

## Get Option Expiration Dates

```python
dates = await client.market.get_option_expire_dates(
    "AAPL",
    expiry_type="ALL",  # ALL, MONTHLY, WEEKLY
)

for expiry in dates:
    print(f"{expiry.expiry_date}: {expiry.expiry_type}")
```

### Response Fields

| Field | Type | Description |
|-------|------|-------------|
| `expiry_date` | `date` | Expiration date |
| `expiry_type` | `str` | MONTHLY, WEEKLY, QUARTERLY |

## Get Options Chain

```python
from datetime import date

chain = await client.market.get_option_chains(
    "AAPL",
    expiry_date=date(2025, 1, 17),
    chain_type="CALLPUT",  # CALL, PUT, CALLPUT
    no_of_strikes=10,  # Number of strikes around current price
)

for pair in chain.option_pairs:
    # Call option
    if pair.call:
        call = pair.call
        print(f"CALL ${call.strike_price:,.2f}")
        print(f"  Bid: ${call.bid:,.2f} Ask: ${call.ask:,.2f}")
        print(f"  Volume: {call.volume} OI: {call.open_interest}")

    # Put option
    if pair.put:
        put = pair.put
        print(f"PUT ${put.strike_price:,.2f}")
        print(f"  Bid: ${put.bid:,.2f} Ask: ${put.ask:,.2f}")
        print(f"  Volume: {put.volume} OI: {put.open_interest}")
```

### Chain Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `symbol` | `str` | Yes | - | Underlying symbol |
| `expiry_date` | `date` | Yes | - | Expiration date |
| `chain_type` | `str` | No | `"CALLPUT"` | CALL, PUT, CALLPUT |
| `no_of_strikes` | `int` | No | - | Number of strikes |
| `strike_price_near` | `float` | No | - | Center strike price |
| `skip_adjusted` | `bool` | No | `True` | Skip adjusted options |

### Option Fields

| Field | Type | Description |
|-------|------|-------------|
| `strike_price` | `float` | Strike price |
| `option_type` | `str` | CALL or PUT |
| `bid` | `float` | Bid price |
| `ask` | `float` | Ask price |
| `last_price` | `float` | Last trade price |
| `volume` | `int` | Trading volume |
| `open_interest` | `int` | Open interest |
| `in_the_money` | `bool` | ITM flag |
| `implied_volatility` | `float` | IV (if available) |

## Symbol Lookup

```python
results = await client.market.lookup("Apple")

for result in results:
    print(f"{result['symbol']}: {result['description']}")
    print(f"  Type: {result['type']}")
```

### Response Format

Returns a list of dictionaries with:

| Field | Type | Description |
|-------|------|-------------|
| `symbol` | `str` | Ticker symbol |
| `description` | `str` | Security description |
| `type` | `str` | Security type |

## Examples

### Build a Watchlist

```python
symbols = ["AAPL", "MSFT", "GOOGL", "AMZN", "META"]

response = await client.market.get_quotes(symbols)

print("Watchlist:")
print("-" * 60)
for quote in response.quotes:
    symbol = quote.product.symbol
    price = quote.all_data.last_trade
    change = quote.all_data.change_close_pct

    arrow = "+" if change >= 0 else ""
    print(f"{symbol:6} ${price:>10,.2f}  {arrow}{change:.2f}%")
```

### Find High IV Options

```python
from datetime import date

dates = await client.market.get_option_expire_dates("SPY")
next_expiry = dates[0].expiry_date

chain = await client.market.get_option_chains(
    "SPY",
    next_expiry,
    chain_type="CALLPUT",
)

# Find options with highest implied volatility
options_with_iv = []
for pair in chain.option_pairs:
    for opt in [pair.call, pair.put]:
        if opt and opt.implied_volatility:
            options_with_iv.append(opt)

# Sort by IV descending
options_with_iv.sort(key=lambda x: x.implied_volatility, reverse=True)

print("Highest IV Options:")
for opt in options_with_iv[:10]:
    print(f"  {opt.option_type} ${opt.strike_price:,.2f}: IV {opt.implied_volatility:.1%}")
```

### Calculate Options Greeks

```python
# Note: Greeks may be included in option details depending on market data
chain = await client.market.get_option_chains(
    "AAPL",
    date(2025, 1, 17),
    chain_type="CALL",
)

for pair in chain.option_pairs:
    if pair.call:
        call = pair.call
        # Access greeks if available in response
        print(f"Strike: ${call.strike_price}")
        print(f"  Price: ${call.last_price}")
        # Greeks depend on API response content
```

### Monitor Multiple Symbols

```python
import asyncio

async def monitor_quotes(symbols: list[str], interval: int = 60):
    """Monitor quotes at regular intervals."""
    while True:
        response = await client.market.get_quotes(symbols)

        print(f"\n{datetime.now().strftime('%H:%M:%S')}")
        for quote in response.quotes:
            symbol = quote.product.symbol
            price = quote.all_data.last_trade
            print(f"  {symbol}: ${price:,.2f}")

        await asyncio.sleep(interval)

# Run monitoring
await monitor_quotes(["AAPL", "MSFT"], interval=60)
```

## Rate Limits

E\*Trade imposes rate limits on market data requests. The library includes automatic retry with exponential backoff when rate limits are hit. For high-frequency access, consider:

1. Batching multiple symbols in single `get_quotes()` calls (up to 25)
2. Implementing local caching (see [Advanced Topics](advanced.md))
3. Using appropriate intervals between requests
