#!/usr/bin/env python3
"""OAuth authentication helper for integration tests.

This script runs the OAuth flow to obtain access tokens for integration testing.
Tokens are saved to tests/integration/.tokens.json for use by the test suite.

Prerequisites:
    Set environment variables (via .env.integration or otherwise):
    - ETRADE_SANDBOX_CONSUMER_KEY
    - ETRADE_SANDBOX_CONSUMER_SECRET

Usage:
    python -m tests.integration.auth_helper

The script will:
    1. Generate an authorization URL
    2. Prompt you to visit the URL and authorize the application
    3. Ask for the verification code
    4. Exchange the code for access tokens
    5. Save tokens to tests/integration/.tokens.json
"""

import asyncio
import os
import sys
from pathlib import Path

# Attempt to load .env.integration if it exists
try:
    from dotenv import load_dotenv

    env_file = Path(__file__).parent.parent.parent / ".env.integration"
    if env_file.exists():
        load_dotenv(env_file)
        print(f"Loaded environment from: {env_file}")
except ImportError:
    pass

from etrade_client import ETradeClient, ETradeConfig
from etrade_client.auth import TokenStore

# Token storage path (same as conftest.py uses)
TOKEN_PATH = Path(__file__).parent / ".tokens.json"


def get_config() -> ETradeConfig:
    """Load configuration from environment variables."""
    consumer_key = os.environ.get("ETRADE_SANDBOX_CONSUMER_KEY")
    consumer_secret = os.environ.get("ETRADE_SANDBOX_CONSUMER_SECRET")

    if not consumer_key or not consumer_secret:
        print("Error: Missing required environment variables.")
        print()
        print("Please set:")
        print("  ETRADE_SANDBOX_CONSUMER_KEY")
        print("  ETRADE_SANDBOX_CONSUMER_SECRET")
        print()
        print("You can set these via:")
        print("  - A .env.integration file in the project root")
        print("  - Shell environment variables")
        print("  - Any other mechanism")
        sys.exit(1)

    return ETradeConfig(
        consumer_key=consumer_key,
        consumer_secret=consumer_secret,
        sandbox=True,
    )


async def run_oauth_flow() -> None:
    """Run the OAuth flow and save tokens."""
    config = get_config()
    token_store = TokenStore(path=TOKEN_PATH)
    client = ETradeClient(config, token_store=token_store)

    print()
    print("=" * 60)
    print("E*Trade OAuth Authentication for Integration Tests")
    print("=" * 60)
    print()
    print(f"Using sandbox API: {config.base_url}")
    print()

    # Check if we already have tokens
    if token_store.has_token():
        print(f"Existing tokens found at: {TOKEN_PATH}")
        response = input("Replace existing tokens? [y/N]: ").strip().lower()
        if response != "y":
            print("Keeping existing tokens.")

            # Optionally try to renew
            response = input("Try to renew existing tokens? [y/N]: ").strip().lower()
            if response == "y":
                client.load_token()
                try:
                    await client.renew_token()
                    client.save_token()
                    print("Tokens renewed successfully!")
                except Exception as e:
                    print(f"Failed to renew tokens: {e}")
                    print("You may need to re-authenticate.")
            return

    # Step 1: Get request token
    print("Step 1: Getting request token...")
    try:
        request_token = await client.auth.get_request_token()
    except Exception as e:
        print(f"Error getting request token: {e}")
        sys.exit(1)

    # Step 2: User authorization
    print()
    print("Step 2: Please authorize the application")
    print()
    print("Visit this URL in your browser:")
    print()
    print(f"  {request_token.authorization_url}")
    print()
    print("After authorizing, E*Trade will display a verification code.")
    print()

    verifier = input("Enter the verification code: ").strip()

    if not verifier:
        print("No verification code provided. Aborting.")
        sys.exit(1)

    # Step 3: Exchange for access token
    print()
    print("Step 3: Exchanging for access token...")
    try:
        access_token = await client.auth.get_access_token(verifier)
    except Exception as e:
        print(f"Error getting access token: {e}")
        sys.exit(1)

    # Save tokens
    client.save_token()

    print()
    print("=" * 60)
    print("SUCCESS!")
    print("=" * 60)
    print()
    print(f"Access tokens saved to: {TOKEN_PATH}")
    print()
    print("You can now run integration tests:")
    print("  pytest tests/integration -m integration")
    print()
    print("Note: Tokens expire at midnight US Eastern time.")
    print("Run this script again or use client.renew_token() to extend.")


def main() -> None:
    """Entry point."""
    asyncio.run(run_oauth_flow())


if __name__ == "__main__":
    main()
