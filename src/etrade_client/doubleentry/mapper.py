"""Map E*Trade transactions to double-entry journal entries."""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from etrade_client.doubleentry.chart import (
    CASH_SETTLEMENT,
    EQUITY_CONTRIBUTIONS,
    EQUITY_DISTRIBUTIONS,
    EXPENSE_ADR_FEE,
    EXPENSE_COMMISSION,
    EXPENSE_MARGIN_INTEREST,
    EXPENSE_OTHER,
    EXPENSE_OTHER_FEE,
    INCOME_INTEREST,
    INCOME_OTHER,
    capital_gains_account,
    capital_losses_account,
    dividend_account,
    get_account,
    option_premiums_account,
    securities_account,
)
from etrade_client.doubleentry.models import Account, JournalEntry
from etrade_client.models.transactions import Transaction


@dataclass
class MappingResult:
    """Result of mapping a transaction to journal entries.

    A single E*Trade transaction may produce multiple journal entries
    (e.g., a trade with fees might produce separate entries).
    """

    entries: list[JournalEntry]
    warnings: list[str]

    @property
    def success(self) -> bool:
        """Return True if at least one entry was created."""
        return len(self.entries) > 0


class TransactionMapper:
    """Maps E*Trade transactions to double-entry journal entries.

    This class translates E*Trade's transaction types into proper
    double-entry bookkeeping journal entries.
    """

    # Transaction types that represent income credits to cash
    DIVIDEND_TYPES = {
        "dividend",
        "qualified dividend",
        "non-qualified dividend",
        "ordinary dividend",
        "cash dividend",
        "foreign tax withheld",  # Handled specially
    }

    # Transaction types that represent buying securities
    BUY_TYPES = {
        "bought",
        "buy",
        "purchased",
        "reinvestment",  # DRIP
        "dividend reinvestment",
    }

    # Transaction types that represent selling securities
    SELL_TYPES = {
        "sold",
        "sell",
        "sale",
    }

    # Transaction types that represent deposits
    DEPOSIT_TYPES = {
        "ach deposit",
        "deposit",
        "wire deposit",
        "transfer in",
        "received from",
        "contribution",
        "internal transfer",
    }

    # Transaction types that represent withdrawals
    WITHDRAWAL_TYPES = {
        "ach withdrawal",
        "withdrawal",
        "wire withdrawal",
        "transfer out",
        "sent to",
        "distribution",
    }

    # Transaction types that represent fees
    FEE_TYPES = {
        "fee",
        "adr fee",
        "foreign tax",
        "sec fee",
        "taf fee",
        "commission",
        "service charge",
    }

    # Transaction types for interest
    INTEREST_TYPES = {
        "interest",
        "credit interest",
        "margin interest",  # Handled specially as expense
    }

    # Option-related transaction types
    OPTION_TYPES = {
        "option assignment",
        "option exercise",
        "option expiration",
        "bought to open",
        "sold to open",
        "bought to close",
        "sold to close",
    }

    def __init__(self) -> None:
        """Initialize the mapper."""
        self._warnings: list[str] = []

    def map_transaction(self, tx: Transaction) -> MappingResult:
        """Map an E*Trade transaction to journal entries.

        Args:
            tx: The E*Trade transaction to map

        Returns:
            MappingResult with journal entries and any warnings
        """
        self._warnings = []
        entries: list[JournalEntry] = []

        tx_type = tx.transaction_type.lower().strip()
        tx_desc_lower = tx.description.lower()

        # Determine the transaction category and create appropriate entry
        # Check BUY_TYPES first because "reinvestment" contains "dividend" in description
        # but should be treated as a buy, not a dividend
        if self._matches_type(tx_type, tx_desc_lower, self.BUY_TYPES):
            entry = self._map_buy(tx)
            if entry:
                entries.append(entry)

        elif self._matches_type(tx_type, tx_desc_lower, self.DIVIDEND_TYPES):
            entry = self._map_dividend(tx)
            if entry:
                entries.append(entry)

        elif self._matches_type(tx_type, tx_desc_lower, self.SELL_TYPES):
            entry = self._map_sell(tx)
            if entry:
                entries.append(entry)

        elif self._matches_type(tx_type, tx_desc_lower, self.DEPOSIT_TYPES):
            entry = self._map_deposit(tx)
            if entry:
                entries.append(entry)

        elif self._matches_type(tx_type, tx_desc_lower, self.WITHDRAWAL_TYPES):
            entry = self._map_withdrawal(tx)
            if entry:
                entries.append(entry)

        elif self._matches_type(tx_type, tx_desc_lower, self.FEE_TYPES):
            entry = self._map_fee(tx)
            if entry:
                entries.append(entry)

        elif self._matches_type(tx_type, tx_desc_lower, self.INTEREST_TYPES):
            entry = self._map_interest(tx)
            if entry:
                entries.append(entry)

        elif self._matches_type(tx_type, tx_desc_lower, self.OPTION_TYPES):
            entry = self._map_option(tx)
            if entry:
                entries.append(entry)

        else:
            # Unknown transaction type - create a generic entry
            entry = self._map_unknown(tx)
            if entry:
                entries.append(entry)
                self._warnings.append(
                    f"Unknown transaction type '{tx.transaction_type}': {tx.description}"
                )

        return MappingResult(entries=entries, warnings=self._warnings)

    def _matches_type(
        self, tx_type: str, description: str, type_set: set[str]
    ) -> bool:
        """Check if a transaction matches any of the given types."""
        # Check exact match first
        if tx_type in type_set:
            return True

        # Check if type starts with any of the types
        for t in type_set:
            if tx_type.startswith(t):
                return True
            # Also check description for keywords
            if t in description:
                return True

        return False

    def _map_dividend(self, tx: Transaction) -> JournalEntry | None:
        """Map a dividend transaction.

        Dividend:
            Debit:  Assets:Cash:Settlement        $X.XX
            Credit: Income:Dividends:{SYMBOL}           $X.XX
        """
        symbol = tx.symbol or "Unknown"
        amount = abs(tx.amount)

        entry = JournalEntry(
            date=tx.transaction_date.date() if hasattr(tx.transaction_date, 'date') else tx.transaction_date,
            description=f"Dividend - {symbol}",
            reference=tx.transaction_id,
        )

        # Cash increases (debit)
        entry.add_debit(CASH_SETTLEMENT, amount)

        # Income (credit)
        income_account = dividend_account(symbol)
        entry.add_credit(income_account, amount)

        return entry

    def _map_buy(self, tx: Transaction) -> JournalEntry | None:
        """Map a buy/purchase transaction.

        For DRIP (reinvestment):
            Debit:  Assets:Securities:{SYMBOL}    $X.XX
            Credit: Income:Dividends:{SYMBOL}           $X.XX

        For regular purchase:
            Debit:  Assets:Securities:{SYMBOL}    $X.XX
            Credit: Assets:Cash:Settlement              $X.XX
        """
        symbol = tx.symbol or "Unknown"
        amount = abs(tx.amount)
        tx_type_lower = tx.transaction_type.lower()
        desc_lower = tx.description.lower()

        is_reinvestment = "reinvest" in tx_type_lower or "reinvest" in desc_lower

        entry = JournalEntry(
            date=tx.transaction_date.date() if hasattr(tx.transaction_date, 'date') else tx.transaction_date,
            description=f"{'Reinvestment' if is_reinvestment else 'Bought'} - {symbol}",
            reference=tx.transaction_id,
        )

        # Add quantity info to memo if available
        qty_memo = ""
        if tx.brokerage and tx.brokerage.quantity:
            qty = tx.brokerage.quantity
            price = tx.brokerage.price or (amount / qty if qty else Decimal(0))
            qty_memo = f"{qty} shares @ ${price:.2f}"

        # Securities increase (debit)
        sec_account = securities_account(symbol)
        entry.add_debit(sec_account, amount, memo=qty_memo)

        if is_reinvestment:
            # DRIP: offset is dividend income (credit)
            income_account = dividend_account(symbol)
            entry.add_credit(income_account, amount)
        else:
            # Regular purchase: cash decreases (credit)
            entry.add_credit(CASH_SETTLEMENT, amount)

        return entry

    def _map_sell(self, tx: Transaction) -> JournalEntry | None:
        """Map a sell transaction.

        Sell with gain:
            Debit:  Assets:Cash:Settlement         $X.XX (proceeds)
            Credit: Assets:Securities:{SYMBOL}           $Y.YY (cost basis)
            Credit: Income:CapitalGains:{SYMBOL}         $Z.ZZ (gain)

        Note: E*Trade doesn't provide cost basis in transactions, so we show
        the full proceeds and note that cost basis is unknown.
        """
        symbol = tx.symbol or "Unknown"
        amount = abs(tx.amount)

        entry = JournalEntry(
            date=tx.transaction_date.date() if hasattr(tx.transaction_date, 'date') else tx.transaction_date,
            description=f"Sold - {symbol}",
            reference=tx.transaction_id,
        )

        # Add quantity info if available
        qty_memo = ""
        if tx.brokerage and tx.brokerage.quantity:
            qty = tx.brokerage.quantity
            price = tx.brokerage.price or (amount / qty if qty else Decimal(0))
            qty_memo = f"{qty} shares @ ${price:.2f}"

        # Cash increases (debit)
        entry.add_debit(CASH_SETTLEMENT, amount)

        # Without cost basis, we credit the full amount to securities
        # This will be incorrect for P&L but preserves cash accuracy
        sec_account = securities_account(symbol)
        entry.add_credit(sec_account, amount, memo=qty_memo + " (proceeds, cost basis unknown)")

        self._warnings.append(
            f"Sell transaction for {symbol}: cost basis not available, "
            "showing proceeds only. P&L not calculated."
        )

        return entry

    def _map_deposit(self, tx: Transaction) -> JournalEntry | None:
        """Map a deposit/transfer-in transaction.

        Deposit:
            Debit:  Assets:Cash:Settlement        $X.XX
            Credit: Equity:Contributions                $X.XX
        """
        amount = abs(tx.amount)

        entry = JournalEntry(
            date=tx.transaction_date.date() if hasattr(tx.transaction_date, 'date') else tx.transaction_date,
            description=f"Deposit - {tx.description}",
            reference=tx.transaction_id,
        )

        # Cash increases (debit)
        entry.add_debit(CASH_SETTLEMENT, amount)

        # Equity contribution (credit)
        entry.add_credit(EQUITY_CONTRIBUTIONS, amount)

        return entry

    def _map_withdrawal(self, tx: Transaction) -> JournalEntry | None:
        """Map a withdrawal/transfer-out transaction.

        Withdrawal:
            Debit:  Equity:Distributions          $X.XX
            Credit: Assets:Cash:Settlement              $X.XX
        """
        amount = abs(tx.amount)

        entry = JournalEntry(
            date=tx.transaction_date.date() if hasattr(tx.transaction_date, 'date') else tx.transaction_date,
            description=f"Withdrawal - {tx.description}",
            reference=tx.transaction_id,
        )

        # Equity distribution (debit)
        entry.add_debit(EQUITY_DISTRIBUTIONS, amount)

        # Cash decreases (credit)
        entry.add_credit(CASH_SETTLEMENT, amount)

        return entry

    def _map_fee(self, tx: Transaction) -> JournalEntry | None:
        """Map a fee transaction.

        Fee:
            Debit:  Expenses:Fees:{Type}          $X.XX
            Credit: Assets:Cash:Settlement              $X.XX
        """
        amount = abs(tx.amount)
        tx_type_lower = tx.transaction_type.lower()
        desc_lower = tx.description.lower()

        # Determine the specific fee account
        if "adr" in tx_type_lower or "adr" in desc_lower:
            fee_account = EXPENSE_ADR_FEE
            fee_type = "ADR Fee"
        elif "commission" in tx_type_lower or "commission" in desc_lower:
            fee_account = EXPENSE_COMMISSION
            fee_type = "Commission"
        elif "margin interest" in tx_type_lower or "margin interest" in desc_lower:
            fee_account = EXPENSE_MARGIN_INTEREST
            fee_type = "Margin Interest"
        elif "sec " in tx_type_lower or "sec " in desc_lower:
            fee_account = get_account("Expenses:Fees:SEC")
            fee_type = "SEC Fee"
        elif "taf" in tx_type_lower or "taf" in desc_lower:
            fee_account = get_account("Expenses:Fees:TAF")
            fee_type = "TAF Fee"
        else:
            fee_account = EXPENSE_OTHER_FEE
            fee_type = "Fee"

        symbol_part = f" - {tx.symbol}" if tx.symbol else ""

        entry = JournalEntry(
            date=tx.transaction_date.date() if hasattr(tx.transaction_date, 'date') else tx.transaction_date,
            description=f"{fee_type}{symbol_part}",
            reference=tx.transaction_id,
        )

        # Expense (debit)
        entry.add_debit(fee_account, amount)

        # Cash decreases (credit)
        entry.add_credit(CASH_SETTLEMENT, amount)

        return entry

    def _map_interest(self, tx: Transaction) -> JournalEntry | None:
        """Map an interest transaction.

        Interest Income:
            Debit:  Assets:Cash:Settlement        $X.XX
            Credit: Income:Interest                     $X.XX

        Margin Interest (expense):
            Debit:  Expenses:Interest:Margin      $X.XX
            Credit: Assets:Cash:Settlement              $X.XX
        """
        amount = abs(tx.amount)
        tx_type_lower = tx.transaction_type.lower()
        desc_lower = tx.description.lower()

        is_margin_interest = "margin" in tx_type_lower or "margin" in desc_lower

        if is_margin_interest:
            # Margin interest is an expense
            entry = JournalEntry(
                date=tx.transaction_date.date() if hasattr(tx.transaction_date, 'date') else tx.transaction_date,
                description="Margin Interest Paid",
                reference=tx.transaction_id,
            )

            # Expense (debit)
            entry.add_debit(EXPENSE_MARGIN_INTEREST, amount)

            # Cash decreases (credit)
            entry.add_credit(CASH_SETTLEMENT, amount)
        else:
            # Interest income
            entry = JournalEntry(
                date=tx.transaction_date.date() if hasattr(tx.transaction_date, 'date') else tx.transaction_date,
                description="Interest Received",
                reference=tx.transaction_id,
            )

            # Cash increases (debit)
            entry.add_debit(CASH_SETTLEMENT, amount)

            # Income (credit)
            entry.add_credit(INCOME_INTEREST, amount)

        return entry

    def _map_option(self, tx: Transaction) -> JournalEntry | None:
        """Map an option transaction.

        This is complex and depends on the specific option action.
        For now, we create a simplified entry based on cash flow.
        """
        symbol = tx.symbol or "Unknown"
        amount = abs(tx.amount)
        tx_type_lower = tx.transaction_type.lower()

        # Determine if money came in or went out
        cash_in = tx.amount > 0

        if "sold to open" in tx_type_lower or "assignment" in tx_type_lower:
            # Premium received or assignment
            entry = JournalEntry(
                date=tx.transaction_date.date() if hasattr(tx.transaction_date, 'date') else tx.transaction_date,
                description=f"Option - {tx.description}",
                reference=tx.transaction_id,
            )

            if cash_in:
                entry.add_debit(CASH_SETTLEMENT, amount)
                entry.add_credit(option_premiums_account(symbol), amount)
            else:
                entry.add_debit(option_premiums_account(symbol), amount)
                entry.add_credit(CASH_SETTLEMENT, amount)
        else:
            # Other option activity
            entry = JournalEntry(
                date=tx.transaction_date.date() if hasattr(tx.transaction_date, 'date') else tx.transaction_date,
                description=f"Option - {tx.description}",
                reference=tx.transaction_id,
            )

            if cash_in:
                entry.add_debit(CASH_SETTLEMENT, amount)
                entry.add_credit(option_premiums_account(symbol), amount)
            else:
                entry.add_debit(get_account(f"Assets:Options:{symbol}"), amount)
                entry.add_credit(CASH_SETTLEMENT, amount)

        return entry

    def _map_unknown(self, tx: Transaction) -> JournalEntry | None:
        """Map an unknown transaction type.

        We use the transaction amount to determine cash direction
        and offset with a generic income/expense account.
        """
        amount = abs(tx.amount)
        cash_in = tx.amount > 0
        symbol_part = f" - {tx.symbol}" if tx.symbol else ""

        entry = JournalEntry(
            date=tx.transaction_date.date() if hasattr(tx.transaction_date, 'date') else tx.transaction_date,
            description=f"{tx.transaction_type}{symbol_part} - {tx.description}",
            reference=tx.transaction_id,
        )

        if cash_in:
            # Money came in
            entry.add_debit(CASH_SETTLEMENT, amount)
            entry.add_credit(INCOME_OTHER, amount, memo=f"Unknown type: {tx.transaction_type}")
        else:
            # Money went out
            entry.add_debit(EXPENSE_OTHER, amount, memo=f"Unknown type: {tx.transaction_type}")
            entry.add_credit(CASH_SETTLEMENT, amount)

        return entry

    def map_transactions(
        self, transactions: list[Transaction]
    ) -> tuple[list[JournalEntry], list[str]]:
        """Map multiple transactions to journal entries.

        Args:
            transactions: List of E*Trade transactions

        Returns:
            Tuple of (all journal entries, all warnings)
        """
        all_entries: list[JournalEntry] = []
        all_warnings: list[str] = []

        for tx in transactions:
            result = self.map_transaction(tx)
            all_entries.extend(result.entries)
            all_warnings.extend(result.warnings)

        return all_entries, all_warnings
