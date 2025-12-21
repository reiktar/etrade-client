"""CLI configuration."""

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
    """Get the default config directory respecting XDG."""
    xdg_config = os.environ.get("XDG_CONFIG_HOME")
    if xdg_config:
        return Path(xdg_config) / "etrade-cli"
    return Path.home() / ".config" / "etrade-cli"


@dataclass
class CLIConfig:
    """Configuration passed through Typer context."""

    sandbox: bool = True
    verbose: bool = False
    config_dir: Path = field(default_factory=_default_config_dir)

    @property
    def environment(self) -> str:
        """Get the environment name."""
        return "sandbox" if self.sandbox else "production"

    @property
    def token_path(self) -> Path:
        """Get the token file path for current environment."""
        return self.config_dir / f"tokens_{self.environment}.json"

    @property
    def credentials_path(self) -> Path:
        """Get the credentials file path for current environment."""
        return self.config_dir / f"credentials_{self.environment}.json"
