"""Tests for request serialization - API request body construction."""

from datetime import date
from unittest.mock import AsyncMock, MagicMock

import pytest

from etrade_client.api.orders import OrdersAPI
from etrade_client.builders import (
    EquityOrderBuilder,
    OptionOrderBuilder,
    OptionType,
    OrderAction,
    PriceType,
)


class TestEquityOrderSerialization:
    """Tests for equity order request body structure."""

    def test_market_order_structure(self) -> None:
        """Market order should have correct request structure."""
        order = EquityOrderBuilder("AAPL").buy(100).market().build()

        # Top-level structure
        assert "orderType" in order
        assert order["orderType"] == "EQ"
        assert "clientOrderId" in order
        assert "Order" in order
        assert isinstance(order["Order"], list)
        assert len(order["Order"]) == 1

        # Order detail structure
        detail = order["Order"][0]
        assert detail["priceType"] == "MARKET"
        assert detail["orderTerm"] == "GOOD_FOR_DAY"
        assert detail["marketSession"] == "REGULAR"

        # Instrument structure
        assert "Instrument" in detail
        assert isinstance(detail["Instrument"], list)
        assert len(detail["Instrument"]) == 1

        instrument = detail["Instrument"][0]
        assert "Product" in instrument
        assert instrument["Product"]["symbol"] == "AAPL"
        assert instrument["Product"]["securityType"] == "EQ"
        assert instrument["orderAction"] == "BUY"
        assert instrument["quantity"] == 100

    def test_limit_order_includes_price(self) -> None:
        """Limit order should include limit price."""
        order = EquityOrderBuilder("MSFT").buy(50).limit(350.00).build()

        detail = order["Order"][0]
        assert detail["priceType"] == "LIMIT"
        assert detail["limitPrice"] == 350.00

    def test_stop_order_includes_stop_price(self) -> None:
        """Stop order should include stop price."""
        order = EquityOrderBuilder("GOOG").sell(25).stop(140.00).build()

        detail = order["Order"][0]
        assert detail["priceType"] == "STOP"
        assert detail["stopPrice"] == 140.00

    def test_stop_limit_order_includes_both_prices(self) -> None:
        """Stop-limit order should include both stop and limit prices."""
        order = (
            EquityOrderBuilder("TSLA")
            .sell(10)
            .stop_limit(stop_price=200.00, limit_price=195.00)
            .build()
        )

        detail = order["Order"][0]
        assert detail["priceType"] == "STOP_LIMIT"
        assert detail["stopPrice"] == 200.00
        assert detail["limitPrice"] == 195.00

    def test_gtc_order_term(self) -> None:
        """GTC order should have correct order term."""
        order = EquityOrderBuilder("AAPL").buy(100).limit(150.00).good_until_cancel().build()

        assert order["Order"][0]["orderTerm"] == "GOOD_UNTIL_CANCEL"

    def test_extended_session(self) -> None:
        """Extended hours order should have correct market session."""
        order = EquityOrderBuilder("AAPL").buy(100).limit(150.00).extended_session().build()

        assert order["Order"][0]["marketSession"] == "EXTENDED"

    def test_all_or_none_flag(self) -> None:
        """All-or-none order should have flag set."""
        order = EquityOrderBuilder("AAPL").buy(100).all_or_none().build()

        assert order["Order"][0]["allOrNone"] == "true"

    def test_sell_short_action(self) -> None:
        """Sell short should have correct order action."""
        order = EquityOrderBuilder("GME").sell_short(100).limit(25.00).build()

        instrument = order["Order"][0]["Instrument"][0]
        assert instrument["orderAction"] == "SELL_SHORT"

    def test_buy_to_cover_action(self) -> None:
        """Buy to cover should have correct order action."""
        order = EquityOrderBuilder("GME").buy_to_cover(100).market().build()

        instrument = order["Order"][0]["Instrument"][0]
        assert instrument["orderAction"] == "BUY_TO_COVER"

    def test_symbol_uppercased(self) -> None:
        """Symbol should be uppercased in request."""
        order = EquityOrderBuilder("aapl").buy(100).build()

        symbol = order["Order"][0]["Instrument"][0]["Product"]["symbol"]
        assert symbol == "AAPL"

    def test_custom_client_order_id(self) -> None:
        """Should use provided client order ID."""
        order = EquityOrderBuilder("AAPL").buy(100).client_order_id("my-order-123").build()

        assert order["clientOrderId"] == "my-order-123"


