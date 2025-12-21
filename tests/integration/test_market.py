"""Integration tests for the Market API."""

import pytest


pytestmark = pytest.mark.integration


class TestMarketAPI:
    """Integration tests for MarketAPI."""

    async def test_get_quotes(self, async_integration_client, analyze_response) -> None:
        """Should get quotes from the sandbox."""
        client = async_integration_client

        response = await client.market.get_quotes(["AAPL", "MSFT"])

        assert response.quotes is not None
        # Sandbox may return different symbols than requested (mock data)
        assert len(response.quotes) >= 1

        # Analyze individual Quote models
        for quote in response.quotes:
            analyze_response(quote, "market/quotes/Quote")

        # Verify quote structure
        for quote in response.quotes:
            assert quote.symbol is not None
            # Sandbox returns mock data with last_trade via all_data
            assert quote.all_data is not None

    async def test_get_single_quote(self, async_integration_client, analyze_response) -> None:
        """Should get a single quote from the sandbox."""
        client = async_integration_client

        response = await client.market.get_quotes(["GOOG"])

        assert response.quotes is not None
        assert len(response.quotes) == 1
        assert response.quotes[0].symbol == "GOOG"

        # Analyze the Quote model
        analyze_response(response.quotes[0], "market/quote")

    async def test_get_option_chains(self, async_integration_client, analyze_response) -> None:
        """Should get option chains from the sandbox."""
        client = async_integration_client

        # Get option expiry dates first (returns list directly, not analyzable)
        expiry_dates = await client.market.get_option_expire_dates("AAPL")

        assert expiry_dates is not None
        assert len(expiry_dates) > 0

        # Get option chain for first expiry
        expiry = expiry_dates[0]
        chain_response = await client.market.get_option_chains(
            "AAPL",
            expiry_date=expiry.expiry_date,
        )

        # Analyze individual OptionPair models
        for pair in chain_response.option_pairs:
            analyze_response(pair, "market/optionchains/OptionPair")

        assert chain_response is not None
