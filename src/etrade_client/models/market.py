"""Market data models."""

from datetime import date
from decimal import Decimal
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field, field_validator


class QuoteStatus(StrEnum):
    """Quote status values."""

    REALTIME = "REALTIME"
    DELAYED = "DELAYED"
    CLOSING = "CLOSING"
    EH_REALTIME = "EH_REALTIME"
    EH_BEFORE_OPEN = "EH_BEFORE_OPEN"
    EH_CLOSED = "EH_CLOSED"
    INDICATIVE_REALTIME = "INDICATIVE_REALTIME"


class OptionExpiryType(StrEnum):
    """Option expiration type values."""

    DAILY = "DAILY"
    WEEKLY = "WEEKLY"
    MONTHLY = "MONTHLY"
    QUARTERLY = "QUARTERLY"


# =============================================================================
# Quote Detail Models by Detail Flag
# =============================================================================
# The E*Trade API returns different quote objects based on the detail_flag
# parameter. Each detail flag returns a mutually exclusive set of fields.
# =============================================================================


class ExtendedHourQuoteDetail(BaseModel):
    """Extended hours quote detail (after-hours/pre-market).

    Present as a nested object within AllQuoteDetail when ahFlag is 'true'
    and extended hours data is available.
    """

    ask: Decimal = Field()
    ask_size: int = Field(alias="askSize")
    bid: Decimal = Field()
    bid_size: int = Field(alias="bidSize")
    change: Decimal = Field()
    last_price: Decimal = Field(alias="lastPrice")
    percent_change: Decimal = Field(alias="percentChange")
    quote_status: str = Field(alias="quoteStatus")
    time_of_last_trade: int = Field(alias="timeOfLastTrade")
    time_zone: str = Field(alias="timeZone")
    volume: int = Field()

    model_config = {"populate_by_name": True}


class FundamentalQuoteDetail(BaseModel):
    """Quote details returned with detail_flag=FUNDAMENTAL.

    Contains company fundamentals like earnings data.
    """

    company_name: str = Field(alias="companyName")
    eps: Decimal = Field()
    est_earnings: Decimal = Field(alias="estEarnings")
    high_52: Decimal = Field(alias="high52")
    last_trade: Decimal = Field(alias="lastTrade")
    low_52: Decimal = Field(alias="low52")
    symbol_description: str = Field(alias="symbolDescription")

    model_config = {"populate_by_name": True}


class IntradayQuoteDetail(BaseModel):
    """Quote details returned with detail_flag=INTRADAY.

    Contains current trading session data.
    """

    ask: Decimal = Field()
    bid: Decimal = Field()
    change_close: Decimal = Field(alias="changeClose")
    change_close_pct: Decimal = Field(alias="changeClosePercentage")
    company_name: str = Field(alias="companyName")
    high: Decimal = Field()
    last_trade: Decimal = Field(alias="lastTrade")
    low: Decimal = Field()
    total_volume: int = Field(alias="totalVolume")

    model_config = {"populate_by_name": True}


class OptionsQuoteDetail(BaseModel):
    """Quote details returned with detail_flag=OPTIONS.

    Contains options-related quote data (not to be confused with OptionDetails
    which represents individual option contracts in an options chain).
    """

    ask: Decimal = Field()
    ask_size: int = Field(alias="askSize")
    bid: Decimal = Field()
    bid_size: int = Field(alias="bidSize")
    company_name: str = Field(alias="companyName")
    contract_size: Decimal = Field(alias="contractSize")
    days_to_expiration: int = Field(alias="daysToExpiration")
    intrinsic_value: Decimal = Field(alias="intrinsicValue")
    last_trade: Decimal = Field(alias="lastTrade")
    open_interest: int = Field(alias="openInterest")
    option_multiplier: Decimal = Field(alias="optionMultiplier")
    option_previous_ask_price: Decimal = Field(alias="optionPreviousAskPrice")
    option_previous_bid_price: Decimal = Field(alias="optionPreviousBidPrice")
    osi_key: str = Field(alias="osiKey")
    symbol_description: str = Field(alias="symbolDescription")
    time_premium: Decimal = Field(alias="timePremium")

    model_config = {"populate_by_name": True}


class Week52QuoteDetail(BaseModel):
    """Quote details returned with detail_flag=WEEK_52.

    Contains 52-week performance data.
    """

    company_name: str = Field(alias="companyName")
    high_52: Decimal = Field(alias="high52")
    last_trade: Decimal = Field(alias="lastTrade")
    low_52: Decimal = Field(alias="low52")
    perf_12_months: Decimal = Field(alias="perf12Months")
    previous_close: Decimal = Field(alias="previousClose")
    symbol_description: str = Field(alias="symbolDescription")
    total_volume: int = Field(alias="totalVolume")

    model_config = {"populate_by_name": True}


