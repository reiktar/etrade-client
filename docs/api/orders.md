# Orders API

The Orders API provides order preview, placement, listing, and cancellation. This includes type-safe order builders for equity and options.

## Quick Reference

| Method | Description |
|--------|-------------|
| `list_orders(account_id)` | List orders |
| `preview_order(account_id, order)` | Preview order before placing |
| `place_order(account_id, order, preview_ids)` | Place order |
| `cancel_order(account_id, order_id)` | Cancel order |

## Order Builders

The library provides fluent builders for constructing orders safely.

### Equity Order Builder

```python
from etrade_client import EquityOrderBuilder

# Market buy
order = (
    EquityOrderBuilder("AAPL")
    .buy(100)
    .market()
    .build()
)

# Limit buy
order = (
    EquityOrderBuilder("AAPL")
    .buy(100)
    .limit(150.00)
    .good_until_cancel()
    .build()
)

# Stop-limit sell
order = (
    EquityOrderBuilder("AAPL")
    .sell(100)
    .stop_limit(stop_price=148.00, limit_price=147.50)
    .good_for_day()
    .build()
)

# Short sell
order = (
    EquityOrderBuilder("AAPL")
    .sell_short(100)
    .limit(155.00)
    .build()
)
```

### Equity Builder Methods

**Actions:**
| Method | Description |
|--------|-------------|
| `.buy(quantity)` | Buy shares |
| `.sell(quantity)` | Sell shares |
| `.sell_short(quantity)` | Short sell |
| `.buy_to_cover(quantity)` | Cover short position |

**Price Types:**
| Method | Description |
|--------|-------------|
| `.market()` | Market order (default) |
| `.limit(price)` | Limit order |
| `.stop(price)` | Stop order |
| `.stop_limit(stop, limit)` | Stop-limit order |

**Duration:**
| Method | Description |
|--------|-------------|
| `.good_for_day()` | Expires end of day (default) |
| `.good_until_cancel()` | Remains until cancelled |
| `.immediate_or_cancel()` | Fill immediately or cancel |
| `.fill_or_kill()` | Fill completely or cancel |

**Session:**
| Method | Description |
|--------|-------------|
| `.regular_session()` | Regular hours (default) |
| `.extended_session()` | Extended hours |

**Options:**
| Method | Description |
|--------|-------------|
| `.all_or_none(True)` | All-or-none flag |
| `.client_order_id("id")` | Custom order ID |

### Option Order Builder

```python
from etrade_client import OptionOrderBuilder, OptionType

# Buy call options
order = (
    OptionOrderBuilder("AAPL", "2025-01-17", 150.00, OptionType.CALL)
    .buy_to_open(5)
    .limit(2.50)
    .good_for_day()
    .build()
)

# Sell put options (write)
order = (
    OptionOrderBuilder("AAPL", "2025-01-17", 140.00, OptionType.PUT)
    .sell_to_open(3)
    .limit(1.75)
    .build()
)

# Close option position
order = (
    OptionOrderBuilder("AAPL", "2025-01-17", 150.00, OptionType.CALL)
    .sell_to_close(5)
    .limit(3.00)
    .build()
)
```

### Option Builder Methods

**Actions:**
| Method | Description |
|--------|-------------|
| `.buy_to_open(quantity)` | Open long position |
| `.sell_to_open(quantity)` | Write/short options |
| `.buy_to_close(quantity)` | Close short position |
| `.sell_to_close(quantity)` | Close long position |

Price, duration, and session methods are the same as equity orders.

## Preview Order

Always preview orders before placing to validate and see estimated costs:

```python
order = (
    EquityOrderBuilder("AAPL")
    .buy(100)
    .limit(150.00)
    .build()
)

preview = await client.orders.preview_order(account_id, order)

# Check preview details
print(f"Order Type: {preview.preview.order_type}")
print(f"Estimated Commission: ${preview.preview.estimated_commission:,.2f}")
print(f"Estimated Total Cost: ${preview.preview.estimated_total_amount:,.2f}")

# Get preview IDs for placing order
preview_ids = preview.preview_ids
```

### Preview Response

| Field | Type | Description |
|-------|------|-------------|
| `preview.order_type` | `str` | Order type |
| `preview.estimated_commission` | `float` | Estimated commission |
| `preview.estimated_total_amount` | `float` | Total estimated cost |
| `preview_ids` | `list[str]` | Preview IDs for placing |

## Place Order

Place an order using the preview IDs:

```python
# Build and preview
order = (
    EquityOrderBuilder("AAPL")
    .buy(100)
    .limit(150.00)
    .build()
)
preview = await client.orders.preview_order(account_id, order)

# Place the order
result = await client.orders.place_order(
    account_id,
    order,
    preview.preview_ids,
)

# Check result
print(f"Order ID: {result.order_id}")
print(f"Status: {result.status}")
```

### Place Response

| Field | Type | Description |
|-------|------|-------------|
| `order_id` | `int` | Assigned order ID |
| `status` | `str` | Order status |

## List Orders

