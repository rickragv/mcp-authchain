"""MCP Server entry point -- FastMCP with pluggable auth middleware.

Auth provider is selected via configs/settings.yaml `auth.provider`.
Tools are auto-discovered by matching configs/tools/*.yaml to mcp-server/tools/*.py.
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
    """Provider-agnostic bearer token middleware.

    The verify function is injected at startup based on settings.yaml auth.provider.
    Works with Firebase, Azure AD, Auth0, Keycloak, or any custom JWT provider.
    """

    def __init__(self, app, verify_fn):
        super().__init__(app)
        self.verify = verify_fn

    async def dispatch(self, request: Request, call_next):
        if not request.url.path.startswith("/mcp"):
            return await call_next(request)

        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            return JSONResponse(
                status_code=401,
                content={"error": "Missing or invalid Authorization header"},
            )

        token = auth_header.split("Bearer ")[1]
        try:
            user = self.verify(token)
            log.info("auth.ok", user=user.uid, provider=settings.auth.provider)
        except Exception as e:
            log.warning("auth.failed", error=str(e), provider=settings.auth.provider)
            return JSONResponse(
                status_code=401,
                content={"error": f"Authentication failed: {e}"},
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

# Wrap lifespan to init auth provider on startup
_original_lifespan = app.router.lifespan_context


@asynccontextmanager
async def lifespan(app_instance):
    log.info(
        "mcp_server.startup",
        auth_provider=settings.auth.provider,
        tools=registered,
    )
    async with _original_lifespan(app_instance) as state:
        yield state
    log.info("mcp_server.shutdown")


app.router.lifespan_context = lifespan

# Load auth provider from config and add middleware
verify = get_verifier(settings)
app.add_middleware(BearerAuthMiddleware, verify_fn=verify)
