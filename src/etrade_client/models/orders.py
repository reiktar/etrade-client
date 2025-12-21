"""Order-related models."""

from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, Field


class OrderAction(StrEnum):
    """Order action types."""

    BUY = "BUY"
    SELL = "SELL"
    BUY_TO_COVER = "BUY_TO_COVER"
    SELL_SHORT = "SELL_SHORT"
    BUY_OPEN = "BUY_OPEN"
    BUY_CLOSE = "BUY_CLOSE"
    SELL_OPEN = "SELL_OPEN"
    SELL_CLOSE = "SELL_CLOSE"


class OrderType(StrEnum):
    """Order price types."""

    MARKET = "MARKET"
    LIMIT = "LIMIT"
    STOP = "STOP"
    STOP_LIMIT = "STOP_LIMIT"
    TRAILING_STOP_CNST = "TRAILING_STOP_CNST"
    TRAILING_STOP_PCT = "TRAILING_STOP_PCT"
    # Spread/complex order types
    NET_DEBIT = "NET_DEBIT"
    NET_CREDIT = "NET_CREDIT"
    NET_EVEN = "NET_EVEN"
    MARKET_ON_OPEN = "MARKET_ON_OPEN"
    MARKET_ON_CLOSE = "MARKET_ON_CLOSE"


class OrderTerm(StrEnum):
    """Order duration/time-in-force."""

    GOOD_FOR_DAY = "GOOD_FOR_DAY"
    GOOD_UNTIL_CANCEL = "GOOD_UNTIL_CANCEL"
    IMMEDIATE_OR_CANCEL = "IMMEDIATE_OR_CANCEL"
    FILL_OR_KILL = "FILL_OR_KILL"


class MarketSession(StrEnum):
    """Market session for order execution."""

    REGULAR = "REGULAR"
    EXTENDED = "EXTENDED"


class OrderStatus(StrEnum):
    """Order status values."""

    OPEN = "OPEN"
    EXECUTED = "EXECUTED"
    CANCELLED = "CANCELLED"
    CANCEL_REQUESTED = "CANCEL_REQUESTED"
    EXPIRED = "EXPIRED"
    REJECTED = "REJECTED"
    PARTIAL = "PARTIAL"
    PENDING = "PENDING"
    DO_NOT_EXERCISE = "DO_NOT_EXERCISE"
    INDIVIDUAL_FILLS = "INDIVIDUAL_FILLS"


class SecurityType(StrEnum):
    """Security types."""

    EQ = "EQ"  # Equity/Stock
    OPTN = "OPTN"  # Option
    MF = "MF"  # Mutual Fund
    MMF = "MMF"  # Money Market Fund


class CallPut(StrEnum):
    """Call or Put indicator for options."""

    CALL = "CALL"
    PUT = "PUT"


class QuantityType(StrEnum):
    """Quantity type for orders."""

    QUANTITY = "QUANTITY"
    DOLLAR = "DOLLAR"
    ALL_I_OWN = "ALL_I_OWN"


class OrderCategory(StrEnum):
    """Order category (type of security/spread or execution type)."""

    # Security types
    EQ = "EQ"  # Equity
    OPTN = "OPTN"  # Option
    SPREADS = "SPREADS"
    BUY_WRITES = "BUY_WRITES"
    BUTTERFLY = "BUTTERFLY"
    IRON_BUTTERFLY = "IRON_BUTTERFLY"
    CONDOR = "CONDOR"
    IRON_CONDOR = "IRON_CONDOR"
    MF = "MF"  # Mutual Fund
    MMF = "MMF"  # Money Market Fund
    # Execution types
    ONE_CANCELS_ALL = "ONE_CANCELS_ALL"
    ONE_TRIGGERS_ALL = "ONE_TRIGGERS_ALL"
    ONE_TRIGGERS_OCO = "ONE_TRIGGERS_OCO"


class OrderProduct(BaseModel):
    """Product in an order."""

    symbol: str
    security_type: SecurityType = Field(alias="securityType")
    call_put: CallPut | None = Field(default=None, alias="callPut")
    expiry_year: int | None = Field(default=None, alias="expiryYear")
    expiry_month: int | None = Field(default=None, alias="expiryMonth")
    expiry_day: int | None = Field(default=None, alias="expiryDay")
    strike_price: Decimal | None = Field(default=None, alias="strikePrice")
    product_id: dict | None = Field(default=None, alias="productId")

    model_config = {"populate_by_name": True}


class OrderInstrument(BaseModel):
    """Instrument/leg of an order."""

    product: OrderProduct = Field(alias="Product")
    order_action: OrderAction = Field(alias="orderAction")
    quantity: int = Field(alias="orderedQuantity")
    quantity_type: QuantityType | None = Field(default=None, alias="quantityType")
    filled_quantity: int | None = Field(default=None, alias="filledQuantity")
    average_execution_price: Decimal | None = Field(default=None, alias="averageExecutionPrice")
    estimated_commission: Decimal | None = Field(default=None, alias="estimatedCommission")
    estimated_fees: Decimal | None = Field(default=None, alias="estimatedFees")
    symbol_description: str | None = Field(default=None, alias="symbolDescription")

    model_config = {"populate_by_name": True}


