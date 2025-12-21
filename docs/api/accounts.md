# Accounts API

The Accounts API provides access to account information, balances, portfolio positions, and transaction history.

## Quick Reference

| Method | Description |
|--------|-------------|
| `list_accounts()` | List all accounts |
| `get_balance(account_id)` | Get account balance |
| `get_portfolio(account_id)` | Get portfolio positions |
| `get_transactions(account_id)` | Get transactions (single page) |
| `iter_transactions(account_id)` | Iterate all transactions |

## List Accounts

```python
response = await client.accounts.list_accounts()

for account in response.accounts:
    print(f"{account.account_id_key}: {account.account_desc}")
    print(f"  Type: {account.account_type}")
    print(f"  Mode: {account.account_mode}")
    print(f"  Status: {account.account_status}")
```

### Response Fields

| Field | Type | Description |
|-------|------|-------------|
| `account_id_key` | `str` | Unique account identifier (use for other API calls) |
| `account_id` | `str` | Display account number |
| `account_name` | `str` | Account name |
| `account_desc` | `str` | Account description |
| `account_type` | `str` | INDIVIDUAL, JOINT, IRA, etc. |
| `account_mode` | `str` | CASH, MARGIN |
| `account_status` | `str` | ACTIVE, CLOSED, etc. |

## Get Balance

```python
response = await client.accounts.get_balance(account_id_key)
balance = response.balance

print(f"Account Type: {balance.account_type}")
print(f"Cash Available: ${balance.computed.cash_available_for_investment:,.2f}")
print(f"Net Cash: ${balance.computed.net_cash:,.2f}")
print(f"Margin Buying Power: ${balance.computed.margin_buying_power:,.2f}")

# Real-time values
rtv = balance.computed.real_time_values
if rtv:
    print(f"Total Account Value: ${rtv.total_account_value:,.2f}")
```

### Balance Fields

| Field | Type | Description |
|-------|------|-------------|
| `account_type` | `str` | Account type |
| `computed.cash_available_for_investment` | `float` | Cash available |
| `computed.net_cash` | `float` | Net cash balance |
| `computed.margin_buying_power` | `float` | Margin buying power |
| `computed.real_time_values.total_account_value` | `float` | Total value |

## Get Portfolio

```python
portfolio = await client.accounts.get_portfolio(
    account_id_key,
    view="QUICK",  # QUICK, PERFORMANCE, FUNDAMENTAL, COMPLETE
)

for position in portfolio.positions:
    product = position.product
    quick = position.quick

    print(f"{product.symbol}: {product.security_type}")
    print(f"  Quantity: {position.quantity}")
    print(f"  Market Value: ${position.market_value:,.2f}")
    print(f"  Last Price: ${quick.last_trade:,.2f}")
    print(f"  Day Change: {quick.change_pct:+.2f}%")
    print(f"  Total Gain: ${position.total_gain:,.2f}")
```

### View Types

| View | Description |
|------|-------------|
| `QUICK` | Basic position info with quick quote data |
| `PERFORMANCE` | Performance metrics and returns |
| `FUNDAMENTAL` | Fundamental data like P/E, yield |
| `COMPLETE` | All available data |

### Position Fields

| Field | Type | Description |
|-------|------|-------------|
| `product.symbol` | `str` | Symbol |
| `product.security_type` | `str` | EQ, OPTN, MF, etc. |
| `quantity` | `float` | Number of shares/contracts |
| `market_value` | `float` | Current market value |
| `cost_basis` | `float` | Cost basis |
| `total_gain` | `float` | Total gain/loss |
| `quick.last_trade` | `float` | Last trade price |
| `quick.change_pct` | `float` | Day change percentage |

## Get Transactions

### Single Page

```python
response = await client.accounts.get_transactions(
    account_id_key,
    start_date=date(2024, 1, 1),
    end_date=date(2024, 12, 31),
    sort_order="DESC",
    count=50,  # Max per page
)

for tx in response.transactions:
    print(f"{tx.transaction_date}: {tx.transaction_type}")
    print(f"  {tx.description}")
    print(f"  Amount: ${tx.amount:,.2f}")

# Check for more pages
if response.next_marker:
    # Fetch next page with marker
    next_page = await client.accounts.get_transactions(
        account_id_key,
        marker=response.next_marker,
    )
```

### Pagination Iterator (Recommended)

The `iter_transactions()` method handles pagination automatically:

```python
async for tx in client.accounts.iter_transactions(
    account_id_key,
    start_date=date(2024, 1, 1),
    end_date=date(2024, 12, 31),
    sort_order="DESC",
    limit=100,  # Optional: stop after N transactions
):
    print(f"{tx.transaction_date}: {tx.description}")
    if tx.brokerage and tx.brokerage.product:
        print(f"  Symbol: {tx.brokerage.product.symbol}")
```

### Transaction Fields

| Field | Type | Description |
|-------|------|-------------|
| `transaction_id` | `str` | Unique transaction ID |
| `transaction_date` | `date` | Transaction date |
| `transaction_type` | `str` | Type of transaction |
| `description` | `str` | Description |
| `amount` | `float` | Transaction amount |
| `brokerage.product.symbol` | `str` | Symbol (if applicable) |
| `brokerage.quantity` | `float` | Quantity (if applicable) |
| `brokerage.price` | `float` | Price (if applicable) |

## Parameters Reference

### `list_accounts()`

No parameters.

### `get_balance(account_id_key)`

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `account_id_key` | `str` | Yes | Account identifier |

### `get_portfolio(account_id_key, **options)`

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `account_id_key` | `str` | Yes | - | Account identifier |
| `view` | `str` | No | `"QUICK"` | View type |
| `lots_required` | `bool` | No | `False` | Include lot details |
| `count` | `int` | No | - | Positions per page |

### `get_transactions(account_id_key, **options)`

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `account_id_key` | `str` | Yes | - | Account identifier |
| `start_date` | `date` | No | - | Start date |
| `end_date` | `date` | No | - | End date |
| `sort_order` | `str` | No | `"DESC"` | ASC or DESC |
| `count` | `int` | No | `50` | Transactions per page |
| `marker` | `str` | No | - | Pagination marker |

### `iter_transactions(account_id_key, **options)`

Same parameters as `get_transactions()`, plus:

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `limit` | `int` | No | - | Max total transactions |

## Examples

### Calculate Portfolio Value

```python
portfolio = await client.accounts.get_portfolio(account_id, view="QUICK")

total_value = sum(
    pos.market_value or 0
    for pos in portfolio.positions
)
print(f"Total Portfolio Value: ${total_value:,.2f}")
```

### Find Recent Dividends

```python
from datetime import date, timedelta

start = date.today() - timedelta(days=30)

async for tx in client.accounts.iter_transactions(
    account_id,
    start_date=start,
):
    if "DIVIDEND" in (tx.transaction_type or "").upper():
        print(f"{tx.transaction_date}: ${tx.amount:,.2f} - {tx.description}")
```

### Export Transactions to CSV

```python
import csv
from datetime import date

async def export_transactions(account_id: str, filename: str):
    with open(filename, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Date", "Type", "Symbol", "Quantity", "Amount", "Description"])

        async for tx in client.accounts.iter_transactions(
            account_id,
            start_date=date(2024, 1, 1),
        ):
            symbol = ""
            quantity = ""
            if tx.brokerage and tx.brokerage.product:
                symbol = tx.brokerage.product.symbol or ""
                quantity = tx.brokerage.quantity or ""

            writer.writerow([
                tx.transaction_date,
                tx.transaction_type,
                symbol,
                quantity,
                tx.amount,
                tx.description,
            ])
```
