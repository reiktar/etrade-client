"""Pytest configuration for integration tests.

Integration tests require:
- ETRADE_SANDBOX_CONSUMER_KEY and ETRADE_SANDBOX_CONSUMER_SECRET environment variables
- Valid access tokens (obtained via auth_helper.py)

Environment variables can be set via:
- .env.integration file (loaded if present)
- Shell environment
- CI/CD secrets
- Any other mechanism - the tests only care that the vars exist

Field Analysis:
Integration tests automatically analyze API responses to detect unknown fields.
A summary of any unknown fields is printed at the end of the test session.
Use @pytest.mark.no_field_analysis to disable for specific tests.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from tests.integration.field_analyzer import FieldAnalysisCollector

if TYPE_CHECKING:
    from collections.abc import Callable

    from pydantic import BaseModel

    from etrade_client import ETradeClient, ETradeConfig
    from etrade_client.auth import TokenStore

# Attempt to load .env.integration if it exists (optional)
try:
    from dotenv import load_dotenv

    env_file = Path(__file__).parent.parent.parent / ".env.integration"
    if env_file.exists():
        load_dotenv(env_file)
except ImportError:
    pass


def _get_env_or_skip(var_name: str) -> str:
    """Get environment variable or skip test."""
    value = os.environ.get(var_name)
    if not value:
        pytest.skip(f"Missing required environment variable: {var_name}")
    return value


# Token storage path for integration tests
INTEGRATION_TOKEN_PATH = Path(__file__).parent / ".tokens.json"


# =============================================================================
# Field Analysis Infrastructure
# =============================================================================

# Session-scoped collector
_collector: FieldAnalysisCollector | None = None


def pytest_configure(config: pytest.Config) -> None:
    """Configure pytest with custom markers."""
    config.addinivalue_line(
        "markers",
        "no_field_analysis: Disable field analysis for this test",
    )


def pytest_sessionstart(session: pytest.Session) -> None:
    """Initialize field analysis collector at session start."""
    global _collector
    _collector = FieldAnalysisCollector()


def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
    """Print field analysis summary at session end."""
    if _collector and _collector.has_unknown_fields:
        print("\n")
        print("=" * 70)
        print(_collector.get_summary())
        print("=" * 70)


@pytest.fixture(scope="session")
def field_collector() -> FieldAnalysisCollector:
    """Get the field analysis collector."""
    global _collector
    if _collector is None:
        _collector = FieldAnalysisCollector()
    return _collector


# =============================================================================
# Client Fixtures
# =============================================================================


@pytest.fixture(scope="session")
def integration_config() -> ETradeConfig:
    """Get E*Trade configuration for integration tests."""
    from etrade_client import ETradeConfig

    consumer_key = _get_env_or_skip("ETRADE_SANDBOX_CONSUMER_KEY")
    consumer_secret = _get_env_or_skip("ETRADE_SANDBOX_CONSUMER_SECRET")

    config = ETradeConfig(
        consumer_key=consumer_key,
        consumer_secret=consumer_secret,
        sandbox=True,
    )

    assert "apisb.etrade.com" in config.base_url, "Integration tests must use sandbox"
    return config


@pytest.fixture(scope="session")
def integration_token_store() -> TokenStore:
    """Get token store for integration tests."""
    from etrade_client.auth import TokenStore

    return TokenStore(path=INTEGRATION_TOKEN_PATH)


@pytest.fixture
async def async_integration_client(
    integration_config: ETradeConfig,
    integration_token_store: TokenStore,
    field_collector: FieldAnalysisCollector,
) -> ETradeClient:
    """Get an authenticated E*Trade client for integration tests.

    This client uses a capturing HTTP client to record raw API responses
    for field analysis.

    Note: Function-scoped because httpx.AsyncClient must be created
    in the same event loop where it will be used.
    """
    from etrade_client import ETradeClient

    # Create client with capturing HTTP client
    http_client = field_collector.response_capture.create_client(timeout=30.0)
    client = ETradeClient(
        integration_config,
        token_store=integration_token_store,
        http_client=http_client,
    )

    # Check for tokens
    access_token = os.environ.get("ETRADE_SANDBOX_ACCESS_TOKEN")
    access_secret = os.environ.get("ETRADE_SANDBOX_ACCESS_TOKEN_SECRET")

    if access_token and access_secret:
        client.set_access_token(access_token, access_secret)
    elif client.load_token():
        pass
    else:
        pytest.skip(
            "No access tokens available. "
            "Run: python -m tests.integration.auth_helper"
        )

    yield client

    await http_client.aclose()


# =============================================================================
# Analysis Fixture
# =============================================================================


@pytest.fixture
def analyze_response(
    field_collector: FieldAnalysisCollector,
    request: pytest.FixtureRequest,
) -> Callable[[BaseModel, str], None]:
    """Fixture that provides a function to analyze the last API response.

    Usage in tests:
        async def test_something(async_integration_client, analyze_response):
            response = await client.accounts.list_accounts()
            analyze_response(response, "accounts/list")

    The analysis results are collected and summarized at session end.
    """
    if request.node.get_closest_marker("no_field_analysis"):
        def _noop(model_instance: BaseModel, endpoint: str) -> None:
            pass
        return _noop

    def _analyze(model_instance: BaseModel, endpoint: str) -> None:
        field_collector.analyze(model_instance, endpoint)

    return _analyze
