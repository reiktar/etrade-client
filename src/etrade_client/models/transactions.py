"""Transaction-related models.

This module implements a discriminated union pattern for E*Trade transactions.
Each transaction type has its own class with type-specific fields, reducing
the number of optional fields and enabling type-safe access.

Transaction types are discriminated by the `transaction_type` field which
maps directly to the API's `transactionType` value.
"""

from datetime import UTC, datetime
from decimal import Decimal  # noqa: TC003 - needed at runtime for Pydantic
from enum import StrEnum
from typing import Annotated, Any, Literal

from pydantic import BaseModel, Discriminator, Field, Tag


class TransactionType(StrEnum):
    """Known transaction type values from E*Trade API.

    Values are exact strings from the API (no normalization).
    """

    BILL_PAYMENT = "Bill Payment"
    BOUGHT = "Bought"
    CASH_IN_LIEU = "Cash in Lieu"
    DIVIDEND = "Dividend"
    EXCHANGE_DELIVERED_OUT = "Exchange Delivered Out"
    EXCHANGE_RECEIVED_IN = "Exchange Received In"
    FEE = "Fee"
    FUNDS_RECEIVED = "Funds Received"
    INTEREST_INCOME = "Interest Income"
    MARGIN_INTEREST = "Margin Interest"
    POS = "POS"
    SERVICE_FEE = "Service Fee"
    SOLD = "Sold"
    TRANSFER = "Transfer"


class Product(BaseModel):
    """Product information within a brokerage transaction.

    When present, both securityType and symbol are always defined.
    """

    security_type: str = Field(alias="securityType")
    symbol: str

    model_config = {"populate_by_name": True}


class BrokerageWithProduct(BaseModel):
    """Brokerage details for transactions with product info.

    Used by: Bought, Cash in Lieu, Dividend, Exchange Received In, Interest Income
    """

    display_symbol: str = Field(alias="displaySymbol")
    fee: int
    payment_currency: str = Field(alias="paymentCurrency")
    price: Decimal
    quantity: Decimal
    settlement_currency: str = Field(alias="settlementCurrency")
    settlement_date: int = Field(alias="settlementDate")
    product: Product = Field(alias="Product")

    model_config = {"populate_by_name": True}

    @property
    def settlement_datetime(self) -> datetime:
        """Convert settlement_date epoch millis to datetime."""
        return datetime.fromtimestamp(self.settlement_date / 1000, tz=UTC)


class BrokerageWithoutProduct(BaseModel):
    """Brokerage details for transactions without product info.

    Used by: Bill Payment, Exchange Delivered Out, Fee, Funds Received,
             Margin Interest, POS, Service Fee, Sold, Transfer
    """

    fee: int
    payment_currency: str = Field(alias="paymentCurrency")
    price: Decimal
    quantity: Decimal
    settlement_currency: str = Field(alias="settlementCurrency")
    settlement_date: int = Field(alias="settlementDate")
    display_symbol: str | None = Field(default=None, alias="displaySymbol")

    model_config = {"populate_by_name": True}

    @property
    def settlement_datetime(self) -> datetime:
        """Convert settlement_date epoch millis to datetime."""
        return datetime.fromtimestamp(self.settlement_date / 1000, tz=UTC)


# Type alias for any brokerage type
Brokerage = BrokerageWithProduct | BrokerageWithoutProduct


class TransactionBase(BaseModel):
    """Base class for all transaction types.

    Note: brokerage field is defined in subclasses with the
    appropriate type (BrokerageWithProduct or BrokerageWithoutProduct).
    """

    account_id: str = Field(alias="accountId")
    amount: Decimal
    description: str
    image_flag: bool = Field(alias="imageFlag")
    memo: str
    post_date: int = Field(alias="postDate")
    store_id: int = Field(alias="storeId")
    transaction_date: int = Field(alias="transactionDate")
    transaction_id: str = Field(alias="transactionId")
    transaction_type: str = Field(alias="transactionType")

    model_config = {"populate_by_name": True}

    @property
    def is_pending(self) -> bool:
        """Check if transaction is pending (post_date is epoch zero)."""
        return self.post_date == 0

    @property
    def transaction_datetime(self) -> datetime:
        """Convert transaction_date epoch millis to datetime."""
        return datetime.fromtimestamp(self.transaction_date / 1000, tz=UTC)

    @property
    def post_datetime(self) -> datetime | None:
        """Convert post_date epoch millis to datetime, or None if pending."""
        if self.is_pending:
            return None
        return datetime.fromtimestamp(self.post_date / 1000, tz=UTC)

    @property
    def symbol(self) -> str | None:
        """Get the symbol from the transaction.

        Returns the symbol from brokerage.product if available,
        otherwise falls back to brokerage.display_symbol.
        """
        brokerage = getattr(self, "brokerage", None)
        if brokerage is None:
            return None

        # Check product first (only BrokerageWithProduct has it)
        if (
            isinstance(brokerage, BrokerageWithProduct)
            and brokerage.product
            and brokerage.product.symbol
        ):
            sym = brokerage.product.symbol.strip()
            if sym:
                return sym

        # Fall back to display_symbol
        if brokerage.display_symbol:
            sym = brokerage.display_symbol.strip()
            if sym:
                return sym

        return None