class TestOptionOrderSerialization:
    """Tests for option order request body structure."""

    def test_option_order_structure(self) -> None:
        """Option order should have correct request structure."""
        order = (
            OptionOrderBuilder("AAPL", "2025-01-17", 150.00, OptionType.CALL)
            .buy_to_open(5)
            .limit(2.50)
            .build()
        )

        # Top-level structure
        assert order["orderType"] == "OPTN"
        assert "clientOrderId" in order

        # Order detail
        detail = order["Order"][0]
        assert detail["priceType"] == "LIMIT"
        assert detail["limitPrice"] == 2.50

        # Instrument/Product for options
        instrument = detail["Instrument"][0]
        assert instrument["orderAction"] == "BUY_OPEN"
        assert instrument["quantity"] == 5

        product = instrument["Product"]
        assert product["securityType"] == "OPTN"
        assert product["callPut"] == "CALL"
        assert product["strikePrice"] == 150.00
        assert product["expiryYear"] == 2025
        assert product["expiryMonth"] == 1
        assert product["expiryDay"] == 17

    def test_put_option_call_put_value(self) -> None:
        """Put option should have correct callPut value."""
        order = (
            OptionOrderBuilder("MSFT", "2025-03-21", 400.00, OptionType.PUT)
            .sell_to_close(10)
            .market()
            .build()
        )

        product = order["Order"][0]["Instrument"][0]["Product"]
        assert product["callPut"] == "PUT"

    def test_option_symbol_occ_format(self) -> None:
        """Option symbol should be in OCC format."""
        builder = OptionOrderBuilder("AAPL", "2025-01-17", 150.00, OptionType.CALL)

        symbol = builder._build_option_symbol()

        # Format: AAPL250117C00150000
        assert symbol == "AAPL250117C00150000"

    def test_option_symbol_put(self) -> None:
        """Put option symbol should have P indicator."""
        builder = OptionOrderBuilder("MSFT", "2025-06-20", 425.50, OptionType.PUT)

        symbol = builder._build_option_symbol()

        # Strike 425.50 * 1000 = 425500 -> 00425500
        assert symbol == "MSFT250620P00425500"

    def test_sell_to_open_action(self) -> None:
        """Sell to open should have correct action."""
        order = (
            OptionOrderBuilder("SPY", "2025-02-14", 500.00, OptionType.CALL)
            .sell_to_open(2)
            .limit(5.00)
            .build()
        )

        instrument = order["Order"][0]["Instrument"][0]
        assert instrument["orderAction"] == "SELL_OPEN"

    def test_buy_to_close_action(self) -> None:
        """Buy to close should have correct action."""
        order = (
            OptionOrderBuilder("NVDA", "2025-04-18", 800.00, OptionType.PUT)
            .buy_to_close(3)
            .limit(10.00)
            .build()
        )

        instrument = order["Order"][0]["Instrument"][0]
        assert instrument["orderAction"] == "BUY_CLOSE"


class TestBuilderValidation:
    """Tests for builder validation before serialization."""

    def test_equity_missing_action_raises(self) -> None:
        """Should raise if no action specified."""
        with pytest.raises(ValueError, match="Order action required"):
            EquityOrderBuilder("AAPL").build()

    def test_equity_missing_limit_price_raises(self) -> None:
        """Should raise if limit order without price."""
        builder = EquityOrderBuilder("AAPL").buy(100)
        builder._price_type = PriceType.LIMIT
        builder._limit_price = None

        with pytest.raises(ValueError, match="Limit price required"):
            builder.build()

    def test_equity_missing_stop_price_raises(self) -> None:
        """Should raise if stop order without price."""
        builder = EquityOrderBuilder("AAPL").buy(100)
        builder._price_type = PriceType.STOP
        builder._stop_price = None

        with pytest.raises(ValueError, match="Stop price required"):
            builder.build()

    def test_equity_zero_quantity_raises(self) -> None:
        """Should raise if quantity is zero."""
        builder = EquityOrderBuilder("AAPL")
        builder._action = OrderAction.BUY
        builder._quantity = 0

        with pytest.raises(ValueError, match="Quantity must be positive"):
            builder.build()

    def test_option_missing_action_raises(self) -> None:
        """Should raise if no action specified for option."""
        with pytest.raises(ValueError, match="Order action required"):
            OptionOrderBuilder("AAPL", "2025-01-17", 150.00, OptionType.CALL).build()


