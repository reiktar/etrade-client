"""Tests for market data model parsing."""

from datetime import date
from decimal import Decimal

import pytest

from etrade_client.models.market import (
    AllQuoteDetails,
    OptionChain,
    OptionDetails,
    OptionExpireDate,
    OptionPair,
    Quote,
    QuoteResponse,
)


class TestQuoteResponse:
    """Tests for QuoteResponse.from_api_response."""

    def test_parses_multiple_quotes(self) -> None:
        """Should parse response with multiple quotes."""
        data = {
            "QuoteResponse": {
                "QuoteData": [
                    {
                        "symbol": "AAPL",
                        "quoteStatus": "REALTIME",
                        "All": {
                            "lastTrade": "175.50",
                            "change": "2.50",
                            "changePct": "1.44",
                            "previousClose": "173.00",
                            "high": "176.00",
                            "low": "172.00",
                            "open": "173.50",
                            "totalVolume": 50000000,
                        },
                    },
                    {
                        "symbol": "MSFT",
                        "quoteStatus": "REALTIME",
                        "All": {
                            "lastTrade": "420.00",
                            "change": "-5.00",
                            "changePct": "-1.18",
                            "previousClose": "425.00",
                            "high": "426.00",
                            "low": "418.00",
                            "open": "425.50",
                            "totalVolume": 25000000,
                        },
                    },
                ]
            }
        }

        result = QuoteResponse.from_api_response(data)

        assert len(result.quotes) == 2
        assert result.quotes[0].symbol == "AAPL"
        assert result.quotes[0].last_trade == Decimal("175.50")
        assert result.quotes[0].change == Decimal("2.50")
        assert result.quotes[1].symbol == "MSFT"
        assert result.quotes[1].last_trade == Decimal("420.00")

    def test_parses_single_quote_as_dict(self) -> None:
        """Should handle E*Trade's single-item-as-dict quirk."""
        data = {
            "QuoteResponse": {
                "QuoteData": {
                    "symbol": "GOOG",
                    "quoteStatus": "DELAYED",
                    "All": {
                        "lastTrade": "140.00",
                        "previousClose": "139.00",
                        "high": "141.00",
                        "low": "138.00",
                        "open": "139.50",
                        "totalVolume": 10000000,
                    },
                }
            }
        }

        result = QuoteResponse.from_api_response(data)

        assert len(result.quotes) == 1
        assert result.quotes[0].symbol == "GOOG"

    def test_parses_empty_quotes(self) -> None:
        """Should handle empty quotes list."""
        data = {"QuoteResponse": {"QuoteData": []}}

        result = QuoteResponse.from_api_response(data)

        assert len(result.quotes) == 0

    def test_handles_missing_quote_data(self) -> None:
        """Should handle missing QuoteData key."""
        data = {"QuoteResponse": {}}

        result = QuoteResponse.from_api_response(data)

        assert len(result.quotes) == 0


class TestQuote:
    """Tests for Quote model and properties."""

    def test_convenience_properties(self) -> None:
        """Should provide convenience properties from all_data."""
        data = {
            "symbol": "AAPL",
            "quoteStatus": "REALTIME",
            "All": {
                "lastTrade": "175.50",
                "change": "2.50",
                "changePct": "1.44",
                "previousClose": "173.00",
                "high": "176.00",
                "low": "172.00",
                "open": "173.50",
                "totalVolume": 50000000,
            },
        }

        quote = Quote.model_validate(data)

        assert quote.last_trade == Decimal("175.50")
        assert quote.change == Decimal("2.50")
        assert quote.change_pct == Decimal("1.44")
        assert quote.volume == 50000000

    def test_convenience_properties_none_without_all_data(self) -> None:
        """Should return None when all_data is missing."""
        data = {"symbol": "AAPL", "quoteStatus": "REALTIME"}

        quote = Quote.model_validate(data)

        assert quote.last_trade is None
        assert quote.change is None
        assert quote.change_pct is None
        assert quote.volume is None