class AllQuoteDetail(BaseModel):
    """Quote details returned with detail_flag=ALL.

    Contains the most comprehensive quote data including price, volume,
    company info, dividend data, and optionally extended hours data.

    Note: Most fields are optional to maintain backwards compatibility
    and handle edge cases where the API may not return all fields.
    Fields marked as required are those that are always present per
    E*Trade API documentation and observed data.
    """

    # Price data - required fields (always present)
    last_trade: Decimal = Field(alias="lastTrade")
    previous_close: Decimal = Field(alias="previousClose")
    open_: Decimal = Field(alias="open")
    high: Decimal = Field()
    low: Decimal = Field()
    total_volume: int = Field(alias="totalVolume")

    # Change from close - may not be present in some responses
    change: Decimal = Field(default=Decimal("0"))
    change_pct: Decimal = Field(default=Decimal("0"), alias="changePct")
    change_close: Decimal | None = Field(default=None, alias="changeClose")
    change_close_pct: Decimal | None = Field(default=None, alias="changeClosePercentage")

    # Core identifiers
    company_name: str | None = Field(default=None, alias="companyName")
    symbol_description: str | None = Field(default=None, alias="symbolDescription")

    # 52-week range
    high_52: Decimal | None = Field(default=None, alias="high52")
    low_52: Decimal | None = Field(default=None, alias="low52")
    week_52_hi_date: int | None = Field(default=None, alias="week52HiDate")
    week_52_low_date: int | None = Field(default=None, alias="week52LowDate")

    # Volume
    average_volume: int | None = Field(default=None, alias="averageVolume")
    previous_day_volume: int | None = Field(default=None, alias="previousDayVolume")

    # Bid/Ask
    bid: Decimal | None = Field(default=None)
    ask: Decimal | None = Field(default=None)
    bid_size: int | None = Field(default=None, alias="bidSize")
    ask_size: int | None = Field(default=None, alias="askSize")
    bid_time: str | None = Field(default=None, alias="bidTime")
    ask_time: str | None = Field(default=None, alias="askTime")
    bid_exchange: str | None = Field(default=None, alias="bidExchange")

    # Company fundamentals
    market_cap: Decimal | None = Field(default=None, alias="marketCap")
    pe_ratio: Decimal | None = Field(default=None, alias="peRatio")
    pe: Decimal | None = Field(default=None)
    eps: Decimal | None = Field(default=None)
    est_earnings: Decimal | None = Field(default=None, alias="estEarnings")
    beta: Decimal | None = Field(default=None)
    shares_outstanding: int | None = Field(default=None, alias="sharesOutstanding")
    primary_exchange: str | None = Field(default=None, alias="primaryExchange")
    upc: int | None = Field(default=None)

    # Dividend info
    dividend: Decimal | None = Field(default=None)
    dividend_yield_field: Decimal | None = Field(default=None, alias="yield")
    dividend_yield: Decimal | None = Field(default=None, alias="dividendYield")
    declared_dividend: Decimal | None = Field(default=None, alias="declaredDividend")
    dividend_payable_date: int | None = Field(default=None, alias="dividendPayableDate")
    ex_dividend_date: int | None = Field(default=None, alias="exDividendDate")

    # Earnings
    next_earning_date: str | None = Field(default=None, alias="nextEarningDate")

    # Options-related fields (present even for non-option quotes)
    open_interest: int | None = Field(default=None, alias="openInterest")
    intrinsic_value: Decimal | None = Field(default=None, alias="intrinsicValue")
    time_premium: Decimal | None = Field(default=None, alias="timePremium")
    option_multiplier: Decimal | None = Field(default=None, alias="optionMultiplier")
    contract_size: Decimal | None = Field(default=None, alias="contractSize")
    expiration_date: int | None = Field(default=None, alias="expirationDate")
    days_to_expiration: int | None = Field(default=None, alias="daysToExpiration")
    option_style: str | None = Field(default=None, alias="optionStyle")
    option_underlier: str | None = Field(default=None, alias="optionUnderlier")
    option_underlier_exchange: str | None = Field(default=None, alias="optionUnderlierExchange")
    osi_key: str | None = Field(default=None, alias="osiKey")
    option_previous_ask_price: Decimal | None = Field(default=None, alias="optionPreviousAskPrice")
    option_previous_bid_price: Decimal | None = Field(default=None, alias="optionPreviousBidPrice")
    cash_deliverable: int | None = Field(default=None, alias="cashDeliverable")

    # Status and timing
    time_of_last_trade: int | None = Field(default=None, alias="timeOfLastTrade")
    dir_last: str | None = Field(default=None, alias="dirLast")
    adjusted_flag: bool | None = Field(default=None, alias="adjustedFlag")

    # Extended hours data - optional, only present when ahFlag is 'true'
    extended_hour_quote_detail: ExtendedHourQuoteDetail | None = Field(
        default=None, alias="ExtendedHourQuoteDetail"
    )

    model_config = {"populate_by_name": True}


