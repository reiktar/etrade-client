"""Tests for order model parsing."""

from decimal import Decimal

import pytest

from etrade_client.models.orders import (
    OrderListResponse,
    OrderPreviewResponse,
    PlaceOrderResponse,
)


class TestOrderListResponse:
    """Tests for OrderListResponse.from_api_response."""

    def test_parses_multiple_orders(self) -> None:
        """Should parse response with multiple orders."""
        data = {
            "OrdersResponse": {
                "Order": [
                    {
                        "orderId": 12345,
                        "OrderDetail": {
                            "orderNumber": 1,
                            "accountId": "acc123",
                            "priceType": "LIMIT",
                            "orderTerm": "GOOD_FOR_DAY",
                            "marketSession": "REGULAR",
                            "status": "OPEN",
                            "limitPrice": "150.00",
                            "Instrument": [
                                {
                                    "Product": {
                                        "symbol": "AAPL",
                                        "securityType": "EQ",
                                    },
                                    "orderAction": "BUY",
                                    "orderedQuantity": 100,
                                }
                            ],
                        },
                    },
                    {
                        "orderId": 12346,
                        "OrderDetail": {
                            "orderNumber": 2,
                            "accountId": "acc123",
                            "priceType": "MARKET",
                            "orderTerm": "GOOD_FOR_DAY",
                            "marketSession": "REGULAR",
                            "status": "EXECUTED",
                            "Instrument": [
                                {
                                    "Product": {
                                        "symbol": "MSFT",
                                        "securityType": "EQ",
                                    },
                                    "orderAction": "SELL",
                                    "orderedQuantity": 50,
                                }
                            ],
                        },
                    },
                ],
                "marker": "next_page",
            }
        }

        result = OrderListResponse.from_api_response(data)

        assert len(result.orders) == 2
        assert result.orders[0].order_id == 12345
        assert result.orders[0].status == "OPEN"
        assert result.orders[0].symbol == "AAPL"
        assert result.orders[1].order_id == 12346
        assert result.orders[1].status == "EXECUTED"
        assert result.marker == "next_page"
        assert result.has_more is True

    def test_parses_single_order_as_dict(self) -> None:
        """Should handle E*Trade's single-item-as-dict quirk."""
        data = {
            "OrdersResponse": {
                "Order": {
                    "orderId": 12345,
                    "OrderDetail": {
                        "orderNumber": 1,
                        "accountId": "acc123",
                        "priceType": "LIMIT",
                        "orderTerm": "GOOD_FOR_DAY",
                        "marketSession": "REGULAR",
                        "status": "OPEN",
                        "Instrument": [
                            {
                                "Product": {"symbol": "AAPL", "securityType": "EQ"},
                                "orderAction": "BUY",
                                "orderedQuantity": 100,
                            }
                        ],
                    },
                }
            }
        }

        result = OrderListResponse.from_api_response(data)

        assert len(result.orders) == 1
        assert result.orders[0].order_id == 12345

    def test_parses_empty_orders(self) -> None:
        """Should handle empty orders list."""
        data = {"OrdersResponse": {"Order": []}}

        result = OrderListResponse.from_api_response(data)

        assert len(result.orders) == 0
        assert result.has_more is False

    def test_has_more_with_marker(self) -> None:
        """has_more should be True when marker exists."""
        data = {
            "OrdersResponse": {
                "Order": [],
                "marker": "page_token",
            }
        }

        result = OrderListResponse.from_api_response(data)

        assert result.has_more is True

    def test_has_more_with_next(self) -> None:
        """has_more should be True when next exists."""
        data = {
            "OrdersResponse": {
                "Order": [],
                "next": "page_token",
            }
        }

        result = OrderListResponse.from_api_response(data)

        assert result.has_more is True

    def test_order_with_option(self) -> None:
        """Should parse option order correctly."""
        data = {
            "OrdersResponse": {
                "Order": {
                    "orderId": 12345,
                    "OrderDetail": {
                        "orderNumber": 1,
                        "accountId": "acc123",
                        "priceType": "LIMIT",
                        "orderTerm": "GOOD_FOR_DAY",
                        "marketSession": "REGULAR",
                        "status": "OPEN",
                        "limitPrice": "2.50",
                        "Instrument": [
                            {
                                "Product": {
                                    "symbol": "AAPL250117C00150000",
                                    "securityType": "OPTN",
                                    "callPut": "CALL",
                                    "expiryYear": 2025,
                                    "expiryMonth": 1,
                                    "expiryDay": 17,
                                    "strikePrice": "150.00",
                                },
                                "orderAction": "BUY_OPEN",
                                "orderedQuantity": 5,
                            }
                        ],
                    },
                }
            }
        }

        result = OrderListResponse.from_api_response(data)

        assert len(result.orders) == 1
        instrument = result.orders[0].details.instruments[0]
        assert instrument.product.security_type == "OPTN"
        assert instrument.product.call_put == "CALL"
        assert instrument.product.strike_price == Decimal("150.00")


class TestOrderPreviewResponse:
    """Tests for OrderPreviewResponse.from_api_response."""

    def test_parses_preview_response(self) -> None:
        """Should parse order preview response."""
        data = {
            "PreviewOrderResponse": {
                "orderType": "EQ",
                "totalOrderValue": "15000.00",
                "estimatedCommission": "0.00",
                "estimatedTotalAmount": "15000.00",
                "PreviewIds": [
                    {"previewId": 123456},
                    {"previewId": 123457},
                ],
                "Order": [
                    {"priceType": "LIMIT", "limitPrice": "150.00"}
                ],
            }
        }

        result = OrderPreviewResponse.from_api_response(data)

        assert result.preview.order_type == "EQ"
        assert result.preview.total_order_value == Decimal("15000.00")
        assert len(result.preview.preview_ids) == 2
        assert result.preview.preview_id_values == [123456, 123457]

    def test_parses_preview_without_ids(self) -> None:
        """Should handle preview without PreviewIds."""
        data = {
            "PreviewOrderResponse": {
                "orderType": "EQ",
            }
        }

        result = OrderPreviewResponse.from_api_response(data)

        assert result.preview.order_type == "EQ"
        assert result.preview.preview_id_values == []


class TestPlaceOrderResponse:
    """Tests for PlaceOrderResponse.from_api_response."""

    def test_parses_place_order_response(self) -> None:
        """Should parse place order response."""
        data = {
            "PlaceOrderResponse": {
                "orderId": 12345,
                "orderNum": 1,
                "placedTime": "2025-01-15T10:30:00",
                "Order": [
                    {"status": "OPEN"}
                ],
            }
        }

        result = PlaceOrderResponse.from_api_response(data)

        assert result.order.order_id == 12345
        assert result.order.order_num == 1
