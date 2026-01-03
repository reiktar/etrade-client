"""Transaction-related models."""

from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field


class TransactionProduct(BaseModel):
    """Product in a transaction."""

    symbol: str | None = Field(default=None)
    security_type: str | None = Field(default=None, alias="securityType")
    security_sub_type: str | None = Field(default=None, alias="securitySubType")
    product_id: dict[str, Any] | None = Field(default=None, alias="productId")

    model_config = {"populate_by_name": True}


class TransactionBrokerage(BaseModel):
    """Brokerage details of a transaction."""

    product: TransactionProduct | None = Field(default=None, alias="Product")
    quantity: Decimal | None = Field(default=None)
    price: Decimal | None = Field(default=None)
    settlement_currency: str | None = Field(default=None, alias="settlementCurrency")
    payment_currency: str | None = Field(default=None, alias="paymentCurrency")
    fee: Decimal | None = Field(default=None)
    display_symbol: str | None = Field(default=None, alias="displaySymbol")
    settlement_date: datetime | None = Field(default=None, alias="settlementDate")
    order_no: str | None = Field(default=None, alias="orderNo")
    check_no: str | None = Field(default=None, alias="checkNo")

    model_config = {"populate_by_name": True}


class Transaction(BaseModel):
    """A single transaction."""

    # Always present fields
    transaction_id: str = Field(alias="transactionId")
    account_id: str = Field(alias="accountId")
    transaction_date: datetime = Field(alias="transactionDate")
    post_date: datetime = Field(alias="postDate")
    amount: Decimal
    description: str = Field()
    transaction_type: str = Field(alias="transactionType")
    memo: str = Field()
    image_flag: bool = Field(alias="imageFlag")
    store_id: int = Field(alias="storeId")
    brokerage: TransactionBrokerage = Field(alias="Brokerage")

    # Sometimes present
    description2: str | None = Field(default=None)
    details_uri: str | None = Field(default=None, alias="detailsURI")
    inst_type: str | None = Field(default=None, alias="instType")

    # Context-specific (may not always be present)
    category: dict[str, Any] | None = Field(default=None, alias="Category")

    model_config = {"populate_by_name": True}

    @property
    def symbol(self) -> str | None:
        """Get the symbol from the transaction."""
        if self.brokerage:
            sym = None
            if self.brokerage.product:
                sym = self.brokerage.product.symbol
            if not sym:
                sym = self.brokerage.display_symbol
            # Return None for empty/whitespace-only symbols
            if sym and sym.strip():
                return sym.strip()
        return None


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
        tx_response = data.get("TransactionListResponse", {})
        tx_list = tx_response.get("Transaction", [])

        if isinstance(tx_list, dict):
            tx_list = [tx_list]

        return cls(
            transactions=[Transaction.model_validate(t) for t in tx_list],
            marker=tx_response.get("marker"),
            next_page=tx_response.get("next"),
            more_transactions=tx_response.get("moreTransactions", False),
        )