# Backwards compatibility alias
AllQuoteDetails = AllQuoteDetail


class QuoteProduct(BaseModel):
    """Product information in a quote."""

    symbol: str
    security_type: str | None = Field(default=None, alias="securityType")
    exchange: str | None = Field(default=None)
    type_code: str | None = Field(default=None, alias="typeCode")

    model_config = {"populate_by_name": True}


class Quote(BaseModel):
    """Stock quote with all available data.

    The detail fields are mutually exclusive based on the detail_flag parameter
    used when fetching quotes:
    - ALL: all_ field populated
    - FUNDAMENTAL: fundamental field populated
    - INTRADAY: intraday field populated
    - OPTIONS: option field populated
    - WEEK_52: week_52 field populated
    """

    # symbol is extracted from Product during parsing
    symbol: str
    # Always present fields
    quote_status: QuoteStatus = Field(alias="quoteStatus")
    date_time: str = Field(alias="dateTime")
    date_time_utc: int = Field(alias="dateTimeUTC")
    ah_flag: str = Field(alias="ahFlag")
    product: QuoteProduct = Field(alias="Product")

    # Detail type objects - only one will be present based on detail_flag
    all_: AllQuoteDetail | None = Field(default=None, alias="All")
    fundamental: FundamentalQuoteDetail | None = Field(default=None, alias="Fundamental")
    intraday: IntradayQuoteDetail | None = Field(default=None, alias="Intraday")
    option: OptionsQuoteDetail | None = Field(default=None, alias="Option")
    week_52: Week52QuoteDetail | None = Field(default=None, alias="Week52")

    # Backwards compatibility alias (deprecated, use all_ instead)
    @property
    def all_data(self) -> AllQuoteDetail | None:
        """Deprecated: Use all_ instead."""
        return self.all_

    # Flattened common fields for convenience - checks all detail types
    @property
    def last_trade(self) -> Decimal | None:
        """Get last trade price from any available detail type."""
        if self.all_:
            return self.all_.last_trade
        if self.fundamental:
            return self.fundamental.last_trade
        if self.intraday:
            return self.intraday.last_trade
        if self.option:
            return self.option.last_trade
        if self.week_52:
            return self.week_52.last_trade
        return None

    @property
    def company_name(self) -> str | None:
        """Get company name from any available detail type."""
        if self.all_:
            return self.all_.company_name
        if self.fundamental:
            return self.fundamental.company_name
        if self.intraday:
            return self.intraday.company_name
        if self.option:
            return self.option.company_name
        if self.week_52:
            return self.week_52.company_name
        return None

    @property
    def change(self) -> Decimal | None:
        """Get change from available detail types (backwards compat)."""
        if self.all_:
            return self.all_.change
        return None

    @property
    def change_pct(self) -> Decimal | None:
        """Get change percentage from available detail types (backwards compat)."""
        if self.all_:
            return self.all_.change_pct
        return None

    @property
    def change_close(self) -> Decimal | None:
        """Get change from close from available detail types."""
        if self.all_:
            return self.all_.change_close
        if self.intraday:
            return self.intraday.change_close
        return None

    @property
    def change_close_pct(self) -> Decimal | None:
        """Get change from close percentage from available detail types."""
        if self.all_:
            return self.all_.change_close_pct
        if self.intraday:
            return self.intraday.change_close_pct
        return None

    @property
    def volume(self) -> int | None:
        """Get total volume from available detail types."""
        if self.all_:
            return self.all_.total_volume
        if self.intraday:
            return self.intraday.total_volume
        if self.week_52:
            return self.week_52.total_volume
        return None

    model_config = {"populate_by_name": True}


class QuoteResponse(BaseModel):
    """Response from quotes endpoint."""

    quotes: list[Quote] = Field(default_factory=list)

    @classmethod
    def from_api_response(cls, data: dict[str, Any]) -> QuoteResponse:
        """Parse from raw API response."""
        quote_response = data.get("QuoteResponse", {})
        quote_data = quote_response.get("QuoteData", [])

        if isinstance(quote_data, dict):
            quote_data = [quote_data]

        quotes = []
        for q in quote_data:
            # Extract symbol from nested Product object
            product = q.get("Product", {})
            symbol = product.get("symbol", "")
            quote_dict = {**q, "symbol": symbol}
            quotes.append(Quote.model_validate(quote_dict))

        return cls(quotes=quotes)


