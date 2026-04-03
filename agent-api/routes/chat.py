"""Chat endpoint -- thin route that delegates to AgentService."""

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from commons.types import FirebaseUser

from ..auth_middleware import get_current_user
from ..service.agent import agent_service

router = APIRouter()


class ChatRequest(BaseModel):
    prompt: str


class ChatResponse(BaseModel):
    response: str
    user_uid: str
    tools_used: list[str] = []


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest, user: FirebaseUser = Depends(get_current_user)):
    result = await agent_service.chat(user, request.prompt)
    return ChatResponse(**result)
