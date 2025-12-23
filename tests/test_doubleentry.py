"""Tests for double-entry bookkeeping functionality."""

from datetime import datetime
from decimal import Decimal

import pytest

from etrade_client.doubleentry import (
    Account,
    AccountType,
    JournalEntry,
    Posting,
    TransactionMapper,
    get_account,
    list_all_accounts,
)
from etrade_client.doubleentry.chart import (
    CASH_SETTLEMENT,
    EXPENSE_ADR_FEE,
    INCOME_INTEREST,
    dividend_account,
    securities_account,
)
from etrade_client.models.transactions import Transaction, TransactionBrokerage, TransactionProduct


class TestAccount:
    """Tests for Account model."""

    def test_creates_account(self) -> None:
        """Should create an account with name and type."""
        account = Account(
            name="Assets:Cash:Settlement",
            account_type=AccountType.ASSET,
        )
        assert account.name == "Assets:Cash:Settlement"
        assert account.account_type == AccountType.ASSET

    def test_short_name(self) -> None:
        """Should return the leaf name."""
        account = Account(name="Assets:Cash:Settlement", account_type=AccountType.ASSET)
        assert account.short_name == "Settlement"

    def test_parent_name(self) -> None:
        """Should return the parent account name."""
        account = Account(name="Assets:Cash:Settlement", account_type=AccountType.ASSET)
        assert account.parent_name == "Assets:Cash"

    def test_parent_name_top_level(self) -> None:
        """Should return None for top-level accounts."""
        account = Account(name="Assets", account_type=AccountType.ASSET)
        assert account.parent_name is None

    def test_depth(self) -> None:
        """Should calculate nesting depth."""
        assert Account(name="Assets", account_type=AccountType.ASSET).depth == 0
        assert Account(name="Assets:Cash", account_type=AccountType.ASSET).depth == 1
        assert Account(name="Assets:Cash:Settlement", account_type=AccountType.ASSET).depth == 2

    def test_is_child_of(self) -> None:
        """Should detect parent-child relationships."""
        parent = Account(name="Assets:Cash", account_type=AccountType.ASSET)
        child = Account(name="Assets:Cash:Settlement", account_type=AccountType.ASSET)
        sibling = Account(name="Assets:Securities", account_type=AccountType.ASSET)

        assert child.is_child_of(parent)
        assert not parent.is_child_of(child)
        assert not sibling.is_child_of(parent)

    def test_increases_with_debit(self) -> None:
        """Should identify debit-increase accounts."""
        assert Account(name="Assets", account_type=AccountType.ASSET).increases_with_debit()
        assert Account(name="Expenses", account_type=AccountType.EXPENSE).increases_with_debit()
        assert not Account(name="Income", account_type=AccountType.INCOME).increases_with_debit()

    def test_increases_with_credit(self) -> None:
        """Should identify credit-increase accounts."""
        assert Account(name="Income", account_type=AccountType.INCOME).increases_with_credit()
        assert Account(name="Liability", account_type=AccountType.LIABILITY).increases_with_credit()
        assert Account(name="Equity", account_type=AccountType.EQUITY).increases_with_credit()
        assert not Account(name="Assets", account_type=AccountType.ASSET).increases_with_credit()


class TestPosting:
    """Tests for Posting model."""

    def test_creates_debit_posting(self) -> None:
        """Should create a debit posting with positive amount."""
        account = Account(name="Assets:Cash", account_type=AccountType.ASSET)
        posting = Posting(account=account, amount=Decimal("100.00"))

        assert posting.is_debit
        assert not posting.is_credit
        assert posting.debit_amount == Decimal("100.00")
        assert posting.credit_amount is None

    def test_creates_credit_posting(self) -> None:
        """Should create a credit posting with negative amount."""
        account = Account(name="Income:Dividends", account_type=AccountType.INCOME)
        posting = Posting(account=account, amount=Decimal("-100.00"))

        assert posting.is_credit
        assert not posting.is_debit
        assert posting.credit_amount == Decimal("100.00")
        assert posting.debit_amount is None