# =============================================================================
# Transaction Subclasses - Types WITH Product
# =============================================================================


class BoughtTransaction(TransactionBase):
    """Transaction type: Bought"""

    transaction_type: Literal["Bought"] = Field(
        default="Bought", alias="transactionType"
    )
    brokerage: BrokerageWithProduct = Field(alias="Brokerage")

    details_uri: str = Field(alias="detailsURI")
    inst_type: str = Field(alias="instType")


class CashInLieuTransaction(TransactionBase):
    """Transaction type: Cash in Lieu"""

    transaction_type: Literal["Cash in Lieu"] = Field(
        default="Cash in Lieu", alias="transactionType"
    )
    brokerage: BrokerageWithProduct = Field(alias="Brokerage")

    details_uri: str = Field(alias="detailsURI")
    inst_type: str = Field(alias="instType")


class DividendTransaction(TransactionBase):
    """Transaction type: Dividend"""

    transaction_type: Literal["Dividend"] = Field(
        default="Dividend", alias="transactionType"
    )
    brokerage: BrokerageWithProduct = Field(alias="Brokerage")

    details_uri: str = Field(alias="detailsURI")
    inst_type: str = Field(alias="instType")


class ExchangeReceivedInTransaction(TransactionBase):
    """Transaction type: Exchange Received In"""

    transaction_type: Literal["Exchange Received In"] = Field(
        default="Exchange Received In", alias="transactionType"
    )
    brokerage: BrokerageWithProduct = Field(alias="Brokerage")

    details_uri: str = Field(alias="detailsURI")
    inst_type: str = Field(alias="instType")


class InterestIncomeTransaction(TransactionBase):
    """Transaction type: Interest Income"""

    transaction_type: Literal["Interest Income"] = Field(
        default="Interest Income", alias="transactionType"
    )
    brokerage: BrokerageWithProduct = Field(alias="Brokerage")

    details_uri: str = Field(alias="detailsURI")
    inst_type: str = Field(alias="instType")


# =============================================================================
# Transaction Subclasses - Types WITHOUT Product
# =============================================================================


class BillPaymentTransaction(TransactionBase):
    """Transaction type: Bill Payment"""

    transaction_type: Literal["Bill Payment"] = Field(
        default="Bill Payment", alias="transactionType"
    )
    brokerage: BrokerageWithoutProduct = Field(alias="Brokerage")


class ExchangeDeliveredOutTransaction(TransactionBase):
    """Transaction type: Exchange Delivered Out"""

    transaction_type: Literal["Exchange Delivered Out"] = Field(
        default="Exchange Delivered Out", alias="transactionType"
    )
    brokerage: BrokerageWithoutProduct = Field(alias="Brokerage")

    details_uri: str = Field(alias="detailsURI")
    inst_type: str = Field(alias="instType")


class FeeTransaction(TransactionBase):
    """Transaction type: Fee"""

    transaction_type: Literal["Fee"] = Field(default="Fee", alias="transactionType")
    brokerage: BrokerageWithoutProduct = Field(alias="Brokerage")

    description2: str


class FundsReceivedTransaction(TransactionBase):
    """Transaction type: Funds Received"""

    transaction_type: Literal["Funds Received"] = Field(
        default="Funds Received", alias="transactionType"
    )
    brokerage: BrokerageWithoutProduct = Field(alias="Brokerage")

    details_uri: str = Field(alias="detailsURI")
    inst_type: str = Field(alias="instType")


class MarginInterestTransaction(TransactionBase):
    """Transaction type: Margin Interest"""

    transaction_type: Literal["Margin Interest"] = Field(
        default="Margin Interest", alias="transactionType"
    )
    brokerage: BrokerageWithoutProduct = Field(alias="Brokerage")

    details_uri: str = Field(alias="detailsURI")
    inst_type: str = Field(alias="instType")


class PosTransaction(TransactionBase):
    """Transaction type: POS"""

    transaction_type: Literal["POS"] = Field(default="POS", alias="transactionType")
    brokerage: BrokerageWithoutProduct = Field(alias="Brokerage")

    description2: str


