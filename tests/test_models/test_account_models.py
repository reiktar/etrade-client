"""Tests for account model parsing."""

from decimal import Decimal

from etrade_client.models.accounts import (
    AccountListResponse,
    BalanceResponse,
    PortfolioResponse,
)


def _complete_account_data(**overrides) -> dict:
    """Helper to create complete account test data with all required fields."""
    base = {
        "accountId": "12345678",
        "accountIdKey": "abc123",
        "accountType": "INDIVIDUAL",
        "accountDesc": "My Brokerage",
        "accountName": "John Doe",
        "accountMode": "CASH",
        "accountStatus": "ACTIVE",
        "institutionType": "BROKERAGE",
        "closedDate": 0,
        "shareWorksAccount": False,
        "fcManagedMssbClosedAccount": False,
    }
    base.update(overrides)
    return base


def _complete_balance_data(**overrides) -> dict:
    """Helper to create complete account balance test data with all required fields."""
    base = {
        "accountId": "12345678",
        "accountType": "INDIVIDUAL",
        "accountDescription": "My Account",
        "optionLevel": "LEVEL_2",
        "Cash": {
            # Required fields (always present in API)
            "fundsForOpenOrdersCash": "0.00",
            "moneyMktBalance": "0.00",
            # Optional fields (never present in sandbox, but may be in production)
            "cashBalance": "5000.00",
            "cashAvailableForWithdrawal": "4500.00",
            "cashAvailableForInvestment": "4800.00",
        },
        "Computed": {
            # Required fields (always present in API)
            "cashAvailableForInvestment": "4800.00",
            "cashAvailableForWithdrawal": "4500.00",
            "netCash": "5000.00",
            "cashBalance": "5000.00",
            "settledCashForInvestment": "4800.00",
            "unSettledCashForInvestment": "0.00",
            "fundsWithheldFromPurchasePower": "0.00",
            "fundsWithheldFromWithdrawal": "0.00",
            "OpenCalls": {
                "minEquityCall": "0.00",
                "fedCall": "0.00",
                "cashCall": "0.00",
                "houseCall": "0.00",
            },
            "RealTimeValues": {
                "totalAccountValue": "150500.00",
                "netMv": "145000.00",
                "netMvLong": "145000.00",
                "netMvShort": "0.00",
            },
            # Optional fields (never present in sandbox)
            "accountBalance": "150000.00",
            "marginBuyingPower": "50000.00",
            "RealTimeAccountValue": "150500.00",
        },
    }
    base.update(overrides)
    return base


def _complete_position_data(**overrides) -> dict:
    """Helper to create complete portfolio position test data with all required fields."""
    base = {
        "positionId": 1,
        "Product": {
            "symbol": "AAPL",
            "securityType": "EQ",
            "expiryDay": 0,
            "expiryMonth": 0,
            "expiryYear": 0,
            "strikePrice": "0.00",
            "productId": {},
        },
        "quantity": 100,
        "costPerShare": 150.00,
        "totalCost": 15000.00,
        "marketValue": 17500.00,
        "totalGain": 2500.00,
        "totalGainPct": 16.67,
        "daysGain": 250.00,
        "daysGainPct": 1.45,
        "positionType": "LONG",
        "Quick": {
            "lastTrade": "175.00",
            "change": "2.50",
            "changePct": "1.45",
            "volume": 50000000,
            "lastTradeTime": 1705318200,
            "quoteStatus": "REALTIME",
        },
        "dateAcquired": "2024-01-15T10:30:00",
        "symbolDescription": "Apple Inc.",
        "positionIndicator": "EQUITY",
        "pctOfPortfolio": 17.50,
        "pricePaid": 150.00,
        "commissions": 0.00,
        "otherFees": 0.00,
        "lotsDetails": "Lot 1",
        "quoteDetails": "NASDAQ",
        "todayQuantity": 0,
        "todayPricePaid": 0.00,
        "todayCommissions": 0.00,
        "todayFees": 0.00,
        "adjPrevClose": 172.50,
    }
    base.update(overrides)
    return base


