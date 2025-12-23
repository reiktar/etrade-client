"""Chart of accounts for E*Trade double-entry bookkeeping."""

from etrade_client.doubleentry.models import Account, AccountType

# =============================================================================
# CHART OF ACCOUNTS
# =============================================================================
# This defines all standard accounts used for E*Trade transaction mapping.
# Accounts are organized hierarchically using colon-separated names.
# =============================================================================

# -----------------------------------------------------------------------------
# ASSETS - What you own (Debit increases)
# -----------------------------------------------------------------------------

# Cash accounts
CASH_SETTLEMENT = Account(
    name="Assets:Cash:Settlement",
    account_type=AccountType.ASSET,
    description="Main brokerage cash balance",
)

CASH_MONEY_MARKET = Account(
    name="Assets:Cash:MoneyMarket",
    account_type=AccountType.ASSET,
    description="Money market sweep account",
)

CASH_PENDING = Account(
    name="Assets:Cash:Pending",
    account_type=AccountType.ASSET,
    description="Cash pending settlement (T+1/T+2)",
)

# Securities (stocks/ETFs) - created dynamically per symbol
# Template: Assets:Securities:{SYMBOL}

# Long options - created dynamically per symbol
# Template: Assets:Options:{SYMBOL}

# -----------------------------------------------------------------------------
# LIABILITIES - What you owe (Credit increases)
# -----------------------------------------------------------------------------

MARGIN_LOAN = Account(
    name="Liabilities:Margin:Loan",
    account_type=AccountType.LIABILITY,
    description="Margin borrowing balance",
)

# Short options obligations - created dynamically per symbol
# Template: Liabilities:ShortOptions:{SYMBOL}

# -----------------------------------------------------------------------------
# EQUITY - Net worth / Owner's stake (Credit increases)
# -----------------------------------------------------------------------------

EQUITY_CONTRIBUTIONS = Account(
    name="Equity:Contributions",
    account_type=AccountType.EQUITY,
    description="Money deposited into account",
)

EQUITY_DISTRIBUTIONS = Account(
    name="Equity:Distributions",
    account_type=AccountType.EQUITY,
    description="Money withdrawn from account",
)

EQUITY_RETAINED_EARNINGS = Account(
    name="Equity:RetainedEarnings",
    account_type=AccountType.EQUITY,
    description="Accumulated profits/losses",
)

# -----------------------------------------------------------------------------
# INCOME - Money earned (Credit increases)
# -----------------------------------------------------------------------------

# Dividends - created dynamically per symbol
# Template: Income:Dividends:{SYMBOL}

INCOME_INTEREST = Account(
    name="Income:Interest",
    account_type=AccountType.INCOME,
    description="Interest earned on cash",
)

# Capital gains - created dynamically per symbol
# Template: Income:CapitalGains:{SYMBOL}

# Option premium income - created dynamically per symbol
# Template: Income:OptionPremiums:{SYMBOL}

INCOME_OTHER = Account(
    name="Income:Other",
    account_type=AccountType.INCOME,
    description="Miscellaneous income",
)

# -----------------------------------------------------------------------------
# EXPENSES - Money spent (Debit increases)
# -----------------------------------------------------------------------------

EXPENSE_COMMISSION = Account(
    name="Expenses:Fees:Commission",
    account_type=AccountType.EXPENSE,
    description="Trading commissions",
)

EXPENSE_SEC_FEE = Account(
    name="Expenses:Fees:SEC",
    account_type=AccountType.EXPENSE,
    description="SEC regulatory fee",
)

EXPENSE_TAF_FEE = Account(
    name="Expenses:Fees:TAF",
    account_type=AccountType.EXPENSE,
    description="Trading Activity Fee",
)

EXPENSE_ADR_FEE = Account(
    name="Expenses:Fees:ADR",
    account_type=AccountType.EXPENSE,
    description="ADR custody fee",
)

EXPENSE_OTHER_FEE = Account(
    name="Expenses:Fees:Other",
    account_type=AccountType.EXPENSE,
    description="Other fees",
)

EXPENSE_MARGIN_INTEREST = Account(
    name="Expenses:Interest:Margin",
    account_type=AccountType.EXPENSE,
    description="Margin interest paid",
)

# Capital losses - created dynamically per symbol
# Template: Expenses:CapitalLosses:{SYMBOL}

EXPENSE_OTHER = Account(
    name="Expenses:Other",
    account_type=AccountType.EXPENSE,
    description="Miscellaneous expenses",
)

# =============================================================================
# ACCOUNT REGISTRY
# =============================================================================

