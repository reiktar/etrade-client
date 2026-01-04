"""Account-related models."""

from datetime import datetime  # noqa: TC003
from decimal import Decimal
from enum import StrEnum
from typing import Annotated, Any

from pydantic import BaseModel, Discriminator, Field, Tag


class AccountType(StrEnum):
    """E*Trade account types."""

    INDIVIDUAL = "INDIVIDUAL"
    JOINT = "JOINT"
    IRA = "IRA"
    ROTH_IRA = "ROTH_IRA"
    CUSTODIAL = "CUSTODIAL"
    TRUST = "TRUST"
    CORPORATE = "CORPORATE"
    # Add more as discovered


class AccountStatus(StrEnum):
    """Account status values."""

    ACTIVE = "ACTIVE"
    CLOSED = "CLOSED"


class PositionType(StrEnum):
    """Position type values."""

    LONG = "LONG"
    SHORT = "SHORT"


class Account(BaseModel):
    """E*Trade account information."""

    account_id: str = Field(alias="accountId")
    account_id_key: str = Field(alias="accountIdKey")
    account_type: str = Field(alias="accountType")
    account_desc: str = Field(alias="accountDesc")
    account_name: str = Field(alias="accountName")
    account_mode: str = Field(alias="accountMode")
    account_status: str = Field(alias="accountStatus")
    institution_type: str = Field(alias="institutionType")
    closed_date: int = Field(alias="closedDate")
    share_works_account: bool = Field(alias="shareWorksAccount")
    fc_managed_mssb_closed_account: bool = Field(alias="fcManagedMssbClosedAccount")

    model_config = {"populate_by_name": True}


class AccountListResponse(BaseModel):
    """Response from list accounts endpoint."""

    accounts: list[Account] = Field(default_factory=list)

    @classmethod
    def from_api_response(cls, data: dict[str, Any]) -> AccountListResponse:
        """Parse from raw API response."""
        accounts_data = data.get("AccountListResponse", {}).get("Accounts", {})
        account_list = accounts_data.get("Account", [])
        # Handle single account returned as dict instead of list
        if isinstance(account_list, dict):
            account_list = [account_list]
        return cls(accounts=[Account.model_validate(a) for a in account_list])


class CashBalance(BaseModel):
    """Cash balance details."""

    # Always present in API responses
    funds_for_open_orders_cash: Decimal = Field(alias="fundsForOpenOrdersCash")
    money_market_balance: Decimal = Field(alias="moneyMktBalance")

    # Never present in sandbox - use None to avoid implying balance is 0
    cash_available_for_investment: Decimal | None = Field(
        default=None, alias="cashAvailableForInvestment"
    )
    cash_available_for_withdrawal: Decimal | None = Field(
        default=None, alias="cashAvailableForWithdrawal"
    )
    cash_balance: Decimal | None = Field(default=None, alias="cashBalance")
    settled_cash_for_investment: Decimal | None = Field(
        default=None, alias="settledCashForInvestment"
    )
    uncleared_deposits: Decimal | None = Field(default=None, alias="unclearedDeposits")

    model_config = {"populate_by_name": True}


class OpenCalls(BaseModel):
    """Open margin call details."""

    min_equity_call: Decimal = Field(default=Decimal("0"), alias="minEquityCall")
    fed_call: Decimal = Field(default=Decimal("0"), alias="fedCall")
    cash_call: Decimal = Field(default=Decimal("0"), alias="cashCall")
    house_call: Decimal = Field(default=Decimal("0"), alias="houseCall")

    model_config = {"populate_by_name": True}


class RealTimeValues(BaseModel):
    """Real-time account values."""

    total_account_value: Decimal = Field(default=Decimal("0"), alias="totalAccountValue")
    net_mv: Decimal = Field(default=Decimal("0"), alias="netMv")
    net_mv_long: Decimal = Field(default=Decimal("0"), alias="netMvLong")
    net_mv_short: Decimal = Field(default=Decimal("0"), alias="netMvShort")
    total_long_value: Decimal | None = Field(default=None, alias="totalLongValue")

    model_config = {"populate_by_name": True}