class TestAccountListResponse:
    """Tests for AccountListResponse.from_api_response."""

    def test_parses_multiple_accounts(self) -> None:
        """Should parse response with multiple accounts as list."""
        data = {
            "AccountListResponse": {
                "Accounts": {
                    "Account": [
                        _complete_account_data(
                            accountId="12345678",
                            accountIdKey="abc123",
                            accountType="INDIVIDUAL",
                            accountDesc="My Brokerage",
                        ),
                        _complete_account_data(
                            accountId="87654321",
                            accountIdKey="xyz789",
                            accountType="IRA",
                            accountDesc="Retirement",
                        ),
                    ]
                }
            }
        }

        result = AccountListResponse.from_api_response(data)

        assert len(result.accounts) == 2
        assert result.accounts[0].account_id == "12345678"
        assert result.accounts[0].account_id_key == "abc123"
        assert result.accounts[0].account_type == "INDIVIDUAL"
        assert result.accounts[1].account_id == "87654321"
        assert result.accounts[1].account_type == "IRA"

    def test_parses_single_account_as_dict(self) -> None:
        """Should handle E*Trade's single-item-as-dict quirk."""
        data = {
            "AccountListResponse": {
                "Accounts": {
                    "Account": _complete_account_data(
                        accountId="12345678",
                        accountIdKey="abc123",
                        accountType="INDIVIDUAL",
                    )
                }
            }
        }

        result = AccountListResponse.from_api_response(data)

        assert len(result.accounts) == 1
        assert result.accounts[0].account_id == "12345678"

    def test_parses_empty_response(self) -> None:
        """Should handle empty accounts list."""
        data = {"AccountListResponse": {"Accounts": {"Account": []}}}

        result = AccountListResponse.from_api_response(data)

        assert len(result.accounts) == 0

    def test_parses_missing_accounts_key(self) -> None:
        """Should handle missing Accounts key gracefully."""
        data = {"AccountListResponse": {}}

        result = AccountListResponse.from_api_response(data)

        assert len(result.accounts) == 0

    def test_parses_all_account_fields(self) -> None:
        """Should parse account with all fields."""
        data = {
            "AccountListResponse": {
                "Accounts": {
                    "Account": _complete_account_data(
                        accountId="12345678",
                        accountDesc="Test Account",
                        accountName="John Doe",
                        accountStatus="ACTIVE",
                    )
                }
            }
        }

        result = AccountListResponse.from_api_response(data)

        assert result.accounts[0].account_id == "12345678"
        assert result.accounts[0].account_desc == "Test Account"
        assert result.accounts[0].account_name == "John Doe"
        assert result.accounts[0].account_status == "ACTIVE"


class TestBalanceResponse:
    """Tests for BalanceResponse.from_api_response."""

    def test_parses_complete_balance(self) -> None:
        """Should parse complete balance response."""
        data = {
            "BalanceResponse": _complete_balance_data(
                netAccountValue="150000.00",
                totalAccountValue="175000.00",
            )
        }

        result = BalanceResponse.from_api_response(data)

        assert result.balance.account_id == "12345678"
        assert result.balance.account_type == "INDIVIDUAL"
        assert result.balance.net_account_value == Decimal("150000.00")
        assert result.balance.cash is not None
        assert result.balance.cash.cash_balance == Decimal("5000.00")
        assert result.balance.computed is not None
        assert result.balance.computed.margin_buying_power == Decimal("50000.00")

    def test_parses_balance_with_all_fields(self) -> None:
        """Should handle balance with all required fields."""
        data = {
            "BalanceResponse": _complete_balance_data(
                accountId="12345678",
                accountType="INDIVIDUAL",
            )
        }

        result = BalanceResponse.from_api_response(data)

        assert result.balance.account_id == "12345678"
        assert result.balance.cash is not None
        assert result.balance.computed is not None