class OrderDetail(BaseModel):
    """Complete order detail."""

    # These may not be present in all responses (e.g., sandbox)
    order_number: int | None = Field(default=None, alias="orderNumber")
    account_id: str | None = Field(default=None, alias="accountId")
    placed_time: datetime | None = Field(default=None, alias="placedTime")
    executed_time: datetime | None = Field(default=None, alias="executedTime")

    # Order configuration - these may also be optional in some responses
    order_type: OrderType | None = Field(default=None, alias="priceType")
    order_term: OrderTerm | None = Field(default=None, alias="orderTerm")
    market_session: MarketSession | None = Field(default=None, alias="marketSession")

    # Pricing
    limit_price: Decimal | None = Field(default=None, alias="limitPrice")
    stop_price: Decimal | None = Field(default=None, alias="stopPrice")

    # Status
    status: OrderStatus | None = Field(default=None)
    order_value: Decimal | None = Field(default=None, alias="orderValue")
    estimated_total_amount: Decimal | None = Field(default=None, alias="estimatedTotalAmount")

    # Instruments/legs
    instruments: list[OrderInstrument] = Field(default_factory=list, alias="Instrument")

    # Messages (warnings, info)
    messages: list[dict] | None = Field(default=None)

    # Additional fields from sandbox
    all_or_none: bool | None = Field(default=None, alias="allOrNone")
    gcd: int | None = Field(default=None)
    ratio: str | None = Field(default=None)

    # Spread/complex order pricing
    net_price: Decimal | None = Field(default=None, alias="netPrice")
    net_bid: Decimal | None = Field(default=None, alias="netBid")
    net_ask: Decimal | None = Field(default=None, alias="netAsk")
    initial_stop_price: Decimal | None = Field(default=None, alias="initialStopPrice")
    bracketed_limit_price: Decimal | None = Field(default=None, alias="bracketedLimitPrice")

    model_config = {"populate_by_name": True}

    @property
    def symbol(self) -> str | None:
        """Primary symbol of the order."""
        if self.instruments:
            return self.instruments[0].product.symbol
        return None

    @property
    def quantity(self) -> int | None:
        """Total quantity of the order."""
        if self.instruments:
            return self.instruments[0].quantity
        return None


class Order(BaseModel):
    """Order summary from list endpoint."""

    order_id: int = Field(alias="orderId")
    # Note: API returns OrderDetail as a list even for single orders
    order_details: list[OrderDetail] = Field(alias="OrderDetail")

    # Order-level metadata
    order_category: OrderCategory | None = Field(default=None, alias="orderType")
    order_description: str | None = Field(default=None, alias="details")
    total_commission: Decimal | None = Field(default=None, alias="totalCommission")
    total_order_value: Decimal | None = Field(default=None, alias="totalOrderValue")

    model_config = {"populate_by_name": True}

    @property
    def details(self) -> OrderDetail | None:
        """Get the first (primary) order detail."""
        return self.order_details[0] if self.order_details else None

    # Convenience accessors
    @property
    def status(self) -> str | None:
        return self.details.status if self.details else None

    @property
    def symbol(self) -> str | None:
        return self.details.symbol if self.details else None


class OrderListResponse(BaseModel):
    """Response from list orders endpoint."""

    orders: list[Order] = Field(default_factory=list)
    marker: str | None = Field(default=None)
    next_page: str | None = Field(default=None)

    @property
    def has_more(self) -> bool:
        """Check if there are more pages to fetch."""
        return bool(self.next_page or self.marker)

    @classmethod
    def from_api_response(cls, data: dict) -> OrderListResponse:
        """Parse from raw API response."""
        orders_response = data.get("OrdersResponse", {})
        order_list = orders_response.get("Order", [])

        if isinstance(order_list, dict):
            order_list = [order_list]

        # Handle E*Trade's quirk where single-element arrays may come as dicts
        parsed_orders = []
        for o in order_list:
            # OrderDetail may come as dict or list
            if "OrderDetail" in o and isinstance(o["OrderDetail"], dict):
                o = {**o, "OrderDetail": [o["OrderDetail"]]}
            parsed_orders.append(Order.model_validate(o))

        return cls(
            orders=parsed_orders,
            marker=orders_response.get("marker"),
            next_page=orders_response.get("next"),
        )


class PreviewId(BaseModel):
    """Preview ID from order preview."""

    preview_id: int = Field(alias="previewId")

    model_config = {"populate_by_name": True}


class OrderPreview(BaseModel):
    """Order preview details."""

    preview_time: datetime | None = Field(default=None, alias="previewTime")
    order_type: str = Field(alias="orderType")
    total_order_value: Decimal | None = Field(default=None, alias="totalOrderValue")
    estimated_commission: Decimal | None = Field(default=None, alias="estimatedCommission")
    estimated_total_amount: Decimal | None = Field(default=None, alias="estimatedTotalAmount")

    # Preview IDs needed for placing the order
    preview_ids: list[PreviewId] = Field(default_factory=list, alias="PreviewIds")

    # Order details
    order: list[dict] = Field(default_factory=list, alias="Order")

    model_config = {"populate_by_name": True}

    @property
    def preview_id_values(self) -> list[int]:
        """Get list of preview ID values for placing order."""
        return [p.preview_id for p in self.preview_ids]


class OrderPreviewResponse(BaseModel):
    """Response from preview order endpoint."""

    preview: OrderPreview

    @classmethod
    def from_api_response(cls, data: dict) -> OrderPreviewResponse:
        """Parse from raw API response."""
        preview_data = data.get("PreviewOrderResponse", {})
        return cls(preview=OrderPreview.model_validate(preview_data))


class PlacedOrder(BaseModel):
    """Placed order confirmation."""

    order_id: int = Field(alias="orderId")
    placed_time: datetime | None = Field(default=None, alias="placedTime")
    order_num: int = Field(alias="orderNum")
    order: list[dict] = Field(default_factory=list, alias="Order")

    model_config = {"populate_by_name": True}


class PlaceOrderResponse(BaseModel):
    """Response from place order endpoint."""

    order: PlacedOrder

    @classmethod
    def from_api_response(cls, data: dict) -> PlaceOrderResponse:
        """Parse from raw API response."""
        order_data = data.get("PlaceOrderResponse", {})
        return cls(order=PlacedOrder.model_validate(order_data))
