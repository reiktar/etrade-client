"""Endpoint-aware field analysis tests.

These tests call various API endpoints and track which fields are present
in each response, grouped by endpoint. This helps identify:

1. Fields that are missing because of endpoint context (list vs detail)
2. Fields that are truly optional within the same endpoint
3. Whether we need separate model classes (e.g., AccountSummary vs AccountDetail)

Run with: pytest tests/integration/test_endpoint_field_analysis.py -v -s
"""

import pytest
from pydantic import BaseModel

from etrade_client.models.accounts import Account, AccountBalance, CashBalance, ComputedBalance
from etrade_client.models.market import Quote, AllQuoteDetails
from tests.integration.endpoint_field_analyzer import EndpointFieldAnalyzer


pytestmark = pytest.mark.integration


def _get_field_mapping(model_class: type[BaseModel]) -> dict[str, str]:
    """Get mapping of python field name -> API alias for a model."""
    mapping = {}
    for field_name, field_info in model_class.model_fields.items():
        alias = field_info.alias if field_info.alias else field_name
        mapping[field_name] = alias
    return mapping


class TestEndpointFieldAnalysis:
    """Analyze field presence across different API endpoints."""

    async def test_account_field_analysis(
        self,
        async_integration_client,
        endpoint_analyzer: EndpointFieldAnalyzer,
        field_collector,
    ) -> None:
        """Analyze Account model fields from list_accounts endpoint."""
        client = async_integration_client

        # Get raw response
        last_response = field_collector.response_capture.get_last_response()

        # Call the endpoint
        response = await client.accounts.list_accounts()

        # Get new response
        current_response = field_collector.response_capture.get_last_response()

        if current_response and current_response.raw_json:
            # Extract raw account data
            accounts_data = (
                current_response.raw_json
                .get("AccountListResponse", {})
                .get("Accounts", {})
                .get("Account", [])
            )
            if isinstance(accounts_data, dict):
                accounts_data = [accounts_data]

            # Record each account observation
            field_mapping = _get_field_mapping(Account)
            for account_data in accounts_data:
                endpoint_analyzer.record(
                    endpoint="list_accounts",
                    model_name="Account",
                    data=account_data,
                    field_mapping=field_mapping,
                )

        assert len(response.accounts) > 0, "Expected at least one account"

    async def test_balance_field_analysis(
        self,
        async_integration_client,
        endpoint_analyzer: EndpointFieldAnalyzer,
        field_collector,
    ) -> None:
        """Analyze AccountBalance model fields from get_balance endpoint."""
        client = async_integration_client

        # First get an account
        accounts_response = await client.accounts.list_accounts()
        assert len(accounts_response.accounts) > 0

        account = accounts_response.accounts[0]

        # Get balance
        balance_response = await client.accounts.get_balance(account.account_id_key)

        # Get raw response
        current_response = field_collector.response_capture.get_last_response()

        if current_response and current_response.raw_json:
            balance_data = current_response.raw_json.get("BalanceResponse", {})

            # Record AccountBalance
            endpoint_analyzer.record(
                endpoint="get_balance",
                model_name="AccountBalance",
                data=balance_data,
                field_mapping=_get_field_mapping(AccountBalance),
            )

            # Record CashBalance (nested)
            if "Cash" in balance_data:
                endpoint_analyzer.record(
                    endpoint="get_balance",
                    model_name="CashBalance",
                    data=balance_data["Cash"],
                    field_mapping=_get_field_mapping(CashBalance),
                )

            # Record ComputedBalance (nested)
            if "Computed" in balance_data:
                endpoint_analyzer.record(
                    endpoint="get_balance",
                    model_name="ComputedBalance",
                    data=balance_data["Computed"],
                    field_mapping=_get_field_mapping(ComputedBalance),
                )

        assert balance_response.balance is not None

    async def test_portfolio_field_analysis(
        self,
        async_integration_client,
        endpoint_analyzer: EndpointFieldAnalyzer,
        field_collector,
    ) -> None:
        """Analyze PortfolioPosition model fields from get_portfolio endpoint."""
        client = async_integration_client

        from etrade_client.models.accounts import PortfolioPosition, Product, PositionQuick

        # First get an account
        accounts_response = await client.accounts.list_accounts()
        assert len(accounts_response.accounts) > 0

        account = accounts_response.accounts[0]

        # Get portfolio
        portfolio_response = await client.accounts.get_portfolio(account.account_id_key)

        # Get raw response
        current_response = field_collector.response_capture.get_last_response()

        if current_response and current_response.raw_json:
            portfolio_data = current_response.raw_json.get("PortfolioResponse", {})
            account_portfolios = portfolio_data.get("AccountPortfolio", [])
            if isinstance(account_portfolios, dict):
                account_portfolios = [account_portfolios]

            for account_portfolio in account_portfolios:
                positions = account_portfolio.get("Position", [])
                if isinstance(positions, dict):
                    positions = [positions]

                for position_data in positions:
                    # Record PortfolioPosition
                    endpoint_analyzer.record(
                        endpoint="get_portfolio",
                        model_name="PortfolioPosition",
                        data=position_data,
                        field_mapping=_get_field_mapping(PortfolioPosition),
                    )

                    # Record Product (nested)
                    if "Product" in position_data:
                        endpoint_analyzer.record(
                            endpoint="get_portfolio",
                            model_name="Product",
                            data=position_data["Product"],
                            field_mapping=_get_field_mapping(Product),
                        )

                    # Record PositionQuick (nested)
                    if "Quick" in position_data:
                        endpoint_analyzer.record(
                            endpoint="get_portfolio",
                            model_name="PositionQuick",
                            data=position_data["Quick"],
                            field_mapping=_get_field_mapping(PositionQuick),
                        )

    async def test_quote_field_analysis(
        self,
        async_integration_client,
        endpoint_analyzer: EndpointFieldAnalyzer,
        field_collector,
    ) -> None:
        """Analyze Quote model fields from get_quotes endpoint."""
        client = async_integration_client

        # Get quotes for multiple symbols
        symbols = ["AAPL", "MSFT", "GOOG"]
        quote_response = await client.market.get_quotes(symbols)

        # Get raw response
        current_response = field_collector.response_capture.get_last_response()

        if current_response and current_response.raw_json:
            quote_data = current_response.raw_json.get("QuoteResponse", {})
            quotes = quote_data.get("QuoteData", [])
            if isinstance(quotes, dict):
                quotes = [quotes]

            for quote in quotes:
                # Record Quote
                endpoint_analyzer.record(
                    endpoint="get_quotes",
                    model_name="Quote",
                    data=quote,
                    field_mapping=_get_field_mapping(Quote),
                )

                # Record AllQuoteDetails (nested)
                if "All" in quote:
                    endpoint_analyzer.record(
                        endpoint="get_quotes",
                        model_name="AllQuoteDetails",
                        data=quote["All"],
                        field_mapping=_get_field_mapping(AllQuoteDetails),
                    )

        assert len(quote_response.quotes) > 0

    async def test_transaction_field_analysis(
        self,
        async_integration_client,
        endpoint_analyzer: EndpointFieldAnalyzer,
        field_collector,
    ) -> None:
        """Analyze Transaction model fields from list_transactions endpoint."""
        client = async_integration_client

        from etrade_client.models.transactions import Transaction

        # First get an account
        accounts_response = await client.accounts.list_accounts()
        assert len(accounts_response.accounts) > 0

        account = accounts_response.accounts[0]

        # Get transactions (via accounts API)
        tx_response = await client.accounts.list_transactions(account.account_id_key)

        # Get raw response
        current_response = field_collector.response_capture.get_last_response()

        if current_response and current_response.raw_json:
            tx_data = current_response.raw_json.get("TransactionListResponse", {})
            transactions = tx_data.get("Transaction", [])
            if isinstance(transactions, dict):
                transactions = [transactions]

            for transaction in transactions:
                endpoint_analyzer.record(
                    endpoint="list_transactions",
                    model_name="Transaction",
                    data=transaction,
                    field_mapping=_get_field_mapping(Transaction),
                )

    async def test_order_field_analysis(
        self,
        async_integration_client,
        endpoint_analyzer: EndpointFieldAnalyzer,
        field_collector,
    ) -> None:
        """Analyze Order model fields from list_orders endpoint."""
        client = async_integration_client

        from etrade_client.models.orders import (
            Order, OrderDetail, OrderInstrument, OrderProduct
        )

        # First get an account
        accounts_response = await client.accounts.list_accounts()
        assert len(accounts_response.accounts) > 0

        account = accounts_response.accounts[0]

        # Get orders
        try:
            orders_response = await client.orders.list_orders(account.account_id_key)
        except Exception:
            # Orders endpoint may fail in sandbox
            pytest.skip("Orders endpoint not available in sandbox")
            return

        # Get raw response
        current_response = field_collector.response_capture.get_last_response()

        if current_response and current_response.raw_json:
            orders_data = current_response.raw_json.get("OrdersResponse", {})
            orders = orders_data.get("Order", [])
            if isinstance(orders, dict):
                orders = [orders]

            for order in orders:
                endpoint_analyzer.record(
                    endpoint="list_orders",
                    model_name="Order",
                    data=order,
                    field_mapping=_get_field_mapping(Order),
                )

                # Record OrderDetail (nested)
                details = order.get("OrderDetail", [])
                if isinstance(details, dict):
                    details = [details]
                for detail in details:
                    endpoint_analyzer.record(
                        endpoint="list_orders",
                        model_name="OrderDetail",
                        data=detail,
                        field_mapping=_get_field_mapping(OrderDetail),
                    )

                    # Record OrderInstrument (nested)
                    instruments = detail.get("Instrument", [])
                    if isinstance(instruments, dict):
                        instruments = [instruments]
                    for instrument in instruments:
                        endpoint_analyzer.record(
                            endpoint="list_orders",
                            model_name="OrderInstrument",
                            data=instrument,
                            field_mapping=_get_field_mapping(OrderInstrument),
                        )

                        # Record OrderProduct (nested)
                        if "Product" in instrument:
                            endpoint_analyzer.record(
                                endpoint="list_orders",
                                model_name="OrderProduct",
                                data=instrument["Product"],
                                field_mapping=_get_field_mapping(OrderProduct),
                            )

    async def test_alert_field_analysis(
        self,
        async_integration_client,
        endpoint_analyzer: EndpointFieldAnalyzer,
        field_collector,
    ) -> None:
        """Analyze Alert model fields from list_alerts endpoint."""
        client = async_integration_client

        from etrade_client.models.alerts import Alert

        # Get alerts
        try:
            alerts_response = await client.alerts.list_alerts()
        except Exception:
            pytest.skip("Alerts endpoint not available")
            return

        # Get raw response
        current_response = field_collector.response_capture.get_last_response()

        if current_response and current_response.raw_json:
            alerts_data = current_response.raw_json.get("AlertsResponse", {})
            alerts = alerts_data.get("Alert", [])
            if isinstance(alerts, dict):
                alerts = [alerts]

            for alert in alerts:
                endpoint_analyzer.record(
                    endpoint="list_alerts",
                    model_name="Alert",
                    data=alert,
                    field_mapping=_get_field_mapping(Alert),
                )

    async def test_option_chain_field_analysis(
        self,
        async_integration_client,
        endpoint_analyzer: EndpointFieldAnalyzer,
        field_collector,
    ) -> None:
        """Analyze OptionChain model fields from get_option_chains endpoint."""
        client = async_integration_client

        from etrade_client.models.market import OptionDetails

        # Get option expiry dates first
        try:
            expiry_dates = await client.market.get_option_expire_dates("AAPL")
            if not expiry_dates:
                pytest.skip("No option expiry dates available")
                return

            # Get option chains for first expiry
            chains_response = await client.market.get_option_chains(
                "AAPL",
                expiry_date=expiry_dates[0].expiry_date,
            )
        except Exception as e:
            pytest.skip(f"Option chains endpoint not available: {e}")
            return

        # Get raw response
        current_response = field_collector.response_capture.get_last_response()

        if current_response and current_response.raw_json:
            chains_data = current_response.raw_json.get("OptionChainResponse", {})
            pairs = chains_data.get("OptionPair", [])
            if isinstance(pairs, dict):
                pairs = [pairs]

            for pair in pairs:
                # Record call option details
                if "Call" in pair:
                    endpoint_analyzer.record(
                        endpoint="get_option_chains",
                        model_name="OptionDetails",
                        data=pair["Call"],
                        field_mapping=_get_field_mapping(OptionDetails),
                    )

                # Record put option details
                if "Put" in pair:
                    endpoint_analyzer.record(
                        endpoint="get_option_chains",
                        model_name="OptionDetails",
                        data=pair["Put"],
                        field_mapping=_get_field_mapping(OptionDetails),
                    )
