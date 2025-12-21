"""Orders API endpoints."""

from collections.abc import AsyncIterator
from datetime import date
from typing import Any

from etrade_client.api.base import BaseAPI
from etrade_client.exceptions import ETradeValidationError
from etrade_client.models.orders import (
    Order,
    OrderListResponse,
    OrderPreviewResponse,
    PlaceOrderResponse,
)


class OrdersAPI(BaseAPI):
    """E*Trade Orders API.

    Provides access to order management - listing, previewing,
    placing, and canceling orders.
    """

    async def list_orders(
        self,
        account_id_key: str,
        *,
        marker: str | None = None,
        count: int | None = None,
        status: str
        | None = None,  # "OPEN", "EXECUTED", "CANCELLED", "INDIVIDUAL_FILLS", "CANCEL_REQUESTED", "EXPIRED", "REJECTED"
        from_date: date | None = None,
        to_date: date | None = None,
        symbol: str | None = None,
        security_type: str | None = None,  # "EQ", "OPTN", "MF", "MMF"
        transaction_type: str | None = None,  # "BUY", "SELL", "SHORT", "BUY_TO_COVER"
        market_session: str | None = None,  # "REGULAR", "EXTENDED"
    ) -> OrderListResponse:
        """List orders for an account.

        Args:
            account_id_key: Account ID key
            marker: Pagination marker from previous response
            count: Number of orders to return (max 100)
            status: Filter by order status
            from_date: Start date filter
            to_date: End date filter
            symbol: Filter by symbol
            security_type: Filter by security type
            transaction_type: Filter by transaction type
            market_session: Filter by market session

        Returns:
            OrderListResponse with orders
        """
        params: dict[str, Any] = {"count": min(count, 100) if count else 100}

        if marker:
            params["marker"] = marker
        if status:
            params["status"] = status
        if from_date:
            params["fromDate"] = from_date.strftime("%m%d%Y")
        if to_date:
            params["toDate"] = to_date.strftime("%m%d%Y")
        if symbol:
            params["symbol"] = symbol
        if security_type:
            params["securityType"] = security_type
        if transaction_type:
            params["transactionType"] = transaction_type
        if market_session:
            params["marketSession"] = market_session

        data = await self._get(f"/accounts/{account_id_key}/orders.json", params=params)
        return OrderListResponse.from_api_response(data)

    async def _iter_order_pages(
        self,
        account_id_key: str,
        *,
        count: int = 100,
        status: str | None = None,
        from_date: date | None = None,
        to_date: date | None = None,
        symbol: str | None = None,
        security_type: str | None = None,
        transaction_type: str | None = None,
        market_session: str | None = None,
    ) -> AsyncIterator[OrderListResponse]:
        """Internal: iterate over order pages.

        Yields pages lazily - next API call only happens when consumer iterates.
        """
        marker = None
        while True:
            page = await self.list_orders(
                account_id_key,
                marker=marker,
                count=count,
                status=status,
                from_date=from_date,
                to_date=to_date,
                symbol=symbol,
                security_type=security_type,
                transaction_type=transaction_type,
                market_session=market_session,
            )
            yield page

            if not page.has_more or not page.marker:
                break
            marker = page.marker

    async def iter_orders(
        self,
        account_id_key: str,
        *,
        count: int = 100,
        status: str | None = None,
        from_date: date | None = None,
        to_date: date | None = None,
        symbol: str | None = None,
        security_type: str | None = None,
        transaction_type: str | None = None,
        market_session: str | None = None,
        limit: int | None = None,
    ) -> AsyncIterator[Order]:
        """Iterate over orders matching the filters.

        Yields individual orders lazily. Next page is only fetched
        when the consumer continues iterating.

        Args:
            account_id_key: Account ID key
            count: Page size for API calls (max 100)
            status: Filter by order status
            from_date: Start date filter
            to_date: End date filter
            symbol: Filter by symbol
            security_type: Filter by security type
            transaction_type: Filter by transaction type
            market_session: Filter by market session
            limit: Maximum orders to yield (None = unlimited)

        Yields:
            Individual Order objects
        """
        yielded = 0
        async for page in self._iter_order_pages(
            account_id_key,
            count=count,
            status=status,
            from_date=from_date,
            to_date=to_date,
            symbol=symbol,
            security_type=security_type,
            transaction_type=transaction_type,
            market_session=market_session,
        ):
            for order in page.orders:
                if limit is not None and yielded >= limit:
                    return
                yield order
                yielded += 1

    async def preview_order(
        self,
        account_id_key: str,
        order: dict[str, Any],
    ) -> OrderPreviewResponse:
        """Preview an order before placing.

        The order dict should follow E*Trade's order format with
        'orderType', 'clientOrderId', 'Order' (list of order legs).

        Args:
            account_id_key: Account ID key
            order: Order specification

        Returns:
            OrderPreviewResponse with preview details and IDs
        """
        if "orderType" not in order:
            raise ETradeValidationError(
                "Order must include 'orderType'",
                field="orderType",
            )

        body = {"PreviewOrderRequest": order}
        data = await self._post(f"/accounts/{account_id_key}/orders/preview", body)
        return OrderPreviewResponse.from_api_response(data)

    async def place_order(
        self,
        account_id_key: str,
        order: dict[str, Any],
        preview_ids: list[dict[str, int]],
    ) -> PlaceOrderResponse:
        """Place a previewed order.

        Args:
            account_id_key: Account ID key
            order: Original order specification
            preview_ids: Preview IDs from preview response
                        Format: [{"previewId": 123}, ...]

        Returns:
            PlaceOrderResponse with order confirmation
        """
        if not preview_ids:
            raise ETradeValidationError(
                "preview_ids required - call preview_order first",
                field="previewIds",
            )

        body = {
            "PlaceOrderRequest": {
                **order,
                "PreviewIds": preview_ids,
            }
        }

        data = await self._post(f"/accounts/{account_id_key}/orders/place", body)
        return PlaceOrderResponse.from_api_response(data)

    async def cancel_order(
        self,
        account_id_key: str,
        order_id: int,
    ) -> dict[str, Any]:
        """Cancel an open order.

        Args:
            account_id_key: Account ID key
            order_id: Order ID to cancel

        Returns:
            Cancellation response
        """
        body = {
            "CancelOrderRequest": {
                "orderId": order_id,
            }
        }

        return await self._put(f"/accounts/{account_id_key}/orders/cancel", body)

    async def preview_change_order(
        self,
        account_id_key: str,
        order_id: int,
        order: dict[str, Any],
    ) -> OrderPreviewResponse:
        """Preview changes to an existing order.

        Args:
            account_id_key: Account ID key
            order_id: Existing order ID to modify
            order: New order specification

        Returns:
            OrderPreviewResponse with preview details
        """
        body = {"PreviewOrderRequest": order}
        data = await self._put(
            f"/accounts/{account_id_key}/orders/{order_id}/change/preview",
            body,
        )
        return OrderPreviewResponse.from_api_response(data)

    async def place_change_order(
        self,
        account_id_key: str,
        order_id: int,
        order: dict[str, Any],
        preview_ids: list[dict[str, int]],
    ) -> PlaceOrderResponse:
        """Place changes to an existing order.

        Args:
            account_id_key: Account ID key
            order_id: Existing order ID to modify
            order: New order specification
            preview_ids: Preview IDs from preview_change_order

        Returns:
            PlaceOrderResponse with confirmation
        """
        body = {
            "PlaceOrderRequest": {
                **order,
                "PreviewIds": preview_ids,
            }
        }

        data = await self._put(
            f"/accounts/{account_id_key}/orders/{order_id}/change/place",
            body,
        )
        return PlaceOrderResponse.from_api_response(data)

    # Convenience methods for building common order types

    @staticmethod
    def build_equity_order(
        *,
        symbol: str,
        action: str,  # "BUY", "SELL", "BUY_TO_COVER", "SELL_SHORT"
        quantity: int,
        order_type: str = "MARKET",  # "MARKET", "LIMIT", "STOP", "STOP_LIMIT"
        limit_price: float | None = None,
        stop_price: float | None = None,
        order_term: str = "GOOD_FOR_DAY",  # "GOOD_FOR_DAY", "GOOD_UNTIL_CANCEL", "IMMEDIATE_OR_CANCEL", "FILL_OR_KILL"
        market_session: str = "REGULAR",  # "REGULAR", "EXTENDED"
        all_or_none: bool = False,
        client_order_id: str | None = None,
    ) -> dict[str, Any]:
        """Build an equity order specification.

        This is a helper to construct the order dict for preview/place.
        """
        import secrets

        instrument = {
            "Product": {
                "symbol": symbol,
                "securityType": "EQ",
            },
            "orderAction": action,
            "quantityType": "QUANTITY",
            "quantity": quantity,
        }

        order_detail: dict[str, Any] = {
            "allOrNone": str(all_or_none).lower(),
            "priceType": order_type,
            "orderTerm": order_term,
            "marketSession": market_session,
            "Instrument": [instrument],
        }

        if limit_price is not None:
            order_detail["limitPrice"] = limit_price
        if stop_price is not None:
            order_detail["stopPrice"] = stop_price

        return {
            "orderType": "EQ",
            "clientOrderId": client_order_id or secrets.token_hex(8),
            "Order": [order_detail],
        }
