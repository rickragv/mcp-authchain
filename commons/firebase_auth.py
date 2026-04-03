"""Firebase Admin SDK init + ID token verification.

Used by agent-api's auth middleware. The MCP server uses its own pluggable
auth provider (mcp-server/auth/firebase.py) which is independent.
"""

import firebase_admin
from firebase_admin import auth as firebase_auth, credentials

from commons.config import settings
from commons.types import FirebaseUser

_firebase_app: firebase_admin.App | None = None


def _get_firebase_config() -> dict:
    """Get Firebase config from auth.providers.firebase in settings."""
    return settings.auth.providers.get("firebase", {})


def init_firebase() -> firebase_admin.App:
    """Initialize Firebase Admin SDK. Safe to call multiple times."""
    global _firebase_app
    if _firebase_app is not None:
        return _firebase_app

    config = _get_firebase_config()
    sa_path = config.get("service_account_path", ".secrets/firebase-service-account.json")
    cred = credentials.Certificate(sa_path)
    _firebase_app = firebase_admin.initialize_app(cred)
    return _firebase_app


def get_role_scopes(role: str) -> list[str]:
    """Map a role name to its scopes from settings.yaml."""
    role_config = settings.roles.get(role)
    if role_config:
        return role_config.scopes
    viewer = settings.roles.get("viewer")
    return viewer.scopes if viewer else []


def verify_token(token: str) -> FirebaseUser:
    """Verify a Firebase ID token and return a FirebaseUser."""
    decoded = firebase_auth.verify_id_token(token)

    scopes = decoded.get("scopes")
    if isinstance(scopes, str):
        scopes = scopes.split()
    elif not isinstance(scopes, list):
        role = decoded.get("role", "viewer")
        scopes = get_role_scopes(role)

    role = decoded.get("role", "viewer")

    return FirebaseUser(
        uid=decoded["sub"],
        email=decoded.get("email"),
        role=role,
        scopes=scopes,
        id_token=token,
        claims=decoded,
    )
