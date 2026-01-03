# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.0] - 2026-01-03

### Added

- `TransactionType` enum with exact API values for all 14 known transaction types
- Transaction subclasses for type-safe access:
  - `BoughtTransaction`, `SoldTransaction`
  - `DividendTransaction`, `InterestIncomeTransaction`
  - `TransferTransaction`, `FundsReceivedTransaction`
  - `FeeTransaction`, `ServiceFeeTransaction`
  - `BillPaymentTransaction`, `PosTransaction`
  - `CashInLieuTransaction`, `MarginInterestTransaction`
  - `ExchangeReceivedInTransaction`, `ExchangeDeliveredOutTransaction`
- `GenericTransaction` fallback for unknown/new transaction types
- `BrokerageWithProduct` and `BrokerageWithoutProduct` for type-appropriate brokerage data
- Helper properties on `TransactionBase`:
  - `is_pending` - Check if transaction is pending (post_date is epoch zero)
  - `transaction_datetime` - Convert epoch millis to datetime
  - `post_datetime` - Convert post_date to datetime (None if pending)
  - `symbol` - Get symbol from product or display_symbol

### Changed

- **BREAKING**: `Transaction` is now a Pydantic v2 discriminated union type alias
  - Use `isinstance(tx, DividendTransaction)` for type checking
  - Use `TypeAdapter(Transaction).validate_python(data)` for validation
- Transaction date fields are now `int` (epoch milliseconds) with datetime properties
- Brokerage data structure varies by transaction type

### Migration Guide

```python
# Before (0.1.0)
if tx.transaction_type == "Dividend":
    symbol = tx.brokerage.product.symbol if tx.brokerage and tx.brokerage.product else None

# After (0.2.0)
if isinstance(tx, DividendTransaction):
    symbol = tx.symbol  # Uses helper property

# Before (0.1.0)
is_pending = tx.post_date == datetime(1970, 1, 1, tzinfo=UTC)

# After (0.2.0)
is_pending = tx.is_pending  # Uses helper property

# Before (0.1.0)
date_str = tx.transaction_date.strftime("%Y-%m-%d")

# After (0.2.0)
date_str = tx.transaction_datetime.strftime("%Y-%m-%d")
```

## [0.1.0] - Initial Release

- Initial release with E*Trade API client
- Support for accounts, orders, market data, alerts, and transactions
- OAuth 1.0a authentication flow
- Async/await support with httpx
