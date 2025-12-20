"""Tests for transaction model parsing."""

from datetime import datetime
from decimal import Decimal

import pytest

from etrade_client.models.transactions import Transaction, TransactionListResponse


class TestTransactionListResponse:
    """Tests for TransactionListResponse.from_api_response."""

    def test_parses_multiple_transactions(self) -> None:
        """Should parse response with multiple transactions."""
        data = {
            "TransactionListResponse": {
                "Transaction": [
                    {
                        "transactionId": "tx001",
                        "transactionDate": "2025-01-15T10:30:00",
                        "amount": "1500.00",
                        "description": "Bought AAPL",
                        "transactionType": "BUY",
                    },
                    {
                        "transactionId": "tx002",
                        "transactionDate": "2025-01-16T14:00:00",
                        "amount": "-500.00",
                        "description": "Sold MSFT",
                        "transactionType": "SELL",
                    },
                ],
                "marker": "next_page_marker",
                "moreTransactions": True,
            }
        }

        result = TransactionListResponse.from_api_response(data)

        assert len(result.transactions) == 2
        assert result.transactions[0].transaction_id == "tx001"
        assert result.transactions[0].amount == Decimal("1500.00")
        assert result.transactions[1].transaction_id == "tx002"
        assert result.transactions[1].amount == Decimal("-500.00")
        assert result.marker == "next_page_marker"
        assert result.more_transactions is True

    def test_parses_single_transaction_as_dict(self) -> None:
        """Should handle E*Trade's single-item-as-dict quirk."""
        data = {
            "TransactionListResponse": {
                "Transaction": {
                    "transactionId": "tx001",
                    "transactionDate": "2025-01-15T10:30:00",
                    "amount": "1500.00",
                }
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

    def test_parses_complete_transaction(self) -> None:
        """Should parse transaction with all fields."""
        data = {
            "transactionId": "tx001",
            "accountId": "acc123",
            "transactionDate": "2025-01-15T10:30:00",
            "postDate": "2025-01-17T00:00:00",
            "amount": "1500.00",
            "description": "Bought 10 shares AAPL @ 150.00",
            "transactionType": "BUY",
            "memo": "Regular purchase",
            "Brokerage": {
                "Product": {
                    "symbol": "AAPL",
                    "securityType": "EQ",
                },
                "quantity": "10",
                "price": "150.00",
                "fee": "0.00",
                "displaySymbol": "AAPL",
            },
        }

        tx = Transaction.model_validate(data)

        assert tx.transaction_id == "tx001"
        assert tx.account_id == "acc123"
        assert tx.amount == Decimal("1500.00")
        assert tx.transaction_type == "BUY"
        assert tx.brokerage is not None
        assert tx.brokerage.product is not None
        assert tx.brokerage.product.symbol == "AAPL"
        assert tx.brokerage.quantity == Decimal("10")
        assert tx.brokerage.price == Decimal("150.00")

    def test_parses_minimal_transaction(self) -> None:
        """Should parse transaction with only required fields."""
        data = {
            "transactionId": "tx001",
            "transactionDate": "2025-01-15T10:30:00",
            "amount": "100.00",
        }

        tx = Transaction.model_validate(data)

        assert tx.transaction_id == "tx001"
        assert tx.amount == Decimal("100.00")
        assert tx.description is None
        assert tx.brokerage is None

    def test_symbol_property_from_product(self) -> None:
        """symbol property should return product symbol."""
        data = {
            "transactionId": "tx001",
            "transactionDate": "2025-01-15T10:30:00",
            "amount": "100.00",
            "Brokerage": {
                "Product": {"symbol": "AAPL"},
            },
        }

        tx = Transaction.model_validate(data)

        assert tx.symbol == "AAPL"

    def test_symbol_property_from_display_symbol(self) -> None:
        """symbol property should fallback to displaySymbol."""
        data = {
            "transactionId": "tx001",
            "transactionDate": "2025-01-15T10:30:00",
            "amount": "100.00",
            "Brokerage": {
                "displaySymbol": "MSFT",
            },
        }

        tx = Transaction.model_validate(data)

        assert tx.symbol == "MSFT"

    def test_symbol_property_none_without_brokerage(self) -> None:
        """symbol property should be None without brokerage."""
        data = {
            "transactionId": "tx001",
            "transactionDate": "2025-01-15T10:30:00",
            "amount": "100.00",
        }

        tx = Transaction.model_validate(data)

        assert tx.symbol is None

    def test_symbol_property_strips_whitespace(self) -> None:
        """symbol property should strip whitespace."""
        data = {
            "transactionId": "tx001",
            "transactionDate": "2025-01-15T10:30:00",
            "amount": "100.00",
            "Brokerage": {
                "Product": {"symbol": "  AAPL  "},
            },
        }

        tx = Transaction.model_validate(data)

        assert tx.symbol == "AAPL"

    def test_symbol_property_none_for_empty_symbol(self) -> None:
        """symbol property should be None for empty/whitespace symbol."""
        data = {
            "transactionId": "tx001",
            "transactionDate": "2025-01-15T10:30:00",
            "amount": "100.00",
            "Brokerage": {
                "Product": {"symbol": "   "},
            },
        }

        tx = Transaction.model_validate(data)

        assert tx.symbol is None