class TestJournalEntry:
    """Tests for JournalEntry model."""

    def test_creates_balanced_entry(self) -> None:
        """Should create a balanced journal entry."""
        cash = Account(name="Assets:Cash", account_type=AccountType.ASSET)
        income = Account(name="Income:Dividends", account_type=AccountType.INCOME)

        entry = JournalEntry(
            date=datetime(2025, 1, 15).date(),
            description="Dividend received",
        )
        entry.add_debit(cash, Decimal("100.00"))
        entry.add_credit(income, Decimal("100.00"))

        assert entry.is_balanced
        assert entry.total_debits == Decimal("100.00")
        assert entry.total_credits == Decimal("100.00")
        assert entry.imbalance == Decimal(0)

    def test_detects_imbalanced_entry(self) -> None:
        """Should detect imbalanced entries."""
        cash = Account(name="Assets:Cash", account_type=AccountType.ASSET)

        entry = JournalEntry(
            date=datetime(2025, 1, 15).date(),
            description="Incomplete entry",
        )
        entry.add_debit(cash, Decimal("100.00"))

        assert not entry.is_balanced
        assert entry.imbalance == Decimal("100.00")

    def test_validate_raises_on_imbalance(self) -> None:
        """Should raise ValueError if not balanced."""
        cash = Account(name="Assets:Cash", account_type=AccountType.ASSET)

        entry = JournalEntry(
            date=datetime(2025, 1, 15).date(),
            description="Incomplete entry",
        )
        entry.add_debit(cash, Decimal("100.00"))

        with pytest.raises(ValueError, match="not balanced"):
            entry.validate()


class TestChartOfAccounts:
    """Tests for chart of accounts functionality."""

    def test_get_predefined_account(self) -> None:
        """Should retrieve predefined accounts."""
        account = get_account("Assets:Cash:Settlement")
        assert account.name == "Assets:Cash:Settlement"
        assert account.account_type == AccountType.ASSET

    def test_get_dynamic_securities_account(self) -> None:
        """Should create dynamic securities accounts."""
        account = get_account("Assets:Securities:AAPL")
        assert account.name == "Assets:Securities:AAPL"
        assert account.account_type == AccountType.ASSET
        assert "AAPL" in account.description

    def test_get_dynamic_dividend_account(self) -> None:
        """Should create dynamic dividend accounts."""
        account = get_account("Income:Dividends:MSTY")
        assert account.name == "Income:Dividends:MSTY"
        assert account.account_type == AccountType.INCOME

    def test_convenience_functions(self) -> None:
        """Should provide convenience functions for common accounts."""
        assert securities_account("AAPL").name == "Assets:Securities:AAPL"
        assert dividend_account("MSTY").name == "Income:Dividends:MSTY"

    def test_unknown_account_raises(self) -> None:
        """Should raise for unrecognized account patterns."""
        with pytest.raises(ValueError, match="Unknown account"):
            get_account("Bogus:Account:Name")

    def test_list_all_accounts(self) -> None:
        """Should list all predefined accounts."""
        accounts = list_all_accounts()
        assert len(accounts) > 0
        assert any(a.name == "Assets:Cash:Settlement" for a in accounts)


