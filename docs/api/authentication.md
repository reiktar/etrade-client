# Authentication

E\*Trade uses OAuth 1.0a for authentication. This guide covers the complete authentication flow.

## OAuth Flow Overview

1. **Request Token** - Get temporary credentials from E\*Trade
2. **User Authorization** - User logs in and authorizes your app
3. **Access Token** - Exchange verifier for access token
4. **Token Renewal** - Extend token before midnight expiration

## First-Time Authentication

```python
from etrade_client import ETradeClient

async def authenticate():
    async with ETradeClient.from_env(sandbox=True) as client:
        # Step 1: Get request token with authorization URL
        request_token = await client.auth.get_request_token()

        # Step 2: User visits URL and authorizes
        print(f"Visit: {request_token.authorization_url}")

        # Step 3: User enters the verifier code
        verifier = input("Enter verifier code: ")

        # Step 4: Exchange for access token
        await client.auth.get_access_token(verifier.strip())

        # Step 5: Save token for future sessions
        client.save_token()

        print("Authentication successful!")
```

## Subsequent Sessions

```python
async with ETradeClient.from_env(sandbox=True) as client:
    if client.load_token():
        # Token loaded from storage
        await client.renew_token()  # Extend expiration
        print("Ready to use!")
    else:
        # No saved token, need full OAuth flow
        print("Please authenticate first")
```

## Token Expiration

E\*Trade tokens expire at **midnight US Eastern time**. To keep a token active:

```python
# Renew before midnight
await client.renew_token()
client.save_token()  # Save the renewed token
```

For long-running applications, schedule token renewal before midnight.

## Token Storage

Tokens are stored by default at:
- Linux/macOS: `~/.config/etrade-client/token.json`
- Windows: `%APPDATA%/etrade-client/token.json`

### Custom Token Storage

```python
from etrade_client.auth import TokenStore

# Custom path
token_store = TokenStore(path="/path/to/token.json")
client = ETradeClient(config, token_store=token_store)
```

### Programmatic Token Management

```python
# Set token directly (from database, vault, etc.)
client.set_access_token(token="...", token_secret="...")

# Check authentication status
if client.is_authenticated:
    print("Ready")

# Clear token
client.clear_token()
```

## Revoking Tokens

Revoke access when no longer needed:

```python
await client.revoke_token()  # Revokes on server and clears locally
```

## Auth Module Reference

### `client.auth.get_request_token()`

Initiates OAuth flow and returns request token with authorization URL.

**Returns:** `RequestToken`
- `token: str` - Request token
- `token_secret: str` - Request token secret
- `authorization_url: str` - URL for user authorization

### `client.auth.get_access_token(verifier)`

Exchanges verifier code for access token.

**Parameters:**
- `verifier: str` - Verification code from user

**Returns:** `AccessToken`

### `client.auth.renew_access_token()`

Extends token expiration. Call before midnight US Eastern.

### `client.auth.revoke_access_token()`

Revokes access token on E\*Trade server.

## Complete Example

```python
import asyncio
from etrade_client import ETradeClient

async def main():
    async with ETradeClient.from_env(sandbox=True) as client:
        # Try to load existing token
        if client.load_token():
            try:
                # Attempt to renew
                await client.renew_token()
                print("Token renewed successfully")
            except Exception:
                # Token invalid, need fresh auth
                print("Token expired, re-authenticating...")
                client.clear_token()
                await authenticate(client)
        else:
            # No token, authenticate
            await authenticate(client)

        # Now ready to use the client
        accounts = await client.accounts.list_accounts()
        print(f"Found {len(accounts.accounts)} accounts")

async def authenticate(client):
    request_token = await client.auth.get_request_token()
    print(f"Visit: {request_token.authorization_url}")
    verifier = input("Enter verifier code: ")
    await client.auth.get_access_token(verifier.strip())
    client.save_token()

asyncio.run(main())
```

## Environment-Specific Notes

### Sandbox

- Use sandbox credentials from E\*Trade Developer Portal
- Safe for testing, no real money involved
- Some features may behave differently than production

### Production

- Requires separate production credentials
- Additional E\*Trade approval may be required
- Real money - use with caution

```python
# Production mode
client = ETradeClient.from_env(sandbox=False)
```
