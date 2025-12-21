"""Integration tests for the Accounts API."""

import pytest


pytestmark = pytest.mark.integration


class TestAccountsAPI:
    """Integration tests for AccountsAPI."""

    async def test_list_accounts(self, async_integration_client, analyze_response) -> None:
        """Should list accounts from the sandbox."""
        client = async_integration_client

        response = await client.accounts.list_accounts()

        # Sandbox should have at least one test account
        assert response.accounts is not None
        assert len(response.accounts) > 0

        # Analyze individual Account models (not wrapper)
        for account in response.accounts:
            analyze_response(account, "accounts/list/Account")

        # Verify account structure
        account = response.accounts[0]
        assert account.account_id is not None
        assert account.account_id_key is not None

    async def test_get_account_balance(self, async_integration_client, analyze_response) -> None:
        """Should get account balance from the sandbox."""
        client = async_integration_client

        # First get an account
        accounts_response = await client.accounts.list_accounts()
        assert len(accounts_response.accounts) > 0

        account = accounts_response.accounts[0]

        # Get balance
        balance_response = await client.accounts.get_balance(account.account_id_key)

        # Analyze the AccountBalance model (not wrapper)
        analyze_response(balance_response.balance, "accounts/balance")

        assert balance_response.balance is not None
        # Cash balance is nested under balance.cash or balance.computed
        assert balance_response.balance.cash is not None or balance_response.balance.computed is not None

    async def test_get_portfolio(self, async_integration_client, analyze_response) -> None:
        """Should get portfolio from the sandbox."""
        client = async_integration_client

        # First get an account
        accounts_response = await client.accounts.list_accounts()
        assert len(accounts_response.accounts) > 0

        account = accounts_response.accounts[0]

        # Get portfolio
        portfolio_response = await client.accounts.get_portfolio(account.account_id_key)

        # Analyze individual PortfolioPosition models
        for position in portfolio_response.positions:
            analyze_response(position, "accounts/portfolio/Position")

        # Portfolio may be empty in sandbox, but should have the structure
        assert portfolio_response is not None
        # positions may be empty list
        assert hasattr(portfolio_response, "positions")