```python
response = await client.orders.list_orders(
    account_id,
    status="OPEN",  # OPEN, EXECUTED, CANCELLED, EXPIRED, REJECTED
    symbol="AAPL",  # Filter by symbol
    from_date=date(2024, 1, 1),
    to_date=date(2024, 12, 31),
    count=25,
)

for order in response.orders:
    print(f"Order {order.order_id}:")

    for detail in order.order_details:
        for instrument in detail.instruments:
            product = instrument.product
            print(f"  {instrument.order_action} {instrument.quantity} {product.symbol}")
            print(f"  Type: {detail.order_type}")
            print(f"  Status: {detail.status}")
            if detail.limit_price:
                print(f"  Limit: ${detail.limit_price:,.2f}")
```

### List Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `account_id` | `str` | Yes | - | Account identifier |
| `status` | `str` | No | - | Filter by status |
| `symbol` | `str` | No | - | Filter by symbol |
| `from_date` | `date` | No | - | Start date |
| `to_date` | `date` | No | - | End date |
| `count` | `int` | No | `25` | Max orders |
| `marker` | `str` | No | - | Pagination marker |

### Order Status Values

| Status | Description |
|--------|-------------|
| `OPEN` | Active, waiting to fill |
| `EXECUTED` | Filled |
| `CANCELLED` | Cancelled by user |
| `EXPIRED` | Expired unfilled |
| `REJECTED` | Rejected by exchange |
| `PARTIAL` | Partially filled |

## Cancel Order

```python
result = await client.orders.cancel_order(account_id, order_id)

# Result is a dict with cancellation details
if result.get("CancelOrderResponse", {}).get("orderId"):
    print(f"Order {order_id} cancelled successfully")
```

## Complete Order Flow Example

```python
from etrade_client import ETradeClient, EquityOrderBuilder

async def place_limit_buy(account_id: str, symbol: str, quantity: int, price: float):
    """Complete flow for placing a limit buy order."""

    async with ETradeClient.from_env(sandbox=True) as client:
        # Load and renew token
        if not client.load_token():
            raise Exception("Not authenticated")
        await client.renew_token()

        # Build the order
        order = (
            EquityOrderBuilder(symbol)
            .buy(quantity)
            .limit(price)
            .good_for_day()
            .build()
        )

        # Preview the order
        print("Previewing order...")
        preview = await client.orders.preview_order(account_id, order)

        print(f"Estimated cost: ${preview.preview.estimated_total_amount:,.2f}")
        print(f"Commission: ${preview.preview.estimated_commission:,.2f}")

        # Confirm with user
        confirm = input("Place order? (y/n): ")
        if confirm.lower() != "y":
            print("Order cancelled")
            return

        # Place the order
        print("Placing order...")
        result = await client.orders.place_order(
            account_id,
            order,
            preview.preview_ids,
        )

        print(f"Order placed! ID: {result.order_id}")
        return result.order_id

# Usage
order_id = await place_limit_buy(
    account_id="abc123",
    symbol="AAPL",
    quantity=10,
    price=150.00,
)
```

## Options Order Example

```python
from etrade_client import ETradeClient, OptionOrderBuilder, OptionType

async def buy_call_option(
    account_id: str,
    symbol: str,
    expiry: str,
    strike: float,
    quantity: int,
    limit_price: float,
):
    """Buy call options with preview and confirmation."""

    async with ETradeClient.from_env(sandbox=True) as client:
        if not client.load_token():
            raise Exception("Not authenticated")
        await client.renew_token()

        # Build option order
        order = (
            OptionOrderBuilder(symbol, expiry, strike, OptionType.CALL)
            .buy_to_open(quantity)
            .limit(limit_price)
            .good_for_day()
            .build()
        )

        # Preview
        preview = await client.orders.preview_order(account_id, order)

        print(f"Buying {quantity} {symbol} ${strike} calls expiring {expiry}")
        print(f"Total cost: ${preview.preview.estimated_total_amount:,.2f}")

        # Place
        result = await client.orders.place_order(
            account_id,
            order,
            preview.preview_ids,
        )

        print(f"Order placed! ID: {result.order_id}")

# Usage
await buy_call_option(
    account_id="abc123",
    symbol="AAPL",
    expiry="2025-01-17",
    strike=150.00,
    quantity=5,
    limit_price=2.50,
)
```

## Error Handling

```python
from etrade_client import ETradeAPIError, ETradeValidationError

try:
    preview = await client.orders.preview_order(account_id, order)
except ETradeValidationError as e:
    # Order validation failed
    print(f"Invalid order: {e.message}")
except ETradeAPIError as e:
    # API error (insufficient funds, etc.)
    print(f"API error: {e.code} - {e.message}")
```

## Safety Notes

- **Always preview first** - Preview catches errors before order submission
- **Use sandbox for testing** - Never test with production credentials
- **Handle errors gracefully** - Network issues, validation errors can occur
- **Monitor placed orders** - Use `list_orders()` to track order status
- **Cancel unwanted orders promptly** - Orders remain active until filled or cancelled
