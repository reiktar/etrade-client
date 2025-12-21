"""Integration tests for field nullability analysis.

This test module collects field presence data from API responses
to determine which fields are truly optional vs. required.

Run with: pytest tests/integration/test_nullability.py -v -m integration -s
"""

import pytest

from etrade_client.models.accounts import (
    Account,
    AccountBalance,
    CashBalance,
    ComputedBalance,
    PortfolioPosition,
    PositionQuick,
    Product,
)
from etrade_client.models.alerts import Alert
from etrade_client.models.market import AllQuoteDetails, OptionDetails, Quote
from etrade_client.models.orders import Order, OrderDetail, OrderInstrument
from etrade_client.models.transactions import Transaction, TransactionBrokerage

from tests.integration.field_analyzer import FieldPresenceAnalyzer


pytestmark = [pytest.mark.integration, pytest.mark.nullability_analysis]


class TestNullabilityAnalysis:
    """Collect field presence data from all API endpoints."""

    async def test_account_fields(
        self,
        async_integration_client,
        presence_analyzer: FieldPresenceAnalyzer,
        field_collector,
    ) -> None:
        """Analyze Account model field presence."""
        client = async_integration_client

        # Get raw response
        last_response = field_collector.response_capture.get_last_response()

        accounts_response = await client.accounts.list_accounts()

        # Get the raw JSON from captured response
        last_response = field_collector.response_capture.get_last_response()
        if last_response and last_response.raw_json:
            raw = last_response.raw_json
            accounts_data = raw.get("AccountListResponse", {}).get("Accounts", {})
            account_list = accounts_data.get("Account", [])
            if isinstance(account_list, dict):
                account_list = [account_list]

            for raw_account in account_list:
                presence_analyzer.analyze_model(raw_account, Account)

        assert len(accounts_response.accounts) > 0

    async def test_balance_fields(
        self,
        async_integration_client,
        presence_analyzer: FieldPresenceAnalyzer,
        field_collector,
    ) -> None:
        """Analyze AccountBalance model field presence."""
        client = async_integration_client

        accounts_response = await client.accounts.list_accounts()
        account = accounts_response.accounts[0]

        balance_response = await client.accounts.get_balance(account.account_id_key)

        last_response = field_collector.response_capture.get_last_response()
        if last_response and last_response.raw_json:
            raw = last_response.raw_json
            balance_data = raw.get("BalanceResponse", {})

            presence_analyzer.analyze_model(balance_data, AccountBalance)

            if "Cash" in balance_data:
                presence_analyzer.analyze_model(balance_data["Cash"], CashBalance)

            if "Computed" in balance_data:
                presence_analyzer.analyze_model(balance_data["Computed"], ComputedBalance)

        assert balance_response is not None

    async def test_portfolio_fields(
        self,
        async_integration_client,
        presence_analyzer: FieldPresenceAnalyzer,
        field_collector,
    ) -> None:
        """Analyze PortfolioPosition model field presence."""
        client = async_integration_client

        accounts_response = await client.accounts.list_accounts()
        account = accounts_response.accounts[0]

        portfolio_response = await client.accounts.get_portfolio(account.account_id_key)

        last_response = field_collector.response_capture.get_last_response()
        if last_response and last_response.raw_json:
            raw = last_response.raw_json
            portfolio_data = raw.get("PortfolioResponse", {})
            account_portfolios = portfolio_data.get("AccountPortfolio", [])

            if isinstance(account_portfolios, dict):
                account_portfolios = [account_portfolios]

            for ap in account_portfolios:
                positions = ap.get("Position", [])
                if isinstance(positions, dict):
                    positions = [positions]

                for pos in positions:
                    presence_analyzer.analyze_model(pos, PortfolioPosition)

                    if "Product" in pos:
                        presence_analyzer.analyze_model(pos["Product"], Product)

                    if "Quick" in pos:
                        presence_analyzer.analyze_model(pos["Quick"], PositionQuick)

        assert portfolio_response is not None

    async def test_quote_fields(
        self,
        async_integration_client,
        presence_analyzer: FieldPresenceAnalyzer,
        field_collector,
    ) -> None:
        """Analyze Quote model field presence."""
        client = async_integration_client

        quotes_response = await client.market.get_quotes(["AAPL", "GOOGL", "MSFT"])

        last_response = field_collector.response_capture.get_last_response()
        if last_response and last_response.raw_json:
            raw = last_response.raw_json
            quote_response = raw.get("QuoteResponse", {})
            quote_data = quote_response.get("QuoteData", [])

            if isinstance(quote_data, dict):
                quote_data = [quote_data]

            for q in quote_data:
                presence_analyzer.analyze_model(q, Quote)

                if "All" in q:
                    presence_analyzer.analyze_model(q["All"], AllQuoteDetails)

        assert len(quotes_response.quotes) > 0

    async def test_option_chain_fields(
        self,
        async_integration_client,
        presence_analyzer: FieldPresenceAnalyzer,
        field_collector,
    ) -> None:
        """Analyze OptionDetails model field presence."""
        client = async_integration_client
        from datetime import date, timedelta

        # Get option expiration dates
        expiry_dates = await client.market.get_option_expire_dates("AAPL")

        if expiry_dates:
            expiry = expiry_dates[0].expiry_date
            chain = await client.market.get_option_chains("AAPL", expiry)

            last_response = field_collector.response_capture.get_last_response()
            if last_response and last_response.raw_json:
                raw = last_response.raw_json
                chain_response = raw.get("OptionChainResponse", {})
                option_pairs = chain_response.get("OptionPair", [])

                if isinstance(option_pairs, dict):
                    option_pairs = [option_pairs]

                for pair in option_pairs:
                    if "Call" in pair:
                        presence_analyzer.analyze_model(pair["Call"], OptionDetails)
                    if "Put" in pair:
                        presence_analyzer.analyze_model(pair["Put"], OptionDetails)

    async def test_order_fields(
        self,
        async_integration_client,
        presence_analyzer: FieldPresenceAnalyzer,
        field_collector,
    ) -> None:
        """Analyze Order model field presence."""
        client = async_integration_client

        accounts_response = await client.accounts.list_accounts()
        account = accounts_response.accounts[0]

        orders_response = await client.orders.list_orders(account.account_id_key)

        last_response = field_collector.response_capture.get_last_response()
        if last_response and last_response.raw_json:
            raw = last_response.raw_json
            orders_data = raw.get("OrdersResponse", {})
            order_list = orders_data.get("Order", [])

            if isinstance(order_list, dict):
                order_list = [order_list]

            for order in order_list:
                presence_analyzer.analyze_model(order, Order)

                order_details = order.get("OrderDetail", [])
                if isinstance(order_details, dict):
                    order_details = [order_details]

                for detail in order_details:
                    presence_analyzer.analyze_model(detail, OrderDetail)

                    instruments = detail.get("Instrument", [])
                    if isinstance(instruments, dict):
                        instruments = [instruments]

                    for instr in instruments:
                        presence_analyzer.analyze_model(instr, OrderInstrument)

    async def test_alert_fields(
        self,
        async_integration_client,
        presence_analyzer: FieldPresenceAnalyzer,
        field_collector,
    ) -> None:
        """Analyze Alert model field presence."""
        client = async_integration_client

        alerts_response = await client.alerts.list_alerts()

        last_response = field_collector.response_capture.get_last_response()
        if last_response and last_response.raw_json:
            raw = last_response.raw_json
            alerts_data = raw.get("AlertsResponse", {})
            alert_list = alerts_data.get("Alert", [])

            if isinstance(alert_list, dict):
                alert_list = [alert_list]

            for alert in alert_list:
                presence_analyzer.analyze_model(alert, Alert)

    async def test_transaction_fields(
        self,
        async_integration_client,
        presence_analyzer: FieldPresenceAnalyzer,
        field_collector,
    ) -> None:
        """Analyze Transaction model field presence."""
        client = async_integration_client

        accounts_response = await client.accounts.list_accounts()
        account = accounts_response.accounts[0]

        # Use the accounts API to get transactions
        tx_response = await client.accounts.list_transactions(account.account_id_key)

        last_response = field_collector.response_capture.get_last_response()
        if last_response and last_response.raw_json:
            raw = last_response.raw_json
            tx_data = raw.get("TransactionListResponse", {})
            tx_list = tx_data.get("Transaction", [])

            if isinstance(tx_list, dict):
                tx_list = [tx_list]

            for tx in tx_list:
                presence_analyzer.analyze_model(tx, Transaction)

                if "Brokerage" in tx:
                    presence_analyzer.analyze_model(tx["Brokerage"], TransactionBrokerage)
