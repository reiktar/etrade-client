"""CLI configuration with XDG-compliant paths and environment variable overrides."""

import json
import os
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path


class OutputFormat(StrEnum):
    """Output format options."""

    TABLE = "table"
    JSON = "json"
    CSV = "csv"


def _default_config_dir() -> Path:
    """Get XDG-compliant config directory for credentials.

    Uses XDG_CONFIG_HOME if set, otherwise ~/.config/etrade-cli.
    """
    xdg_config = os.environ.get("XDG_CONFIG_HOME")
    if xdg_config:
        return Path(xdg_config) / "etrade-cli"
    return Path.home() / ".config" / "etrade-cli"


def _default_data_dir() -> Path:
    """Get XDG-compliant data directory for tokens.

    Uses XDG_DATA_HOME if set, otherwise ~/.local/share/etrade-cli.
    """
    xdg_data = os.environ.get("XDG_DATA_HOME")
    if xdg_data:
        return Path(xdg_data) / "etrade-cli"
    return Path.home() / ".local" / "share" / "etrade-cli"


@dataclass
class CLIConfig:
    """Configuration passed through Typer context.

    Attributes:
        sandbox: Whether to use sandbox (True) or production (False) environment.
        verbose: Enable verbose output.
        config_dir: Directory for configuration files (credentials).
        data_dir: Directory for data files (tokens).

    Directory Structure:
        config_dir/
        ├── sandbox.json        # Sandbox credentials
        └── production.json     # Production credentials

        data_dir/
        ├── sandbox-token.json      # Sandbox OAuth token
        └── production-token.json   # Production OAuth token
    """

    sandbox: bool = True
    verbose: bool = False
    config_dir: Path = field(default_factory=_default_config_dir)
    data_dir: Path = field(default_factory=_default_data_dir)

    @property
    def environment(self) -> str:
        """Get the environment name."""
        return "sandbox" if self.sandbox else "production"

    @property
    def token_path(self) -> Path:
        """Get the token file path for current environment.

        Tokens are stored in the data directory (XDG_DATA_HOME).
        """
        return self.data_dir / f"{self.environment}-token.json"

    @property
    def credentials_path(self) -> Path:
        """Get the credentials file path for current environment.

        Credentials are stored in the config directory (XDG_CONFIG_HOME).
        """
        return self.config_dir / f"{self.environment}.json"

    def load_credentials(self) -> tuple[str, str]:
        """Load credentials from config file with environment variable overrides.

        Loading priority:
        1. Load from environment-specific config file (sandbox.json or production.json)
        2. Override individual values with environment variables if set

        Environment variables:
        - ETRADE_CONSUMER_KEY: Overrides consumer_key from file
        - ETRADE_CONSUMER_SECRET: Overrides consumer_secret from file

        Returns:
            Tuple of (consumer_key, consumer_secret)

        Raises:
            ValueError: If credentials cannot be determined from file or env vars
        """
        consumer_key: str | None = None
        consumer_secret: str | None = None

        # Step 1: Try to load from environment-specific config file
        if self.credentials_path.exists():
            try:
                with self.credentials_path.open() as f:
                    data = json.load(f)
                consumer_key = data.get("consumer_key")
                consumer_secret = data.get("consumer_secret")
            except (json.JSONDecodeError, OSError) as e:
                if self.verbose:
                    import sys

                    print(f"Warning: Failed to read {self.credentials_path}: {e}", file=sys.stderr)

        # Step 2: Override with environment variables (if set)
        if env_key := os.environ.get("ETRADE_CONSUMER_KEY"):
            consumer_key = env_key
        if env_secret := os.environ.get("ETRADE_CONSUMER_SECRET"):
            consumer_secret = env_secret

        # Step 3: Validate
        if not consumer_key or not consumer_secret:
            missing = []
            if not consumer_key:
                missing.append("consumer_key")
            if not consumer_secret:
                missing.append("consumer_secret")

            msg = (
                f"Missing credentials: {', '.join(missing)}. "
                f"Set via environment variables (ETRADE_CONSUMER_KEY, ETRADE_CONSUMER_SECRET) "
                f"or create config file at {self.credentials_path}"
            )
            raise ValueError(msg)

        return consumer_key, consumer_secret

    def save_credentials(self, consumer_key: str, consumer_secret: str) -> None:
        """Save credentials to the environment-specific config file.

        Args:
            consumer_key: E*Trade consumer key
            consumer_secret: E*Trade consumer secret
        """
        self.config_dir.mkdir(parents=True, exist_ok=True)

        data = {
            "consumer_key": consumer_key,
            "consumer_secret": consumer_secret,
        }

        with self.credentials_path.open("w") as f:
            json.dump(data, f, indent=2)

        # Set restrictive permissions (owner read/write only)
        self.credentials_path.chmod(0o600)

    def has_credentials(self) -> bool:
        """Check if credentials are available from file or environment.

        Returns:
            True if credentials can be loaded, False otherwise.
        """
        try:
            self.load_credentials()
            return True
        except ValueError:
            return False