class ComputedBalance(BaseModel):
    """Computed account balance values."""

    # Always present in API responses
    cash_available_for_investment: Decimal = Field(alias="cashAvailableForInvestment")
    cash_available_for_withdrawal: Decimal = Field(alias="cashAvailableForWithdrawal")
    net_cash: Decimal = Field(alias="netCash")
    cash_balance: Decimal = Field(alias="cashBalance")
    settled_cash_for_investment: Decimal = Field(alias="settledCashForInvestment")
    un_settled_cash_for_investment: Decimal = Field(alias="unSettledCashForInvestment")

    # Nested objects - always present in API responses
    open_calls: OpenCalls = Field(alias="OpenCalls")
    real_time_values: RealTimeValues = Field(alias="RealTimeValues")

    # Sandbox-only fields (not in production)
    funds_withheld_from_purchase_power: Decimal | None = Field(
        default=None, alias="fundsWithheldFromPurchasePower"
    )
    funds_withheld_from_withdrawal: Decimal | None = Field(
        default=None, alias="fundsWithheldFromWithdrawal"
    )

    # Production-only fields (margin accounts)
    account_balance: Decimal | None = Field(default=None, alias="accountBalance")
    margin_buying_power: Decimal | None = Field(default=None, alias="marginBuyingPower")
    cash_buying_power: Decimal | None = Field(default=None, alias="cashBuyingPower")
    margin_balance: Decimal | None = Field(default=None, alias="marginBalance")
    total_available_for_withdrawal: Decimal | None = Field(
        default=None, alias="totalAvailableForWithdrawal"
    )
    dt_margin_buying_power: Decimal | None = Field(
        default=None, alias="dtMarginBuyingPower"
    )
    dt_cash_buying_power: Decimal | None = Field(default=None, alias="dtCashBuyingPower")
    short_adjust_balance: Decimal | None = Field(default=None, alias="shortAdjustBalance")
    regt_equity: Decimal | None = Field(default=None, alias="regtEquity")
    regt_equity_percent: Decimal | None = Field(default=None, alias="regtEquityPercent")

    model_config = {"populate_by_name": True}


class AccountBalance(BaseModel):
    """Complete account balance information."""

    # Always present
    account_id: str = Field(alias="accountId")
    account_type: str = Field(alias="accountType")
    account_description: str = Field(alias="accountDescription")
    option_level: str = Field(alias="optionLevel")
    cash: CashBalance = Field(alias="Cash")
    computed: ComputedBalance = Field(alias="Computed")

    # Production-only fields
    quote_mode: int | None = Field(default=None, alias="quoteMode")
    day_trader_status: str | None = Field(default=None, alias="dayTraderStatus")
    account_mode: str | None = Field(default=None, alias="accountMode")

    # Context-specific - may not always be present
    net_account_value: Decimal | None = Field(default=None, alias="netAccountValue")
    total_account_value: Decimal | None = Field(default=None, alias="totalAccountValue")

    model_config = {"populate_by_name": True}


class BalanceResponse(BaseModel):
    """Response from balance endpoint."""

    balance: AccountBalance

    @classmethod
    def from_api_response(cls, data: dict[str, Any]) -> BalanceResponse:
        """Parse from raw API response."""
        balance_data = data.get("BalanceResponse", {})
        return cls(balance=AccountBalance.model_validate(balance_data))


class Product(BaseModel):
    """Security product information."""

    symbol: str
    security_type: str = Field(alias="securityType")
    # Option-specific fields - always present (0 for non-options)
    expiry_day: int = Field(alias="expiryDay")
    expiry_month: int = Field(alias="expiryMonth")
    expiry_year: int = Field(alias="expiryYear")
    strike_price: Decimal = Field(alias="strikePrice")
    product_id: dict[str, Any] = Field(alias="productId")
    # These may not always be present
    security_sub_type: str | None = Field(default=None, alias="securitySubType")
    exchange: str | None = Field(default=None)

    model_config = {"populate_by_name": True}


# =============================================================================
# Portfolio Quote Models (View-Specific)
# =============================================================================


class QuickQuote(BaseModel):
    """Quote data returned with QUICK view.

    Contains basic price and volume information.
    """

    last_trade: Decimal = Field(alias="lastTrade")
    last_trade_time: int = Field(alias="lastTradeTime")
    change: Decimal
    change_pct: Decimal = Field(alias="changePct")
    volume: int
    quote_status: str = Field(alias="quoteStatus")

    model_config = {"populate_by_name": True}


class PerformanceQuote(BaseModel):
    """Quote data returned with PERFORMANCE view.

    Contains basic price and change information (no volume).
    """

    change: Decimal
    change_pct: Decimal = Field(alias="changePct")
    last_trade: Decimal = Field(alias="lastTrade")
    last_trade_time: int = Field(alias="lastTradeTime")
    quote_status: str = Field(alias="quoteStatus")

    model_config = {"populate_by_name": True}


class FundamentalQuote(BaseModel):
    """Quote data returned with FUNDAMENTAL view.

    Contains price data plus fundamental metrics.
    """

    last_trade: Decimal = Field(alias="lastTrade")
    last_trade_time: int = Field(alias="lastTradeTime")
    change: Decimal
    change_pct: Decimal = Field(alias="changePct")
    pe_ratio: Decimal = Field(alias="peRatio")
    eps: Decimal
    dividend: Decimal
    div_yield: Decimal = Field(alias="divYield")
    market_cap: Decimal = Field(alias="marketCap")
    week_52_range: str = Field(alias="week52Range")
    quote_status: str = Field(alias="quoteStatus")

    model_config = {"populate_by_name": True}


