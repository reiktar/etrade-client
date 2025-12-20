"""OAuth 1.0a authentication for E*Trade API."""

import base64
import hashlib
import hmac
import secrets
import time
from typing import TYPE_CHECKING
from urllib.parse import parse_qs, quote, urlencode

import httpx

from etrade_client.exceptions import ETradeAuthError, ETradeTokenError
from etrade_client.models.auth import AccessToken, RequestToken

if TYPE_CHECKING:
    from etrade_client.config import ETradeConfig


class ETradeAuth:
    """OAuth 1.0a authentication handler for E*Trade API.

    Implements the full OAuth 1.0a flow:
    1. Get request token
    2. User authorization (manual step)
    3. Exchange verifier for access token
    4. Token renewal
    """

    def __init__(self, config: ETradeConfig) -> None:
        self.config = config
        self._access_token: AccessToken | None = None
        self._request_token: str | None = None
        self._request_token_secret: str | None = None

    @property
    def is_authenticated(self) -> bool:
        """Check if we have valid access tokens."""
        return self._access_token is not None

    @property
    def access_token(self) -> AccessToken | None:
        """Get current access token if authenticated."""
        return self._access_token

    def set_access_token(self, token: AccessToken) -> None:
        """Set access token (e.g., loaded from storage)."""
        self._access_token = token

    async def get_request_token(self) -> RequestToken:
        """Step 1: Get a request token to start OAuth flow.

        Returns a RequestToken with the authorization URL that the user
        must visit to authorize the application.
        """
        url = f"{self.config.oauth_base_url}/request_token"
        callback_url = "oob"  # Out-of-band for desktop apps

        oauth_params = self._build_oauth_params()
        oauth_params["oauth_callback"] = callback_url

        signature = self._generate_signature(
            method="GET",
            url=url,
            oauth_params=oauth_params,
            token_secret="",
        )
        oauth_params["oauth_signature"] = signature

        headers = {"Authorization": self._build_auth_header(oauth_params)}

        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=headers)

            if response.status_code != 200:
                raise ETradeAuthError(
                    f"Failed to get request token: {response.status_code} {response.text}",
                    stage="request_token",
                )

            # Parse response (URL-encoded)
            data = parse_qs(response.text)
            token = data.get("oauth_token", [""])[0]
            token_secret = data.get("oauth_token_secret", [""])[0]

            if not token or not token_secret:
                raise ETradeAuthError(
                    "Invalid request token response",
                    stage="request_token",
                )

        # Store for later use in access token exchange
        self._request_token = token
        self._request_token_secret = token_secret

        # Build authorization URL
        auth_url = (
            f"{self.config.base_url}/e/t/etws/authorize"
            f"?key={self.config.consumer_key}&token={token}"
        )

        return RequestToken(
            token=token,
            token_secret=token_secret,
            authorization_url=auth_url,
        )

    async def get_access_token(self, verifier: str) -> AccessToken:
        """Step 2: Exchange verifier code for access token.

        Args:
            verifier: The verification code shown to user after authorization

        Returns:
            AccessToken for API access
        """
        if not self._request_token or not self._request_token_secret:
            raise ETradeAuthError(
                "No request token available. Call get_request_token first.",
                stage="access_token",
            )

        url = f"{self.config.oauth_base_url}/access_token"

        oauth_params = self._build_oauth_params()
        oauth_params["oauth_token"] = self._request_token
        oauth_params["oauth_verifier"] = verifier

        signature = self._generate_signature(
            method="GET",
            url=url,
            oauth_params=oauth_params,
            token_secret=self._request_token_secret,
        )
        oauth_params["oauth_signature"] = signature

        headers = {"Authorization": self._build_auth_header(oauth_params)}

        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=headers)

            if response.status_code != 200:
                raise ETradeAuthError(
                    f"Failed to get access token: {response.status_code} {response.text}",
                    stage="access_token",
                )

            data = parse_qs(response.text)
            token = data.get("oauth_token", [""])[0]
            token_secret = data.get("oauth_token_secret", [""])[0]

            if not token or not token_secret:
                raise ETradeAuthError(
                    "Invalid access token response",
                    stage="access_token",
                )

        self._access_token = AccessToken(token=token, token_secret=token_secret)

        # Clear request tokens
        self._request_token = None
        self._request_token_secret = None

        return self._access_token

    async def renew_access_token(self) -> AccessToken:
        """Renew the current access token.

        Access tokens expire at midnight US Eastern time.
        Call this to extend the token for another day.
        """
        if not self._access_token:
            raise ETradeTokenError("No access token to renew", token_type="access")

        url = f"{self.config.oauth_base_url}/renew_access_token"

        oauth_params = self._build_oauth_params()
        oauth_params["oauth_token"] = self._access_token.token

        signature = self._generate_signature(
            method="GET",
            url=url,
            oauth_params=oauth_params,
            token_secret=self._access_token.token_secret,
        )
        oauth_params["oauth_signature"] = signature

        headers = {"Authorization": self._build_auth_header(oauth_params)}

        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=headers)

            if response.status_code != 200:
                # Token may be expired or invalid
                if response.status_code == 401:
                    raise ETradeTokenError(
                        "Access token expired or invalid",
                        token_type="access",
                        expired=True,
                    )
                raise ETradeAuthError(
                    f"Failed to renew token: {response.status_code} {response.text}",
                    stage="renewal",
                )

        # Token is renewed (same token, extended expiry)
        return self._access_token

    async def revoke_access_token(self) -> None:
        """Revoke the current access token."""
        if not self._access_token:
            raise ETradeTokenError("No access token to revoke", token_type="access")

        url = f"{self.config.oauth_base_url}/revoke_access_token"

        oauth_params = self._build_oauth_params()
        oauth_params["oauth_token"] = self._access_token.token

        signature = self._generate_signature(
            method="GET",
            url=url,
            oauth_params=oauth_params,
            token_secret=self._access_token.token_secret,
        )
        oauth_params["oauth_signature"] = signature

        headers = {"Authorization": self._build_auth_header(oauth_params)}

        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=headers)

            if response.status_code != 200:
                raise ETradeAuthError(
                    f"Failed to revoke token: {response.status_code} {response.text}",
                    stage="revocation",
                )

        self._access_token = None

    def sign_request(
        self,
        method: str,
        url: str,
        params: dict[str, str] | None = None,
    ) -> dict[str, str]:
        """Generate OAuth headers for an API request.

        Args:
            method: HTTP method (GET, POST, PUT, DELETE)
            url: Full request URL
            params: Additional parameters (query or body)

        Returns:
            Headers dict with Authorization header
        """
        if not self._access_token:
            raise ETradeTokenError(
                "Not authenticated. Complete OAuth flow first.",
                token_type="access",
            )

        oauth_params = self._build_oauth_params()
        oauth_params["oauth_token"] = self._access_token.token

        # Combine OAuth params with request params for signature
        all_params = {**oauth_params}
        if params:
            all_params.update(params)

        signature = self._generate_signature(
            method=method,
            url=url,
            oauth_params=all_params,
            token_secret=self._access_token.token_secret,
        )
        oauth_params["oauth_signature"] = signature

        return {"Authorization": self._build_auth_header(oauth_params)}

    def _build_oauth_params(self) -> dict[str, str]:
        """Build base OAuth parameters."""
        return {
            "oauth_consumer_key": self.config.consumer_key,
            "oauth_nonce": secrets.token_hex(16),
            "oauth_signature_method": "HMAC-SHA1",
            "oauth_timestamp": str(int(time.time())),
            "oauth_version": "1.0",
        }

    def _generate_signature(
        self,
        method: str,
        url: str,
        oauth_params: dict[str, str],
        token_secret: str,
    ) -> str:
        """Generate OAuth 1.0a HMAC-SHA1 signature."""
        # Sort and encode parameters
        sorted_params = sorted(oauth_params.items())
        param_string = urlencode(sorted_params, safe="")

        # Build signature base string
        base_string = "&".join(
            [
                method.upper(),
                quote(url, safe=""),
                quote(param_string, safe=""),
            ]
        )

        # Build signing key
        signing_key = (
            f"{quote(self.config.consumer_secret, safe='')}&{quote(token_secret, safe='')}"
        )

        # Generate HMAC-SHA1 signature
        signature = hmac.new(
            signing_key.encode(),
            base_string.encode(),
            hashlib.sha1,
        ).digest()

        return base64.b64encode(signature).decode()

    def _build_auth_header(self, oauth_params: dict[str, str]) -> str:
        """Build OAuth Authorization header."""
        auth_parts = [f'{k}="{quote(v, safe="")}"' for k, v in sorted(oauth_params.items())]
        return "OAuth " + ", ".join(auth_parts)
