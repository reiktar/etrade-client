"""API parameter types.

This module defines Literal type aliases for API parameters that have
constrained values. These are used for type checking in the API layer
and CLI commands to ensure only valid values are passed to E*Trade.

Note: These are separate from the StrEnum types in models/ which are
used for parsing API responses. The API types here validate input
parameters before sending to the API.
"""

from typing import Literal

# =============================================================================
# Common Types
# =============================================================================

SortOrder = Literal["ASC", "DESC"]
"""Sort order for paginated results."""

MarketSession = Literal["REGULAR", "EXTENDED"]
"""Market session for orders and quotes."""

# =============================================================================
# Account Types
# =============================================================================

PortfolioView = Literal["QUICK", "PERFORMANCE", "FUNDAMENTAL", "OPTIONSWATCH", "COMPLETE"]
"""Portfolio position view type."""

# =============================================================================
# Order Types
# =============================================================================

OrderStatus = Literal[
    "OPEN",
    "EXECUTED",
    "CANCELLED",
    "INDIVIDUAL_FILLS",
    "CANCEL_REQUESTED",
    "EXPIRED",
    "REJECTED",
]
"""Order status filter values."""

SecurityType = Literal["EQ", "OPTN", "MF", "MMF"]
"""Security type filter values."""

TransactionType = Literal["BUY", "SELL", "SHORT", "BUY_TO_COVER"]
"""Transaction type filter values."""

OrderAction = Literal["BUY", "SELL", "BUY_TO_COVER", "SELL_SHORT"]
"""Order action for equity orders."""

PriceType = Literal["MARKET", "LIMIT", "STOP", "STOP_LIMIT"]
"""Order price type."""

OrderTerm = Literal["GOOD_FOR_DAY", "GOOD_UNTIL_CANCEL", "IMMEDIATE_OR_CANCEL", "FILL_OR_KILL"]
"""Order duration/time-in-force."""

# =============================================================================
# Market Data Types
# =============================================================================

QuoteDetailFlag = Literal["ALL", "FUNDAMENTAL", "INTRADAY", "OPTIONS", "WEEK_52", "MF_DETAIL"]
"""Quote detail level."""

OptionCategory = Literal["STANDARD", "ALL", "MINI"]
"""Option category filter."""

ChainType = Literal["CALL", "PUT", "CALLPUT"]
"""Option chain type (calls, puts, or both)."""

OptionPriceType = Literal["ATNM", "ALL"]
"""Option strike price filter."""

ExpiryType = Literal["ALL", "MONTHLY", "WEEKLY"]
"""Option expiration type filter."""
