"""Test MCP server with Firebase auth token.

Usage:
    python scripts/test_mcp_server.py <firebase_id_token>
    python scripts/test_mcp_server.py  # uses hardcoded test token
"""

import asyncio
import sys

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

MCP_URL = "http://localhost:8001/mcp"


async def test_mcp(token: str):
    print(f"MCP Server: {MCP_URL}")
    print(f"Token: {token[:50]}...")
    print()

    # Step 1: Connect and initialize
    print("--- Step 1: Initialize ---")
    try:
        async with streamablehttp_client(
            MCP_URL,
            headers={"Authorization": f"Bearer {token}"},
        ) as (read_stream, write_stream, _):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                print("OK: MCP session initialized")
                print()

                # Step 2: List tools
                print("--- Step 2: List tools ---")
                tools = await session.list_tools()
                for tool in tools.tools:
                    print(f"  Tool: {tool.name} - {tool.description}")
                print()

                # Step 3: Call weather tool
                print("--- Step 3: Call get_weather('Mumbai') ---")
                result = await session.call_tool("get_weather", {"city": "Mumbai"})
                for content in result.content:
                    print(f"  Result: {content.text}")
                print()

                print("ALL TESTS PASSED")

    except Exception as e:
        print(f"FAILED: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        token = sys.argv[1]
    else:
        # Default test token -- replace or pass as argument
        token = "YOUR_FIREBASE_TOKEN_HERE"
        print("Usage: python scripts/test_mcp_server.py <firebase_id_token>")
        print()

    asyncio.run(test_mcp(token))
