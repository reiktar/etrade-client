"""Integration tests for E*Trade client.

These tests run against the E*Trade sandbox API and require valid credentials.

Setup:
    1. Set environment variables (via .env.integration or otherwise):
       - ETRADE_SANDBOX_CONSUMER_KEY
       - ETRADE_SANDBOX_CONSUMER_SECRET

    2. Run the auth helper to obtain access tokens:
       python -m tests.integration.auth_helper

    3. Run integration tests:
       pytest tests/integration -m integration
"""
