"""Type-safe order builders for E*Trade API."""

import secrets
from typing import Any

from etrade_client.models.market import OptionType
from etrade_client.models.orders import (
    MarketSession,
    OrderAction,
    OrderTerm,
    OrderType,
)

# Backwards compatibility alias - PriceType was the original name in builders
PriceType = OrderType

__all__ = [
    # Builders
    "EquityOrderBuilder",
    "OptionOrderBuilder",
    # Re-exported enums
    "MarketSession",
    "OptionType",
    "OrderAction",
    "OrderTerm",
    "OrderType",
    "PriceType",
]


class EquityOrderBuilder:
    """Fluent builder for equity orders.

    Example:
        order = (
            EquityOrderBuilder("AAPL")
            .buy(100)
            .limit(150.00)
            .good_until_cancel()
            .build()
        )

        # Then use with OrdersAPI:
        preview = await client.orders.preview_order(account_id, order)
    """

    def __init__(self, symbol: str) -> None:
        """Initialize builder with symbol.

        Args:
            symbol: Stock ticker symbol (e.g., "AAPL")
        """
        self._symbol = symbol.upper()
        self._action: OrderAction | None = None
        self._quantity: int | None = None
        self._price_type: PriceType = PriceType.MARKET
        self._limit_price: float | None = None
        self._stop_price: float | None = None
        self._order_term: OrderTerm = OrderTerm.GOOD_FOR_DAY
        self._market_session: MarketSession = MarketSession.REGULAR
        self._all_or_none: bool = False
        self._client_order_id: str | None = None

    # Action methods
    def buy(self, quantity: int) -> "EquityOrderBuilder":
        """Set action to BUY with quantity."""
        self._action = OrderAction.BUY
        self._quantity = quantity
        return self

    def sell(self, quantity: int) -> "EquityOrderBuilder":
        """Set action to SELL with quantity."""
        self._action = OrderAction.SELL
        self._quantity = quantity
        return self

    def sell_short(self, quantity: int) -> "EquityOrderBuilder":
        """Set action to SELL_SHORT with quantity."""
        self._action = OrderAction.SELL_SHORT
        self._quantity = quantity
        return self

    def buy_to_cover(self, quantity: int) -> "EquityOrderBuilder":
        """Set action to BUY_TO_COVER with quantity."""
        self._action = OrderAction.BUY_TO_COVER
        self._quantity = quantity
        return self

    # Price type methods
    def market(self) -> "EquityOrderBuilder":
        """Set as market order (default)."""
        self._price_type = PriceType.MARKET
        self._limit_price = None
        self._stop_price = None
        return self

    def limit(self, price: float) -> "EquityOrderBuilder":
        """Set as limit order with specified price."""
        self._price_type = PriceType.LIMIT
        self._limit_price = price
        return self

    def stop(self, price: float) -> "EquityOrderBuilder":
        """Set as stop order with specified trigger price."""
        self._price_type = PriceType.STOP
        self._stop_price = price
        return self

    def stop_limit(self, stop_price: float, limit_price: float) -> "EquityOrderBuilder":
        """Set as stop-limit order with trigger and limit prices."""
        self._price_type = PriceType.STOP_LIMIT
        self._stop_price = stop_price
        self._limit_price = limit_price
        return self

    # Order term methods
    def good_for_day(self) -> "EquityOrderBuilder":
        """Set order to expire at end of day (default)."""
        self._order_term = OrderTerm.GOOD_FOR_DAY
        return self

    def good_until_cancel(self) -> "EquityOrderBuilder":
        """Set order to remain active until cancelled."""
        self._order_term = OrderTerm.GOOD_UNTIL_CANCEL
        return self

    def immediate_or_cancel(self) -> "EquityOrderBuilder":
        """Set order to fill immediately or cancel."""
        self._order_term = OrderTerm.IMMEDIATE_OR_CANCEL
        return self

    def fill_or_kill(self) -> "EquityOrderBuilder":
        """Set order to fill completely or cancel entirely."""
        self._order_term = OrderTerm.FILL_OR_KILL
        return self

    # Session methods
    def regular_session(self) -> "EquityOrderBuilder":
        """Execute during regular market hours (default)."""
        self._market_session = MarketSession.REGULAR
        return self

    def extended_session(self) -> "EquityOrderBuilder":
        """Execute during extended market hours."""
        self._market_session = MarketSession.EXTENDED
        return self

    # Other options
    def all_or_none(self, enabled: bool = True) -> "EquityOrderBuilder":
        """Set all-or-none flag."""
        self._all_or_none = enabled
        return self

    def client_order_id(self, order_id: str) -> "EquityOrderBuilder":
        """Set custom client order ID."""
        self._client_order_id = order_id
        return self

    def build(self) -> dict[str, Any]:
        """Build the order specification dict.

        Returns:
            Order dict ready for preview_order() or place_order()

        Raises:
            ValueError: If required fields are missing
        """
        if self._action is None:
            raise ValueError("Order action required - call buy(), sell(), etc.")
        if self._quantity is None or self._quantity <= 0:
            raise ValueError("Quantity must be positive")
        if self._price_type == PriceType.LIMIT and self._limit_price is None:
            raise ValueError("Limit price required for limit orders")
        if self._price_type == PriceType.STOP and self._stop_price is None:
            raise ValueError("Stop price required for stop orders")
        if self._price_type == PriceType.STOP_LIMIT:
            if self._stop_price is None or self._limit_price is None:
                raise ValueError("Both stop and limit prices required for stop-limit orders")

        instrument = {
            "Product": {
                "symbol": self._symbol,
                "securityType": "EQ",
            },
            "orderAction": self._action.value,
            "quantityType": "QUANTITY",
            "quantity": self._quantity,
        }

        order_detail: dict[str, Any] = {
            "allOrNone": str(self._all_or_none).lower(),
            "priceType": self._price_type.value,
            "orderTerm": self._order_term.value,
            "marketSession": self._market_session.value,
            "Instrument": [instrument],
        }

        if self._limit_price is not None:
            order_detail["limitPrice"] = self._limit_price
        if self._stop_price is not None:
            order_detail["stopPrice"] = self._stop_price

        return {
            "orderType": "EQ",
            "clientOrderId": self._client_order_id or secrets.token_hex(8),
            "Order": [order_detail],
        }


