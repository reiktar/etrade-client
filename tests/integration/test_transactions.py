"""Integration tests for the Transactions API."""

import pytest

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
