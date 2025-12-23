"""Tests for pagination iterators."""

from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from etrade_client.api.accounts import AccountsAPI
from etrade_client.api.orders import OrdersAPI
from etrade_client.models.orders import Order, OrderDetail, OrderInstrument, OrderProduct
from etrade_client.models.transactions import Transaction


class TestTransactionIterator:
    """Tests for iter_transactions async generator."""

    @pytest.fixture
    def accounts_api(self):
        """Create an AccountsAPI instance with mocked dependencies."""
        config = MagicMock()
        auth = MagicMock()
        return AccountsAPI(config, auth)

    @pytest.mark.asyncio
    async def test_yields_transactions_from_single_page(self, accounts_api) -> None:
        """Should yield all transactions from a single page."""
        # Mock response with no more pages
        mock_response = MagicMock()
        mock_response.transactions = [
            MagicMock(spec=Transaction, transaction_id="tx1"),
            MagicMock(spec=Transaction, transaction_id="tx2"),
        ]
        mock_response.has_more = False
        mock_response.marker = None

        accounts_api.list_transactions = AsyncMock(return_value=mock_response)

        results = []
        async for tx in accounts_api.iter_transactions("acc123"):
            results.append(tx)

        assert len(results) == 2
        accounts_api.list_transactions.assert_called_once()

    @pytest.mark.asyncio
    async def test_fetches_multiple_pages(self, accounts_api) -> None:
        """Should fetch additional pages when has_more is True."""
        # First page with more available
        page1 = MagicMock()
        page1.transactions = [MagicMock(spec=Transaction, transaction_id="tx1")]
        page1.has_more = True
        page1.marker = "page2_marker"

        # Second page with more available
        page2 = MagicMock()
        page2.transactions = [MagicMock(spec=Transaction, transaction_id="tx2")]
        page2.has_more = True
        page2.marker = "page3_marker"

        # Third (last) page
        page3 = MagicMock()
        page3.transactions = [MagicMock(spec=Transaction, transaction_id="tx3")]
        page3.has_more = False
        page3.marker = None

        accounts_api.list_transactions = AsyncMock(side_effect=[page1, page2, page3])

        results = []
        async for tx in accounts_api.iter_transactions("acc123"):
            results.append(tx)

        assert len(results) == 3
        assert accounts_api.list_transactions.call_count == 3

    @pytest.mark.asyncio
    async def test_passes_marker_to_next_page(self, accounts_api) -> None:
        """Should pass marker from previous page to fetch next."""
        page1 = MagicMock()
        page1.transactions = [MagicMock(spec=Transaction, transaction_id="tx1")]
        page1.has_more = True
        page1.marker = "next_page_token"

        page2 = MagicMock()
        page2.transactions = [MagicMock(spec=Transaction, transaction_id="tx2")]
        page2.has_more = False
        page2.marker = None

        accounts_api.list_transactions = AsyncMock(side_effect=[page1, page2])

        async for _ in accounts_api.iter_transactions("acc123"):
            pass

        # Second call should include the marker
        calls = accounts_api.list_transactions.call_args_list
        assert calls[0].kwargs.get("marker") is None
        assert calls[1].kwargs.get("marker") == "next_page_token"

    @pytest.mark.asyncio
    async def test_respects_limit(self, accounts_api) -> None:
        """Should stop yielding after limit is reached."""
        # Page with 5 transactions
        page = MagicMock()
        page.transactions = [
            MagicMock(spec=Transaction, transaction_id=f"tx{i}") for i in range(5)
        ]
        page.has_more = True
        page.marker = "more"

        accounts_api.list_transactions = AsyncMock(return_value=page)

        results = []
        async for tx in accounts_api.iter_transactions("acc123", limit=3):
            results.append(tx)

        assert len(results) == 3
        # Should only fetch one page since limit was reached
        accounts_api.list_transactions.assert_called_once()

    @pytest.mark.asyncio
    async def test_limit_spans_multiple_pages(self, accounts_api) -> None:
        """Should respect limit even when spanning multiple pages."""
        page1 = MagicMock()
        page1.transactions = [MagicMock(spec=Transaction, transaction_id=f"p1-{i}") for i in range(3)]
        page1.has_more = True
        page1.marker = "page2"

        page2 = MagicMock()
        page2.transactions = [MagicMock(spec=Transaction, transaction_id=f"p2-{i}") for i in range(3)]
        page2.has_more = False
        page2.marker = None

        accounts_api.list_transactions = AsyncMock(side_effect=[page1, page2])

        results = []
        async for tx in accounts_api.iter_transactions("acc123", limit=5):
            results.append(tx)

        assert len(results) == 5  # 3 from page1, 2 from page2
        assert accounts_api.list_transactions.call_count == 2

    @pytest.mark.asyncio
    async def test_handles_empty_response(self, accounts_api) -> None:
        """Should handle empty transaction list gracefully."""
        page = MagicMock()
        page.transactions = []
        page.has_more = False
        page.marker = None

        accounts_api.list_transactions = AsyncMock(return_value=page)

        results = []
        async for tx in accounts_api.iter_transactions("acc123"):
            results.append(tx)

        assert len(results) == 0

    @pytest.mark.asyncio
    async def test_passes_filters_to_api(self, accounts_api) -> None:
        """Should pass date filters and other params to API."""
        page = MagicMock()
        page.transactions = []
        page.has_more = False
        page.marker = None

        accounts_api.list_transactions = AsyncMock(return_value=page)

        start = date(2025, 1, 1)
        end = date(2025, 1, 31)

        async for _ in accounts_api.iter_transactions(
            "acc123",
            start_date=start,
            end_date=end,
            sort_order="ASC",
            count=25,
        ):
            pass

        accounts_api.list_transactions.assert_called_with(
            "acc123",
            start_date=start,
            end_date=end,
            sort_order="ASC",
            marker=None,
            count=25,
        )