class TestPortfolioResponse:
    """Tests for PortfolioResponse.from_api_response."""

    def test_parses_multiple_positions(self) -> None:
        """Should parse portfolio with multiple positions."""
        data = {
            "PortfolioResponse": {
                "AccountPortfolio": {
                    "totalValue": "100000.00",
                    "Position": [
                        _complete_position_data(
                            positionId=1,
                            Product={
                                "symbol": "AAPL",
                                "securityType": "EQ",
                                "expiryDay": 0,
                                "expiryMonth": 0,
                                "expiryYear": 0,
                                "strikePrice": "0.00",
                                "productId": {},
                            },
                            quantity=100,
                            costPerShare=150.00,
                            totalCost=15000.00,
                            marketValue=17500.00,
                            totalGain=2500.00,
                            totalGainPct=16.67,
                        ),
                        _complete_position_data(
                            positionId=2,
                            Product={
                                "symbol": "MSFT",
                                "securityType": "EQ",
                                "expiryDay": 0,
                                "expiryMonth": 0,
                                "expiryYear": 0,
                                "strikePrice": "0.00",
                                "productId": {},
                            },
                            quantity=50,
                            costPerShare=300.00,
                            totalCost=15000.00,
                            marketValue=18000.00,
                            totalGain=3000.00,
                            totalGainPct=20.00,
                        ),
                    ],
                }
            }
        }

        result = PortfolioResponse.from_api_response(data, "acc123")

        assert result.account_id == "acc123"
        assert len(result.positions) == 2
        assert result.positions[0].product.symbol == "AAPL"
        assert result.positions[0].quantity == Decimal("100")
        assert result.positions[1].product.symbol == "MSFT"
        assert result.total_value == Decimal("100000.00")

    def test_parses_single_position_as_dict(self) -> None:
        """Should handle single position returned as dict."""
        data = {
            "PortfolioResponse": {
                "AccountPortfolio": {
                    "totalValue": "50000.00",
                    "Position": _complete_position_data(
                        positionId=1,
                        Product={
                            "symbol": "GOOG",
                            "securityType": "EQ",
                            "expiryDay": 0,
                            "expiryMonth": 0,
                            "expiryYear": 0,
                            "strikePrice": "0.00",
                            "productId": {},
                        },
                        quantity=25,
                        costPerShare=140.00,
                        totalCost=3500.00,
                        marketValue=4000.00,
                        totalGain=500.00,
                        totalGainPct=14.29,
                    ),
                }
            }
        }

        result = PortfolioResponse.from_api_response(data, "acc123")

        assert len(result.positions) == 1
        assert result.positions[0].product.symbol == "GOOG"

    def test_parses_empty_portfolio(self) -> None:
        """Should handle empty portfolio."""
        data = {
            "PortfolioResponse": {
                "AccountPortfolio": {
                    "totalValue": "0.00",
                    "Position": [],
                }
            }
        }

        result = PortfolioResponse.from_api_response(data, "acc123")

        assert len(result.positions) == 0
        assert result.total_value == Decimal("0.00")

    def test_parses_multiple_account_portfolios(self) -> None:
        """Should handle AccountPortfolio as list (edge case)."""
        data = {
            "PortfolioResponse": {
                "AccountPortfolio": [
                    {
                        "totalValue": "50000.00",
                        "Position": _complete_position_data(
                            positionId=1,
                            Product={
                                "symbol": "AAPL",
                                "securityType": "EQ",
                                "expiryDay": 0,
                                "expiryMonth": 0,
                                "expiryYear": 0,
                                "strikePrice": "0.00",
                                "productId": {},
                            },
                            quantity=100,
                            costPerShare=150.00,
                            totalCost=15000.00,
                            marketValue=17500.00,
                            totalGain=2500.00,
                            totalGainPct=16.67,
                        ),
                    },
                    {
                        "totalValue": "30000.00",
                        "Position": _complete_position_data(
                            positionId=2,
                            Product={
                                "symbol": "MSFT",
                                "securityType": "EQ",
                                "expiryDay": 0,
                                "expiryMonth": 0,
                                "expiryYear": 0,
                                "strikePrice": "0.00",
                                "productId": {},
                            },
                            quantity=50,
                            costPerShare=300.00,
                            totalCost=15000.00,
                            marketValue=16000.00,
                            totalGain=1000.00,
                            totalGainPct=6.67,
                        ),
                    },
                ]
            }
        }

        result = PortfolioResponse.from_api_response(data, "acc123")

        assert len(result.positions) == 2
        assert result.total_value == Decimal("80000.00")  # 50000 + 30000