class TestAPIRequestBuilding:
    """Tests for API request body construction."""

    @pytest.fixture
    def orders_api(self):
        """Create an OrdersAPI with mocked request method."""
        config = MagicMock()
        auth = MagicMock()
        api = OrdersAPI(config, auth)
        api._post = AsyncMock(
            return_value={
                "PreviewOrderResponse": {
                    "orderType": "EQ",
                    "PreviewIds": [{"previewId": 123}],
                }
            }
        )
        return api

    @pytest.mark.asyncio
    async def test_preview_order_sends_correct_body(self, orders_api) -> None:
        """preview_order should send order dict as request body."""
        order = EquityOrderBuilder("AAPL").buy(100).limit(150.00).build()

        await orders_api.preview_order("acc123", order)

        # Verify the order dict was passed to _post
        # _post signature: (endpoint, json_body)
        orders_api._post.assert_called_once()
        call_args = orders_api._post.call_args
        # Body is wrapped in PreviewOrderRequest
        sent_body = call_args[0][1]  # Second positional arg is the body
        assert sent_body["PreviewOrderRequest"] == order

    @pytest.mark.asyncio
    async def test_preview_preserves_order_structure(self, orders_api) -> None:
        """Order structure should be preserved through the API call."""
        order = (
            EquityOrderBuilder("MSFT")
            .sell(50)
            .stop_limit(stop_price=350.00, limit_price=345.00)
            .good_until_cancel()
            .build()
        )

        await orders_api.preview_order("acc123", order)

        # Body is wrapped in PreviewOrderRequest
        sent_body = orders_api._post.call_args[0][1]["PreviewOrderRequest"]

        # Verify key fields preserved
        assert sent_body["orderType"] == "EQ"
        assert sent_body["Order"][0]["priceType"] == "STOP_LIMIT"
        assert sent_body["Order"][0]["stopPrice"] == 350.00
        assert sent_body["Order"][0]["limitPrice"] == 345.00
        assert sent_body["Order"][0]["orderTerm"] == "GOOD_UNTIL_CANCEL"
        assert sent_body["Order"][0]["Instrument"][0]["orderAction"] == "SELL"


class TestDateFormatting:
    """Tests for date formatting in API requests."""

    @pytest.fixture
    def accounts_api(self):
        """Create an AccountsAPI with mocked request method."""
        from etrade_client.api.accounts import AccountsAPI

        config = MagicMock()
        auth = MagicMock()
        api = AccountsAPI(config, auth)
        api._get = AsyncMock(return_value={"TransactionListResponse": {"Transaction": []}})
        return api

    @pytest.mark.asyncio
    async def test_transaction_dates_formatted_correctly(self, accounts_api) -> None:
        """Transaction date params should be in MMDDYYYY format."""
        start = date(2025, 1, 15)
        end = date(2025, 1, 31)

        await accounts_api.list_transactions(
            "acc123",
            start_date=start,
            end_date=end,
        )

        call_args = accounts_api._get.call_args
        params = call_args[1]["params"]

        # E*Trade expects MMDDYYYY format
        assert params["startDate"] == "01152025"
        assert params["endDate"] == "01312025"

    @pytest.mark.asyncio
    async def test_optional_dates_not_sent(self, accounts_api) -> None:
        """Optional date params should not be sent if not provided."""
        await accounts_api.list_transactions("acc123")

        call_args = accounts_api._get.call_args
        params = call_args[1]["params"]

        assert "startDate" not in params
        assert "endDate" not in params