class TestOrderIterator:
    """Tests for iter_orders async generator."""

    @pytest.fixture
    def orders_api(self):
        """Create an OrdersAPI instance with mocked dependencies."""
        config = MagicMock()
        auth = MagicMock()
        return OrdersAPI(config, auth)

    def _make_mock_order(self, order_id: int) -> MagicMock:
        """Create a mock Order object."""
        order = MagicMock(spec=Order)
        order.order_id = order_id
        return order

    @pytest.mark.asyncio
    async def test_yields_orders_from_single_page(self, orders_api) -> None:
        """Should yield all orders from a single page."""
        page = MagicMock()
        page.orders = [self._make_mock_order(1), self._make_mock_order(2)]
        page.has_more = False
        page.marker = None

        orders_api.list_orders = AsyncMock(return_value=page)

        results = []
        async for order in orders_api.iter_orders("acc123"):
            results.append(order)

        assert len(results) == 2

    @pytest.mark.asyncio
    async def test_fetches_multiple_pages(self, orders_api) -> None:
        """Should fetch multiple pages when has_more is True."""
        page1 = MagicMock()
        page1.orders = [self._make_mock_order(1)]
        page1.has_more = True
        page1.marker = "page2"

        page2 = MagicMock()
        page2.orders = [self._make_mock_order(2)]
        page2.has_more = False
        page2.marker = None

        orders_api.list_orders = AsyncMock(side_effect=[page1, page2])

        results = []
        async for order in orders_api.iter_orders("acc123"):
            results.append(order)

        assert len(results) == 2
        assert orders_api.list_orders.call_count == 2

    @pytest.mark.asyncio
    async def test_respects_limit(self, orders_api) -> None:
        """Should stop after limit is reached."""
        page = MagicMock()
        page.orders = [self._make_mock_order(i) for i in range(10)]
        page.has_more = True
        page.marker = "more"

        orders_api.list_orders = AsyncMock(return_value=page)

        results = []
        async for order in orders_api.iter_orders("acc123", limit=5):
            results.append(order)

        assert len(results) == 5


class TestPaginationBehavior:
    """Tests for general pagination behavior patterns."""

    @pytest.fixture
    def accounts_api(self):
        """Create an AccountsAPI instance."""
        config = MagicMock()
        auth = MagicMock()
        return AccountsAPI(config, auth)

    @pytest.mark.asyncio
    async def test_lazy_loading_does_not_fetch_ahead(self, accounts_api) -> None:
        """Pagination should be lazy - no fetching until consumed."""
        page1 = MagicMock()
        page1.transactions = [MagicMock(spec=Transaction, transaction_id="tx1")]
        page1.has_more = True
        page1.marker = "page2"

        page2 = MagicMock()
        page2.transactions = [MagicMock(spec=Transaction, transaction_id="tx2")]
        page2.has_more = False

        accounts_api.list_transactions = AsyncMock(side_effect=[page1, page2])

        # Create iterator but don't consume it
        iterator = accounts_api.iter_transactions("acc123")

        # No API calls yet
        accounts_api.list_transactions.assert_not_called()

        # Consume first item
        await iterator.__anext__()

        # First page should be fetched
        assert accounts_api.list_transactions.call_count == 1

    @pytest.mark.asyncio
    async def test_stops_on_has_more_false(self, accounts_api) -> None:
        """Should stop fetching when has_more becomes False."""
        page = MagicMock()
        page.transactions = [MagicMock(spec=Transaction, transaction_id="tx1")]
        page.has_more = False
        page.marker = "ignored"  # Marker exists but has_more is False

        accounts_api.list_transactions = AsyncMock(return_value=page)

        results = []
        async for tx in accounts_api.iter_transactions("acc123"):
            results.append(tx)

        # Should only make one call
        assert accounts_api.list_transactions.call_count == 1

    @pytest.mark.asyncio
    async def test_stops_on_no_marker(self, accounts_api) -> None:
        """Should stop when marker is None even if has_more is somehow True."""
        page = MagicMock()
        page.transactions = [MagicMock(spec=Transaction, transaction_id="tx1")]
        page.has_more = True
        page.marker = None  # No marker despite has_more=True

        accounts_api.list_transactions = AsyncMock(return_value=page)

        results = []
        async for tx in accounts_api.iter_transactions("acc123"):
            results.append(tx)

        # Should only make one call
        assert accounts_api.list_transactions.call_count == 1

    @pytest.mark.asyncio
    async def test_early_break_stops_fetching(self, accounts_api) -> None:
        """Breaking early should prevent additional API calls."""
        page1 = MagicMock()
        page1.transactions = [MagicMock(spec=Transaction, transaction_id="tx1")]
        page1.has_more = True
        page1.marker = "page2"

        page2 = MagicMock()
        page2.transactions = [MagicMock(spec=Transaction, transaction_id="tx2")]
        page2.has_more = False

        accounts_api.list_transactions = AsyncMock(side_effect=[page1, page2])

        async for tx in accounts_api.iter_transactions("acc123"):
            break  # Exit after first item

        # Should only fetch first page
        assert accounts_api.list_transactions.call_count == 1
