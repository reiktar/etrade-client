"""Market Data API endpoints."""

from typing import TYPE_CHECKING

from etrade_client.api.base import BaseAPI
from etrade_client.models.market import OptionChain, OptionExpireDate, QuoteResponse

if TYPE_CHECKING:
    from datetime import date


class MarketAPI(BaseAPI):
    """E*Trade Market Data API.

    Provides access to quotes, options chains, and market lookup.
    """

    async def get_quotes(
        self,
        symbols: list[str],
        *,
        detail_flag: str = "ALL",  # "ALL", "FUNDAMENTAL", "INTRADAY", "OPTIONS", "WEEK_52", "MF_DETAIL"
        require_earnings_date: bool = False,
        skip_mini_options: bool = True,
    ) -> QuoteResponse:
        """Get quotes for one or more symbols.

        Args:
            symbols: List of ticker symbols (max 25)
            detail_flag: Level of quote detail
            require_earnings_date: Include earnings date
            skip_mini_options: Skip mini options in response

        Returns:
            QuoteResponse with quotes for all symbols
        """
        if len(symbols) > 25:
            msg = "Maximum 25 symbols per request"
            raise ValueError(msg)

        # Symbols go in the URL path
        symbols_str = ",".join(symbols)
        params = {
            "detailFlag": detail_flag,
            "requireEarningsDate": str(require_earnings_date).lower(),
            "skipMiniOptionsCheck": str(skip_mini_options).lower(),
        }

        data = await self._get(f"/market/quote/{symbols_str}", params=params)
        return QuoteResponse.from_api_response(data)

    async def get_option_chains(
        self,
        symbol: str,
        expiry_date: date,
        *,
        strike_price_near: float | None = None,
        no_of_strikes: int | None = None,
        include_weekly: bool = True,
        skip_adjusted: bool = True,
        option_category: str = "STANDARD",  # "STANDARD", "ALL", "MINI"
        chain_type: str = "CALLPUT",  # "CALL", "PUT", "CALLPUT"
        price_type: str = "ATNM",  # "ATNM", "ALL"
    ) -> OptionChain:
        """Get options chain for a symbol.

        Args:
            symbol: Underlying symbol
            expiry_date: Expiration date
            strike_price_near: Center strikes around this price
            no_of_strikes: Number of strikes to return
            include_weekly: Include weekly options
            skip_adjusted: Skip adjusted options
            option_category: Option category filter
            chain_type: Type of options (calls, puts, or both)
            price_type: Strike price filter

        Returns:
            OptionChain with option contracts
        """
        params = {
            "symbol": symbol,
            "expiryYear": expiry_date.year,
            "expiryMonth": expiry_date.month,
            "expiryDay": expiry_date.day,
            "includeWeekly": str(include_weekly).lower(),
            "skipAdjusted": str(skip_adjusted).lower(),
            "optionCategory": option_category,
            "chainType": chain_type,
            "priceType": price_type,
        }
        if strike_price_near is not None:
            params["strikePriceNear"] = strike_price_near
        if no_of_strikes is not None:
            params["noOfStrikes"] = no_of_strikes

        data = await self._get("/market/optionchains", params=params)
        return OptionChain.from_api_response(data, symbol, expiry_date)

    async def get_option_expire_dates(
        self,
        symbol: str,
        *,
        expiry_type: str | None = None,  # "ALL", "MONTHLY", "WEEKLY"
    ) -> list[OptionExpireDate]:
        """Get available option expiration dates for a symbol.

        Args:
            symbol: Underlying symbol
            expiry_type: Filter by expiration type

        Returns:
            List of available expiration dates
        """
        params = {"symbol": symbol}
        if expiry_type:
            params["expiryType"] = expiry_type

        data = await self._get("/market/optionexpiredate", params=params)
        return OptionExpireDate.from_api_response(data)

    async def lookup(
        self,
        search: str,
    ) -> list[dict]:
        """Look up securities by name or partial symbol.

        Args:
            search: Search term (company name or symbol)

        Returns:
            List of matching securities
        """
        data = await self._get(f"/market/lookup/{search}")

        lookup_response = data.get("LookupResponse", {})
        results = lookup_response.get("Data", [])

        if isinstance(results, dict):
            results = [results]

        return results
