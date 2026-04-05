"""OAuth 2.1 + DCR route handlers for Starlette."""

import json
import logging
from typing import Callable
from urllib.parse import urlencode

from starlette.requests import Request
from starlette.responses import HTMLResponse, JSONResponse
from starlette.routing import Route

from commons.types import FirebaseUser

from .store import OAuthStore
from .templates import render_authorize_page
from .token_service import mint_access_token
from .pkce import verify_pkce

log = logging.getLogger(__name__)


def oauth_routes(settings, store: OAuthStore, firebase_verify: Callable[[str], FirebaseUser]) -> list[Route]:
    """Create all OAuth route handlers. Returns list of Starlette Routes."""

    # --- Well-Known Metadata ---

    async def protected_resource_metadata(request: Request):
        """RFC 9728 - Protected Resource Metadata."""
        issuer = settings.oauth.issuer
        return JSONResponse({
            "resource": issuer,
            "authorization_servers": [issuer],
            "scopes_supported": settings.mcp_server.scopes,
            "bearer_methods_supported": ["header"],
        })

    async def openid_configuration(request: Request):
        """RFC 8414 - Authorization Server Metadata."""
        issuer = settings.oauth.issuer
        return JSONResponse({
            "issuer": issuer,
            "authorization_endpoint": f"{issuer}/authorize",
            "token_endpoint": f"{issuer}/token",
            "registration_endpoint": f"{issuer}/register",
            "scopes_supported": settings.mcp_server.scopes,
            "response_types_supported": ["code"],
            "grant_types_supported": ["authorization_code", "refresh_token"],
            "token_endpoint_auth_methods_supported": ["none", "client_secret_post"],
            "code_challenge_methods_supported": ["S256"],
        })

    # --- Dynamic Client Registration (RFC 7591) ---

    async def register_client(request: Request):
        """DCR endpoint - registers a new OAuth client."""
        try:
            body = await request.json()
        except Exception:
            return JSONResponse({"error": "invalid_request", "error_description": "Invalid JSON body"}, status_code=400)

        redirect_uris = body.get("redirect_uris")
        if not redirect_uris or not isinstance(redirect_uris, list):
            return JSONResponse(
                {"error": "invalid_client_metadata", "error_description": "redirect_uris is required"},
                status_code=400,
            )

        client_name = body.get("client_name", "Unknown Client")
        grant_types = body.get("grant_types", ["authorization_code", "refresh_token"])
        response_types = body.get("response_types", ["code"])
        auth_method = body.get("token_endpoint_auth_method", "none")

        reg = store.register_client(
            client_name=client_name,
            redirect_uris=redirect_uris,
            grant_types=grant_types,
            response_types=response_types,
            token_endpoint_auth_method=auth_method,
        )

        log.info("oauth.client_registered client_id=%s name=%s", reg.client_id, reg.client_name)

        response = {
            "client_id": reg.client_id,
            "client_name": reg.client_name,
            "redirect_uris": reg.redirect_uris,
            "grant_types": reg.grant_types,
            "response_types": reg.response_types,
            "token_endpoint_auth_method": reg.token_endpoint_auth_method,
        }
        if reg.client_secret:
            response["client_secret"] = reg.client_secret

        return JSONResponse(response, status_code=201)

    # --- Authorization Endpoint ---

    async def authorize(request: Request):
        """Serves the Firebase login page for OAuth authorization."""
        params = request.query_params

        client_id = params.get("client_id", "")
        redirect_uri = params.get("redirect_uri", "")
        response_type = params.get("response_type", "")
        state = params.get("state", "")
        code_challenge = params.get("code_challenge", "")
        code_challenge_method = params.get("code_challenge_method", "")
        scope = params.get("scope", "")

        # Validate required params
        if response_type != "code":
            return JSONResponse(
                {"error": "unsupported_response_type", "error_description": "Only 'code' is supported"},
                status_code=400,
            )

        client = store.get_client(client_id)
        if not client:
            return JSONResponse(
                {"error": "invalid_request", "error_description": "Unknown client_id"},
                status_code=400,
            )

        if redirect_uri not in client.redirect_uris:
            return JSONResponse(
                {"error": "invalid_request", "error_description": "redirect_uri not registered"},
                status_code=400,
            )

        if not code_challenge:
            return JSONResponse(
                {"error": "invalid_request", "error_description": "PKCE code_challenge is required"},
                status_code=400,
            )

        if code_challenge_method != "S256":
            return JSONResponse(
                {"error": "invalid_request", "error_description": "Only S256 code_challenge_method is supported"},
                status_code=400,
            )

        html = render_authorize_page(
            firebase_api_key=settings.oauth.firebase_api_key,
            firebase_auth_domain=settings.oauth.firebase_auth_domain,
            firebase_project_id=settings.oauth.firebase_project_id,
            client_id=client_id,
            redirect_uri=redirect_uri,
            state=state,
            code_challenge=code_challenge,
            code_challenge_method=code_challenge_method,
            scope=scope,
        )
        return HTMLResponse(html)

    async def authorize_callback(request: Request):
        """Receives Firebase token from the login page, generates auth code."""
        try:
            body = await request.json()
        except Exception:
            return JSONResponse({"error": "Invalid JSON body"}, status_code=400)

        firebase_id_token = body.get("firebase_id_token")
        client_id = body.get("client_id")
        redirect_uri = body.get("redirect_uri")
        state = body.get("state", "")
        code_challenge = body.get("code_challenge")
        code_challenge_method = body.get("code_challenge_method")

        if not all([firebase_id_token, client_id, redirect_uri, code_challenge]):
            return JSONResponse({"error": "Missing required fields"}, status_code=400)

        # Validate client
        client = store.get_client(client_id)
        if not client:
            return JSONResponse({"error": "Unknown client_id"}, status_code=400)

        if redirect_uri not in client.redirect_uris:
            return JSONResponse({"error": "redirect_uri not registered"}, status_code=400)

        # Verify Firebase token using the existing provider
        try:
            user = firebase_verify(firebase_id_token)
        except Exception as e:
            log.warning("oauth.firebase_verify_failed error=%s", str(e))
            return JSONResponse({"error": f"Firebase authentication failed: {e}"}, status_code=401)

        # Generate authorization code
        auth_code = store.store_auth_code(
            client_id=client_id,
            redirect_uri=redirect_uri,
            code_challenge=code_challenge,
            code_challenge_method=code_challenge_method,
            firebase_uid=user.uid,
            firebase_email=user.email,
            firebase_role=user.role,
            firebase_scopes=user.scopes,
        )

        log.info("oauth.code_issued uid=%s client=%s", user.uid, client_id)

        # Build redirect URL
        query = urlencode({"code": auth_code.code, "state": state})
        redirect_url = f"{redirect_uri}?{query}"

        return JSONResponse({"redirect_url": redirect_url})

    # --- Token Endpoint ---

    async def token(request: Request):
        """Exchange authorization code or refresh token for access token."""
        # OAuth spec requires application/x-www-form-urlencoded
        content_type = request.headers.get("content-type", "")
        if "application/x-www-form-urlencoded" in content_type:
            form = await request.form()
            body = dict(form)
        elif "application/json" in content_type:
            # Some clients send JSON - be lenient
            body = await request.json()
        else:
            # Try form-encoded by default
            form = await request.form()
            body = dict(form)

        grant_type = body.get("grant_type")

        if grant_type == "authorization_code":
            return await _handle_authorization_code(body, settings, store)
        elif grant_type == "refresh_token":
            return await _handle_refresh_token(body, settings, store)
        else:
            return JSONResponse(
                {"error": "unsupported_grant_type", "error_description": f"Grant type '{grant_type}' not supported"},
                status_code=400,
            )

    return [
        Route("/.well-known/oauth-protected-resource", protected_resource_metadata, methods=["GET"]),
        Route("/.well-known/openid-configuration", openid_configuration, methods=["GET"]),
        Route("/register", register_client, methods=["POST"]),
        Route("/authorize", authorize, methods=["GET"]),
        Route("/authorize/callback", authorize_callback, methods=["POST"]),
        Route("/token", token, methods=["POST"]),
    ]


