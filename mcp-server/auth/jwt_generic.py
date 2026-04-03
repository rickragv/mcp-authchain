"""Generic JWKS-based JWT auth provider. Works with Auth0, Keycloak, any OIDC provider.

Config example in settings.yaml:
    auth:
      provider: "jwt"
      providers:
        jwt:
          jwks_url: "https://your-provider.com/.well-known/jwks.json"
          issuer: "https://your-provider.com/"
          audience: "your-api-audience"
          scopes_claim: "scope"       # default: "scope" (space-separated string)
          subject_claim: "sub"        # default: "sub"
"""

import jwt as pyjwt
from jwt import PyJWKClient
from typing import Callable

from commons.types import FirebaseUser

_jwks_client: PyJWKClient | None = None


def create_verifier(config: dict) -> Callable[[str], FirebaseUser]:
    """Create a generic JWT verifier from config.

    Config keys:
        jwks_url: JWKS endpoint URL
        issuer: Expected token issuer
        audience: Expected token audience (optional)
        scopes_claim: JWT claim name for scopes (default: "scope")
        subject_claim: JWT claim name for subject (default: "sub")
    """
    jwks_url = config["jwks_url"]
    issuer = config["issuer"]
    audience = config.get("audience")
    scopes_claim = config.get("scopes_claim", "scope")
    subject_claim = config.get("subject_claim", "sub")

    def verify(token: str) -> FirebaseUser:
        global _jwks_client
        if _jwks_client is None:
            _jwks_client = PyJWKClient(jwks_url)

        signing_key = _jwks_client.get_signing_key_from_jwt(token)

        decode_opts = {
            "algorithms": ["RS256", "ES256"],
            "issuer": issuer,
        }
        if audience:
            decode_opts["audience"] = audience

        decoded = pyjwt.decode(token, signing_key.key, **decode_opts)

        # Extract scopes -- handle both space-separated string and list
        raw_scopes = decoded.get(scopes_claim, "")
        if isinstance(raw_scopes, str):
            scopes = raw_scopes.split() if raw_scopes else []
        elif isinstance(raw_scopes, list):
            scopes = raw_scopes
        else:
            scopes = []

        return FirebaseUser(
            uid=decoded.get(subject_claim, ""),
            email=decoded.get("email"),
            role=decoded.get("role", "viewer"),
            scopes=scopes,
            id_token=token,
            claims=decoded,
        )

    return verify
