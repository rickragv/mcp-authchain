"""ADK Agent setup -- loads config, creates Agent with McpToolset + LiteLLM."""

import yaml
from pathlib import Path

from google.adk.agents.llm_agent import Agent
from google.adk.models.lite_llm import LiteLlm
from google.adk.tools.mcp_tool.mcp_toolset import McpToolset
from google.adk.tools.mcp_tool.mcp_session_manager import StreamableHTTPConnectionParams

from commons.config import settings


def _load_agent_config() -> dict:
    """Load agent.yaml config."""
    config_path = Path(__file__).parent.parent / "configs" / "agent.yaml"
    with open(config_path) as f:
        return yaml.safe_load(f)


def mcp_header_provider(callback_context) -> dict[str, str]:
    """Injects the current user's Firebase token into MCP requests.

    callback_context.session is per-request, so this is multi-user safe.
    User A's token never appears in User B's MCP calls.
    """
    token = callback_context.session.state.get("user_token")
    if not token:
        return {}
    return {"Authorization": f"Bearer {token}"}


def create_agent() -> Agent:
    """Create the ADK Agent with MCP tools and LiteLLM."""
    agent_config = _load_agent_config()

    mcp_toolset = McpToolset(
        connection_params=StreamableHTTPConnectionParams(
            url=settings.mcp_server.url,
        ),
        header_provider=mcp_header_provider,
    )

    llm_kwargs = {"model": settings.llm.model}
    if settings.llm.base_url:
        llm_kwargs["api_base"] = settings.llm.base_url
    if settings.llm.api_key:
        llm_kwargs["api_key"] = settings.llm.api_key

    agent = Agent(
        model=LiteLlm(**llm_kwargs),
        name=agent_config["name"],
        description=agent_config.get("description", ""),
        instruction=agent_config.get("instruction", ""),
        tools=[mcp_toolset],
    )

    return agent
