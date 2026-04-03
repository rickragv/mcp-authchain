"""Agent service -- encapsulates ADK agent lifecycle and chat execution."""

import logging

from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from commons.types import FirebaseUser

from ..agent_setup import create_agent

log = logging.getLogger(__name__)

APP_NAME = "mcp_auth_demo"


class AgentService:
    """Manages the ADK agent, runner, and session service."""

    def __init__(self):
        self._runner: Runner | None = None
        self._session_service = InMemorySessionService()

    def initialize(self):
        """Create the agent and runner. Call once during app startup."""
        agent = create_agent()
        self._runner = Runner(
            agent=agent,
            app_name=APP_NAME,
            session_service=self._session_service,
        )
        log.info("AgentService initialized")

    @property
    def is_ready(self) -> bool:
        return self._runner is not None

    async def chat(self, user: FirebaseUser, prompt: str) -> dict:
        """Run the agent with the user's prompt and return the result.

        Returns dict with keys: response, user_uid, tools_used
        """
        if not self.is_ready:
            return {"response": "Agent not initialized", "user_uid": user.uid, "tools_used": []}

        session = await self._session_service.create_session(
            app_name=APP_NAME,
            user_id=user.uid,
            state={"user_token": user.id_token},
        )

        log.info("chat_request user=%s prompt_len=%d", user.uid, len(prompt))

        response_text = ""
        tools_used = []

        async for event in self._runner.run_async(
            user_id=user.uid,
            session_id=session.id,
            new_message=types.Content(
                role="user",
                parts=[types.Part(text=prompt)],
            ),
        ):
            if hasattr(event, "function_calls") and event.function_calls:
                for fc in event.function_calls:
                    tools_used.append(fc.name)

            if event.is_final_response():
                for part in event.content.parts:
                    if part.text:
                        response_text += part.text

        log.info("chat_response user=%s tools=%s", user.uid, tools_used)

        return {
            "response": response_text or "No response from agent",
            "user_uid": user.uid,
            "tools_used": tools_used,
        }


# Singleton instance
agent_service = AgentService()
