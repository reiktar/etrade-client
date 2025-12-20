"""Token storage and persistence."""

import json
import os
from dataclasses import dataclass
from pathlib import Path

from etrade_client.models.auth import AccessToken


def _get_token_path() -> Path:
    """Get default token storage path."""
    xdg_data = os.environ.get("XDG_DATA_HOME")
    base = Path(xdg_data) if xdg_data else Path.home() / ".local" / "share"
    return base / "etrade-client" / "tokens.json"


@dataclass
class TokenStore:
    """Persistent storage for OAuth tokens.

    Stores tokens in a JSON file. For production use, consider
    encrypting the file or using a secrets manager.
    """

    path: Path

    def __init__(self, path: Path | None = None) -> None:
        self.path = path or _get_token_path()

    def save(self, token: AccessToken) -> None:
        """Save access token to storage."""
        self.path.parent.mkdir(parents=True, exist_ok=True)

        data = {
            "token": token.token,
            "token_secret": token.token_secret,
        }

        with self.path.open("w") as f:
            json.dump(data, f, indent=2)

        # Set restrictive permissions (owner read/write only)
        self.path.chmod(0o600)

    def load(self) -> AccessToken | None:
        """Load access token from storage.

        Returns None if no token is stored or file doesn't exist.
        """
        if not self.path.exists():
            return None

        try:
            with self.path.open() as f:
                data = json.load(f)
            return AccessToken(
                token=data["token"],
                token_secret=data["token_secret"],
            )
        except (json.JSONDecodeError, KeyError):
            return None

    def clear(self) -> None:
        """Remove stored token."""
        if self.path.exists():
            self.path.unlink()

    def has_token(self) -> bool:
        """Check if a token is stored."""
        return self.path.exists()
