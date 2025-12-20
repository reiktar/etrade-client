"""Base API client with common functionality."""

import logging
from typing import TYPE_CHECKING, Any

import httpx

from etrade_client.exceptions import ETradeAPIError, ETradeRateLimitError

if TYPE_CHECKING:
    from etrade_client.auth import ETradeAuth
    from etrade_client.config import ETradeConfig

logger = logging.getLogger(__name__)


class BaseAPI:
    """Base class for E*Trade API endpoints.

    Provides common HTTP functionality with OAuth signing,
    error handling, and response parsing.
    """

    def __init__(
        self,
        config: ETradeConfig,
        auth: ETradeAuth,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self.config = config
        self.auth = auth
        self._http_client = http_client

    def set_http_client(self, http_client: httpx.AsyncClient | None) -> None:
        """Set the shared HTTP client for connection pooling."""
        self._http_client = http_client

    async def _request(
        self,
        method: str,
        endpoint: str,
        *,
        params: dict[str, Any] | None = None,
        json_body: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Make an authenticated API request.

        Args:
            method: HTTP method
            endpoint: API endpoint (e.g., "/accounts/list")
            params: Query parameters
            json_body: JSON request body

        Returns:
            Parsed JSON response

        Raises:
            ETradeAPIError: On API error
            ETradeRateLimitError: On rate limit (429)
        """
        url = f"{self.config.api_base_url}{endpoint}"

        # Build query string params for signature
        query_params: dict[str, str] = {}
        if params:
            query_params = {k: str(v) for k, v in params.items() if v is not None}

        # Sign the request
        headers = self.auth.sign_request(method, url, query_params if query_params else None)
        headers["Accept"] = "application/json"

        if json_body:
            headers["Content-Type"] = "application/json"

        logger.debug("Request: %s %s", method, url)
        logger.debug("Params: %s", query_params)

        if self._http_client is not None:
            # Use shared connection pool
            response = await self._http_client.request(
                method,
                url,
                params=query_params if query_params else None,
                json=json_body,
                headers=headers,
            )
        else:
            # Fallback: create per-request client (no pooling)
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.request(
                    method,
                    url,
                    params=query_params if query_params else None,
                    json=json_body,
                    headers=headers,
                )

        return self._handle_response(response)

    def _handle_response(self, response: httpx.Response) -> dict[str, Any]:
        """Handle API response, raising appropriate errors."""
        if response.status_code == 429:
            retry_after = response.headers.get("Retry-After")
            raise ETradeRateLimitError(
                "Rate limit exceeded",
                retry_after=int(retry_after) if retry_after else None,
            )

        if response.status_code >= 400:
            try:
                error_body = response.json()
            except Exception:
                error_body = None

            error_msg = f"API error: {response.status_code}"
            if error_body:
                # E*Trade error format
                error_detail = error_body.get("Error", {})
                if error_detail:
                    error_msg = error_detail.get("message", error_msg)

            raise ETradeAPIError(
                error_msg,
                status_code=response.status_code,
                response_body=error_body,
            )

        if response.status_code == 204:
            return {}

        return response.json()

    async def _get(
        self,
        endpoint: str,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Make a GET request."""
        return await self._request("GET", endpoint, params=params)

    async def _post(
        self,
        endpoint: str,
        json_body: dict[str, Any],
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Make a POST request."""
        return await self._request("POST", endpoint, params=params, json_body=json_body)

    async def _put(
        self,
        endpoint: str,
        json_body: dict[str, Any],
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Make a PUT request."""
        return await self._request("PUT", endpoint, params=params, json_body=json_body)

    async def _delete(
        self,
        endpoint: str,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Make a DELETE request."""
        return await self._request("DELETE", endpoint, params=params)
