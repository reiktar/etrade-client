"""Transaction-related models."""

from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from datetime import datetime
    from decimal import Decimal


class TransactionProduct(BaseModel):
    """Product in a transaction."""

    symbol: str | None = Field(default=None)
    security_type: str | None = Field(default=None, alias="securityType")
    security_sub_type: str | None = Field(default=None, alias="securitySubType")
    product_id: dict | None = Field(default=None, alias="productId")

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

    model_config = {"populate_by_name": True}


class Transaction(BaseModel):
    """A single transaction."""

    transaction_id: str = Field(alias="transactionId")
    account_id: str | None = Field(default=None, alias="accountId")
    transaction_date: datetime = Field(alias="transactionDate")
    post_date: datetime | None = Field(default=None, alias="postDate")
    amount: Decimal
    description: str | None = Field(default=None)
    transaction_type: str | None = Field(default=None, alias="transactionType")
    memo: str | None = Field(default=None)
    category: dict | None = Field(default=None, alias="Category")
    brokerage: TransactionBrokerage | None = Field(default=None, alias="Brokerage")

    model_config = {"populate_by_name": True}

    @property
    def symbol(self) -> str | None:
        """Get the symbol from the transaction."""
        if self.brokerage and self.brokerage.product:
            return self.brokerage.product.symbol or self.brokerage.display_symbol
        return None


class TransactionListResponse(BaseModel):
    """Response from list transactions endpoint."""

    transactions: list[Transaction] = Field(default_factory=list)
    marker: str | None = Field(default=None)
    more_transactions: bool = Field(default=False)

    @classmethod
    def from_api_response(cls, data: dict) -> TransactionListResponse:
        """Parse from raw API response."""
        tx_response = data.get("TransactionListResponse", {})
        tx_list = tx_response.get("Transaction", [])

        if isinstance(tx_list, dict):
            tx_list = [tx_list]

        return cls(
            transactions=[Transaction.model_validate(t) for t in tx_list],
            marker=tx_response.get("marker"),
            more_transactions=tx_response.get("moreTransactions", False),
        )