class TestAllQuoteDetails:
    """Tests for AllQuoteDetails model."""

    def test_parses_complete_quote_details(self) -> None:
        """Should parse all available quote fields."""
        data = {
            "lastTrade": "175.50",
            "change": "2.50",
            "changePct": "1.44",
            "previousClose": "173.00",
            "high": "176.00",
            "low": "172.00",
            "open": "173.50",
            "high52": "200.00",
            "low52": "120.00",
            "totalVolume": 50000000,
            "averageVolume": 45000000,
            "bid": "175.45",
            "ask": "175.55",
            "bidSize": 100,
            "askSize": 200,
            "companyName": "Apple Inc.",
            "marketCap": "2750000000000",
            "peRatio": "28.5",
            "eps": "6.15",
            "dividend": "0.96",
            "dividendYield": "0.55",
            "sharesOutstanding": 15700000000,
        }

        details = AllQuoteDetails.model_validate(data)

        assert details.last_trade == Decimal("175.50")
        assert details.high_52 == Decimal("200.00")
        assert details.low_52 == Decimal("120.00")
        assert details.average_volume == 45000000
        assert details.company_name == "Apple Inc."
        assert details.pe_ratio == Decimal("28.5")

    def test_parses_minimal_quote_details(self) -> None:
        """Should parse with only required fields."""
        data = {
            "lastTrade": "175.50",
            "previousClose": "173.00",
            "high": "176.00",
            "low": "172.00",
            "open": "173.50",
            "totalVolume": 50000000,
        }

        details = AllQuoteDetails.model_validate(data)

        assert details.last_trade == Decimal("175.50")
        assert details.high_52 is None
        assert details.bid is None
        assert details.company_name is None

    def test_defaults_change_to_zero(self) -> None:
        """Should default change values to zero."""
        data = {
            "lastTrade": "175.50",
            "previousClose": "173.00",
            "high": "176.00",
            "low": "172.00",
            "open": "173.50",
            "totalVolume": 50000000,
        }

        details = AllQuoteDetails.model_validate(data)

        assert details.change == Decimal("0")
        assert details.change_pct == Decimal("0")


class TestOptionChain:
    """Tests for OptionChain.from_api_response."""

    def test_parses_option_chain_with_multiple_pairs(self) -> None:
        """Should parse option chain with multiple strike prices."""
        data = {
            "OptionChainResponse": {
                "OptionPair": [
                    {
                        "Call": {
                            "optionSymbol": "AAPL250117C00145000",
                            "optionType": "CALL",
                            "strikePrice": "145.00",
                            "expiryDate": "2025-01-17",
                            "bid": "32.50",
                            "ask": "33.00",
                            "lastPrice": "32.75",
                            "volume": 1500,
                            "openInterest": 5000,
                            "inTheMoney": True,
                        },
                        "Put": {
                            "optionSymbol": "AAPL250117P00145000",
                            "optionType": "PUT",
                            "strikePrice": "145.00",
                            "expiryDate": "2025-01-17",
                            "bid": "1.20",
                            "ask": "1.35",
                            "lastPrice": "1.25",
                            "volume": 800,
                            "openInterest": 3000,
                            "inTheMoney": False,
                        },
                    },
                    {
                        "Call": {
                            "optionSymbol": "AAPL250117C00150000",
                            "optionType": "CALL",
                            "strikePrice": "150.00",
                            "expiryDate": "2025-01-17",
                            "bid": "28.00",
                            "ask": "28.50",
                        },
                        "Put": {
                            "optionSymbol": "AAPL250117P00150000",
                            "optionType": "PUT",
                            "strikePrice": "150.00",
                            "expiryDate": "2025-01-17",
                            "bid": "2.50",
                            "ask": "2.75",
                        },
                    },
                ]
            }
        }

        result = OptionChain.from_api_response(data, "AAPL", date(2025, 1, 17))

        assert result.symbol == "AAPL"
        assert result.expiry_date == date(2025, 1, 17)
        assert len(result.option_pairs) == 2

        first_pair = result.option_pairs[0]
        assert first_pair.call is not None
        assert first_pair.call.strike_price == Decimal("145.00")
        assert first_pair.call.in_the_money is True
        assert first_pair.put is not None
        assert first_pair.put.strike_price == Decimal("145.00")
        assert first_pair.put.in_the_money is False

    def test_parses_single_option_pair_as_dict(self) -> None:
        """Should handle E*Trade's single-item-as-dict quirk."""
        data = {
            "OptionChainResponse": {
                "OptionPair": {
                    "Call": {
                        "optionSymbol": "AAPL250117C00150000",
                        "optionType": "CALL",
                        "strikePrice": "150.00",
                        "expiryDate": "2025-01-17",
                    },
                    "Put": {
                        "optionSymbol": "AAPL250117P00150000",
                        "optionType": "PUT",
                        "strikePrice": "150.00",
                        "expiryDate": "2025-01-17",
                    },
                }
            }
        }

        result = OptionChain.from_api_response(data, "AAPL", date(2025, 1, 17))

        assert len(result.option_pairs) == 1

    def test_parses_empty_option_chain(self) -> None:
        """Should handle empty option pairs."""
        data = {"OptionChainResponse": {"OptionPair": []}}

        result = OptionChain.from_api_response(data, "AAPL", date(2025, 1, 17))

        assert len(result.option_pairs) == 0