class OptionType(StrEnum):
    """Option type."""

    CALL = "CALL"
    PUT = "PUT"


class OptionGreeks(BaseModel):
    """Option greeks (sensitivities)."""

    delta: Decimal | None = Field(default=None)
    gamma: Decimal | None = Field(default=None)
    theta: Decimal | None = Field(default=None)
    vega: Decimal | None = Field(default=None)
    rho: Decimal | None = Field(default=None)
    iv: Decimal | None = Field(default=None)
    current_value: bool | None = Field(default=None, alias="currentValue")

    model_config = {"populate_by_name": True}


class OptionDetails(BaseModel):
    """Individual option contract details."""

    # Core option identifiers - always present
    symbol: str = Field(alias="optionSymbol")
    option_type: OptionType = Field(alias="optionType")
    strike_price: Decimal = Field(alias="strikePrice")

    # Display and symbol info - always present
    display_symbol: str = Field(alias="displaySymbol")
    option_root_symbol: str = Field(alias="optionRootSymbol")
    osi_key: str = Field(alias="osiKey")
    option_category: str = Field(alias="optionCategory")
    quote_detail: str = Field(alias="quoteDetail")

    # Pricing - always present
    bid: Decimal = Field()
    ask: Decimal = Field()
    bid_size: int = Field(alias="bidSize")
    ask_size: int = Field(alias="askSize")
    last_price: Decimal = Field(alias="lastPrice")
    net_change: Decimal = Field(alias="netChange")

    # Volume and interest - always present
    volume: int = Field()
    open_interest: int = Field(alias="openInterest")

    # Greeks - always present as nested object
    option_greeks: OptionGreeks = Field(alias="OptionGreeks")

    # Status flags - always present
    in_the_money: bool = Field(alias="inTheMoney")
    adjusted_flag: bool = Field(alias="adjustedFlag")
    time_stamp: int = Field(alias="timeStamp")

    @field_validator("in_the_money", mode="before")
    @classmethod
    def parse_in_the_money(cls, v: Any) -> bool:
        """Convert API's 'y'/'n' strings to boolean."""
        if isinstance(v, bool):
            return v
        if isinstance(v, str):
            return v.lower() in ("y", "yes", "true", "1")
        return bool(v)

    # Deprecated/legacy inline greeks - never present in current API
    implied_volatility: Decimal | None = Field(default=None, alias="impliedVolatility")
    delta: Decimal | None = Field(default=None)
    gamma: Decimal | None = Field(default=None)
    theta: Decimal | None = Field(default=None)
    vega: Decimal | None = Field(default=None)
    rho: Decimal | None = Field(default=None)
    expiry_date: date | None = Field(default=None, alias="expiryDate")

    model_config = {"populate_by_name": True}


class OptionPair(BaseModel):
    """Call/Put pair at a strike price."""

    call: OptionDetails | None = Field(default=None, alias="Call")
    put: OptionDetails | None = Field(default=None, alias="Put")

    model_config = {"populate_by_name": True}


class OptionChain(BaseModel):
    """Options chain for a symbol."""

    symbol: str
    expiry_date: date
    option_pairs: list[OptionPair] = Field(default_factory=list)

    @classmethod
    def from_api_response(cls, data: dict[str, Any], symbol: str, expiry: date) -> OptionChain:
        """Parse from raw API response."""
        chain_response = data.get("OptionChainResponse", {})
        option_pairs_data = chain_response.get("OptionPair", [])

        if isinstance(option_pairs_data, dict):
            option_pairs_data = [option_pairs_data]

        return cls(
            symbol=symbol,
            expiry_date=expiry,
            option_pairs=[OptionPair.model_validate(p) for p in option_pairs_data],
        )


class OptionExpireDate(BaseModel):
    """Available expiration date for options."""

    expiry_date: date = Field(alias="expiryDate")
    expiry_type: OptionExpiryType | None = Field(default=None, alias="expiryType")

    model_config = {"populate_by_name": True}

    @classmethod
    def from_api_response(cls, data: dict[str, Any]) -> list[OptionExpireDate]:
        """Parse from raw API response."""
        expire_response = data.get("OptionExpireDateResponse", {})
        expire_dates = expire_response.get("ExpirationDate", [])

        if isinstance(expire_dates, dict):
            expire_dates = [expire_dates]

        results = []
        for exp in expire_dates:
            # API returns year, month, day separately
            expiry = date(exp["year"], exp["month"], exp["day"])
            results.append(
                cls.model_validate({"expiryDate": expiry, "expiryType": exp.get("expiryType")})
            )

        return results
