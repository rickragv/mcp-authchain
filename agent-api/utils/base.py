"""Base class for agent-side MCP client utilities.

Inherits AuthenticatedMCPClient -- every method gets 401-retry for free.
"""

from commons.mcp_client import AuthenticatedMCPClient
from commons.token_refresh import RefreshFn


class BaseToolClient(AuthenticatedMCPClient):
    """Base class for typed MCP tool client utilities.

    Subclass this and add typed methods for each MCP tool.
    All calls auto-retry on 401 via inherited AuthenticatedMCPClient.

    Example:
        class MyClient(BaseToolClient):
            async def do_thing(self) -> dict:
                return await self.call_tool("my_tool", {"arg": "val"})
    """

    def __init__(self, server_url: str, initial_token: str, refresh: RefreshFn):
        super().__init__(server_url, initial_token, refresh)
