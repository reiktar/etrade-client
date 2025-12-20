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
    account_desc: str | None = Field(default=None, alias="accountDesc")
    account_name: str | None = Field(default=None, alias="accountName")
    account_mode: str | None = Field(default=None, alias="accountMode")
    account_status: str | None = Field(default=None, alias="accountStatus")
    institution_type: str | None = Field(default=None, alias="institutionType")

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

    funds_for_open_orders_cash: Decimal = Field(
        default=Decimal("0"), alias="fundsForOpenOrdersCash"
    )
    money_market_balance: Decimal = Field(default=Decimal("0"), alias="moneyMktBalance")
    cash_available_for_investment: Decimal = Field(
        default=Decimal("0"), alias="cashAvailableForInvestment"
    )
    cash_available_for_withdrawal: Decimal = Field(
        default=Decimal("0"), alias="cashAvailableForWithdrawal"
    )
    cash_balance: Decimal = Field(default=Decimal("0"), alias="cashBalance")
    settled_cash_for_investment: Decimal = Field(
        default=Decimal("0"), alias="settledCashForInvestment"
    )
    uncleared_deposits: Decimal = Field(default=Decimal("0"), alias="unclearedDeposits")

    model_config = {"populate_by_name": True}


class ComputedBalance(BaseModel):
    """Computed account balance values."""

    account_balance: Decimal = Field(default=Decimal("0"), alias="accountBalance")
    cash_available_for_investment: Decimal = Field(
        default=Decimal("0"), alias="cashAvailableForInvestment"
    )
    cash_available_for_withdrawal: Decimal = Field(
        default=Decimal("0"), alias="cashAvailableForWithdrawal"
    )
    net_cash: Decimal = Field(default=Decimal("0"), alias="netCash")
    cash_balance: Decimal = Field(default=Decimal("0"), alias="cashBalance")
    margin_buying_power: Decimal = Field(default=Decimal("0"), alias="marginBuyingPower")
    real_time_account_value: Decimal = Field(default=Decimal("0"), alias="RealTimeAccountValue")

    model_config = {"populate_by_name": True}


class AccountBalance(BaseModel):
    """Complete account balance information."""

    account_id: str = Field(alias="accountId")
    account_type: str = Field(alias="accountType")
    account_description: str | None = Field(default=None, alias="accountDescription")
    cash: CashBalance | None = Field(default=None, alias="Cash")
    computed: ComputedBalance | None = Field(default=None, alias="Computed")
    net_account_value: Decimal = Field(default=Decimal("0"), alias="netAccountValue")
    total_account_value: Decimal = Field(default=Decimal("0"), alias="totalAccountValue")

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
    security_sub_type: str | None = Field(default=None, alias="securitySubType")
    exchange: str | None = Field(default=None)

    model_config = {"populate_by_name": True}


class PositionQuick(BaseModel):
    """Quick quote for a position."""

    last_trade: Decimal = Field(alias="lastTrade")
    change: Decimal | None = Field(default=None)
    change_pct: Decimal | None = Field(default=None, alias="changePct")
    volume: int | None = Field(default=None)

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
    days_gain: Decimal | None = Field(default=None, alias="daysGain")
    days_gain_pct: Decimal | None = Field(default=None, alias="daysGainPct")
    position_type: PositionType = Field(alias="positionType")
    quick: PositionQuick | None = Field(default=None, alias="Quick")
    date_acquired: datetime | None = Field(default=None, alias="dateAcquired")

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
