"""Market data models."""

from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, Field


class QuoteStatus(StrEnum):
    """Quote status values."""

    REALTIME = "REALTIME"
    DELAYED = "DELAYED"
    CLOSING = "CLOSING"
    EH_REALTIME = "EH_REALTIME"
    EH_BEFORE_OPEN = "EH_BEFORE_OPEN"
    EH_CLOSED = "EH_CLOSED"


class AllQuoteDetails(BaseModel):
    """Detailed quote information."""

    # Price data
    last_trade: Decimal = Field(alias="lastTrade")
    change: Decimal = Field(default=Decimal("0"))
    change_pct: Decimal = Field(default=Decimal("0"), alias="changePct")
    previous_close: Decimal = Field(alias="previousClose")

    # Day range
    high: Decimal = Field(alias="high")
    low: Decimal = Field(alias="low")
    open_: Decimal = Field(alias="open")

    # 52-week range
    high_52: Decimal | None = Field(default=None, alias="high52")
    low_52: Decimal | None = Field(default=None, alias="low52")

    # Volume
    total_volume: int = Field(alias="totalVolume")
    average_volume: int | None = Field(default=None, alias="averageVolume")

    # Bid/Ask
    bid: Decimal | None = Field(default=None)
    ask: Decimal | None = Field(default=None)
    bid_size: int | None = Field(default=None, alias="bidSize")
    ask_size: int | None = Field(default=None, alias="askSize")

    # Company info
    company_name: str | None = Field(default=None, alias="companyName")
    market_cap: Decimal | None = Field(default=None, alias="marketCap")
    pe_ratio: Decimal | None = Field(default=None, alias="peRatio")
    eps: Decimal | None = Field(default=None)
    dividend: Decimal | None = Field(default=None)
    dividend_yield: Decimal | None = Field(default=None, alias="dividendYield")
    shares_outstanding: int | None = Field(default=None, alias="sharesOutstanding")

    # Timestamps
    quote_time: datetime | None = Field(default=None, alias="dateTimeUTC")

    model_config = {"populate_by_name": True}


class Quote(BaseModel):
    """Stock quote with all available data."""

    symbol: str
    quote_status: str | None = Field(default=None, alias="quoteStatus")
    date_time: str | None = Field(default=None, alias="dateTime")
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
    def from_api_response(cls, data: dict) -> QuoteResponse:
        """Parse from raw API response."""
        quote_response = data.get("QuoteResponse", {})
        quote_data = quote_response.get("QuoteData", [])

        if isinstance(quote_data, dict):
            quote_data = [quote_data]

        return cls(quotes=[Quote.model_validate(q) for q in quote_data])


class OptionType(StrEnum):
    """Option type."""

    CALL = "CALL"
    PUT = "PUT"


class OptionDetails(BaseModel):
    """Individual option contract details."""

    symbol: str = Field(alias="optionSymbol")
    option_type: str = Field(alias="optionType")
    strike_price: Decimal = Field(alias="strikePrice")
    expiry_date: date = Field(alias="expiryDate")
    bid: Decimal | None = Field(default=None)
    ask: Decimal | None = Field(default=None)
    last_price: Decimal | None = Field(default=None, alias="lastPrice")
    volume: int | None = Field(default=None)
    open_interest: int | None = Field(default=None, alias="openInterest")
    implied_volatility: Decimal | None = Field(default=None, alias="impliedVolatility")
    delta: Decimal | None = Field(default=None)
    gamma: Decimal | None = Field(default=None)
    theta: Decimal | None = Field(default=None)
    vega: Decimal | None = Field(default=None)
    rho: Decimal | None = Field(default=None)
    in_the_money: bool | None = Field(default=None, alias="inTheMoney")

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
    def from_api_response(cls, data: dict, symbol: str, expiry: date) -> OptionChain:
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
    expiry_type: str | None = Field(default=None, alias="expiryType")  # WEEKLY, MONTHLY, QUARTERLY

    model_config = {"populate_by_name": True}

    @classmethod
    def from_api_response(cls, data: dict) -> list[OptionExpireDate]:
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
