"""MCP Server entry point -- FastMCP with pluggable auth middleware.

Auth provider is selected via configs/settings.yaml `auth.provider`.
Tools are auto-discovered by matching configs/tools/*.yaml to mcp-server/tools/*.py.
OAuth 2.1 + DCR endpoints enable Claude Desktop to connect via Connectors.
"""

from contextlib import asynccontextmanager

import structlog
from mcp.server.fastmcp import FastMCP
from mcp.server.streamable_http import TransportSecuritySettings
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from commons.config import settings

from .auth import get_verifier
from .tools import register_all_tools
from .oauth.store import OAuthStore
from .oauth.endpoints import oauth_routes
from .oauth.token_service import create_oauth_verifier

structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.add_log_level,
        structlog.processors.JSONRenderer(),
    ],
)
log = structlog.get_logger()


# --- Pluggable auth middleware ---

class BearerAuthMiddleware(BaseHTTPMiddleware):
    """Provider-agnostic bearer token middleware with dual verification.

    Tries the primary verify function (e.g. Firebase) first.
    Falls back to OAuth JWT verification for server-signed tokens.
    """

    def __init__(self, app, verify_fn, oauth_verify_fn=None):
        super().__init__(app)
        self.verify = verify_fn
        self.oauth_verify = oauth_verify_fn

    async def dispatch(self, request: Request, call_next):
        if not request.url.path.startswith("/mcp"):
            return await call_next(request)

        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            return JSONResponse(
                status_code=401,
                content={"error": "Missing or invalid Authorization header"},
                headers={
                    "WWW-Authenticate": (
                        f'Bearer resource_metadata="{settings.oauth.issuer}'
                        f'/.well-known/oauth-protected-resource"'
                    ),
                },
            )

        token = auth_header.split("Bearer ")[1]

        # Try primary verifier (Firebase/Azure AD/JWT) first
        user = None
        try:
            user = self.verify(token)
            log.info("auth.ok", user=user.uid, provider=settings.auth.provider)
        except Exception:
            # Fall back to OAuth JWT verification
            if self.oauth_verify:
                try:
                    user = self.oauth_verify(token)
                    log.info("auth.ok", user=user.uid, provider="oauth_jwt")
                except Exception as e:
                    log.warning("auth.failed", error=str(e), provider="oauth_jwt")
            else:
                log.warning("auth.failed", provider=settings.auth.provider)

        if not user:
            return JSONResponse(
                status_code=401,
                content={"error": "Authentication failed"},
                headers={
                    "WWW-Authenticate": (
                        f'Bearer resource_metadata="{settings.oauth.issuer}'
                        f'/.well-known/oauth-protected-resource"'
                    ),
                },
            )

        return await call_next(request)


# --- Create MCP server ---

mcp = FastMCP(
    name="MCP Auth Demo Server",
    stateless_http=True,
    transport_security=TransportSecuritySettings(
        enable_dns_rebinding_protection=False,
    ),
)

# Dummy auth context for tool registration (scope checking not wired to middleware yet)
class _AuthContext:
    @property
    def auth_info(self):
        return None

# Auto-discover and register tools from YAML configs
registered = register_all_tools(mcp, _AuthContext())
log.info("tools_registered", tools=registered)

# Get Starlette app from FastMCP
app = mcp.streamable_http_app()

# --- Mount OAuth routes ---
oauth_store = OAuthStore()
verify = get_verifier(settings)
oauth_verify = create_oauth_verifier(settings)

for route in oauth_routes(settings, oauth_store, verify):
    app.routes.insert(0, route)

# Wrap lifespan to init auth provider on startup
_original_lifespan = app.router.lifespan_context


@asynccontextmanager
async def lifespan(app_instance):
    log.info(
        "mcp_server.startup",
        auth_provider=settings.auth.provider,
        oauth_enabled=settings.oauth.enabled,
        tools=registered,
    )
    async with _original_lifespan(app_instance) as state:
        yield state
    log.info("mcp_server.shutdown")


app.router.lifespan_context = lifespan

# Add auth middleware with dual verification
app.add_middleware(BearerAuthMiddleware, verify_fn=verify, oauth_verify_fn=oauth_verify)
