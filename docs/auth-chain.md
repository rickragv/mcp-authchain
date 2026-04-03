# Auth Chain: Multi-User, Multi-Session

This guide explains how authentication flows through the entire system and why it's safe for multiple concurrent users.

## The E2E Auth Chain

```
Step 1: User signs in via Firebase (browser)
        ┌─────────────────────────────────┐
        │  Firebase JS SDK                │
        │  signInWithEmailAndPassword()   │
        │  → id_token (JWT, 1h TTL)       │
        │  → refresh_token (auto-managed) │
        └────────────────┬────────────────┘
                         │ Bearer <id_token>
                         ▼
Step 2: Agent API validates token
        ┌─────────────────────────────────┐
        │  auth_middleware.py             │
        │  verify_token(token)            │
        │  → checks JWT signature (RS256) │
        │  → checks expiry, audience, iss │
        │  → extracts uid, email, scopes  │
        │  → returns FirebaseUser         │
        └────────────────┬────────────────┘
                         │ token stored in ADK session
                         ▼
Step 3: ADK agent calls MCP tools with user's token
        ┌─────────────────────────────────┐
        │  header_provider(callback_ctx)  │
        │  → reads token from session     │
        │  → returns Authorization header │
        └────────────────┬────────────────┘
                         │ Bearer <same id_token>
                         ▼
Step 4: MCP server validates same token
        ┌─────────────────────────────────┐
        │  FirebaseBearerAuthMiddleware   │
        │  verify_token(token)            │
        │  → same verification as Step 2  │
        │  → rejects if expired/invalid   │
        └────────────────┬────────────────┘
                         │ token valid
                         ▼
Step 5: Tool executes, result flows back
        MCP tool → Agent → FastAPI → Frontend
```

**Same Firebase ID token** flows from browser to MCP server. The MCP server sees the actual user, not "the agent".

## Multi-User Safety

### The problem

If User A and User B send requests at the same time, their tokens must never mix:

```
User A: POST /chat "weather in Tokyo"   → must use token_A for MCP
User B: POST /chat "weather in London"  → must use token_B for MCP
```

### The solution: Per-request ADK sessions

```python
# agent-api/routes/chat.py

@router.post("/chat")
async def chat(request: ChatRequest, user: FirebaseUser = Depends(get_current_user)):
    # NEW session for EVERY request -- isolated per-user
    session = await session_service.create_session(
        app_name=APP_NAME,
        user_id=user.uid,
        state={"user_token": user.id_token},  # This user's token only
    )

    # Runner uses THIS session for the entire agent execution
    async for event in _runner.run_async(
        user_id=user.uid,
        session_id=session.id,   # Bound to this session
        ...
    ):
```

When the agent calls an MCP tool, ADK invokes `header_provider`:

```python
def mcp_header_provider(callback_context):
    # callback_context.session = the per-request session
    # User A's request reads User A's token
    # User B's request reads User B's token
    token = callback_context.session.state.get("user_token")
    return {"Authorization": f"Bearer {token}"}
```

### What's shared vs. per-request

| Component | Shared? | Thread-safe? | Why |
|-----------|---------|-------------|-----|
| `Agent` instance | Shared | Yes | Stateless -- just model config + instructions |
| `McpToolset` | Shared | Yes | Connection params only, no mutable state |
| `Runner` | Shared | Yes | Dispatches to per-session execution |
| `InMemorySessionService` | Shared | Yes | Thread-safe dict keyed by session ID |
| `header_provider` | Per-call | Yes | Reads from `callback_context.session` |
| ADK `Session` | Per-request | N/A | Created new for each POST /chat |
| User token | Per-request | N/A | Stored in session state, never in globals |

### Concurrent request flow

```
Time →

User A: POST /chat ─── create session_A{token_A} ─── agent runs ─── header_provider reads token_A ─── MCP validates token_A
User B: POST /chat ─── create session_B{token_B} ─── agent runs ─── header_provider reads token_B ─── MCP validates token_B
User C: POST /chat ─── create session_C{token_C} ─── agent runs ─── header_provider reads token_C ─── MCP validates token_C

All concurrent. All isolated. No token leakage.
```

## Token Lifecycle

### Browser-side (automatic)

Firebase JS SDK handles token refresh in the browser:
- `user.getIdToken()` returns a cached token if valid, or refreshes if expired
- Tokens live for 1 hour
- Refresh tokens never expire (unless user is disabled)
- The frontend calls `getIdToken()` before every API call

```typescript
// frontend/src/components/Chat.tsx
const idToken = await user.getIdToken()  // auto-refreshes if expired
const res = await sendChat(prompt, idToken)
```

### Server-side (401-driven)

For headless/background scenarios using `AuthenticatedMCPClient` (in `commons/mcp_client.py`):

```
call_tool() → send with current token
  ├── 200 OK → done
  └── 401 → call refresh_fn() → get new token → retry once
              └── 401 again → raise AuthenticationError (revoked)
```

Built-in refresh strategies in `commons/token_refresh.py`:
- `firebase_refresh(api_key, refresh_token)` -- for Cloud Run Jobs
- `websocket_refresh(send_fn, receive_fn)` -- for browser-connected backends

## What happens when...

### Token expires mid-agent-run?

The agent may make multiple MCP calls during one `/chat` request. If the token expires between calls:

1. **Browser path**: Unlikely -- `getIdToken()` refreshes before each `/chat` request, and agent runs take seconds not hours
2. **Background path**: `AuthenticatedMCPClient` catches 401, refreshes, retries

### User is disabled/revoked?

1. Firebase rejects the token at Step 2 (agent-api) or Step 4 (MCP server)
2. Returns 401 to the caller
3. Frontend shows "Unauthorized -- please sign in again"

### Token is forged?

1. Firebase Admin SDK verifies the RS256 signature against Google's public keys
2. Checks `iss` (must be `https://securetoken.google.com/<project_id>`)
3. Checks `aud` (must be your project ID)
4. Forged tokens fail signature verification → 401

### Same user, multiple tabs?

Each tab gets its own session. Firebase SDK shares the auth state across tabs (same browser), so all tabs use the same token. MCP server doesn't care -- it validates the token, not the session.

## Security properties

1. **Token never stored server-side** -- passed through in memory, per-request
2. **Same identity E2E** -- MCP server sees the actual user UID, not a service account
3. **Scope enforcement at tool level** -- even with a valid token, users can only call tools their role permits
4. **Stateless MCP server** -- no session state, scales horizontally on Cloud Run
5. **No token passthrough to external APIs** -- tools use their own credentials for external calls (e.g., Open-Meteo needs no auth)
