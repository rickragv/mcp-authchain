# Adding New MCP Tools

Tools are YAML-configured and auto-discovered. Adding a tool takes two files.

## Step 1: Create the tool YAML config

```yaml
# configs/tools/stock.yaml
name: "get_stock_price"
description: "Get current stock price by ticker symbol."
required_scopes:
  - "stocks:read"
parameters:
  - name: "ticker"
    type: "string"
    description: "Stock ticker symbol (e.g., AAPL)"
    required: true
api:
  base_url: "https://api.example.com/stock"
```

The YAML defines:
- **name** -- Tool name exposed via MCP
- **description** -- What the LLM sees to decide when to use the tool
- **required_scopes** -- Users need these scopes to call it (set to `[]` for no restriction)
- **parameters** -- Documentation for the tool's inputs
- **api** -- Any tool-specific config (URLs, keys, etc.) accessible in Python via `self.config`

## Step 2: Create the tool Python file

Filename must match the YAML: `configs/tools/stock.yaml` → `mcp-server/tools/stock.py`

```python
# mcp-server/tools/stock.py

import logging
import httpx
from .base import BaseMCPTool

log = logging.getLogger(__name__)


class GetStockPriceTool(BaseMCPTool):

    async def execute(self, ticker: str, **kwargs) -> dict:
        base_url = self.config.get("api", {}).get("base_url", "https://api.example.com/stock")
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(f"{base_url}/{ticker}")
            resp.raise_for_status()
            return resp.json()

    def register(self, mcp, mcp_auth) -> None:
        tool = self

        @mcp.tool(name=self.name, description=self.description)
        async def get_stock_price(ticker: str) -> dict:
            log.info("tool_call tool=%s ticker=%s", tool.name, ticker)
            return await tool.execute(ticker=ticker)
```

Key points:
- **`self.config`** contains the raw YAML -- use it for API URLs, keys, etc.
- **`name` and `description`** are loaded from YAML automatically via `from_yaml()`
- **`register()`** must define the inner function with **explicit typed parameters** (not `**kwargs`) -- FastMCP uses these types for the JSON schema

## Step 3: Add scope to settings

```bash
# .env or configs/settings.yaml
# Add "stocks:read" to the roles that should access this tool
```

In `configs/settings.yaml`:
```yaml
mcp_server:
  scopes:
    - "weather:read"
    - "stocks:read"

roles:
  admin:
    scopes: ["weather:read", "stocks:read"]
  viewer:
    scopes: ["weather:read"]
```

## Step 4: Update agent instructions

```yaml
# configs/agent.yaml
instruction: |
  You have access to get_weather and get_stock_price tools.
  Use get_weather for weather questions.
  Use get_stock_price for stock price questions.
```

## Step 5: Restart

```bash
PYTHONPATH=. python -m uvicorn run_mcp_server:app --host 0.0.0.0 --port 8001
```

Logs should show: `{"tools": ["get_weather", "get_stock_price"], "event": "tools_registered"}`

## How auto-discovery works

1. `mcp-server/tools/__init__.py` scans `configs/tools/*.yaml`
2. For each YAML (e.g., `stock.yaml`), it looks for `mcp-server/tools/stock.py`
3. Finds the `BaseMCPTool` subclass in that module
4. Calls `cls.from_yaml(yaml_path)` to load config into the tool instance
5. Calls `tool.register(mcp, mcp_auth)` to register with FastMCP

**Filename matching**: `configs/tools/weather.yaml` → `mcp-server/tools/weather.py`

## Optional: Create a typed client utility

For direct (non-agent) usage in `agent-api/utils/`:

```python
# agent-api/utils/stock_client.py
from .base import BaseToolClient

class StockMCPClient(BaseToolClient):
    async def get_price(self, ticker: str) -> dict:
        return await self.call_tool("get_stock_price", {"ticker": ticker})
```

Gets 401-retry for free via `BaseToolClient`.

## Tool without scope restriction

```yaml
# configs/tools/echo.yaml
name: "echo"
description: "Echoes back the input message."
required_scopes: []
```

## Tool with multiple parameters

```python
def register(self, mcp, mcp_auth) -> None:
    tool = self

    @mcp.tool(name=self.name, description=self.description)
    async def search_documents(query: str, limit: int = 10) -> dict:
        return await tool.execute(query=query, limit=limit)
```