class CompleteQuote(BaseModel):
    """Quote data returned with COMPLETE view.

    Contains comprehensive quote data including price, volume, performance,
    volatility, options greeks, and fundamental metrics.
    """

    # Price data
    price_adjusted_flag: bool = Field(alias="priceAdjustedFlag")
    price: Decimal
    adj_price: Decimal = Field(alias="adjPrice")
    change: Decimal
    change_pct: Decimal = Field(alias="changePct")
    prev_close: Decimal = Field(alias="prevClose")
    adj_prev_close: Decimal = Field(alias="adjPrevClose")
    last_trade: Decimal = Field(alias="lastTrade")
    last_trade_time: int = Field(alias="lastTradeTime")
    adj_last_trade: Decimal = Field(alias="adjLastTrade")
    open: Decimal

    # Volume data
    volume: int
    prev_day_volume: int = Field(alias="prevDayVolume")
    ten_day_volume: int = Field(alias="tenDayVolume")

    # Bid/Ask data
    bid: Decimal
    ask: Decimal
    bid_ask_spread: Decimal = Field(alias="bidAskSpread")
    bid_size: int = Field(alias="bidSize")
    ask_size: int = Field(alias="askSize")

    # Performance metrics
    # These fields are absent for newly-listed securities that haven't
    # traded for the corresponding time period (e.g., an ETF < 6 months old
    # won't have perform6Month or perform12Month data)
    perform_1_month: int | None = Field(default=None, alias="perform1Month")
    perform_3_month: int | None = Field(default=None, alias="perform3Month")
    perform_6_month: int | None = Field(default=None, alias="perform6Month")
    perform_12_month: int | None = Field(default=None, alias="perform12Month")

    # Volatility/Statistical data
    beta: Decimal
    sv_10_days_avg: Decimal = Field(alias="sv10DaysAvg")
    sv_20_days_avg: Decimal = Field(alias="sv20DaysAvg")
    sv_1_mon_avg: Decimal = Field(alias="sv1MonAvg")
    sv_2_mon_avg: Decimal = Field(alias="sv2MonAvg")
    sv_3_mon_avg: Decimal = Field(alias="sv3MonAvg")
    sv_4_mon_avg: Decimal = Field(alias="sv4MonAvg")
    sv_6_mon_avg: Decimal = Field(alias="sv6MonAvg")

    # 52-week data
    week_52_high: Decimal = Field(alias="week52High")
    week_52_low: Decimal = Field(alias="week52Low")
    week_52_range: str = Field(alias="week52Range")
    delta_52_wk_high: Decimal = Field(alias="delta52WkHigh")
    delta_52_wk_low: Decimal = Field(alias="delta52WkLow")
    days_range: str = Field(alias="daysRange")

    # Market data
    market_cap: Decimal = Field(alias="marketCap")
    currency: str
    exchange: str
    marginable: bool

    # Options greeks (0 for non-options)
    delta: Decimal
    gamma: Decimal
    iv_pct: Decimal = Field(alias="ivPct")
    rho: Decimal
    theta: Decimal
    vega: Decimal
    premium: Decimal
    intrinsic_value: Decimal = Field(alias="intrinsicValue")
    open_interest: int = Field(alias="openInterest")
    options_adjusted_flag: bool = Field(alias="optionsAdjustedFlag")
    deliverables_str: str = Field(alias="deliverablesStr")
    option_multiplier: int = Field(alias="optionMultiplier")
    base_symbol_and_price: str = Field(alias="baseSymbolAndPrice")

    # Fundamental data
    eps: Decimal
    pe_ratio: Decimal = Field(alias="peRatio")
    annual_dividend: Decimal = Field(alias="annualDividend")
    dividend: Decimal
    div_yield: Decimal = Field(alias="divYield")
    div_pay_date: int = Field(alias="divPayDate")
    ex_dividend_date: int = Field(alias="exDividendDate")
    cusip: str

    # Description and status
    symbol_description: str = Field(alias="symbolDescription")
    quote_status: str = Field(alias="quoteStatus")

    model_config = {"populate_by_name": True}


# =============================================================================
# Portfolio Position Models (View-Specific)
# =============================================================================