class TestOptionExpireDate:
    """Tests for OptionExpireDate.from_api_response."""

    def test_parses_multiple_expiration_dates(self) -> None:
        """Should parse multiple expiration dates."""
        data = {
            "OptionExpireDateResponse": {
                "ExpirationDate": [
                    {"year": 2025, "month": 1, "day": 17, "expiryType": "WEEKLY"},
                    {"year": 2025, "month": 1, "day": 24, "expiryType": "WEEKLY"},
                    {"year": 2025, "month": 2, "day": 21, "expiryType": "MONTHLY"},
                ]
            }
        }

        result = OptionExpireDate.from_api_response(data)

        assert len(result) == 3
        assert result[0].expiry_date == date(2025, 1, 17)
        assert result[0].expiry_type == "WEEKLY"
        assert result[1].expiry_date == date(2025, 1, 24)
        assert result[2].expiry_date == date(2025, 2, 21)
        assert result[2].expiry_type == "MONTHLY"

    def test_parses_single_expiration_date_as_dict(self) -> None:
        """Should handle E*Trade's single-item-as-dict quirk."""
        data = {
            "OptionExpireDateResponse": {
                "ExpirationDate": {"year": 2025, "month": 3, "day": 21, "expiryType": "QUARTERLY"}
            }
        }

        result = OptionExpireDate.from_api_response(data)

        assert len(result) == 1
        assert result[0].expiry_date == date(2025, 3, 21)
        assert result[0].expiry_type == "QUARTERLY"

    def test_parses_expiration_without_type(self) -> None:
        """Should handle missing expiryType."""
        data = {
            "OptionExpireDateResponse": {
                "ExpirationDate": {"year": 2025, "month": 1, "day": 17}
            }
        }

        result = OptionExpireDate.from_api_response(data)

        assert len(result) == 1
        assert result[0].expiry_date == date(2025, 1, 17)
        assert result[0].expiry_type is None

    def test_parses_empty_expirations(self) -> None:
        """Should handle empty expiration list."""
        data = {"OptionExpireDateResponse": {"ExpirationDate": []}}

        result = OptionExpireDate.from_api_response(data)

        assert len(result) == 0


class TestOptionDetails:
    """Tests for OptionDetails model."""

    def test_parses_complete_option_details(self) -> None:
        """Should parse option with all Greek values."""
        data = {
            "optionSymbol": "AAPL250117C00150000",
            "optionType": "CALL",
            "strikePrice": "150.00",
            "expiryDate": "2025-01-17",
            "bid": "28.00",
            "ask": "28.50",
            "lastPrice": "28.25",
            "volume": 5000,
            "openInterest": 15000,
            "impliedVolatility": "0.35",
            "delta": "0.85",
            "gamma": "0.02",
            "theta": "-0.15",
            "vega": "0.25",
            "rho": "0.10",
            "inTheMoney": True,
        }

        option = OptionDetails.model_validate(data)

        assert option.symbol == "AAPL250117C00150000"
        assert option.option_type == "CALL"
        assert option.strike_price == Decimal("150.00")
        assert option.delta == Decimal("0.85")
        assert option.gamma == Decimal("0.02")
        assert option.theta == Decimal("-0.15")
        assert option.in_the_money is True

    def test_parses_minimal_option_details(self) -> None:
        """Should parse option with only required fields."""
        data = {
            "optionSymbol": "AAPL250117C00150000",
            "optionType": "CALL",
            "strikePrice": "150.00",
            "expiryDate": "2025-01-17",
        }

        option = OptionDetails.model_validate(data)

        assert option.symbol == "AAPL250117C00150000"
        assert option.bid is None
        assert option.delta is None
        assert option.in_the_money is None


class TestOptionPair:
    """Tests for OptionPair model."""

    def test_parses_both_call_and_put(self) -> None:
        """Should parse pair with both call and put."""
        data = {
            "Call": {
                "optionSymbol": "AAPL250117C00150000",
                "optionType": "CALL",
                "strikePrice": "150.00",
                "expiryDate": "2025-01-17",
            },
            "Put": {
                "optionSymbol": "AAPL250117P00150000",
                "optionType": "PUT",
                "strikePrice": "150.00",
                "expiryDate": "2025-01-17",
            },
        }

        pair = OptionPair.model_validate(data)

        assert pair.call is not None
        assert pair.put is not None
        assert pair.call.option_type == "CALL"
        assert pair.put.option_type == "PUT"

    def test_parses_call_only(self) -> None:
        """Should handle pair with only call option."""
        data = {
            "Call": {
                "optionSymbol": "AAPL250117C00150000",
                "optionType": "CALL",
                "strikePrice": "150.00",
                "expiryDate": "2025-01-17",
            }
        }

        pair = OptionPair.model_validate(data)

        assert pair.call is not None
        assert pair.put is None

    def test_parses_put_only(self) -> None:
        """Should handle pair with only put option."""
        data = {
            "Put": {
                "optionSymbol": "AAPL250117P00150000",
                "optionType": "PUT",
                "strikePrice": "150.00",
                "expiryDate": "2025-01-17",
            }
        }

        pair = OptionPair.model_validate(data)

        assert pair.call is None
        assert pair.put is not None