async def _handle_authorization_code(body: dict, settings, store: OAuthStore) -> JSONResponse:
    """Handle grant_type=authorization_code."""
    code = body.get("code")
    redirect_uri = body.get("redirect_uri")
    client_id = body.get("client_id")
    code_verifier = body.get("code_verifier")

    if not all([code, redirect_uri, client_id, code_verifier]):
        return JSONResponse(
            {"error": "invalid_request", "error_description": "Missing required parameters"},
            status_code=400,
        )

    # Consume auth code (single-use)
    auth_code = store.consume_auth_code(code, ttl=settings.oauth.auth_code_ttl)
    if not auth_code:
        return JSONResponse(
            {"error": "invalid_grant", "error_description": "Invalid or expired authorization code"},
            status_code=400,
        )

    # Validate client and redirect_uri match
    if auth_code.client_id != client_id:
        return JSONResponse(
            {"error": "invalid_grant", "error_description": "client_id mismatch"},
            status_code=400,
        )

    if auth_code.redirect_uri != redirect_uri:
        return JSONResponse(
            {"error": "invalid_grant", "error_description": "redirect_uri mismatch"},
            status_code=400,
        )

    # Verify PKCE
    if not verify_pkce(code_verifier, auth_code.code_challenge, auth_code.code_challenge_method):
        return JSONResponse(
            {"error": "invalid_grant", "error_description": "PKCE verification failed"},
            status_code=400,
        )

    # Mint access token
    access_token, expires_in = mint_access_token(
        settings,
        uid=auth_code.firebase_uid,
        email=auth_code.firebase_email,
        role=auth_code.firebase_role,
        scopes=auth_code.firebase_scopes,
        client_id=client_id,
    )

    # Issue refresh token
    refresh_record = store.store_refresh_token(
        client_id=client_id,
        firebase_uid=auth_code.firebase_uid,
        firebase_email=auth_code.firebase_email,
        firebase_role=auth_code.firebase_role,
        firebase_scopes=auth_code.firebase_scopes,
    )

    log.info("oauth.token_issued uid=%s client=%s", auth_code.firebase_uid, client_id)

    return JSONResponse({
        "access_token": access_token,
        "token_type": "Bearer",
        "expires_in": expires_in,
        "refresh_token": refresh_record.token,
    })


