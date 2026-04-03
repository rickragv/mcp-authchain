# Creating New Agents

This guide explains how ADK agents work in this repo, how context flows through the system, and how to create new agents.

## How the current agent works

### Agent definition (`configs/agent.yaml`)

```yaml
name: "mcp_auth_agent"
model: "openai/qwen3.5:9b"
description: "Weather assistant"
instruction: |
  You are a weather assistant...
```

### Agent setup (`agent-api/agent_setup.py`)

```python
agent = Agent(
    model=LiteLlm(**llm_kwargs),
    name=agent_config["name"],
    instruction=agent_config["instruction"],
    tools=[mcp_toolset],  # MCP tools via authenticated connection
)
```

### Context flow: How user identity reaches MCP tools

```
1. User sends: POST /chat + Bearer token
                    │
2. auth_middleware.py: verify_token(token) → FirebaseUser
                    │
3. chat.py: Create ADK session with user's token in state
            session.state = {"user_token": user.id_token}
                    │
4. Runner executes agent with this session
                    │
5. Agent decides to call MCP tool (e.g., get_weather)
                    │
6. McpToolset calls header_provider(callback_context)
   → callback_context.session.state["user_token"]
   → Returns: {"Authorization": "Bearer <user's token>"}
                    │
7. MCP server receives request with user's Bearer token
   → Validates token → Executes tool → Returns result
```

The key is **`header_provider`** in `agent_setup.py`:

```python
def mcp_header_provider(callback_context) -> dict[str, str]:
    token = callback_context.session.state.get("user_token")
    return {"Authorization": f"Bearer {token}"} if token else {}
```

This is called by ADK before every MCP request. It reads the token from the **per-request session**, not a global variable. This is what makes it multi-user safe.

## Creating a new agent

### Option 1: Change the existing agent via config

Edit `configs/agent.yaml`:

```yaml
name: "my_new_agent"
model: "openai/qwen3.5:9b"
description: "Multi-purpose assistant with weather and document tools"
instruction: |
  You are an assistant with access to weather and document tools.
  Use get_weather for weather questions.
  Use search_documents for document queries.
  Be concise and factual.
```

Restart agent-api. No code changes needed.

### Option 2: Create a new agent programmatically

If you need different tools or behavior, create a new agent in `agent-api/agent_setup.py`:

```python
def create_weather_agent() -> Agent:
    """Agent that only uses weather tools."""
    agent_config = _load_agent_config()

    mcp_toolset = McpToolset(
        connection_params=StreamableHTTPConnectionParams(
            url=settings.mcp_server.url,
        ),
        header_provider=mcp_header_provider,
        tool_filter=["get_weather"],  # Only expose weather tool
    )

    return Agent(
        model=LiteLlm(model=settings.llm.model, api_base=settings.llm.base_url, api_key=settings.llm.api_key),
        name="weather_agent",
        instruction="You are a weather assistant. Only answer weather questions.",
        tools=[mcp_toolset],
    )


def create_admin_agent() -> Agent:
    """Agent with access to all tools."""
    mcp_toolset = McpToolset(
        connection_params=StreamableHTTPConnectionParams(
            url=settings.mcp_server.url,
        ),
        header_provider=mcp_header_provider,
        # No tool_filter = all tools available
    )

    return Agent(
        model=LiteLlm(model=settings.llm.model, api_base=settings.llm.base_url, api_key=settings.llm.api_key),
        name="admin_agent",
        instruction="You are an admin assistant with full tool access.",
        tools=[mcp_toolset],
    )
```

### Option 3: Multi-agent setup (sub-agents)

ADK supports agents as tools for other agents:

```python
weather_agent = Agent(
    model=LiteLlm(model=settings.llm.model),
    name="weather_agent",
    description="Handles weather queries",
    instruction="Use get_weather to answer weather questions.",
    tools=[weather_mcp_toolset],
)

stock_agent = Agent(
    model=LiteLlm(model=settings.llm.model),
    name="stock_agent",
    description="Handles stock price queries",
    instruction="Use get_stock_price to answer stock questions.",
    tools=[stock_mcp_toolset],
)

# Coordinator agent delegates to sub-agents
coordinator = Agent(
    model=LiteLlm(model=settings.llm.model),
    name="coordinator",
    description="Routes queries to the right specialist agent",
    instruction="Route weather questions to weather_agent, stock questions to stock_agent.",
    tools=[weather_agent, stock_agent],  # Agents as tools
)
```

### Option 4: Role-based agent selection

Select which agent to use based on the user's role:

```python
# agent-api/routes/chat.py

@router.post("/chat")
async def chat(request: ChatRequest, user: FirebaseUser = Depends(get_current_user)):
    # Choose agent based on user role
    if user.role == "admin":
        runner = admin_runner
    else:
        runner = viewer_runner

    session = await session_service.create_session(
        app_name=APP_NAME,
        user_id=user.uid,
        state={"user_token": user.id_token, "user_role": user.role},
    )

    async for event in runner.run_async(
        user_id=user.uid,
        session_id=session.id,
        new_message=types.Content(role="user", parts=[types.Part(text=request.prompt)]),
    ):
        ...
```

## Adding custom (non-MCP) tools to an agent

You can mix MCP tools with plain Python functions:

```python
def get_current_time(timezone: str = "UTC") -> dict:
    """Returns the current time in the specified timezone."""
    from datetime import datetime
    import pytz
    tz = pytz.timezone(timezone)
    now = datetime.now(tz)
    return {"time": now.strftime("%H:%M:%S"), "timezone": timezone}

agent = Agent(
    model=LiteLlm(model=settings.llm.model),
    name="my_agent",
    instruction="You can check weather and time.",
    tools=[mcp_toolset, get_current_time],  # Mix MCP tools + plain functions
)
```

## Passing additional context to the agent

You can put anything in the session state and access it in tools:

```python
# In chat.py: store user info in session
session = await session_service.create_session(
    app_name=APP_NAME,
    user_id=user.uid,
    state={
        "user_token": user.id_token,
        "user_email": user.email,
        "user_role": user.role,
        "user_scopes": user.scopes,
        "preferred_units": "metric",  # Custom context
    },
)
```

Access in a custom tool:

```python
def get_user_preferences(tool_context) -> dict:
    """Returns the current user's preferences."""
    state = tool_context.state
    return {
        "email": state.get("user_email"),
        "role": state.get("user_role"),
        "units": state.get("preferred_units"),
    }
```

## Testing a new agent

```bash
# Direct API test
curl -X POST http://localhost:8000/chat \
  -H "Authorization: Bearer <firebase_token>" \
  -H "Content-Type: application/json" \
  -d '{"prompt": "weather in London"}'

# Check agent-api logs for tool calls
tail -f agent-api.log
```
