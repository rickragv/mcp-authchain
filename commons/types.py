"""Shared types used across mcp-server and agent-api."""

from dataclasses import dataclass


@dataclass
class FirebaseUser:
    """Authenticated Firebase user extracted from ID token."""

    uid: str
    email: str | None
    role: str
    scopes: list[str]
    id_token: str  # raw token, forwarded to MCP server
    claims: dict
