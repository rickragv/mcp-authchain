"""JWT minting and verification for OAuth-issued access tokens.

Uses the Firebase service account's RSA private key for signing (RS256),
so no separate JWT secret is needed.
"""

import json
import time
from typing import Callable

import jwt
from cryptography.hazmat.primitives.serialization import load_pem_private_key

from commons.types import FirebaseUser


def _load_sa_private_key(settings) -> tuple[bytes, str]:
    """Load RSA private key from the Firebase service account JSON.

    Returns (private_key_bytes, key_id).
    """
    sa_path = settings.auth.providers.get("firebase", {}).get(
        "service_account_path", ".secrets/firebase-service-account.json"
    )
    with open(sa_path) as f:
        sa_data = json.load(f)

    private_key_pem = sa_data["private_key"].encode("utf-8")
    key_id = sa_data.get("private_key_id", "")
    return private_key_pem, key_id


def mint_access_token(
    settings,
    uid: str,
    email: str | None,
    role: str,
    scopes: list[str],
    client_id: str,
) -> tuple[str, int]:
    """Mint an RS256-signed JWT access token. Returns (token, expires_in)."""
    private_key_pem, key_id = _load_sa_private_key(settings)

    now = int(time.time())
    ttl = settings.oauth.access_token_ttl
    payload = {
        "sub": uid,
        "email": email,
        "role": role,
        "scopes": scopes,
        "iss": settings.oauth.issuer,
        "aud": "mcp-authchain",
        "client_id": client_id,
        "iat": now,
        "exp": now + ttl,
    }
    token = jwt.encode(
        payload,
        private_key_pem,
        algorithm="RS256",
        headers={"kid": key_id},
    )
    return token, ttl


def create_oauth_verifier(settings) -> Callable[[str], FirebaseUser]:
    """Create a verifier for server-signed OAuth JWTs.

    Uses the public key derived from the same Firebase SA private key.
    Returns a function matching: verify(token: str) -> FirebaseUser
    """
    private_key_pem, _ = _load_sa_private_key(settings)

    # Derive the public key from the private key for verification
    private_key = load_pem_private_key(private_key_pem, password=None)
    public_key = private_key.public_key()

    def verify(token: str) -> FirebaseUser:
        decoded = jwt.decode(
            token,
            public_key,
            algorithms=["RS256"],
            audience="mcp-authchain",
            issuer=settings.oauth.issuer,
        )
        return FirebaseUser(
            uid=decoded["sub"],
            email=decoded.get("email"),
            role=decoded.get("role", "viewer"),
            scopes=decoded.get("scopes", []),
            id_token=token,
            claims=decoded,
        )

    return verify