class ServiceFeeTransaction(TransactionBase):
    """Transaction type: Service Fee"""

    transaction_type: Literal["Service Fee"] = Field(
        default="Service Fee", alias="transactionType"
    )
    brokerage: BrokerageWithoutProduct = Field(alias="Brokerage")

    details_uri: str = Field(alias="detailsURI")
    inst_type: str = Field(alias="instType")


class SoldTransaction(TransactionBase):
    """Transaction type: Sold"""

    transaction_type: Literal["Sold"] = Field(default="Sold", alias="transactionType")
    brokerage: BrokerageWithoutProduct = Field(alias="Brokerage")

    details_uri: str = Field(alias="detailsURI")
    inst_type: str = Field(alias="instType")


class TransferTransaction(TransactionBase):
    """Transaction type: Transfer"""

    transaction_type: Literal["Transfer"] = Field(
        default="Transfer", alias="transactionType"
    )
    brokerage: BrokerageWithoutProduct = Field(alias="Brokerage")

    details_uri: str | None = Field(default=None, alias="detailsURI")
    inst_type: str | None = Field(default=None, alias="instType")


# =============================================================================
# Generic Fallback for Unknown Types
# =============================================================================


class GenericTransaction(TransactionBase):
    """Fallback for unknown transaction types.

    All type-specific fields are optional to handle any transaction type
    that hasn't been explicitly modeled.
    """

    brokerage: BrokerageWithProduct | BrokerageWithoutProduct = Field(alias="Brokerage")

    # Optional fields that may be present
    details_uri: str | None = Field(default=None, alias="detailsURI")
    inst_type: str | None = Field(default=None, alias="instType")
    description2: str | None = None


# =============================================================================
# Discriminated Union
# =============================================================================


# Known transaction type values that map to specific model classes
_KNOWN_TRANSACTION_TYPES = frozenset({
    "Bill Payment",
    "Bought",
    "Cash in Lieu",
    "Dividend",
    "Exchange Delivered Out",
    "Exchange Received In",
    "Fee",
    "Funds Received",
    "Interest Income",
    "Margin Interest",
    "POS",
    "Service Fee",
    "Sold",
    "Transfer",
})


def _get_transaction_discriminator(v: Any) -> str:
    """Get discriminator value from transaction data.

    Returns the transaction type if known, otherwise '__generic__' for fallback.
    """
    if isinstance(v, dict):
        tx_type = v.get("transactionType", "__generic__")
    else:
        tx_type = getattr(v, "transaction_type", "__generic__")

    return tx_type if tx_type in _KNOWN_TRANSACTION_TYPES else "__generic__"


# Discriminated union of all transaction types
Transaction = Annotated[
    Annotated[BillPaymentTransaction, Tag("Bill Payment")] | Annotated[BoughtTransaction, Tag("Bought")] | Annotated[CashInLieuTransaction, Tag("Cash in Lieu")] | Annotated[DividendTransaction, Tag("Dividend")] | Annotated[ExchangeDeliveredOutTransaction, Tag("Exchange Delivered Out")] | Annotated[ExchangeReceivedInTransaction, Tag("Exchange Received In")] | Annotated[FeeTransaction, Tag("Fee")] | Annotated[FundsReceivedTransaction, Tag("Funds Received")] | Annotated[InterestIncomeTransaction, Tag("Interest Income")] | Annotated[MarginInterestTransaction, Tag("Margin Interest")] | Annotated[PosTransaction, Tag("POS")] | Annotated[ServiceFeeTransaction, Tag("Service Fee")] | Annotated[SoldTransaction, Tag("Sold")] | Annotated[TransferTransaction, Tag("Transfer")] | Annotated[GenericTransaction, Tag("__generic__")],
    Discriminator(_get_transaction_discriminator),
]


# =============================================================================
# Response Models
# =============================================================================


class TransactionListResponse(BaseModel):
    """Response from list transactions endpoint."""

    transactions: list[Transaction] = Field(default_factory=list)
    marker: str | None = Field(default=None)
    next_page: str | None = Field(default=None)
    more_transactions: bool = Field(default=False)

    @property
    def has_more(self) -> bool:
        """Check if there are more pages to fetch."""
        return bool(self.next_page)

    @classmethod
    def from_api_response(cls, data: dict[str, Any]) -> TransactionListResponse:
        """Parse from raw API response."""
        from pydantic import TypeAdapter

        tx_response = data.get("TransactionListResponse", {})
        tx_list = tx_response.get("Transaction", [])

        if isinstance(tx_list, dict):
            tx_list = [tx_list]

        # Use TypeAdapter to parse the discriminated union
        adapter = TypeAdapter(Transaction)
        transactions = [adapter.validate_python(t) for t in tx_list]

        return cls(
            transactions=transactions,
            marker=tx_response.get("marker"),
            next_page=tx_response.get("next"),
            more_transactions=tx_response.get("moreTransactions", False),
        )
