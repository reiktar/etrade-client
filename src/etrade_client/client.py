"""Main E*Trade client."""


from typing import TYPE_CHECKING

import httpx

from etrade_client.api.accounts import AccountsAPI
from etrade_client.api.alerts import AlertsAPI
from etrade_client.api.market import MarketAPI
from etrade_client.api.orders import OrdersAPI
from etrade_client.auth import ETradeAuth, TokenStore
from etrade_client.config import ETradeConfig
from etrade_client.models.auth import AccessToken

if TYPE_CHECKING:
    from types import TracebackType


class ETradeClient:
    """E*Trade API client.

    Provides a unified interface to E*Trade's APIs with OAuth authentication.

    Usage (context manager - recommended for connection pooling):
        async with ETradeClient(config) as client:
            accounts = await client.accounts.list_accounts()
            quotes = await client.market.get_quotes(["AAPL", "MSFT"])

    Usage (explicit lifecycle):
        client = ETradeClient(config)
        await client.open()
        try:
            accounts = await client.accounts.list_accounts()
        finally:
            await client.close()

    Usage (external HTTP client - shared across integrations):
        http_client = httpx.AsyncClient(timeout=30.0)
        client = ETradeClient(config, http_client=http_client)
        # Client uses shared pool, doesn't close it

    Usage (no pooling - creates connection per request):
        client = ETradeClient(config)
        accounts = await client.accounts.list_accounts()  # Per-request connection
    """

    def __init__(
        self,
        config: ETradeConfig,
        *,
        token_store: TokenStore | None = None,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        """Initialize the client.

        Args:
            config: E*Trade configuration with credentials
            token_store: Optional token storage (uses default if not provided)
            http_client: Optional httpx.AsyncClient for connection pooling.
                        If provided, the client will use this pool and NOT close it.
                        If not provided, use open()/close() or context manager to
                        enable pooling, or each request creates its own connection.
        """
        self.config = config
        self.token_store = token_store or TokenStore()
        self.auth = ETradeAuth(config)

        # HTTP client management
        self._http_client = http_client
        self._owns_http_client = http_client is None  # We manage lifecycle if not provided

        # Initialize API modules
        self.accounts = AccountsAPI(config, self.auth, http_client)
        self.alerts = AlertsAPI(config, self.auth, http_client)
        self.market = MarketAPI(config, self.auth, http_client)
        self.orders = OrdersAPI(config, self.auth, http_client)

    def _set_http_client(self, http_client: httpx.AsyncClient | None) -> None:
        """Update HTTP client on all API modules."""
        self._http_client = http_client
        self.accounts.set_http_client(http_client)
        self.alerts.set_http_client(http_client)
        self.market.set_http_client(http_client)
        self.orders.set_http_client(http_client)

    async def open(self) -> None:
        """Open connection pool for HTTP requests.

        Creates a shared httpx.AsyncClient for connection pooling.
        Only needed if not using context manager or external http_client.
        """
        if self._http_client is None and self._owns_http_client:
            http_client = httpx.AsyncClient(timeout=30.0)
            self._set_http_client(http_client)

    async def close(self) -> None:
        """Close connection pool.

        Only closes the pool if this client owns it (not external).
        """
        if self._owns_http_client and self._http_client is not None:
            await self._http_client.aclose()
            self._set_http_client(None)

    async def __aenter__(self) -> ETradeClient:
        """Async context manager entry - opens connection pool."""
        await self.open()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        """Async context manager exit - closes connection pool."""
        await self.close()

    @classmethod
    def from_env(cls, *, sandbox: bool = True) -> ETradeClient:
        """Create client from environment variables.

        Expects:
        - ETRADE_CONSUMER_KEY
        - ETRADE_CONSUMER_SECRET
        """
        config = ETradeConfig.from_env(sandbox=sandbox)
        return cls(config)

    @property
    def is_authenticated(self) -> bool:
        """Check if the client is authenticated."""
        return self.auth.is_authenticated

    def load_token(self) -> bool:
        """Load saved access token.

        Returns:
            True if token was loaded, False if no token saved
        """
        token = self.token_store.load()
        if token:
            self.auth.set_access_token(token)
            return True
        return False

    def save_token(self) -> None:
        """Save current access token."""
        if self.auth.access_token:
            self.token_store.save(self.auth.access_token)

    def clear_token(self) -> None:
        """Clear saved access token."""
        self.token_store.clear()

    def set_access_token(self, token: str, token_secret: str) -> None:
        """Set access token directly.

        Useful when you have tokens from another source.
        """
        self.auth.set_access_token(AccessToken(token=token, token_secret=token_secret))

    async def renew_token(self) -> None:
        """Renew the current access token.

        Tokens expire at midnight US Eastern. Call this to extend.
        """
        await self.auth.renew_access_token()

    async def revoke_token(self) -> None:
        """Revoke and clear the current access token."""
        await self.auth.revoke_access_token()
        self.clear_token()
