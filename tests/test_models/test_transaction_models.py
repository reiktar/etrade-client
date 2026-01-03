"""Tests for transaction model parsing."""

from decimal import Decimal

from pydantic import TypeAdapter

from etrade_client.models.transactions import (
    BoughtTransaction,
    DividendTransaction,
    FeeTransaction,
    GenericTransaction,
    SoldTransaction,
    Transaction,
    TransactionListResponse,
)


def _base_transaction_data(**overrides) -> dict:
    """Helper to create base transaction test data with all required fields."""
    base = {
        "transactionId": "tx001",
        "accountId": "acc123",
        "transactionDate": 1705318200000,  # Unix timestamp in milliseconds
        "postDate": 1705489200000,
        "amount": "1500.00",
        "description": "Test transaction",
        "transactionType": "Bought",  # Default to Bought (uses BrokerageWithProduct)
        "memo": "",
        "imageFlag": False,
        "storeId": 0,
        "Brokerage": {
            "Product": {"symbol": "AAPL", "securityType": "EQ"},
            "displaySymbol": "AAPL",
            "quantity": "10",
            "price": "150.00",
            "fee": 0,
            "paymentCurrency": "USD",
            "settlementCurrency": "USD",
            "settlementDate": 1705489200000,
        },
        "detailsURI": "/details/tx001",
        "instType": "BROKERAGE",
    }
    base.update(overrides)
    return base


def _sold_transaction_data(**overrides) -> dict:
    """Helper to create Sold transaction data (uses BrokerageWithoutProduct)."""
    base = {
        "transactionId": "tx002",
        "accountId": "acc123",
        "transactionDate": 1705318200000,
        "postDate": 1705489200000,
        "amount": "-500.00",
        "description": "Sold MSFT",
        "transactionType": "Sold",
        "memo": "",
        "imageFlag": False,
        "storeId": 0,
        "Brokerage": {
            "displaySymbol": "MSFT",
            "quantity": "5",
            "price": "100.00",
            "fee": 0,
            "paymentCurrency": "USD",
            "settlementCurrency": "USD",
            "settlementDate": 1705489200000,
        },
        "detailsURI": "/details/tx002",
        "instType": "BROKERAGE",
    }
    base.update(overrides)
    return base


def _fee_transaction_data(**overrides) -> dict:
    """Helper to create Fee transaction data (has description2 field)."""
    base = {
        "transactionId": "tx003",
        "accountId": "acc123",
        "transactionDate": 1705318200000,
        "postDate": 1705489200000,
        "amount": "-9.99",
        "description": "Service fee",
        "transactionType": "Fee",
        "memo": "",
        "imageFlag": False,
        "storeId": 0,
        "description2": "Additional fee details",
        "Brokerage": {
            "quantity": "0",
            "price": "0",
            "fee": 0,
            "paymentCurrency": "USD",
            "settlementCurrency": "USD",
            "settlementDate": 1705489200000,
        },
    }
    base.update(overrides)
    return base


# TypeAdapter for parsing discriminated union
_tx_adapter = TypeAdapter(Transaction)


class TestTransactionListResponse:
    """Tests for TransactionListResponse.from_api_response."""

    def test_parses_multiple_transactions(self) -> None:
        """Should parse response with multiple transactions."""
        data = {
            "TransactionListResponse": {
                "Transaction": [
                    _base_transaction_data(
                        transactionId="tx001",
                        amount="1500.00",
                        description="Bought AAPL",
                    ),
                    _sold_transaction_data(
                        transactionId="tx002",
                        amount="-500.00",
                        description="Sold MSFT",
                    ),
                ],
                "marker": "next_page_marker",
                "moreTransactions": True,
            }
        }

        result = TransactionListResponse.from_api_response(data)

        assert len(result.transactions) == 2
        assert result.transactions[0].transaction_id == "tx001"
        assert result.transactions[0].amount == Decimal("1500.00")
        assert isinstance(result.transactions[0], BoughtTransaction)
        assert result.transactions[1].transaction_id == "tx002"
        assert result.transactions[1].amount == Decimal("-500.00")
        assert isinstance(result.transactions[1], SoldTransaction)
        assert result.marker == "next_page_marker"
        assert result.more_transactions is True

    def test_parses_single_transaction_as_dict(self) -> None:
        """Should handle E*Trade's single-item-as-dict quirk."""
        data = {
            "TransactionListResponse": {
                "Transaction": _base_transaction_data(
                    transactionId="tx001",
                    amount="1500.00",
                )
            }
        }

        result = TransactionListResponse.from_api_response(data)

        assert len(result.transactions) == 1
        assert result.transactions[0].transaction_id == "tx001"

    def test_parses_empty_transactions(self) -> None:
        """Should handle empty transaction list."""
        data = {"TransactionListResponse": {"Transaction": []}}

        result = TransactionListResponse.from_api_response(data)

        assert len(result.transactions) == 0
        assert result.has_more is False

    def test_has_more_with_next_page(self) -> None:
        """has_more should be True when next page exists."""
        data = {
            "TransactionListResponse": {
                "Transaction": [],
                "next": "page_token",
            }
        }

        result = TransactionListResponse.from_api_response(data)

        assert result.next_page == "page_token"
        assert result.has_more is True

    def test_has_more_without_next_page(self) -> None:
        """has_more should be False when no next page."""
        data = {
            "TransactionListResponse": {
                "Transaction": [],
            }
        }

        result = TransactionListResponse.from_api_response(data)

        assert result.next_page is None
        assert result.has_more is False


