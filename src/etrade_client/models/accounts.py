"""Account-related models."""

from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, Field


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
    def from_api_response(cls, data: dict) -> AccountListResponse:
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
    funds_withheld_from_purchase_power: Decimal = Field(
        alias="fundsWithheldFromPurchasePower"
    )
    funds_withheld_from_withdrawal: Decimal = Field(alias="fundsWithheldFromWithdrawal")

    # Nested objects - always present in API responses
    open_calls: OpenCalls = Field(alias="OpenCalls")
    real_time_values: RealTimeValues = Field(alias="RealTimeValues")

    # Never present in sandbox - use None to avoid implying balance is 0
    account_balance: Decimal | None = Field(default=None, alias="accountBalance")
    margin_buying_power: Decimal | None = Field(default=None, alias="marginBuyingPower")
    real_time_account_value: Decimal | None = Field(
        default=None, alias="RealTimeAccountValue"
    )

    model_config = {"populate_by_name": True}


class AccountBalance(BaseModel):
    """Complete account balance information."""

    account_id: str = Field(alias="accountId")
    account_type: str = Field(alias="accountType")
    account_description: str = Field(alias="accountDescription")
    option_level: str = Field(alias="optionLevel")
    cash: CashBalance = Field(alias="Cash")
    computed: ComputedBalance = Field(alias="Computed")
    # These fields are context-specific - may not always be present
    net_account_value: Decimal | None = Field(default=None, alias="netAccountValue")
    total_account_value: Decimal | None = Field(default=None, alias="totalAccountValue")

    model_config = {"populate_by_name": True}


class BalanceResponse(BaseModel):
    """Response from balance endpoint."""

    balance: AccountBalance

    @classmethod
    def from_api_response(cls, data: dict) -> BalanceResponse:
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
    product_id: dict = Field(alias="productId")
    # These may not always be present
    security_sub_type: str | None = Field(default=None, alias="securitySubType")
    exchange: str | None = Field(default=None)

    model_config = {"populate_by_name": True}


class PositionQuick(BaseModel):
    """Quick quote for a position."""

    last_trade: Decimal = Field(alias="lastTrade")
    change: Decimal = Field()
    change_pct: Decimal = Field(alias="changePct")
    volume: int = Field()
    last_trade_time: int = Field(alias="lastTradeTime")

    model_config = {"populate_by_name": True}


class PortfolioPosition(BaseModel):
    """A position in the portfolio."""

    position_id: int = Field(alias="positionId")
    product: Product = Field(alias="Product")
    quantity: Decimal
    cost_per_share: Decimal = Field(alias="costPerShare")
    total_cost: Decimal = Field(alias="totalCost")
    market_value: Decimal = Field(alias="marketValue")
    total_gain: Decimal = Field(alias="totalGain")
    total_gain_pct: Decimal = Field(alias="totalGainPct")
    days_gain: Decimal = Field(alias="daysGain")
    days_gain_pct: Decimal = Field(alias="daysGainPct")
    position_type: PositionType = Field(alias="positionType")
    quick: PositionQuick = Field(alias="Quick")
    date_acquired: datetime = Field(alias="dateAcquired")

    # Additional position details - all always present
    symbol_description: str = Field(alias="symbolDescription")
    position_indicator: str = Field(alias="positionIndicator")
    pct_of_portfolio: Decimal = Field(alias="pctOfPortfolio")
    price_paid: Decimal = Field(alias="pricePaid")
    commissions: Decimal = Field()
    other_fees: Decimal = Field(alias="otherFees")
    lots_details: str = Field(alias="lotsDetails")
    quote_details: str = Field(alias="quoteDetails")

    # Today's activity - all always present
    today_quantity: int = Field(alias="todayQuantity")
    today_price_paid: Decimal = Field(alias="todayPricePaid")
    today_commissions: Decimal = Field(alias="todayCommissions")
    today_fees: Decimal = Field(alias="todayFees")

    model_config = {"populate_by_name": True}


class PortfolioResponse(BaseModel):
    """Response from portfolio endpoint."""

    account_id: str
    positions: list[PortfolioPosition] = Field(default_factory=list)
    total_value: Decimal = Field(default=Decimal("0"))

    @classmethod
    def from_api_response(cls, data: dict, account_id: str) -> PortfolioResponse:
        """Parse from raw API response."""
        portfolio_data = data.get("PortfolioResponse", {})
        account_portfolios = portfolio_data.get("AccountPortfolio", [])

        if isinstance(account_portfolios, dict):
            account_portfolios = [account_portfolios]

        positions = []
        total_value = Decimal("0")

        for account_portfolio in account_portfolios:
            position_list = account_portfolio.get("Position", [])
            if isinstance(position_list, dict):
                position_list = [position_list]
            for pos in position_list:
                positions.append(PortfolioPosition.model_validate(pos))

            total_value += Decimal(str(account_portfolio.get("totalValue", 0)))

        return cls(account_id=account_id, positions=positions, total_value=total_value)
