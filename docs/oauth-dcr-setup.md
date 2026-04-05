# OAuth 2.1 + DCR: Claude Desktop Integration

This guide explains how the MCP server exposes OAuth 2.1 with Dynamic Client Registration (DCR) so that Claude Desktop (and any MCP-compliant client) can connect securely.

## Architecture Overview

The MCP server supports **two authentication paths** on the same `/mcp` endpoint:

```
Path 1: Direct Firebase Token (your frontend / agent-api)
──────────────────────────────────────────────────────────
Browser → Firebase Auth → id_token → Agent API → Bearer token → /mcp
                                                                  │
                                                    BearerAuthMiddleware
                                                    tries Firebase verify ✓


Path 2: OAuth 2.1 Flow (Claude Desktop / remote MCP clients)
──────────────────────────────────────────────────────────────
Claude Desktop → 401 → discovers OAuth endpoints → DCR → /authorize
→ Firebase login in browser → auth code → /token (PKCE) → JWT
→ Bearer JWT → /mcp
                  │
    BearerAuthMiddleware
    tries Firebase verify ✗ → falls back to OAuth JWT verify ✓
```

Both paths arrive at `/mcp` with a valid Bearer token. The middleware tries Firebase verification first, then falls back to OAuth JWT verification. Existing flows are unaffected.

## How Claude Desktop Connects

Claude Desktop cannot use Firebase tokens directly -- it has no Firebase login UI. Instead, it speaks OAuth 2.1, which wraps Firebase as the identity provider.

### Step-by-step flow

```
Claude Desktop                          MCP Server (Cloud Run)
     │                                        │
  1. │── POST /mcp ──────────────────────────► │ 401 + WWW-Authenticate header
     │                                        │   ↳ points to protected resource metadata
     │                                        │
  2. │── GET /.well-known/                   │
     │   oauth-protected-resource ──────────► │ { resource, authorization_servers, scopes }
     │                                        │
  3. │── GET /.well-known/                   │
     │   openid-configuration ──────────────► │ { authorization_endpoint, token_endpoint,
     │                                        │   registration_endpoint, ... }
     │                                        │
  4. │── POST /register ────────────────────► │ DCR: returns { client_id }
     │   { client_name: "Claude",            │
     │     redirect_uris: [claude.ai/...] }  │
     │                                        │
  5. │── Opens user's browser ──────────────► │ GET /authorize?response_type=code
     │                                        │   &client_id=X&redirect_uri=Y
     │                                        │   &code_challenge=Z&code_challenge_method=S256
     │                                        │   &state=S
     │                                        │
     │   User sees Firebase login page        │ ◄── serves HTML with Firebase JS SDK
     │   User signs in (Google / email+pw)    │
     │                                        │
  6. │   Browser JS gets Firebase id_token    │
     │── POST /authorize/callback ──────────► │ Verifies Firebase token, generates auth code
     │   { firebase_id_token, client_id,     │
     │     redirect_uri, code_challenge }    │
     │                                        │ Returns { redirect_url }
     │                                        │
  7. │   Browser redirects to:                │
     │   claude.ai/api/mcp/auth_callback     │
     │   ?code=AUTH_CODE&state=S             │
     │                                        │
  8. │── POST /token ───────────────────────► │ Validates PKCE code_verifier
     │   { grant_type: authorization_code,   │ Mints RS256 JWT access token
     │     code, code_verifier, client_id }  │ Issues refresh token
     │                                        │ Returns { access_token, refresh_token }
     │                                        │
  9. │── POST /mcp ──────────────────────────► │ BearerAuthMiddleware validates JWT ✓
     │   Authorization: Bearer <jwt>          │ Tool executes, result returned
     │                                        │
 10. │   (when token expires)                 │
     │── POST /token ───────────────────────► │ Refresh token rotation
     │   { grant_type: refresh_token,        │ New access_token + new refresh_token
     │     refresh_token, client_id }        │
```

### Key points

- **Step 5**: The `/authorize` page is an HTML page served by your MCP server, using the Firebase JS SDK. Same Firebase auth you already use.
- **Step 6**: The `/authorize/callback` is an internal endpoint called by JavaScript on the authorize page, not by Claude Desktop directly.
- **Step 8**: PKCE (S256) is mandatory per OAuth 2.1. Claude Desktop generates the code_verifier/code_challenge pair.
- **Step 10**: Refresh tokens are rotated on every use (old token is invalidated).

## OAuth Endpoints Reference

