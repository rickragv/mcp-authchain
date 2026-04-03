"""Auto-discovery: matches YAML configs in configs/tools/ to Python tool classes.

For each .yaml in configs/tools/:
  1. Finds matching .py in mcp-server/tools/ (by filename)
  2. Loads the BaseMCPTool subclass from that .py
  3. Calls from_yaml() to load config
  4. Registers the tool with FastMCP
"""

import importlib
import pkgutil
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from .base import BaseMCPTool

_discovered_tools: list[type[BaseMCPTool]] = []


def _discover_tool_classes() -> dict[str, type[BaseMCPTool]]:
    """Import all tool modules and return {module_name: ToolClass} mapping."""
    package_dir = Path(__file__).parent
    result = {}

    for module_info in pkgutil.iter_modules([str(package_dir)]):
        if module_info.name in ("base", "__init__"):
            continue
        mod = importlib.import_module(f".{module_info.name}", package=__package__)

        # Find BaseMCPTool subclass in this module
        for attr_name in dir(mod):
            attr = getattr(mod, attr_name)
            if (
                isinstance(attr, type)
                and issubclass(attr, BaseMCPTool)
                and attr is not BaseMCPTool
            ):
                result[module_info.name] = attr
                break

    return result


def register_all_tools(mcp: FastMCP, mcp_auth) -> list[str]:
    """Discover YAML configs and match them to Python tool classes.

    For each configs/tools/<name>.yaml:
      - If mcp-server/tools/<name>.py exists with a BaseMCPTool subclass
      - Load the class via from_yaml(yaml_path)
      - Call tool.register(mcp, mcp_auth)

    Returns list of registered tool names.
    """
    configs_dir = Path(__file__).parent.parent.parent / "configs" / "tools"
    tool_classes = _discover_tool_classes()
    registered = []

    if not configs_dir.exists():
        # Fallback: register tool classes without YAML (use hardcoded defaults)
        for name, cls in tool_classes.items():
            tool = cls()
            tool.register(mcp, mcp_auth)
            registered.append(tool.name)
        return registered

    for yaml_file in sorted(configs_dir.glob("*.yaml")):
        tool_module_name = yaml_file.stem  # e.g., "weather"

        if tool_module_name not in tool_classes:
            continue

        cls = tool_classes[tool_module_name]
        tool = cls.from_yaml(yaml_file)
        tool.register(mcp, mcp_auth)
        registered.append(tool.name)

    return registered