class TestTransactionMapper:
    """Tests for transaction to journal entry mapping."""

    def _make_transaction(
        self,
        amount: Decimal,
        tx_type: str,
        description: str,
        symbol: str | None = None,
    ) -> Transaction:
        """Create a test transaction."""
        product = None
        if symbol:
            product = TransactionProduct(symbol=symbol, security_type="EQ")

        return Transaction(
            transaction_id="TX123",
            account_id="ACCT123",
            transaction_date=datetime(2025, 1, 15),
            post_date=datetime(2025, 1, 15),
            amount=amount,
            description=description,
            transaction_type=tx_type,
            memo="",
            image_flag=False,
            store_id=0,
            brokerage=TransactionBrokerage(product=product),
        )

    def test_maps_dividend(self) -> None:
        """Should map dividend transaction correctly."""
        tx = self._make_transaction(
            amount=Decimal("125.50"),
            tx_type="Dividend",
            description="MSTY dividend",
            symbol="MSTY",
        )

        mapper = TransactionMapper()
        result = mapper.map_transaction(tx)

        assert result.success
        assert len(result.entries) == 1

        entry = result.entries[0]
        assert entry.is_balanced
        assert "Dividend" in entry.description
        assert "MSTY" in entry.description

        # Check postings
        debits = [p for p in entry.postings if p.is_debit]
        credits = [p for p in entry.postings if p.is_credit]

        assert len(debits) == 1
        assert len(credits) == 1
        assert debits[0].account.name == "Assets:Cash:Settlement"
        assert credits[0].account.name == "Income:Dividends:MSTY"

    def test_maps_buy(self) -> None:
        """Should map buy transaction correctly."""
        tx = self._make_transaction(
            amount=Decimal("-1500.00"),  # Cash outflow
            tx_type="Bought",
            description="Bought AAPL",
            symbol="AAPL",
        )

        mapper = TransactionMapper()
        result = mapper.map_transaction(tx)

        assert result.success
        entry = result.entries[0]
        assert entry.is_balanced

        debits = [p for p in entry.postings if p.is_debit]
        credits = [p for p in entry.postings if p.is_credit]

        assert debits[0].account.name == "Assets:Securities:AAPL"
        assert credits[0].account.name == "Assets:Cash:Settlement"

    def test_maps_reinvestment(self) -> None:
        """Should map DRIP as dividend income to securities."""
        tx = self._make_transaction(
            amount=Decimal("-50.00"),  # Shows as cash outflow but is reinvested
            tx_type="Reinvestment",
            description="Dividend reinvested MSTY",
            symbol="MSTY",
        )

        mapper = TransactionMapper()
        result = mapper.map_transaction(tx)

        assert result.success
        entry = result.entries[0]
        assert entry.is_balanced

        # Reinvestment: Securities debited, Dividend income credited
        debits = [p for p in entry.postings if p.is_debit]
        credits = [p for p in entry.postings if p.is_credit]

        assert debits[0].account.name == "Assets:Securities:MSTY"
        assert credits[0].account.name == "Income:Dividends:MSTY"

    def test_maps_fee(self) -> None:
        """Should map fee transaction correctly."""
        tx = self._make_transaction(
            amount=Decimal("-2.50"),
            tx_type="ADR Fee",
            description="ADR custody fee",
            symbol="TM",
        )

        mapper = TransactionMapper()
        result = mapper.map_transaction(tx)

        assert result.success
        entry = result.entries[0]
        assert entry.is_balanced

        debits = [p for p in entry.postings if p.is_debit]
        assert debits[0].account.name == "Expenses:Fees:ADR"

    def test_maps_interest(self) -> None:
        """Should map interest income correctly."""
        tx = self._make_transaction(
            amount=Decimal("5.25"),
            tx_type="Interest",
            description="Credit interest",
        )

        mapper = TransactionMapper()
        result = mapper.map_transaction(tx)

        assert result.success
        entry = result.entries[0]
        assert entry.is_balanced

        credits = [p for p in entry.postings if p.is_credit]
        assert credits[0].account.name == "Income:Interest"

    def test_maps_deposit(self) -> None:
        """Should map deposit correctly."""
        tx = self._make_transaction(
            amount=Decimal("5000.00"),
            tx_type="ACH Deposit",
            description="Transfer from bank",
        )

        mapper = TransactionMapper()
        result = mapper.map_transaction(tx)

        assert result.success
        entry = result.entries[0]
        assert entry.is_balanced

        credits = [p for p in entry.postings if p.is_credit]
        assert credits[0].account.name == "Equity:Contributions"

    def test_maps_withdrawal(self) -> None:
        """Should map withdrawal correctly."""
        tx = self._make_transaction(
            amount=Decimal("-1000.00"),
            tx_type="ACH Withdrawal",
            description="Transfer to bank",
        )

        mapper = TransactionMapper()
        result = mapper.map_transaction(tx)

        assert result.success
        entry = result.entries[0]
        assert entry.is_balanced

        debits = [p for p in entry.postings if p.is_debit]
        assert debits[0].account.name == "Equity:Distributions"

    def test_maps_unknown_with_warning(self) -> None:
        """Should map unknown types and generate warning."""
        tx = self._make_transaction(
            amount=Decimal("100.00"),
            tx_type="SomeNewType",
            description="Unknown transaction",
        )

        mapper = TransactionMapper()
        result = mapper.map_transaction(tx)

        assert result.success
        assert len(result.warnings) > 0
        assert "Unknown" in result.warnings[0]

    def test_maps_multiple_transactions(self) -> None:
        """Should map multiple transactions."""
        transactions = [
            self._make_transaction(Decimal("100"), "Dividend", "Div", "AAPL"),
            self._make_transaction(Decimal("-50"), "Fee", "Fee", None),
        ]

        mapper = TransactionMapper()
        entries, warnings = mapper.map_transactions(transactions)

        assert len(entries) == 2
        assert all(e.is_balanced for e in entries)
