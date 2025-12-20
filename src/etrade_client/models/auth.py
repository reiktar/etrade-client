"""OAuth token models."""

from pydantic import BaseModel, Field


class RequestToken(BaseModel):
    """OAuth request token (first step of OAuth flow)."""

    token: str = Field(description="Request token value")
    token_secret: str = Field(description="Request token secret")
    authorization_url: str = Field(description="URL to redirect user for authorization")


class AccessToken(BaseModel):
    """OAuth access token (final step of OAuth flow)."""

    token: str = Field(description="Access token value")
    token_secret: str = Field(description="Access token secret")
