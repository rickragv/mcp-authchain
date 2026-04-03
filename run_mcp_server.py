"""Runner for mcp-server (hyphen in dir name can't be imported directly)."""
import importlib
import sys

sys.path.insert(0, ".")
mod = importlib.import_module("mcp-server.main")
app = mod.app
