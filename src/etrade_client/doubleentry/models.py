"""Double-entry bookkeeping models."""

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from enum import StrEnum


class AccountType(StrEnum):
    """Classification of accounts in double-entry bookkeeping.

    Debit increases: ASSET, EXPENSE
    Credit increases: LIABILITY, EQUITY, INCOME
    """

    ASSET = "Asset"
    LIABILITY = "Liability"
    EQUITY = "Equity"
    INCOME = "Income"
    EXPENSE = "Expense"


@dataclass(frozen=True)
class Account:
    """A ledger account in the chart of accounts.

    Attributes:
        name: Full hierarchical account name (e.g., "Assets:Cash:Settlement")
        account_type: The type classification (Asset, Liability, etc.)
        description: Optional human-readable description

    The account name uses colon-separated hierarchy:
        Assets:Securities:AAPL
        Income:Dividends:MSTY
        Expenses:Fees:Commission
    """

    name: str
    account_type: AccountType
    description: str = ""

    @property
    def short_name(self) -> str:
        """Return just the leaf name (last component)."""
        return self.name.split(":")[-1]

    @property
    def parent_name(self) -> str | None:
        """Return the parent account name, or None if top-level."""
        parts = self.name.split(":")
        if len(parts) <= 1:
            return None
        return ":".join(parts[:-1])

    @property
    def depth(self) -> int:
        """Return the nesting depth (0 for top-level)."""
        return self.name.count(":")

    def is_child_of(self, other: "Account") -> bool:
        """Check if this account is a child of another."""
        return self.name.startswith(other.name + ":")

    def increases_with_debit(self) -> bool:
        """Return True if debits increase this account's balance."""
        return self.account_type in (AccountType.ASSET, AccountType.EXPENSE)

    def increases_with_credit(self) -> bool:
        """Return True if credits increase this account's balance."""
        return self.account_type in (AccountType.LIABILITY, AccountType.EQUITY, AccountType.INCOME)


@dataclass
class Posting:
    """A single line in a journal entry.

    A posting records a debit or credit to a specific account.
    By convention:
        - Positive amount = Debit
        - Negative amount = Credit

    Attributes:
        account: The account being affected
        amount: The amount (positive=debit, negative=credit)
        memo: Optional note for this specific posting
    """

    account: Account
    amount: Decimal
    memo: str = ""

    @property
    def is_debit(self) -> bool:
        """Return True if this is a debit posting."""
        return self.amount > 0

    @property
    def is_credit(self) -> bool:
        """Return True if this is a credit posting."""
        return self.amount < 0

    @property
    def debit_amount(self) -> Decimal | None:
        """Return the debit amount, or None if this is a credit."""
        return self.amount if self.amount > 0 else None

    @property
    def credit_amount(self) -> Decimal | None:
        """Return the credit amount (as positive), or None if this is a debit."""
        return -self.amount if self.amount < 0 else None


@dataclass
class JournalEntry:
    """A complete journal entry with balanced debits and credits.

    A journal entry records a single transaction as multiple postings
    that must sum to zero (debits = credits).

    Attributes:
        date: The transaction date
        description: A description of the transaction
        postings: List of debit/credit postings (must balance)
        reference: Optional reference ID (e.g., E*Trade transaction ID)
    """

    date: date
    description: str
    postings: list[Posting] = field(default_factory=list)
    reference: str = ""

    def add_debit(self, account: Account, amount: Decimal, memo: str = "") -> None:
        """Add a debit posting (positive amount)."""
        self.postings.append(Posting(account=account, amount=abs(amount), memo=memo))

    def add_credit(self, account: Account, amount: Decimal, memo: str = "") -> None:
        """Add a credit posting (negative amount)."""
        self.postings.append(Posting(account=account, amount=-abs(amount), memo=memo))

    @property
    def total_debits(self) -> Decimal:
        """Sum of all debit amounts."""
        return sum((p.amount for p in self.postings if p.amount > 0), Decimal(0))

    @property
    def total_credits(self) -> Decimal:
        """Sum of all credit amounts (as positive)."""
        return sum((-p.amount for p in self.postings if p.amount < 0), Decimal(0))

    @property
    def is_balanced(self) -> bool:
        """Check if debits equal credits."""
        return self.total_debits == self.total_credits

    @property
    def imbalance(self) -> Decimal:
        """Return the imbalance amount (should be zero)."""
        return sum((p.amount for p in self.postings), Decimal(0))

    def validate(self) -> None:
        """Raise ValueError if the entry is not balanced."""
        if not self.is_balanced:
            raise ValueError(
                f"Journal entry is not balanced: "
                f"debits={self.total_debits}, credits={self.total_credits}, "
                f"imbalance={self.imbalance}"
            )