| Endpoint | Method | RFC | Purpose |
|----------|--------|-----|---------|
| `/.well-known/oauth-protected-resource` | GET | [RFC 9728](https://datatracker.ietf.org/doc/html/rfc9728) | Resource metadata discovery |
| `/.well-known/openid-configuration` | GET | [RFC 8414](https://datatracker.ietf.org/doc/html/rfc8414) | Authorization server metadata |
| `/register` | POST | [RFC 7591](https://datatracker.ietf.org/doc/html/rfc7591) | Dynamic Client Registration |
| `/authorize` | GET | OAuth 2.1 | Firebase login page |
| `/authorize/callback` | POST | Internal | Exchanges Firebase token for auth code |
| `/token` | POST | OAuth 2.1 | Token exchange (auth code or refresh) |

## File Structure

```
mcp-server/oauth/
├── __init__.py          # Package init
├── endpoints.py         # All 6 route handlers (Starlette Routes)
├── store.py             # In-memory storage: clients, auth codes, refresh tokens
├── pkce.py              # PKCE S256 verification
├── token_service.py     # JWT minting (RS256) + OAuth token verifier
└── templates.py         # Firebase login HTML page for /authorize
```

## Token Strategy

OAuth-issued tokens are **server-signed RS256 JWTs**, not Firebase ID tokens:

```json
{
  "sub": "firebase-uid-abc123",
  "email": "user@example.com",
  "role": "viewer",
  "scopes": ["weather:read"],
  "iss": "https://your-mcp-server.run.app",
  "aud": "mcp-authchain",
  "client_id": "claude-registered-client-id",
  "iat": 1712300000,
  "exp": 1712303600
}
```

**Why not pass through Firebase ID tokens?**

| | Firebase ID Token | Server-signed JWT |
|-|---|---|
| TTL | Fixed 1 hour | Configurable (`OAUTH_ACCESS_TOKEN_TTL`) |
| Refresh | Requires Firebase SDK | Standard OAuth refresh_token flow |
| Scopes | From Firebase custom claims | Embedded from role mapping at issue time |
| Signing key | Google's private key | Your Firebase SA private key (RS256) |

The signing key is the RSA private key from your Firebase service account JSON (`.secrets/firebase-service-account.json`). No separate JWT secret needed.

## Dual Verification in Middleware

The `BearerAuthMiddleware` supports both token types:

```python
class BearerAuthMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, verify_fn, oauth_verify_fn=None):
        self.verify = verify_fn           # Firebase / Azure AD / JWT
        self.oauth_verify = oauth_verify_fn  # Server-signed OAuth JWT

    async def dispatch(self, request, call_next):
        token = extract_bearer(request)

        # Try primary verifier first (Firebase)
        try:
            user = self.verify(token)
        except Exception:
            # Fall back to OAuth JWT verifier
            if self.oauth_verify:
                user = self.oauth_verify(token)
            else:
                raise

        return await call_next(request)
```

401 responses include a `WWW-Authenticate` header pointing to the protected resource metadata:

```
HTTP/1.1 401 Unauthorized
WWW-Authenticate: Bearer resource_metadata="https://your-server.run.app/.well-known/oauth-protected-resource"
```

This is how Claude Desktop discovers the OAuth flow.

## In-Memory Storage

The OAuth store (`mcp-server/oauth/store.py`) holds three types of records:

| Record | Key | TTL | Single-use? |
|--------|-----|-----|-------------|
| `ClientRegistration` | `client_id` | None (persists) | No |
| `AuthorizationCode` | `code` | 5 minutes | Yes |
| `RefreshTokenRecord` | `token` | 24 hours | Yes (rotation) |

**Production note**: For Cloud Run with multiple instances, replace with Firestore or Redis. Single-instance deployments work fine with in-memory storage.

## Setup Guide

### 1. Prerequisites

- Firebase project with Authentication enabled (Google + Email/Password)
- Firebase service account JSON at `.secrets/firebase-service-account.json`
- Python 3.10+ with `PyJWT[crypto]>=2.8`

### 2. Environment Variables

Add to your `.env`:

```bash
# OAuth issuer -- MUST match the public URL where your server is reachable
# For local testing with cloudflared:
OAUTH_ISSUER=https://your-tunnel-url.trycloudflare.com
# For Cloud Run:
# OAUTH_ISSUER=https://mcp-server-abc123-uc.a.run.app

# Firebase Web SDK config (public, client-side values -- same as your frontend)
FIREBASE_WEB_API_KEY=AIzaSy...
FIREBASE_AUTH_DOMAIN=your-project.firebaseapp.com

# Optional tuning
# OAUTH_ACCESS_TOKEN_TTL=3600      # Access token lifetime (seconds, default 1h)
# OAUTH_REFRESH_TOKEN_TTL=86400    # Refresh token lifetime (seconds, default 24h)
# OAUTH_AUTH_CODE_TTL=300           # Auth code lifetime (seconds, default 5min)
```

**Where to find `FIREBASE_WEB_API_KEY`**: Firebase Console → Project Settings → General → Web API Key. It's the same value as `VITE_FIREBASE_API_KEY` in `frontend/.env`. This is a public value, not a secret.

### 3. Local Testing with Cloudflared

```bash
# Terminal 1: Start MCP server
conda activate mcp-auth
python -m uvicorn run_mcp_server:app --host 0.0.0.0 --port 8001

# Terminal 2: Start tunnel (no signup required)
pip install pycloudflared
python -c "from pycloudflared import try_cloudflare; t = try_cloudflare(port=8001); print(t.tunnel); input('Press Enter to stop')"
```

Or run cloudflared directly:

```bash
cloudflared tunnel --url http://localhost:8001
# Outputs: https://random-words.trycloudflare.com
```

**Important**: Set `OAUTH_ISSUER` to the tunnel URL and restart the MCP server before connecting Claude Desktop.

### 4. Verify Endpoints

```bash
TUNNEL=https://your-tunnel-url.trycloudflare.com

# Protected resource metadata
curl $TUNNEL/.well-known/oauth-protected-resource

# OpenID configuration
curl $TUNNEL/.well-known/openid-configuration

# Dynamic Client Registration
curl -X POST $TUNNEL/register \
  -H "Content-Type: application/json" \
  -d '{"client_name":"test","redirect_uris":["http://localhost"]}'

# 401 with WWW-Authenticate header
curl -v $TUNNEL/mcp
```

### 5. Connect Claude Desktop

1. Open Claude Desktop
2. **Settings** (gear icon) → **Connectors**
3. **Add Connector**
4. URL: `https://your-tunnel-url.trycloudflare.com/mcp`
5. Name: e.g. "MCP Auth Demo"
6. Save
7. Start a **new conversation**
8. Ask: "Use the get_weather tool to check weather in London"
9. Your browser opens → Firebase login → sign in → redirect back to Claude
10. Tool executes and returns the result

### 6. Deploy to Cloud Run

```bash
# Set the issuer to your Cloud Run URL
gcloud run deploy mcp-server \
  --source . \
  --set-env-vars OAUTH_ISSUER=https://mcp-server-abc123-uc.a.run.app \
  --set-env-vars FIREBASE_WEB_API_KEY=AIzaSy... \
  --set-env-vars FIREBASE_AUTH_DOMAIN=your-project.firebaseapp.com \
  --set-env-vars FIREBASE_PROJECT_ID=your-project-id \
  --set-env-vars AUTH_PROVIDER=firebase \
  --set-env-vars FIREBASE_SA_PATH=.secrets/firebase-service-account.json \
  --allow-unauthenticated \
  --port 8001
```

`--allow-unauthenticated` is correct -- your OAuth layer handles auth, not Cloud Run IAM.

Update the connector URL in Claude Desktop to the Cloud Run URL.

## PKCE (Proof Key for Code Exchange)

OAuth 2.1 mandates PKCE to prevent authorization code interception. Only S256 is supported (plain is rejected).

```
Client generates:
  code_verifier  = random 43-128 character string
  code_challenge = BASE64URL(SHA256(code_verifier))

/authorize receives:     code_challenge + code_challenge_method=S256
/token receives:         code_verifier

Server verifies:         SHA256(code_verifier) == code_challenge
```

Implementation in `mcp-server/oauth/pkce.py`:

```python
def verify_pkce(code_verifier: str, code_challenge: str, method: str = "S256") -> bool:
    if method == "S256":
        digest = hashlib.sha256(code_verifier.encode("ascii")).digest()
        computed = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
        return computed == code_challenge
    return False
```

## Dynamic Client Registration (DCR)

DCR allows MCP clients to register themselves without manual setup.

### Request (from Claude Desktop)

```http
POST /register
Content-Type: application/json

{
  "client_name": "Claude Desktop",
  "redirect_uris": ["https://claude.ai/api/mcp/auth_callback"],
  "grant_types": ["authorization_code", "refresh_token"],
  "response_types": ["code"],
  "token_endpoint_auth_method": "none"
}
```

### Response

```http
HTTP/1.1 201 Created
Content-Type: application/json

{
  "client_id": "zm-TyWYltmLISylqwbCUVKeM...",
  "client_name": "Claude Desktop",
  "redirect_uris": ["https://claude.ai/api/mcp/auth_callback"],
  "grant_types": ["authorization_code", "refresh_token"],
  "response_types": ["code"],
  "token_endpoint_auth_method": "none"
}
```

### Validation rules

- `redirect_uris` is required and must be a non-empty list
- `redirect_uri` matching at `/authorize` time uses **exact string comparison** (no wildcards)
- `client_id` is generated as `secrets.token_urlsafe(32)`
- Claude's callback URL: `https://claude.ai/api/mcp/auth_callback`

## The Authorize Page

The `/authorize` endpoint serves an HTML page with the Firebase JS SDK. It's a self-contained login form -- no React build, no external assets beyond Firebase CDN.

### What it renders

- Google sign-in button
- Email/password form
- Requested scopes display
- Error messages

### How it works

1. Firebase Web SDK initializes with your project config (injected server-side)
2. User signs in → Firebase returns an ID token client-side
3. JavaScript POSTs the ID token + OAuth params to `/authorize/callback`
4. Server verifies the Firebase token using the existing auth provider
5. Server generates an authorization code, stores it with the PKCE challenge
6. Returns `{ redirect_url }` → JavaScript redirects the browser

The Firebase config values (`apiKey`, `authDomain`, `projectId`) are **public client-side values** -- the same ones your React frontend uses. They are not secrets.

## Refresh Token Rotation

When a refresh token is used, it is **invalidated** and a new one is issued:

```
Request:  POST /token { grant_type: refresh_token, refresh_token: OLD, client_id: X }
Response: { access_token: NEW_JWT, refresh_token: NEW_REFRESH }

OLD refresh token is now invalid. Only NEW_REFRESH works for the next refresh.
```

This prevents replay attacks -- a stolen refresh token can only be used once.

## Security Considerations

### What's validated

| Check | Where | Why |
|-------|-------|-----|
| Firebase token signature | `/authorize/callback` | Ensures the user actually signed in |
| PKCE code_challenge/verifier | `/token` | Prevents auth code interception |
| redirect_uri exact match | `/authorize` | Prevents redirect to attacker-controlled URLs |
| Auth code single-use | `/token` | Prevents code replay |
| Auth code TTL (5 min) | `/token` | Limits window for code theft |
| Refresh token rotation | `/token` | Prevents refresh token replay |
| JWT signature (RS256) | `BearerAuthMiddleware` | Ensures token was issued by this server |
| JWT audience + issuer | `BearerAuthMiddleware` | Prevents token confusion between services |

### Production hardening

- [ ] Replace in-memory `OAuthStore` with Firestore for multi-instance support
- [ ] Add rate limiting on `/register` and `/token` endpoints
- [ ] Add allowed redirect_uri allowlist in config (beyond per-client validation)
- [ ] Set `OAUTH_ISSUER` to your production Cloud Run URL
- [ ] Use Cloud Run's HTTPS (automatic) -- never expose OAuth over plain HTTP
- [ ] Monitor token issuance via structured logs (`oauth.token_issued`, `oauth.client_registered`)

## Configuration Reference

### settings.yaml

```yaml
oauth:
  enabled: true
  issuer: ${OAUTH_ISSUER:http://localhost:8001}
  access_token_ttl: ${OAUTH_ACCESS_TOKEN_TTL:3600}
  refresh_token_ttl: ${OAUTH_REFRESH_TOKEN_TTL:86400}
  auth_code_ttl: ${OAUTH_AUTH_CODE_TTL:300}
  firebase_api_key: ${FIREBASE_WEB_API_KEY:}
  firebase_auth_domain: ${FIREBASE_AUTH_DOMAIN:}
  firebase_project_id: ${FIREBASE_PROJECT_ID:}
```

### OAuthConfig model

```python
class OAuthConfig(BaseModel):
    enabled: bool = True
    issuer: str = "http://localhost:8001"
    jwt_algorithm: str = "RS256"
    access_token_ttl: int = 3600        # 1 hour
    refresh_token_ttl: int = 86400      # 24 hours
    auth_code_ttl: int = 300            # 5 minutes
    firebase_api_key: str = ""
    firebase_auth_domain: str = ""
    firebase_project_id: str = ""
```

## Troubleshooting

### Claude Desktop says "Couldn't reach the MCP server"

1. Check `OAUTH_ISSUER` matches your public URL (not `localhost`)
2. Verify the tunnel is running: `curl $TUNNEL/.well-known/oauth-protected-resource`
3. Verify the MCP server is running: `curl http://localhost:8001/mcp` (should return 401)

### OAuth flow doesn't start (no browser popup)

1. Ensure the 401 response includes `WWW-Authenticate` header
2. Check `/.well-known/oauth-protected-resource` returns valid JSON
3. Check `/.well-known/openid-configuration` lists correct endpoint URLs

### Firebase login page doesn't load

1. Check `FIREBASE_WEB_API_KEY` is set (not empty)
2. Check `FIREBASE_AUTH_DOMAIN` matches your Firebase project
3. Open the `/authorize` URL directly in your browser to debug

### Token exchange fails

1. Check the auth code hasn't expired (5 min TTL)
2. Check PKCE: `code_challenge_method` must be `S256`
3. Check `redirect_uri` exactly matches what was registered

### "Authentication failed" on /mcp after OAuth

1. Check `OAUTH_ISSUER` matches the `iss` claim the middleware expects
2. Check the Firebase SA private key is readable at `FIREBASE_SA_PATH`
3. Check the JWT `aud` is `mcp-authchain`
