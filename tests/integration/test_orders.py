"""Integration tests for the Orders API."""

import pytest


pytestmark = pytest.mark.integration


class TestOrdersAPI:
    """Integration tests for OrdersAPI."""

    async def test_list_orders(self, async_integration_client, analyze_response) -> None:
        """Should list orders from the sandbox."""
        client = async_integration_client

        # First get an account
        accounts_response = await client.accounts.list_accounts()
        assert len(accounts_response.accounts) > 0

        account = accounts_response.accounts[0]

        # List orders (may be empty in sandbox)
        orders_response = await client.orders.list_orders(account.account_id_key)

        # Analyze individual Order models
        for order in orders_response.orders:
            analyze_response(order, "orders/list/Order")

        # Should have the response structure even if empty
        assert orders_response is not None
        assert hasattr(orders_response, "orders")

    @pytest.mark.xfail(reason="Sandbox returns 500 error when filtering by status")
    async def test_list_orders_with_filters(self, async_integration_client, analyze_response) -> None:
        """Should filter orders by status."""
        client = async_integration_client

        accounts_response = await client.accounts.list_accounts()
        assert len(accounts_response.accounts) > 0

        account = accounts_response.accounts[0]

        # Test various status filters
        for status in ["OPEN", "EXECUTED", "CANCELLED"]:
            orders_response = await client.orders.list_orders(
                account.account_id_key,
                status=status,
            )
            assert orders_response is not None

            # Analyze any orders found
            for order in orders_response.orders:
                analyze_response(order, f"orders/list/{status}/Order")