async def _handle_refresh_token(body: dict, settings, store: OAuthStore) -> JSONResponse:
    """Handle grant_type=refresh_token."""
    refresh_token = body.get("refresh_token")
    client_id = body.get("client_id")

    if not all([refresh_token, client_id]):
        return JSONResponse(
            {"error": "invalid_request", "error_description": "Missing required parameters"},
            status_code=400,
        )

    # Consume refresh token (rotation: old token is invalidated)
    record = store.consume_refresh_token(refresh_token, ttl=settings.oauth.refresh_token_ttl)
    if not record:
        return JSONResponse(
            {"error": "invalid_grant", "error_description": "Invalid or expired refresh token"},
            status_code=400,
        )

    if record.client_id != client_id:
        return JSONResponse(
            {"error": "invalid_grant", "error_description": "client_id mismatch"},
            status_code=400,
        )

    # Mint new access token
    access_token, expires_in = mint_access_token(
        settings,
        uid=record.firebase_uid,
        email=record.firebase_email,
        role=record.firebase_role,
        scopes=record.firebase_scopes,
        client_id=client_id,
    )

    # Issue new refresh token (rotation)
    new_refresh = store.store_refresh_token(
        client_id=client_id,
        firebase_uid=record.firebase_uid,
        firebase_email=record.firebase_email,
        firebase_role=record.firebase_role,
        firebase_scopes=record.firebase_scopes,
    )

    log.info("oauth.token_refreshed uid=%s client=%s", record.firebase_uid, client_id)

    return JSONResponse({
        "access_token": access_token,
        "token_type": "Bearer",
        "expires_in": expires_in,
        "refresh_token": new_refresh.token,
    })
