"""Load settings.yaml with env var interpolation into typed Pydantic models."""

import os
import re
from pathlib import Path

import yaml
from dotenv import load_dotenv
from pydantic import BaseModel

# Load .env before anything else
load_dotenv(Path(__file__).parent.parent / ".env")


class AuthConfig(BaseModel):
    provider: str = "firebase"
    providers: dict[str, dict] = {}


class GCPConfig(BaseModel):
    project_id: str


class MCPServerConfig(BaseModel):
    url: str
    host: str = "0.0.0.0"
    port: int = 8001
    scopes: list[str] = []


class AgentAPIConfig(BaseModel):
    host: str = "0.0.0.0"
    port: int = 8000


class LLMConfig(BaseModel):
    model: str = "openai/qwen3.5:9b"
    base_url: str | None = None
    api_key: str | None = None


class OAuthConfig(BaseModel):
    enabled: bool = True
    issuer: str = "http://localhost:8001"
    jwt_algorithm: str = "RS256"
    access_token_ttl: int = 3600
    refresh_token_ttl: int = 86400
    auth_code_ttl: int = 300
    firebase_api_key: str = ""
    firebase_auth_domain: str = ""
    firebase_project_id: str = ""


class RoleConfig(BaseModel):
    scopes: list[str] = []


class Settings(BaseModel):
    auth: AuthConfig
    gcp: GCPConfig
    mcp_server: MCPServerConfig
    agent_api: AgentAPIConfig
    llm: LLMConfig
    oauth: OAuthConfig = OAuthConfig()
    roles: dict[str, RoleConfig] = {}


def _interpolate_env(value: str) -> str:
    """Replace ${VAR:default} patterns with env var values."""

    def replacer(match):
        var = match.group(1)
        default = match.group(3) if match.group(3) else ""
        return os.environ.get(var, default)

    return re.sub(r"\$\{([^:}]+)(:([^}]*))?\}", replacer, value)


def _walk_and_interpolate(data):
    """Recursively interpolate env vars in all string values."""
    if isinstance(data, dict):
        return {k: _walk_and_interpolate(v) for k, v in data.items()}
    if isinstance(data, list):
        return [_walk_and_interpolate(v) for v in data]
    if isinstance(data, str):
        return _interpolate_env(data)
    return data


def load_settings(config_path: str | None = None) -> Settings:
    """Load settings from YAML file with env var interpolation."""
    if config_path is None:
        root = Path(__file__).parent.parent
        config_path = str(root / "configs" / "settings.yaml")

    with open(config_path) as f:
        raw = yaml.safe_load(f)

    interpolated = _walk_and_interpolate(raw)
    return Settings(**interpolated)


# Singleton
settings = load_settings()
