# Changing the Auth Middleware

Auth is **config-driven**. Switch providers by changing one line in `.env`:

```bash
AUTH_PROVIDER=firebase    # or: azure_ad, jwt
```

## Supported providers

| Provider | `.env` value | Required env vars |
|----------|-------------|-------------------|
| Firebase | `firebase` | `FIREBASE_PROJECT_ID`, `FIREBASE_SA_PATH` |
| Azure AD (Entra ID) | `azure_ad` | `AZURE_TENANT_ID`, `AZURE_CLIENT_ID` |
| Generic JWT (Auth0, Keycloak, any OIDC) | `jwt` | `JWT_JWKS_URL`, `JWT_ISSUER`, `JWT_AUDIENCE` |

## How it works

```
settings.yaml reads AUTH_PROVIDER env var
    ↓
mcp-server/auth/__init__.py loads the matching provider module
    ↓
Provider module returns a verify(token) → FirebaseUser function
    ↓
BearerAuthMiddleware in main.py calls verify() on every request
```

## Switching to Azure AD

```bash
# .env
AUTH_PROVIDER=azure_ad
AZURE_TENANT_ID=your-tenant-id
AZURE_CLIENT_ID=your-app-client-id
```

Restart MCP server. Done.

Azure AD tokens carry scopes in the `scp` claim (space-separated) and roles in the `roles` claim.

## Switching to Auth0 / Keycloak / any OIDC

```bash
# .env
AUTH_PROVIDER=jwt
JWT_JWKS_URL=https://your-domain.auth0.com/.well-known/jwks.json
JWT_ISSUER=https://your-domain.auth0.com/
JWT_AUDIENCE=your-api-audience
```

The generic JWT provider works with any OIDC-compliant provider that exposes a JWKS endpoint.

## Adding a custom provider

1. Create `mcp-server/auth/my_provider.py`:

```python
from typing import Callable
from commons.types import FirebaseUser

def create_verifier(config: dict) -> Callable[[str], FirebaseUser]:
    """Return a sync function: verify(token: str) → FirebaseUser"""

    def verify(token: str) -> FirebaseUser:
        # Your verification logic here
        decoded = your_verify_function(token)
        return FirebaseUser(
            uid=decoded["sub"],
            email=decoded.get("email"),
            role=decoded.get("role", "viewer"),
            scopes=decoded.get("scopes", []),
            id_token=token,
            claims=decoded,
        )

    return verify
```

2. Register it in `mcp-server/auth/__init__.py`:

```python
PROVIDERS = {
    "firebase": ".auth.firebase",
    "azure_ad": ".auth.azure_ad",
    "jwt": ".auth.jwt_generic",
    "my_provider": ".auth.my_provider",  # Add here
}
```

3. Add config to `.env`:

```bash
AUTH_PROVIDER=my_provider
MY_PROVIDER_SETTING=value
```

4. Add provider config in `settings.yaml` under `auth.providers`:

```yaml
auth:
  providers:
    my_provider:
      setting: ${MY_PROVIDER_SETTING}
```

## Architecture

```
mcp-server/auth/
├── __init__.py         # Provider registry: get_verifier(settings) → verify function
├── firebase.py         # Firebase Admin SDK verification
├── azure_ad.py         # Azure AD / Entra ID JWKS verification
└── jwt_generic.py      # Generic OIDC JWKS (Auth0, Keycloak, etc.)
```

The middleware in `mcp-server/main.py` is **provider-agnostic** -- it just calls `verify(token)` and doesn't know which provider is behind it:

```python
class BearerAuthMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, verify_fn):
        self.verify = verify_fn  # Injected at startup

    async def dispatch(self, request, call_next):
        token = extract_bearer(request)
        user = self.verify(token)  # Could be Firebase, Azure AD, anything
        return await call_next(request)
```
