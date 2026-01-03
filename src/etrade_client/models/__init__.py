"""Pydantic models for E*Trade API responses."""

from etrade_client.models.accounts import (
    Account,
    AccountBalance,
    AccountListResponse,
    AccountStatus,
    AccountType,
    BalanceResponse,
    # Portfolio quote models
    CompleteQuote,
    FundamentalQuote,
    PerformanceQuote,
    QuickQuote,
    # Portfolio position models
    CompleteViewPosition,
    FundamentalViewPosition,
    PerformanceViewPosition,
    PortfolioPosition,
    PortfolioPositionBase,
    PortfolioResponse,
    PositionType,
    QuickViewPosition,
)
from etrade_client.models.alerts import (
    Alert,
    AlertCategory,
    AlertDetail,
    AlertDetailResponse,
    AlertListResponse,
    AlertStatus,
    DeleteAlertsResponse,
)
from etrade_client.models.auth import AccessToken, RequestToken
from etrade_client.models.market import (
    # Quote detail models by detail_flag
    AllQuoteDetail,
    AllQuoteDetails,  # Backwards compatibility alias
    ExtendedHourQuoteDetail,
    FundamentalQuoteDetail,
    IntradayQuoteDetail,
    OptionsQuoteDetail,
    Week52QuoteDetail,
    # Option chain models
    OptionChain,
    OptionExpireDate,
    OptionExpiryType,
    OptionType,
    # Quote wrapper and response
    Quote,
    QuoteResponse,
    QuoteStatus,
)
from etrade_client.models.orders import (
    CallPut,
    MarketSession,
    Order,
    OrderAction,
    OrderDetail,
    OrderListResponse,
    OrderPreview,
    OrderPreviewResponse,
    OrderStatus,
    OrderTerm,
    OrderType,
    PlaceOrderResponse,
    SecurityType,
)
from etrade_client.models.transactions import (
    # Response model
    Transaction,
    TransactionListResponse,
    # Enum
    TransactionType,
    # Base classes
    TransactionBase,
    Product,
    Brokerage,
    BrokerageWithProduct,
    BrokerageWithoutProduct,
    # Transaction subclasses
    BillPaymentTransaction,
    BoughtTransaction,
    CashInLieuTransaction,
    DividendTransaction,
    ExchangeDeliveredOutTransaction,
    ExchangeReceivedInTransaction,
    FeeTransaction,
    FundsReceivedTransaction,
    GenericTransaction,
    InterestIncomeTransaction,
    MarginInterestTransaction,
    PosTransaction,
    ServiceFeeTransaction,
    SoldTransaction,
    TransferTransaction,
)

__all__ = [
    # Auth
    "AccessToken",
    "RequestToken",
    # Account enums
    "AccountStatus",
    "AccountType",
    "PositionType",
    # Account models
    "Account",
    "AccountBalance",
    "AccountListResponse",
    "BalanceResponse",
    # Portfolio quote models
    "QuickQuote",
    "PerformanceQuote",
    "FundamentalQuote",
    "CompleteQuote",
    # Portfolio position models
    "PortfolioPositionBase",
    "QuickViewPosition",
    "PerformanceViewPosition",
    "FundamentalViewPosition",
    "CompleteViewPosition",
    "PortfolioPosition",
    "PortfolioResponse",
    # Alert enums
    "AlertCategory",
    "AlertStatus",
    # Alert models
    "Alert",
    "AlertDetail",
    "AlertDetailResponse",
    "AlertListResponse",
    "DeleteAlertsResponse",
    # Market enums
    "OptionExpiryType",
    "OptionType",
    "QuoteStatus",
    # Quote detail models by detail_flag
    "AllQuoteDetail",
    "AllQuoteDetails",  # Backwards compatibility alias
    "ExtendedHourQuoteDetail",
    "FundamentalQuoteDetail",
    "IntradayQuoteDetail",
    "OptionsQuoteDetail",
    "Week52QuoteDetail",
    # Market models
    "OptionChain",
    "OptionExpireDate",
    "Quote",
    "QuoteResponse",
    # Order enums
    "CallPut",
    "MarketSession",
    "OrderAction",
    "OrderStatus",
    "OrderTerm",
    "OrderType",
    "SecurityType",
    # Order models
    "Order",
    "OrderDetail",
    "OrderListResponse",
    "OrderPreview",
    "OrderPreviewResponse",
    "PlaceOrderResponse",
    # Transaction enum
    "TransactionType",
    # Transaction base classes
    "TransactionBase",
    "Product",
    "Brokerage",
    "BrokerageWithProduct",
    "BrokerageWithoutProduct",
    # Transaction subclasses
    "BillPaymentTransaction",
    "BoughtTransaction",
    "CashInLieuTransaction",
    "DividendTransaction",
    "ExchangeDeliveredOutTransaction",
    "ExchangeReceivedInTransaction",
    "FeeTransaction",
    "FundsReceivedTransaction",
    "GenericTransaction",
    "InterestIncomeTransaction",
    "MarginInterestTransaction",
    "PosTransaction",
    "ServiceFeeTransaction",
    "SoldTransaction",
    "TransferTransaction",
    # Transaction union type and response
    "Transaction",
    "TransactionListResponse",
]
