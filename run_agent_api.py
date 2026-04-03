"""Runner for agent-api (hyphen in dir name can't be imported directly)."""
import importlib
import sys

sys.path.insert(0, ".")
mod = importlib.import_module("agent-api.main")
app = mod.app
