"""Tests for account model parsing."""

from decimal import Decimal

import pytest

from etrade_client.models.accounts import (
    AccountListResponse,
    BalanceResponse,
    PortfolioResponse,
)


class TestAccountListResponse:
    """Tests for AccountListResponse.from_api_response."""

    def test_parses_multiple_accounts(self) -> None:
        """Should parse response with multiple accounts as list."""
        data = {
            "AccountListResponse": {
                "Accounts": {
                    "Account": [
                        {
                            "accountId": "12345678",
                            "accountIdKey": "abc123",
                            "accountType": "INDIVIDUAL",
                            "accountDesc": "My Brokerage",
                            "accountStatus": "ACTIVE",
                        },
                        {
                            "accountId": "87654321",
                            "accountIdKey": "xyz789",
                            "accountType": "IRA",
                            "accountDesc": "Retirement",
                            "accountStatus": "ACTIVE",
                        },
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
                    "Account": {
                        "accountId": "12345678",
                        "accountIdKey": "abc123",
                        "accountType": "INDIVIDUAL",
                    }
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

    def test_parses_minimal_account_fields(self) -> None:
        """Should parse account with only required fields."""
        data = {
            "AccountListResponse": {
                "Accounts": {
                    "Account": {
                        "accountId": "12345678",
                        "accountIdKey": "abc123",
                        "accountType": "INDIVIDUAL",
                    }
                }
            }
        }

        result = AccountListResponse.from_api_response(data)

        assert result.accounts[0].account_id == "12345678"
        assert result.accounts[0].account_desc is None
        assert result.accounts[0].account_name is None
        assert result.accounts[0].account_status is None


class TestBalanceResponse:
    """Tests for BalanceResponse.from_api_response."""

    def test_parses_complete_balance(self) -> None:
        """Should parse complete balance response."""
        data = {
            "BalanceResponse": {
                "accountId": "12345678",
                "accountType": "INDIVIDUAL",
                "accountDescription": "My Account",
                "netAccountValue": "150000.00",
                "totalAccountValue": "175000.00",
                "Cash": {
                    "cashBalance": "5000.00",
                    "cashAvailableForWithdrawal": "4500.00",
                    "cashAvailableForInvestment": "4800.00",
                },
                "Computed": {
                    "accountBalance": "150000.00",
                    "marginBuyingPower": "50000.00",
                    "RealTimeAccountValue": "150500.00",
                },
            }
        }

        result = BalanceResponse.from_api_response(data)

        assert result.balance.account_id == "12345678"
        assert result.balance.account_type == "INDIVIDUAL"
        assert result.balance.net_account_value == Decimal("150000.00")
        assert result.balance.cash is not None
        assert result.balance.cash.cash_balance == Decimal("5000.00")
        assert result.balance.computed is not None
        assert result.balance.computed.margin_buying_power == Decimal("50000.00")

    def test_parses_balance_without_cash_section(self) -> None:
        """Should handle missing Cash section."""
        data = {
            "BalanceResponse": {
                "accountId": "12345678",
                "accountType": "INDIVIDUAL",
            }
        }

        result = BalanceResponse.from_api_response(data)

        assert result.balance.account_id == "12345678"
        assert result.balance.cash is None
        assert result.balance.computed is None


class TestPortfolioResponse:
    """Tests for PortfolioResponse.from_api_response."""

    def test_parses_multiple_positions(self) -> None:
        """Should parse portfolio with multiple positions."""
        data = {
            "PortfolioResponse": {
                "AccountPortfolio": {
                    "totalValue": "100000.00",
                    "Position": [
                        {
                            "positionId": 1,
                            "Product": {
                                "symbol": "AAPL",
                                "securityType": "EQ",
                            },
                            "quantity": 100,
                            "costPerShare": 150.00,
                            "totalCost": 15000.00,
                            "marketValue": 17500.00,
                            "totalGain": 2500.00,
                            "totalGainPct": 16.67,
                            "positionType": "LONG",
                        },
                        {
                            "positionId": 2,
                            "Product": {
                                "symbol": "MSFT",
                                "securityType": "EQ",
                            },
                            "quantity": 50,
                            "costPerShare": 300.00,
                            "totalCost": 15000.00,
                            "marketValue": 18000.00,
                            "totalGain": 3000.00,
                            "totalGainPct": 20.00,
                            "positionType": "LONG",
                        },
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
                    "Position": {
                        "positionId": 1,
                        "Product": {
                            "symbol": "GOOG",
                            "securityType": "EQ",
                        },
                        "quantity": 25,
                        "costPerShare": 140.00,
                        "totalCost": 3500.00,
                        "marketValue": 4000.00,
                        "totalGain": 500.00,
                        "totalGainPct": 14.29,
                        "positionType": "LONG",
                    },
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
                        "Position": {
                            "positionId": 1,
                            "Product": {"symbol": "AAPL", "securityType": "EQ"},
                            "quantity": 100,
                            "costPerShare": 150.00,
                            "totalCost": 15000.00,
                            "marketValue": 17500.00,
                            "totalGain": 2500.00,
                            "totalGainPct": 16.67,
                            "positionType": "LONG",
                        },
                    },
                    {
                        "totalValue": "30000.00",
                        "Position": {
                            "positionId": 2,
                            "Product": {"symbol": "MSFT", "securityType": "EQ"},
                            "quantity": 50,
                            "costPerShare": 300.00,
                            "totalCost": 15000.00,
                            "marketValue": 16000.00,
                            "totalGain": 1000.00,
                            "totalGainPct": 6.67,
                            "positionType": "LONG",
                        },
                    },
                ]
            }
        }

        result = PortfolioResponse.from_api_response(data, "acc123")

        assert len(result.positions) == 2
        assert result.total_value == Decimal("80000.00")  # 50000 + 30000
