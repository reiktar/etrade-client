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


class AllQuoteDetails(BaseModel):
    """Detailed quote information."""

    # Price data
    last_trade: Decimal = Field(alias="lastTrade")
    change: Decimal = Field(default=Decimal("0"))
    change_pct: Decimal = Field(default=Decimal("0"), alias="changePct")
    change_close: Decimal | None = Field(default=None, alias="changeClose")
    change_close_pct: Decimal | None = Field(default=None, alias="changeClosePercentage")
    previous_close: Decimal = Field(alias="previousClose")

    # Day range
    high: Decimal = Field(alias="high")
    low: Decimal = Field(alias="low")
    open_: Decimal = Field(alias="open")

    # 52-week range
    high_52: Decimal | None = Field(default=None, alias="high52")
    low_52: Decimal | None = Field(default=None, alias="low52")
    week_52_hi_date: int | None = Field(default=None, alias="week52HiDate")
    week_52_low_date: int | None = Field(default=None, alias="week52LowDate")

    # Volume
    total_volume: int = Field(alias="totalVolume")
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

    # Company info
    company_name: str | None = Field(default=None, alias="companyName")
    symbol_description: str | None = Field(default=None, alias="symbolDescription")
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

    # Options-related (when quoting options)
    open_interest: int | None = Field(default=None, alias="openInterest")
    intrinsic_value: Decimal | None = Field(default=None, alias="intrinsicValue")
    time_premium: Decimal | None = Field(default=None, alias="timePremium")
    option_multiplier: Decimal | None = Field(default=None, alias="optionMultiplier")
    contract_size: Decimal | None = Field(default=None, alias="contractSize")
    expiration_date: int | None = Field(default=None, alias="expirationDate")
    days_to_expiration: int | None = Field(default=None, alias="daysToExpiration")
    option_style: str | None = Field(default=None, alias="optionStyle")
    cash_deliverable: int | None = Field(default=None, alias="cashDeliverable")

    # Timestamps and status
    time_of_last_trade: int | None = Field(default=None, alias="timeOfLastTrade")
    dir_last: str | None = Field(default=None, alias="dirLast")
    adjusted_flag: bool | None = Field(default=None, alias="adjustedFlag")

    model_config = {"populate_by_name": True}


class QuoteProduct(BaseModel):
    """Product information in a quote."""

    symbol: str
    security_type: str | None = Field(default=None, alias="securityType")
    exchange: str | None = Field(default=None)
    type_code: str | None = Field(default=None, alias="typeCode")

    model_config = {"populate_by_name": True}


class Quote(BaseModel):
    """Stock quote with all available data."""

    # symbol is extracted from Product during parsing
    symbol: str
    # Always present fields
    quote_status: QuoteStatus = Field(alias="quoteStatus")
    date_time: str = Field(alias="dateTime")
    date_time_utc: int = Field(alias="dateTimeUTC")
    ah_flag: str = Field(alias="ahFlag")
    product: QuoteProduct = Field(alias="Product")
    # May not be present depending on detail level requested
    all_data: AllQuoteDetails | None = Field(default=None, alias="All")

    # Flattened common fields for convenience
    @property
    def last_trade(self) -> Decimal | None:
        return self.all_data.last_trade if self.all_data else None

    @property
    def change(self) -> Decimal | None:
        return self.all_data.change if self.all_data else None

    @property
    def change_pct(self) -> Decimal | None:
        return self.all_data.change_pct if self.all_data else None

    @property
    def volume(self) -> int | None:
        return self.all_data.total_volume if self.all_data else None

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
