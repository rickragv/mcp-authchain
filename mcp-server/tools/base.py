"""Base class for MCP tools. Subclass this to add a new tool.

Adding a new tool:
  1. Create configs/tools/my_tool.yaml (name, description, scopes, api config)
  2. Create mcp-server/tools/my_tool.py (subclass BaseMCPTool, implement execute + register)
  3. Done -- auto-discovered on server startup
"""

import logging
from pathlib import Path
from typing import Any

import yaml
from mcp.server.fastmcp import FastMCP

log = logging.getLogger(__name__)


class BaseMCPTool:
    """Base class for all MCP tools."""

    name: str = ""
    description: str = ""
    required_scopes: list[str] = []
    config: dict = {}  # Raw YAML content -- tool-specific config (api URLs, etc.)

    @classmethod
    def from_yaml(cls, yaml_path: str | Path) -> "BaseMCPTool":
        """Load tool metadata from a YAML config file.

        The YAML overrides name, description, required_scopes, and provides
        additional config (e.g., API URLs) in the `config` dict.
        """
        with open(yaml_path) as f:
            data = yaml.safe_load(f)

        instance = cls()
        instance.name = data.get("name", instance.name)
        instance.description = data.get("description", instance.description)
        instance.required_scopes = data.get("required_scopes", instance.required_scopes)
        instance.config = data
        return instance

    def check_scope(self, auth_scopes: list[str] | None) -> str | None:
        """Return error string if required scope is missing, else None."""
        if not self.required_scopes:
            return None
        if not auth_scopes:
            return f"Permission denied. Missing scopes: {self.required_scopes}"
        for scope in self.required_scopes:
            if scope not in auth_scopes:
                return f"Permission denied. Missing scope: {scope}"
        return None

    async def execute(self, **kwargs: Any) -> dict:
        """Override this with your tool logic."""
        raise NotImplementedError

    def register(self, mcp: FastMCP, mcp_auth) -> None:
        """Override this to register with explicit typed parameters."""
        raise NotImplementedError(
            f"Tool {self.name} must override register() with explicit parameters"
        )
