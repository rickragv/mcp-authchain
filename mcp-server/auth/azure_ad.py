"""Azure AD (Entra ID) auth provider for MCP server.

Config example in settings.yaml:
    auth:
      provider: "azure_ad"
      providers:
        azure_ad:
          tenant_id: "your-tenant-id"
          client_id: "your-client-id"
"""

import jwt
from jwt import PyJWKClient
from typing import Callable

from commons.types import FirebaseUser

_jwks_client: PyJWKClient | None = None


def create_verifier(config: dict) -> Callable[[str], FirebaseUser]:
    """Create an Azure AD token verifier from config.

    Config keys:
        tenant_id: Azure AD tenant ID
        client_id: Application (client) ID registered in Azure AD
    """
    tenant_id = config["tenant_id"]
    client_id = config["client_id"]
    issuer = f"https://login.microsoftonline.com/{tenant_id}/v2.0"
    jwks_url = f"https://login.microsoftonline.com/{tenant_id}/discovery/v2.0/keys"

    def verify(token: str) -> FirebaseUser:
        global _jwks_client
        if _jwks_client is None:
            _jwks_client = PyJWKClient(jwks_url)

        signing_key = _jwks_client.get_signing_key_from_jwt(token)
        decoded = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            audience=client_id,
            issuer=issuer,
        )

        # Azure AD scopes come from "scp" claim (space-separated)
        scopes_str = decoded.get("scp", "")
        scopes = scopes_str.split() if scopes_str else []

        # Azure AD roles come from "roles" claim (list)
        roles = decoded.get("roles", [])

        return FirebaseUser(
            uid=decoded["sub"],
            email=decoded.get("preferred_username") or decoded.get("email"),
            role=roles[0] if roles else "viewer",
            scopes=scopes,
            id_token=token,
            claims=decoded,
        )

    return verify