class PortfolioPositionBase(BaseModel):
    """Base class for all portfolio position types.

    Contains fields that are always present regardless of view type.
    """

    # Core identification
    position_id: int = Field(alias="positionId")
    product: Product = Field(alias="Product")
    symbol_description: str = Field(alias="symbolDescription")

    # Position details
    quantity: Decimal
    cost_per_share: Decimal = Field(alias="costPerShare")
    total_cost: Decimal = Field(alias="totalCost")
    price_paid: Decimal = Field(alias="pricePaid")
    commissions: Decimal
    other_fees: Decimal = Field(alias="otherFees")

    # Value metrics
    market_value: Decimal = Field(alias="marketValue")
    total_gain: Decimal = Field(alias="totalGain")
    total_gain_pct: Decimal = Field(alias="totalGainPct")
    days_gain: Decimal = Field(alias="daysGain")
    days_gain_pct: Decimal = Field(alias="daysGainPct")
    pct_of_portfolio: Decimal = Field(alias="pctOfPortfolio")

    # Position type and indicator
    position_type: PositionType = Field(alias="positionType")
    position_indicator: str = Field(alias="positionIndicator")

    # Date
    date_acquired: datetime = Field(alias="dateAcquired")

    # URLs
    lots_details: str = Field(alias="lotsDetails")
    quote_details: str = Field(alias="quoteDetails")

    # Today's activity
    today_quantity: int = Field(alias="todayQuantity")
    today_price_paid: Decimal = Field(alias="todayPricePaid")
    today_commissions: Decimal = Field(alias="todayCommissions")
    today_fees: Decimal = Field(alias="todayFees")

    # Adjusted previous close (always present)
    adj_prev_close: Decimal = Field(alias="adjPrevClose")

    model_config = {"populate_by_name": True}


class QuickViewPosition(PortfolioPositionBase):
    """Position with QUICK view quote data.

    Contains basic price and volume information.
    """

    quick: QuickQuote = Field(alias="Quick")


class PerformanceViewPosition(PortfolioPositionBase):
    """Position with PERFORMANCE view quote data.

    Contains price and change information focused on performance metrics.
    """

    performance: PerformanceQuote = Field(alias="Performance")


class FundamentalViewPosition(PortfolioPositionBase):
    """Position with FUNDAMENTAL view quote data.

    Contains price data plus fundamental analysis metrics.
    """

    fundamental: FundamentalQuote = Field(alias="Fundamental")


class CompleteViewPosition(PortfolioPositionBase):
    """Position with COMPLETE view quote data.

    Contains comprehensive quote data including all available metrics.
    """

    complete: CompleteQuote = Field(alias="Complete")


# =============================================================================
# Portfolio Position Discriminated Union
# =============================================================================


def _get_position_view_discriminator(v: Any) -> str:
    """Get discriminator value from position data based on which quote object is present.

    Returns the view type tag based on the quote object present in the data.
    """
    if isinstance(v, dict):
        if "Quick" in v:
            return "quick"
        elif "Performance" in v:
            return "performance"
        elif "Fundamental" in v:
            return "fundamental"
        elif "Complete" in v:
            return "complete"
    # For already-parsed models
    if hasattr(v, "quick"):
        return "quick"
    elif hasattr(v, "performance"):
        return "performance"
    elif hasattr(v, "fundamental"):
        return "fundamental"
    elif hasattr(v, "complete"):
        return "complete"
    # Default to quick view
    return "quick"


# Discriminated union of all position view types
PortfolioPosition = Annotated[
    Annotated[QuickViewPosition, Tag("quick")]
    | Annotated[PerformanceViewPosition, Tag("performance")]
    | Annotated[FundamentalViewPosition, Tag("fundamental")]
    | Annotated[CompleteViewPosition, Tag("complete")],
    Discriminator(_get_position_view_discriminator),
]


# Backwards compatibility alias
PositionQuick = QuickQuote


class PortfolioResponse(BaseModel):
    """Response from portfolio endpoint."""

    account_id: str
    positions: list[PortfolioPosition] = Field(default_factory=list)
    total_value: Decimal = Field(default=Decimal("0"))

    @classmethod
    def from_api_response(cls, data: dict[str, Any], account_id: str) -> PortfolioResponse:
        """Parse from raw API response."""
        from pydantic import TypeAdapter

        portfolio_data = data.get("PortfolioResponse", {})
        account_portfolios = portfolio_data.get("AccountPortfolio", [])

        if isinstance(account_portfolios, dict):
            account_portfolios = [account_portfolios]

        positions: list[PortfolioPosition] = []
        total_value = Decimal("0")

        # Use TypeAdapter to parse the discriminated union
        adapter = TypeAdapter(PortfolioPosition)

        for account_portfolio in account_portfolios:
            position_list = account_portfolio.get("Position", [])
            if isinstance(position_list, dict):
                position_list = [position_list]
            for pos in position_list:
                positions.append(adapter.validate_python(pos))

            total_value += Decimal(str(account_portfolio.get("totalValue", 0)))

        return cls(account_id=account_id, positions=positions, total_value=total_value)