class TestTransaction:
    """Tests for Transaction model parsing and properties."""

    def test_parses_bought_transaction(self) -> None:
        """Should parse Bought transaction with BrokerageWithProduct."""
        data = _base_transaction_data(
            transactionId="tx001",
            accountId="acc123",
            amount="1500.00",
            description="Bought 10 shares AAPL @ 150.00",
        )

        tx = _tx_adapter.validate_python(data)

        assert isinstance(tx, BoughtTransaction)
        assert tx.transaction_id == "tx001"
        assert tx.account_id == "acc123"
        assert tx.amount == Decimal("1500.00")
        assert tx.transaction_type == "Bought"
        assert tx.brokerage is not None
        assert tx.brokerage.product is not None
        assert tx.brokerage.product.symbol == "AAPL"
        assert tx.brokerage.quantity == Decimal("10")
        assert tx.brokerage.price == Decimal("150.00")

    def test_parses_sold_transaction(self) -> None:
        """Should parse Sold transaction with BrokerageWithoutProduct."""
        data = _sold_transaction_data()

        tx = _tx_adapter.validate_python(data)

        assert isinstance(tx, SoldTransaction)
        assert tx.transaction_type == "Sold"
        assert tx.brokerage is not None
        assert tx.brokerage.display_symbol == "MSFT"

    def test_parses_fee_with_description2(self) -> None:
        """Should parse Fee transaction with description2 field."""
        data = _fee_transaction_data()

        tx = _tx_adapter.validate_python(data)

        assert isinstance(tx, FeeTransaction)
        assert tx.description2 == "Additional fee details"

    def test_parses_unknown_type_as_generic(self) -> None:
        """Should parse unknown transaction type as GenericTransaction."""
        data = _base_transaction_data(transactionType="UnknownNewType")

        tx = _tx_adapter.validate_python(data)

        assert isinstance(tx, GenericTransaction)
        assert tx.transaction_type == "UnknownNewType"

    def test_symbol_property_from_product(self) -> None:
        """symbol property should return product symbol for BrokerageWithProduct."""
        data = _base_transaction_data(
            transactionType="Dividend",
        )

        tx = _tx_adapter.validate_python(data)

        assert isinstance(tx, DividendTransaction)
        assert tx.symbol == "AAPL"

    def test_symbol_property_from_display_symbol(self) -> None:
        """symbol property should fallback to displaySymbol for BrokerageWithoutProduct."""
        data = _sold_transaction_data()

        tx = _tx_adapter.validate_python(data)

        assert tx.symbol == "MSFT"

    def test_symbol_property_strips_whitespace(self) -> None:
        """symbol property should strip whitespace."""
        data = _base_transaction_data()
        data["Brokerage"]["Product"]["symbol"] = "  AAPL  "

        tx = _tx_adapter.validate_python(data)

        assert tx.symbol == "AAPL"

    def test_symbol_property_none_for_empty_symbol(self) -> None:
        """symbol property should be None for empty/whitespace symbol."""
        data = _sold_transaction_data()
        data["Brokerage"]["displaySymbol"] = "   "

        tx = _tx_adapter.validate_python(data)

        assert tx.symbol is None

    def test_is_pending_true_for_zero_post_date(self) -> None:
        """is_pending should be True when post_date is 0."""
        data = _base_transaction_data(postDate=0)

        tx = _tx_adapter.validate_python(data)

        assert tx.is_pending is True
        assert tx.post_datetime is None

    def test_is_pending_false_for_valid_post_date(self) -> None:
        """is_pending should be False when post_date is set."""
        data = _base_transaction_data()

        tx = _tx_adapter.validate_python(data)

        assert tx.is_pending is False
        assert tx.post_datetime is not None

    def test_transaction_datetime_property(self) -> None:
        """transaction_datetime should convert epoch millis to datetime."""
        data = _base_transaction_data(transactionDate=1705318200000)

        tx = _tx_adapter.validate_python(data)

        assert tx.transaction_datetime.year == 2024
        assert tx.transaction_datetime.month == 1
