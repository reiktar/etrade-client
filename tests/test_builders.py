"""Tests for order builders."""

import pytest

from etrade_client.builders import (
    EquityOrderBuilder,
    OptionOrderBuilder,
    OptionType,
    OrderAction,
    OrderTerm,
    PriceType,
)


class TestEquityOrderBuilder:
    """Tests for EquityOrderBuilder."""

    def test_simple_market_buy(self) -> None:
        """Build a simple market buy order."""
        order = EquityOrderBuilder("AAPL").buy(100).build()

        assert order["orderType"] == "EQ"
        assert "clientOrderId" in order
        assert len(order["Order"]) == 1

        detail = order["Order"][0]
        assert detail["priceType"] == "MARKET"
        assert detail["orderTerm"] == "GOOD_FOR_DAY"
        assert detail["marketSession"] == "REGULAR"

        instrument = detail["Instrument"][0]
        assert instrument["Product"]["symbol"] == "AAPL"
        assert instrument["Product"]["securityType"] == "EQ"
        assert instrument["orderAction"] == "BUY"
        assert instrument["quantity"] == 100

    def test_limit_order(self) -> None:
        """Build a limit order."""
        order = EquityOrderBuilder("MSFT").buy(50).limit(350.00).build()

        detail = order["Order"][0]
        assert detail["priceType"] == "LIMIT"
        assert detail["limitPrice"] == 350.00

    def test_stop_order(self) -> None:
        """Build a stop order."""
        order = EquityOrderBuilder("GOOG").sell(25).stop(140.00).build()

        detail = order["Order"][0]
        assert detail["priceType"] == "STOP"
        assert detail["stopPrice"] == 140.00
        assert detail["Instrument"][0]["orderAction"] == "SELL"

    def test_stop_limit_order(self) -> None:
        """Build a stop-limit order."""
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

    def test_sell_short(self) -> None:
        """Build a short sell order."""
        order = EquityOrderBuilder("GME").sell_short(100).limit(25.00).build()

        instrument = order["Order"][0]["Instrument"][0]
        assert instrument["orderAction"] == "SELL_SHORT"

    def test_buy_to_cover(self) -> None:
        """Build a buy-to-cover order."""
        order = EquityOrderBuilder("GME").buy_to_cover(100).market().build()

        instrument = order["Order"][0]["Instrument"][0]
        assert instrument["orderAction"] == "BUY_TO_COVER"

    def test_good_until_cancel(self) -> None:
        """Build a GTC order."""
        order = EquityOrderBuilder("AAPL").buy(100).limit(150.00).good_until_cancel().build()

        assert order["Order"][0]["orderTerm"] == "GOOD_UNTIL_CANCEL"

    def test_extended_session(self) -> None:
        """Build an extended hours order."""
        order = EquityOrderBuilder("AAPL").buy(100).limit(150.00).extended_session().build()

        assert order["Order"][0]["marketSession"] == "EXTENDED"

    def test_all_or_none(self) -> None:
        """Build an all-or-none order."""
        order = EquityOrderBuilder("AAPL").buy(100).all_or_none().build()

        assert order["Order"][0]["allOrNone"] == "true"

    def test_custom_client_order_id(self) -> None:
        """Build an order with custom client order ID."""
        order = EquityOrderBuilder("AAPL").buy(100).client_order_id("my-order-123").build()

        assert order["clientOrderId"] == "my-order-123"

    def test_symbol_uppercase(self) -> None:
        """Symbol should be uppercased."""
        order = EquityOrderBuilder("aapl").buy(100).build()

        assert order["Order"][0]["Instrument"][0]["Product"]["symbol"] == "AAPL"

    def test_fluent_chaining(self) -> None:
        """Test full fluent chain."""
        order = (
            EquityOrderBuilder("AAPL")
            .buy(100)
            .limit(150.00)
            .good_until_cancel()
            .extended_session()
            .all_or_none()
            .client_order_id("test-123")
            .build()
        )

        assert order["clientOrderId"] == "test-123"
        detail = order["Order"][0]
        assert detail["priceType"] == "LIMIT"
        assert detail["limitPrice"] == 150.00
        assert detail["orderTerm"] == "GOOD_UNTIL_CANCEL"
        assert detail["marketSession"] == "EXTENDED"
        assert detail["allOrNone"] == "true"

    def test_missing_action_raises(self) -> None:
        """Should raise if no action specified."""
        with pytest.raises(ValueError, match="Order action required"):
            EquityOrderBuilder("AAPL").build()

    def test_missing_limit_price_raises(self) -> None:
        """Should raise if limit order without price."""
        builder = EquityOrderBuilder("AAPL").buy(100)
        builder._price_type = PriceType.LIMIT
        builder._limit_price = None

        with pytest.raises(ValueError, match="Limit price required"):
            builder.build()

    def test_missing_stop_price_raises(self) -> None:
        """Should raise if stop order without price."""
        builder = EquityOrderBuilder("AAPL").buy(100)
        builder._price_type = PriceType.STOP
        builder._stop_price = None

        with pytest.raises(ValueError, match="Stop price required"):
            builder.build()

    def test_zero_quantity_raises(self) -> None:
        """Should raise if quantity is zero."""
        builder = EquityOrderBuilder("AAPL")
        builder._action = OrderAction.BUY
        builder._quantity = 0

        with pytest.raises(ValueError, match="Quantity must be positive"):
            builder.build()


