"""Firebase auth provider for MCP server."""

import firebase_admin
from firebase_admin import auth as firebase_auth, credentials
from typing import Callable

from commons.types import FirebaseUser

_state = {"app": None}


def create_verifier(config: dict) -> Callable[[str], FirebaseUser]:
    """Create a Firebase token verifier from config.

    Config keys:
        project_id: Firebase project ID
        service_account_path: Path to service account JSON
    """

    def _init():
        if _state["app"] is not None:
            return
        sa_path = config.get("service_account_path", ".secrets/firebase-service-account.json")
        cred = credentials.Certificate(sa_path)
        _state["app"] = firebase_admin.initialize_app(cred)

    def verify(token: str) -> FirebaseUser:
        _init()
        decoded = firebase_auth.verify_id_token(token)

        # Extract scopes from custom claims or map from role
        scopes = decoded.get("scopes")
        if isinstance(scopes, str):
            scopes = scopes.split()
        elif not isinstance(scopes, list):
            scopes = _role_scopes(config, decoded.get("role", "viewer"))

        return FirebaseUser(
            uid=decoded["sub"],
            email=decoded.get("email"),
            role=decoded.get("role", "viewer"),
            scopes=scopes,
            id_token=token,
            claims=decoded,
        )

    return verify


def _role_scopes(config: dict, role: str) -> list[str]:
    """Map role to scopes from config. Falls back to empty."""
    roles = config.get("roles", {})
    return roles.get(role, roles.get("viewer", {}).get("scopes", []))
