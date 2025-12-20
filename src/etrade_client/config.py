"""Configuration management for E*Trade client."""

import json
import os
from dataclasses import dataclass, field
from pathlib import Path


def _get_config_dir() -> Path:
    """Get XDG-compliant config directory."""
    xdg_config = os.environ.get("XDG_CONFIG_HOME")
    if xdg_config:
        return Path(xdg_config) / "etrade-client"
    return Path.home() / ".config" / "etrade-client"


@dataclass(frozen=True, slots=True)
class ETradeConfig:
    """E*Trade API configuration."""

    consumer_key: str
    consumer_secret: str
    sandbox: bool = True

    # API URLs
    _sandbox_base_url: str = field(default="https://apisb.etrade.com", repr=False)
    _production_base_url: str = field(default="https://api.etrade.com", repr=False)

    @property
    def base_url(self) -> str:
        """Get the appropriate base URL based on sandbox mode."""
        return self._sandbox_base_url if self.sandbox else self._production_base_url

    @property
    def oauth_base_url(self) -> str:
        """Get OAuth base URL."""
        return f"{self.base_url}/oauth"

    @property
    def api_base_url(self) -> str:
        """Get API v1 base URL."""
        return f"{self.base_url}/v1"

    @classmethod
    def from_env(cls, *, sandbox: bool = True) -> ETradeConfig:
        """Create config from environment variables.

        Expected env vars:
        - ETRADE_CONSUMER_KEY
        - ETRADE_CONSUMER_SECRET
        """
        consumer_key = os.environ.get("ETRADE_CONSUMER_KEY")
        consumer_secret = os.environ.get("ETRADE_CONSUMER_SECRET")

        if not consumer_key or not consumer_secret:
            msg = (
                "Missing required environment variables: "
                "ETRADE_CONSUMER_KEY and ETRADE_CONSUMER_SECRET"
            )
            raise ValueError(msg)

        return cls(
            consumer_key=consumer_key,
            consumer_secret=consumer_secret,
            sandbox=sandbox,
        )

    @classmethod
    def from_file(cls, path: Path | None = None, *, sandbox: bool = True) -> ETradeConfig:
        """Load config from JSON file.

        Default path: ~/.config/etrade-client/config.json

        Expected format:
        {
            "consumer_key": "...",
            "consumer_secret": "..."
        }
        """
        if path is None:
            path = _get_config_dir() / "config.json"

        if not path.exists():
            msg = f"Config file not found: {path}"
            raise FileNotFoundError(msg)

        with path.open() as f:
            data = json.load(f)

        return cls(
            consumer_key=data["consumer_key"],
            consumer_secret=data["consumer_secret"],
            sandbox=sandbox,
        )

    @classmethod
    def load(cls, *, sandbox: bool = True) -> ETradeConfig:
        """Load config from environment or file (env takes precedence)."""
        try:
            return cls.from_env(sandbox=sandbox)
        except ValueError:
            return cls.from_file(sandbox=sandbox)