class OptionOrderBuilder:
    """Fluent builder for option orders.

    Example:
        order = (
            OptionOrderBuilder("AAPL", "2025-01-17", 150.00, OptionType.CALL)
            .buy_to_open(5)
            .limit(2.50)
            .build()
        )
    """

    def __init__(
        self,
        symbol: str,
        expiry: str,
        strike: float,
        option_type: OptionType,
    ) -> None:
        """Initialize builder with option contract details.

        Args:
            symbol: Underlying stock ticker (e.g., "AAPL")
            expiry: Expiration date as "YYYY-MM-DD"
            strike: Strike price
            option_type: CALL or PUT
        """
        self._symbol = symbol.upper()
        self._expiry = expiry
        self._strike = strike
        self._option_type = option_type
        self._action: OrderAction | None = None
        self._quantity: int | None = None
        self._price_type: PriceType = PriceType.MARKET
        self._limit_price: float | None = None
        self._stop_price: float | None = None
        self._order_term: OrderTerm = OrderTerm.GOOD_FOR_DAY
        self._market_session: MarketSession = MarketSession.REGULAR
        self._all_or_none: bool = False
        self._client_order_id: str | None = None

    # Action methods
    def buy_to_open(self, quantity: int) -> "OptionOrderBuilder":
        """Open a new long position."""
        self._action = OrderAction.BUY_OPEN
        self._quantity = quantity
        return self

    def sell_to_open(self, quantity: int) -> "OptionOrderBuilder":
        """Open a new short position (write)."""
        self._action = OrderAction.SELL_OPEN
        self._quantity = quantity
        return self

    def buy_to_close(self, quantity: int) -> "OptionOrderBuilder":
        """Close an existing short position."""
        self._action = OrderAction.BUY_CLOSE
        self._quantity = quantity
        return self

    def sell_to_close(self, quantity: int) -> "OptionOrderBuilder":
        """Close an existing long position."""
        self._action = OrderAction.SELL_CLOSE
        self._quantity = quantity
        return self

    # Price type methods (same as equity)
    def market(self) -> "OptionOrderBuilder":
        """Set as market order (default)."""
        self._price_type = PriceType.MARKET
        self._limit_price = None
        self._stop_price = None
        return self

    def limit(self, price: float) -> "OptionOrderBuilder":
        """Set as limit order with specified price."""
        self._price_type = PriceType.LIMIT
        self._limit_price = price
        return self

    def stop(self, price: float) -> "OptionOrderBuilder":
        """Set as stop order with specified trigger price."""
        self._price_type = PriceType.STOP
        self._stop_price = price
        return self

    def stop_limit(self, stop_price: float, limit_price: float) -> "OptionOrderBuilder":
        """Set as stop-limit order with trigger and limit prices."""
        self._price_type = PriceType.STOP_LIMIT
        self._stop_price = stop_price
        self._limit_price = limit_price
        return self

    # Order term methods
    def good_for_day(self) -> "OptionOrderBuilder":
        """Set order to expire at end of day (default)."""
        self._order_term = OrderTerm.GOOD_FOR_DAY
        return self

    def good_until_cancel(self) -> "OptionOrderBuilder":
        """Set order to remain active until cancelled."""
        self._order_term = OrderTerm.GOOD_UNTIL_CANCEL
        return self

    def immediate_or_cancel(self) -> "OptionOrderBuilder":
        """Set order to fill immediately or cancel."""
        self._order_term = OrderTerm.IMMEDIATE_OR_CANCEL
        return self

    def fill_or_kill(self) -> "OptionOrderBuilder":
        """Set order to fill completely or cancel entirely."""
        self._order_term = OrderTerm.FILL_OR_KILL
        return self

    # Session methods
    def regular_session(self) -> "OptionOrderBuilder":
        """Execute during regular market hours (default)."""
        self._market_session = MarketSession.REGULAR
        return self

    def extended_session(self) -> "OptionOrderBuilder":
        """Execute during extended market hours."""
        self._market_session = MarketSession.EXTENDED
        return self

    # Other options
    def all_or_none(self, enabled: bool = True) -> "OptionOrderBuilder":
        """Set all-or-none flag."""
        self._all_or_none = enabled
        return self

    def client_order_id(self, order_id: str) -> "OptionOrderBuilder":
        """Set custom client order ID."""
        self._client_order_id = order_id
        return self

    def _build_option_symbol(self) -> str:
        """Build the OCC option symbol.

        Format: SYMBOL + YYMMDD + C/P + strike (8 digits, strike * 1000)
        Example: AAPL250117C00150000
        """
        # Parse expiry date
        year, month, day = self._expiry.split("-")
        date_part = f"{year[2:]}{month}{day}"

        # Option type
        type_part = "C" if self._option_type == OptionType.CALL else "P"

        # Strike price (8 digits, multiplied by 1000)
        strike_int = int(self._strike * 1000)
        strike_part = f"{strike_int:08d}"

        return f"{self._symbol}{date_part}{type_part}{strike_part}"

    def build(self) -> dict[str, Any]:
        """Build the order specification dict.

        Returns:
            Order dict ready for preview_order() or place_order()

        Raises:
            ValueError: If required fields are missing
        """
        if self._action is None:
            raise ValueError("Order action required - call buy_to_open(), sell_to_close(), etc.")
        if self._quantity is None or self._quantity <= 0:
            raise ValueError("Quantity must be positive")
        if self._price_type == PriceType.LIMIT and self._limit_price is None:
            raise ValueError("Limit price required for limit orders")
        if self._price_type == PriceType.STOP and self._stop_price is None:
            raise ValueError("Stop price required for stop orders")
        if self._price_type == PriceType.STOP_LIMIT:
            if self._stop_price is None or self._limit_price is None:
                raise ValueError("Both stop and limit prices required for stop-limit orders")

        option_symbol = self._build_option_symbol()

        instrument = {
            "Product": {
                "symbol": option_symbol,
                "securityType": "OPTN",
                "callPut": self._option_type.value,
                "expiryYear": int(self._expiry.split("-")[0]),
                "expiryMonth": int(self._expiry.split("-")[1]),
                "expiryDay": int(self._expiry.split("-")[2]),
                "strikePrice": self._strike,
            },
            "orderAction": self._action.value,
            "quantityType": "QUANTITY",
            "quantity": self._quantity,
        }

        order_detail: dict[str, Any] = {
            "allOrNone": str(self._all_or_none).lower(),
            "priceType": self._price_type.value,
            "orderTerm": self._order_term.value,
            "marketSession": self._market_session.value,
            "Instrument": [instrument],
        }

        if self._limit_price is not None:
            order_detail["limitPrice"] = self._limit_price
        if self._stop_price is not None:
            order_detail["stopPrice"] = self._stop_price

        return {
            "orderType": "OPTN",
            "clientOrderId": self._client_order_id or secrets.token_hex(8),
            "Order": [order_detail],
        }
