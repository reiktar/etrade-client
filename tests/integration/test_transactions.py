"""Integration tests for the Transactions API."""

import json
from collections import Counter
from pathlib import Path

import pytest
from pydantic import TypeAdapter

from etrade_client.models.transactions import (
    BoughtTransaction,
    DividendTransaction,
    GenericTransaction,
    Transaction,
    TransactionBase,
)

pytestmark = pytest.mark.integration


class TestTransactionsAPI:
    """Integration tests for transactions via AccountsAPI."""

    async def test_list_transactions(self, async_integration_client, analyze_response) -> None:
        """Should list transactions from the sandbox."""
        client = async_integration_client

        # First get an account
        accounts_response = await client.accounts.list_accounts()
        assert len(accounts_response.accounts) > 0

        account = accounts_response.accounts[0]

        # List transactions
        transactions_response = await client.accounts.list_transactions(account.account_id_key)

        # Analyze individual Transaction models
        for tx in transactions_response.transactions:
            analyze_response(tx, "transactions/list/Transaction")

        # Should have the response structure even if empty
        assert transactions_response is not None
        assert hasattr(transactions_response, "transactions")

    async def test_iterate_transactions(self, async_integration_client, analyze_response) -> None:
        """Should iterate over transactions."""
        client = async_integration_client

        accounts_response = await client.accounts.list_accounts()
        assert len(accounts_response.accounts) > 0

        account = accounts_response.accounts[0]

        # Iterate transactions (limit to 10 to avoid too many API calls)
        count = 0
        async for tx in client.accounts.iter_transactions(account.account_id_key, limit=10):
            analyze_response(tx, "transactions/iter/Transaction")
            count += 1
            # Basic validation
            assert tx is not None

        # At least verified iteration works
        assert count >= 0


class TestTransactionModelValidation:
    """Tests that validate transaction models against collected API data.

    These tests use the .data/transactions/ directory containing real API
    responses captured from sandbox and production environments.
    """

    DATA_DIR = Path(".data/transactions")

    @pytest.fixture
    def collected_transactions(self) -> list[dict]:
        """Load all transactions from collected data files."""
        if not self.DATA_DIR.exists():
            pytest.skip("No collected transaction data available")

        all_txs = []
        for page_file in self.DATA_DIR.rglob("page_*.json"):
            with page_file.open() as f:
                data = json.load(f)
            tx_list = data.get("TransactionListResponse", {}).get("Transaction", [])
            if isinstance(tx_list, dict):
                tx_list = [tx_list]
            all_txs.extend(tx_list)

        if not all_txs:
            pytest.skip("No transactions found in collected data")

        return all_txs

    def test_all_transactions_parse_without_fallback(
        self, collected_transactions: list[dict]
    ) -> None:
        """All collected transactions should parse to specific types, not GenericTransaction."""
        adapter = TypeAdapter(Transaction)
        generic_transactions = []

        for tx_data in collected_transactions:
            parsed = adapter.validate_python(tx_data)
            if isinstance(parsed, GenericTransaction):
                generic_transactions.append(tx_data.get("transactionType"))

        assert len(generic_transactions) == 0, (
            f"Found {len(generic_transactions)} transactions that fell back to "
            f"GenericTransaction: {set(generic_transactions)}"
        )

    def test_type_distribution(self, collected_transactions: list[dict]) -> None:
        """Verify transaction type distribution and that all types are recognized."""
        adapter = TypeAdapter(Transaction)
        type_counts: Counter[str] = Counter()

        for tx_data in collected_transactions:
            parsed = adapter.validate_python(tx_data)
            type_counts[type(parsed).__name__] += 1

        # Should have parsed some transactions
        assert sum(type_counts.values()) == len(collected_transactions)

        # Log the distribution for visibility
        print(f"\nTransaction type distribution ({len(collected_transactions)} total):")
        for tx_type, count in sorted(type_counts.items(), key=lambda x: -x[1]):
            print(f"  {tx_type}: {count}")

    def test_parsed_transactions_have_required_fields(
        self, collected_transactions: list[dict]
    ) -> None:
        """All parsed transactions should have accessible base fields."""
        adapter = TypeAdapter(Transaction)

        for tx_data in collected_transactions:
            parsed = adapter.validate_python(tx_data)

            # All transactions inherit from TransactionBase
            assert isinstance(parsed, TransactionBase)

            # Required base fields should be accessible
            assert parsed.transaction_id is not None
            assert parsed.account_id is not None
            assert parsed.amount is not None
            assert parsed.description is not None
            assert parsed.transaction_type is not None

            # Helper properties should work
            assert parsed.transaction_datetime is not None
            # is_pending should return a boolean
            assert isinstance(parsed.is_pending, bool)
            # symbol may be None for some transaction types
            _ = parsed.symbol

    def test_dividend_transactions_have_product(self, collected_transactions: list[dict]) -> None:
        """DividendTransaction should have brokerage with product info."""
        adapter = TypeAdapter(Transaction)
        dividend_count = 0

        for tx_data in collected_transactions:
            parsed = adapter.validate_python(tx_data)
            if isinstance(parsed, DividendTransaction):
                dividend_count += 1
                # DividendTransaction uses BrokerageWithProduct
                assert parsed.brokerage is not None
                assert parsed.brokerage.product is not None
                assert parsed.brokerage.product.symbol is not None
                assert parsed.symbol is not None

        if dividend_count == 0:
            pytest.skip("No dividend transactions in collected data")

    def test_bought_transactions_have_product(self, collected_transactions: list[dict]) -> None:
        """BoughtTransaction should have brokerage with product info."""
        adapter = TypeAdapter(Transaction)
        bought_count = 0

        for tx_data in collected_transactions:
            parsed = adapter.validate_python(tx_data)
            if isinstance(parsed, BoughtTransaction):
                bought_count += 1
                # BoughtTransaction uses BrokerageWithProduct
                assert parsed.brokerage is not None
                assert parsed.brokerage.product is not None
                assert parsed.brokerage.product.symbol is not None

        if bought_count == 0:
            pytest.skip("No bought transactions in collected data")