# All predefined accounts
CHART_OF_ACCOUNTS: dict[str, Account] = {
    # Assets
    CASH_SETTLEMENT.name: CASH_SETTLEMENT,
    CASH_MONEY_MARKET.name: CASH_MONEY_MARKET,
    CASH_PENDING.name: CASH_PENDING,
    # Liabilities
    MARGIN_LOAN.name: MARGIN_LOAN,
    # Equity
    EQUITY_CONTRIBUTIONS.name: EQUITY_CONTRIBUTIONS,
    EQUITY_DISTRIBUTIONS.name: EQUITY_DISTRIBUTIONS,
    EQUITY_RETAINED_EARNINGS.name: EQUITY_RETAINED_EARNINGS,
    # Income
    INCOME_INTEREST.name: INCOME_INTEREST,
    INCOME_OTHER.name: INCOME_OTHER,
    # Expenses
    EXPENSE_COMMISSION.name: EXPENSE_COMMISSION,
    EXPENSE_SEC_FEE.name: EXPENSE_SEC_FEE,
    EXPENSE_TAF_FEE.name: EXPENSE_TAF_FEE,
    EXPENSE_ADR_FEE.name: EXPENSE_ADR_FEE,
    EXPENSE_OTHER_FEE.name: EXPENSE_OTHER_FEE,
    EXPENSE_MARGIN_INTEREST.name: EXPENSE_MARGIN_INTEREST,
    EXPENSE_OTHER.name: EXPENSE_OTHER,
}

# Cache for dynamically created accounts
_dynamic_accounts: dict[str, Account] = {}


def get_account(name: str) -> Account:
    """Get an account by name, creating dynamic accounts as needed.

    For symbol-specific accounts, this will create the account on demand:
        - Assets:Securities:AAPL
        - Income:Dividends:MSTY
        - Income:CapitalGains:TSLA
        - Expenses:CapitalLosses:META

    Args:
        name: Full account name (e.g., "Assets:Cash:Settlement")

    Returns:
        The Account object

    Raises:
        ValueError: If the account name pattern is not recognized
    """
    # Check predefined accounts first
    if name in CHART_OF_ACCOUNTS:
        return CHART_OF_ACCOUNTS[name]

    # Check dynamic account cache
    if name in _dynamic_accounts:
        return _dynamic_accounts[name]

    # Try to create dynamic account based on pattern
    account = _create_dynamic_account(name)
    if account:
        _dynamic_accounts[name] = account
        return account

    raise ValueError(f"Unknown account: {name}")


def _create_dynamic_account(name: str) -> Account | None:
    """Create a dynamic account based on naming patterns."""
    parts = name.split(":")

    if len(parts) < 2:
        return None

    # Assets:Securities:{SYMBOL}
    if name.startswith("Assets:Securities:") and len(parts) == 3:
        symbol = parts[2]
        return Account(
            name=name,
            account_type=AccountType.ASSET,
            description=f"Holdings of {symbol}",
        )

    # Assets:Options:{SYMBOL}
    if name.startswith("Assets:Options:") and len(parts) == 3:
        symbol = parts[2]
        return Account(
            name=name,
            account_type=AccountType.ASSET,
            description=f"Long option positions in {symbol}",
        )

    # Liabilities:ShortOptions:{SYMBOL}
    if name.startswith("Liabilities:ShortOptions:") and len(parts) == 3:
        symbol = parts[2]
        return Account(
            name=name,
            account_type=AccountType.LIABILITY,
            description=f"Short option obligations in {symbol}",
        )

    # Income:Dividends:{SYMBOL}
    if name.startswith("Income:Dividends:") and len(parts) == 3:
        symbol = parts[2]
        return Account(
            name=name,
            account_type=AccountType.INCOME,
            description=f"Dividends received from {symbol}",
        )

    # Income:CapitalGains:{SYMBOL}
    if name.startswith("Income:CapitalGains:") and len(parts) == 3:
        symbol = parts[2]
        return Account(
            name=name,
            account_type=AccountType.INCOME,
            description=f"Capital gains from {symbol}",
        )

    # Income:OptionPremiums:{SYMBOL}
    if name.startswith("Income:OptionPremiums:") and len(parts) == 3:
        symbol = parts[2]
        return Account(
            name=name,
            account_type=AccountType.INCOME,
            description=f"Option premium income from {symbol}",
        )

    # Expenses:CapitalLosses:{SYMBOL}
    if name.startswith("Expenses:CapitalLosses:") and len(parts) == 3:
        symbol = parts[2]
        return Account(
            name=name,
            account_type=AccountType.EXPENSE,
            description=f"Capital losses from {symbol}",
        )

    return None


def securities_account(symbol: str) -> Account:
    """Get the securities account for a symbol."""
    return get_account(f"Assets:Securities:{symbol}")


def dividend_account(symbol: str) -> Account:
    """Get the dividend income account for a symbol."""
    return get_account(f"Income:Dividends:{symbol}")


def capital_gains_account(symbol: str) -> Account:
    """Get the capital gains account for a symbol."""
    return get_account(f"Income:CapitalGains:{symbol}")


def capital_losses_account(symbol: str) -> Account:
    """Get the capital losses account for a symbol."""
    return get_account(f"Expenses:CapitalLosses:{symbol}")


def option_premiums_account(symbol: str) -> Account:
    """Get the option premium income account for a symbol."""
    return get_account(f"Income:OptionPremiums:{symbol}")


def list_all_accounts() -> list[Account]:
    """List all accounts (predefined + dynamically created)."""
    all_accounts = list(CHART_OF_ACCOUNTS.values()) + list(_dynamic_accounts.values())
    return sorted(all_accounts, key=lambda a: a.name)