class TestOptionOrderBuilder:
    """Tests for OptionOrderBuilder."""

    def test_buy_to_open_call(self) -> None:
        """Build a buy-to-open call option order."""
        order = (
            OptionOrderBuilder("AAPL", "2025-01-17", 150.00, OptionType.CALL)
            .buy_to_open(5)
            .limit(2.50)
            .build()
        )

        assert order["orderType"] == "OPTN"
        assert "clientOrderId" in order

        detail = order["Order"][0]
        assert detail["priceType"] == "LIMIT"
        assert detail["limitPrice"] == 2.50

        instrument = detail["Instrument"][0]
        assert instrument["orderAction"] == "BUY_OPEN"
        assert instrument["quantity"] == 5
        assert instrument["Product"]["securityType"] == "OPTN"
        assert instrument["Product"]["callPut"] == "CALL"
        assert instrument["Product"]["strikePrice"] == 150.00
        assert instrument["Product"]["expiryYear"] == 2025
        assert instrument["Product"]["expiryMonth"] == 1
        assert instrument["Product"]["expiryDay"] == 17

    def test_sell_to_close_put(self) -> None:
        """Build a sell-to-close put option order."""
        order = (
            OptionOrderBuilder("MSFT", "2025-03-21", 400.00, OptionType.PUT)
            .sell_to_close(10)
            .market()
            .build()
        )

        instrument = order["Order"][0]["Instrument"][0]
        assert instrument["orderAction"] == "SELL_CLOSE"
        assert instrument["Product"]["callPut"] == "PUT"

    def test_sell_to_open(self) -> None:
        """Build a sell-to-open (write) order."""
        order = (
            OptionOrderBuilder("SPY", "2025-02-14", 500.00, OptionType.CALL)
            .sell_to_open(2)
            .limit(5.00)
            .build()
        )

        instrument = order["Order"][0]["Instrument"][0]
        assert instrument["orderAction"] == "SELL_OPEN"

    def test_buy_to_close(self) -> None:
        """Build a buy-to-close order."""
        order = (
            OptionOrderBuilder("NVDA", "2025-04-18", 800.00, OptionType.PUT)
            .buy_to_close(3)
            .limit(10.00)
            .build()
        )

        instrument = order["Order"][0]["Instrument"][0]
        assert instrument["orderAction"] == "BUY_CLOSE"

    def test_option_symbol_format(self) -> None:
        """Option symbol should follow OCC format."""
        builder = OptionOrderBuilder("AAPL", "2025-01-17", 150.00, OptionType.CALL)

        # Build the symbol directly
        symbol = builder._build_option_symbol()

        # Format: AAPL250117C00150000
        assert symbol == "AAPL250117C00150000"

    def test_option_symbol_put(self) -> None:
        """Put option symbol should have P."""
        builder = OptionOrderBuilder("MSFT", "2025-06-20", 425.50, OptionType.PUT)

        symbol = builder._build_option_symbol()

        # Strike 425.50 * 1000 = 425500 -> 00425500
        assert symbol == "MSFT250620P00425500"

    def test_missing_action_raises(self) -> None:
        """Should raise if no action specified."""
        with pytest.raises(ValueError, match="Order action required"):
            OptionOrderBuilder("AAPL", "2025-01-17", 150.00, OptionType.CALL).build()


class TestEnums:
    """Tests for enum values."""

    def test_order_action_values(self) -> None:
        """OrderAction enum should have correct values."""
        assert OrderAction.BUY.value == "BUY"
        assert OrderAction.SELL.value == "SELL"
        assert OrderAction.BUY_OPEN.value == "BUY_OPEN"
        assert OrderAction.SELL_CLOSE.value == "SELL_CLOSE"

    def test_price_type_values(self) -> None:
        """PriceType enum should have correct values."""
        assert PriceType.MARKET.value == "MARKET"
        assert PriceType.LIMIT.value == "LIMIT"
        assert PriceType.STOP.value == "STOP"
        assert PriceType.STOP_LIMIT.value == "STOP_LIMIT"

    def test_order_term_values(self) -> None:
        """OrderTerm enum should have correct values."""
        assert OrderTerm.GOOD_FOR_DAY.value == "GOOD_FOR_DAY"
        assert OrderTerm.GOOD_UNTIL_CANCEL.value == "GOOD_UNTIL_CANCEL"

    def test_enums_are_str(self) -> None:
        """Enums should be usable as strings (StrEnum behavior)."""
        # StrEnum returns the value directly when converted to str
        assert str(OrderAction.BUY) == "BUY"
        assert OrderAction.BUY.value == "BUY"
        # Can be used directly in string contexts
        assert f"{OrderAction.BUY}" == "BUY"
