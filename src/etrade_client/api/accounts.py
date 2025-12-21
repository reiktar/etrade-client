"""Accounts API endpoints."""

from collections.abc import AsyncIterator
from datetime import date
from typing import Any

from etrade_client.api.base import BaseAPI
from etrade_client.models.accounts import (
    AccountListResponse,
    BalanceResponse,
    PortfolioResponse,
)
from etrade_client.models.transactions import Transaction, TransactionListResponse


class AccountsAPI(BaseAPI):
    """E*Trade Accounts API.

    Provides access to account information, balances, and portfolio.
    """

    async def list_accounts(self) -> AccountListResponse:
        """List all accounts for the authenticated user.

        Returns:
            AccountListResponse with list of accounts
        """
        data = await self._get("/accounts/list.json")
        return AccountListResponse.from_api_response(data)

    async def get_balance(
        self,
        account_id_key: str,
        *,
        account_type: str | None = None,
        real_time: bool = True,
    ) -> BalanceResponse:
        """Get account balance.

        Args:
            account_id_key: The account ID key (from list_accounts)
            account_type: Account type filter (optional)
            real_time: Whether to get real-time balance (default: True)

        Returns:
            BalanceResponse with balance details
        """
        params = {
            "instType": "BROKERAGE",
            "realTimeNAV": str(real_time).lower(),
        }
        if account_type:
            params["accountType"] = account_type

        data = await self._get(f"/accounts/{account_id_key}/balance.json", params=params)
        return BalanceResponse.from_api_response(data)

    async def get_portfolio(
        self,
        account_id_key: str,
        *,
        count: int | None = None,
        sort_by: str | None = None,
        sort_order: str | None = None,  # "ASC" or "DESC"
        market_session: str | None = None,  # "REGULAR" or "EXTENDED"
        totals_required: bool = True,
        lots_required: bool = False,
        view: str = "QUICK",  # "PERFORMANCE", "FUNDAMENTAL", "OPTIONSWATCH", "QUICK", "COMPLETE"
    ) -> PortfolioResponse:
        """Get account portfolio/positions.

        Args:
            account_id_key: The account ID key
            count: Number of positions to return
            sort_by: Field to sort by
            sort_order: Sort direction ("ASC" or "DESC")
            market_session: Market session ("REGULAR" or "EXTENDED")
            totals_required: Include totals in response
            lots_required: Include lot details
            view: View type for position data

        Returns:
            PortfolioResponse with positions
        """
        params: dict[str, Any] = {
            "totalsRequired": str(totals_required).lower(),
            "lotsRequired": str(lots_required).lower(),
            "view": view,
        }
        if count:
            params["count"] = count
        if sort_by:
            params["sortBy"] = sort_by
        if sort_order:
            params["sortOrder"] = sort_order
        if market_session:
            params["marketSession"] = market_session

        data = await self._get(f"/accounts/{account_id_key}/portfolio.json", params=params)
        return PortfolioResponse.from_api_response(data, account_id_key)

    async def list_transactions(
        self,
        account_id_key: str,
        *,
        start_date: date | None = None,
        end_date: date | None = None,
        sort_order: str = "DESC",
        marker: str | None = None,
        count: int = 50,
    ) -> TransactionListResponse:
        """List transactions for an account.

        Args:
            account_id_key: The account ID key
            start_date: Start date for transaction range
            end_date: End date for transaction range
            sort_order: Sort order ("ASC" or "DESC", default: DESC)
            marker: Pagination marker from previous response
            count: Number of transactions to return (max 50)

        Returns:
            TransactionListResponse with transactions
        """
        params: dict[str, Any] = {
            "count": min(count, 50),
            "sortOrder": sort_order,
        }

        if start_date:
            params["startDate"] = start_date.strftime("%m%d%Y")
        if end_date:
            params["endDate"] = end_date.strftime("%m%d%Y")
        if marker:
            params["marker"] = marker

        data = await self._get(f"/accounts/{account_id_key}/transactions.json", params=params)
        return TransactionListResponse.from_api_response(data)

    async def _iter_transaction_pages(
        self,
        account_id_key: str,
        *,
        start_date: date | None = None,
        end_date: date | None = None,
        sort_order: str = "DESC",
        count: int = 50,
    ) -> AsyncIterator[TransactionListResponse]:
        """Internal: iterate over transaction pages.

        Yields pages lazily - next API call only happens when consumer iterates.
        """
        marker = None
        while True:
            page = await self.list_transactions(
                account_id_key,
                start_date=start_date,
                end_date=end_date,
                sort_order=sort_order,
                marker=marker,
                count=count,
            )
            yield page

            if not page.has_more or not page.marker:
                break
            marker = page.marker

    async def iter_transactions(
        self,
        account_id_key: str,
        *,
        start_date: date | None = None,
        end_date: date | None = None,
        sort_order: str = "DESC",
        count: int = 50,
        limit: int | None = None,
    ) -> AsyncIterator[Transaction]:
        """Iterate over transactions matching the filters.

        Yields individual transactions lazily. Next page is only fetched
        when the consumer continues iterating.

        Note: The E*Trade API has a pagination quirk where the last transaction
        of each page may be duplicated as the first transaction of the next page.
        This method automatically deduplicates by transaction_id.

        Args:
            account_id_key: The account ID key
            start_date: Start date for transaction range
            end_date: End date for transaction range
            sort_order: Sort order ("ASC" or "DESC", default: DESC)
            count: Page size for API calls (max 50)
            limit: Maximum transactions to yield (None = unlimited)

        Yields:
            Individual Transaction objects
        """
        yielded = 0
        seen_ids: set[str] = set()

        async for page in self._iter_transaction_pages(
            account_id_key,
            start_date=start_date,
            end_date=end_date,
            sort_order=sort_order,
            count=count,
        ):
            for tx in page.transactions:
                # Skip duplicates (E*Trade API pagination quirk)
                if tx.transaction_id in seen_ids:
                    continue
                seen_ids.add(tx.transaction_id)

                if limit is not None and yielded >= limit:
                    return
                yield tx
                yielded += 1
