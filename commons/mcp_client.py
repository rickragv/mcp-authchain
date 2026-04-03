"""Authenticated MCP client with 401-driven token refresh.

Three ways to use:
1. Direct: AuthenticatedMCPClient(url, token, refresh=fn)
2. Inherit: class MyClient(AuthenticatedMCPClient)
3. Decorator: @with_token_refresh(fn)
"""

import logging
from contextlib import asynccontextmanager
from functools import wraps
from typing import Any, Awaitable, Callable

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

from commons.token_refresh import RefreshFn, TokenRefreshError

log = logging.getLogger(__name__)


class AuthenticationError(Exception):
    """MCP server returned 401."""

    pass


class AuthenticatedMCPClient:
    """Base MCP client with automatic 401-retry. Subclass for typed clients."""

    def __init__(self, server_url: str, initial_token: str, refresh: RefreshFn):
        self._server_url = server_url
        self._token = initial_token
        self._refresh = refresh

    @asynccontextmanager
    async def connect(self):
        yield AutoRefreshSession(self._server_url, self)

    async def call_tool(self, name: str, arguments: dict[str, Any] | None = None):
        async with self.connect() as session:
            return await session.call_tool(name, arguments)

    async def _get_token(self) -> str:
        return self._token

    async def _do_refresh(self) -> str:
        self._token = await self._refresh()
        log.info("Token refreshed")
        return self._token


class AutoRefreshSession:
    """Proxy that intercepts 401 → refresh → retry once."""

    def __init__(self, server_url: str, client: AuthenticatedMCPClient):
        self._server_url = server_url
        self._client = client

    async def call_tool(self, name: str, arguments: dict[str, Any] | None = None):
        return await self._with_retry("call_tool", name, arguments or {})

    async def list_tools(self):
        return await self._with_retry("list_tools")

    async def list_resources(self):
        return await self._with_retry("list_resources")

    async def read_resource(self, uri: str):
        return await self._with_retry("read_resource", uri)

    async def list_prompts(self):
        return await self._with_retry("list_prompts")

    async def get_prompt(self, name: str, arguments: dict[str, str] | None = None):
        return await self._with_retry("get_prompt", name, arguments)

    async def _with_retry(self, method: str, *args, **kwargs):
        try:
            return await self._execute(method, *args, **kwargs)
        except AuthenticationError:
            log.info("Got 401, refreshing token and retrying %s", method)
            await self._client._do_refresh()
            try:
                return await self._execute(method, *args, **kwargs)
            except AuthenticationError:
                raise AuthenticationError(
                    f"401 after token refresh on {method}. Token is revoked or invalid."
                )

    async def _execute(self, method: str, *args, **kwargs):
        token = await self._client._get_token()

        try:
            async with streamablehttp_client(
                self._server_url,
                headers={"Authorization": f"Bearer {token}"},
            ) as (read_stream, write_stream, _):
                async with ClientSession(read_stream, write_stream) as session:
                    await session.initialize()
                    fn = getattr(session, method)
                    return await fn(*args, **kwargs)
        except Exception as e:
            if _is_auth_error(e):
                raise AuthenticationError(str(e)) from e
            raise


def _is_auth_error(exc: Exception) -> bool:
    if hasattr(exc, "response") and hasattr(exc.response, "status_code"):
        return exc.response.status_code == 401
    msg = str(exc).lower()
    return "401" in msg or "unauthorized" in msg


def with_token_refresh(refresh: RefreshFn):
    """Decorator that retries an async function once on AuthenticationError."""

    def decorator(fn: Callable[..., Awaitable[Any]]):
        @wraps(fn)
        async def wrapper(*args, **kwargs):
            try:
                return await fn(*args, **kwargs)
            except (AuthenticationError, TokenRefreshError):
                log.info("Token error in %s, refreshing and retrying", fn.__name__)
                await refresh()
                return await fn(*args, **kwargs)

        return wrapper

    return decorator
