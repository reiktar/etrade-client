"""Main E*Trade client."""

from etrade_client.api.accounts import AccountsAPI
from etrade_client.api.alerts import AlertsAPI
from etrade_client.api.market import MarketAPI
from etrade_client.api.orders import OrdersAPI
from etrade_client.auth import ETradeAuth, TokenStore
from etrade_client.config import ETradeConfig
from etrade_client.models.auth import AccessToken


class ETradeClient:
    """E*Trade API client.

    Provides a unified interface to E*Trade's APIs with OAuth authentication.

    Usage:
        # Create client
        config = ETradeConfig.from_env(sandbox=True)
        client = ETradeClient(config)

        # Authenticate (first time)
        request_token = await client.auth.get_request_token()
        print(f"Visit: {request_token.authorization_url}")
        verifier = input("Enter verifier: ")
        await client.auth.get_access_token(verifier)

        # Save token for later
        client.save_token()

        # Use APIs
        accounts = await client.accounts.list_accounts()
        quotes = await client.market.get_quotes(["AAPL", "MSFT"])
    """

    def __init__(
        self,
        config: ETradeConfig,
        *,
        token_store: TokenStore | None = None,
    ) -> None:
        """Initialize the client.

        Args:
            config: E*Trade configuration with credentials
            token_store: Optional token storage (uses default if not provided)
        """
        self.config = config
        self.token_store = token_store or TokenStore()
        self.auth = ETradeAuth(config)

        # Initialize API modules
        self.accounts = AccountsAPI(config, self.auth)
        self.alerts = AlertsAPI(config, self.auth)
        self.market = MarketAPI(config, self.auth)
        self.orders = OrdersAPI(config, self.auth)

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
