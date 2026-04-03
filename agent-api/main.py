"""Agent API entry point -- FastAPI + ADK agent + Firebase auth + static frontend."""

from contextlib import asynccontextmanager
from pathlib import Path

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from commons.config import settings
from commons.firebase_auth import init_firebase

from .routes import chat, health
from .service.agent import agent_service

structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.add_log_level,
        structlog.processors.JSONRenderer(),
    ],
)
log = structlog.get_logger()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_firebase()
    agent_service.initialize()
    log.info("agent_api.startup", model=settings.llm.model)
    yield
    log.info("agent_api.shutdown")


app = FastAPI(title="MCP Auth Demo API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(chat.router)

# Serve built frontend from /app/static (populated in Docker build)
# Must be LAST -- catches all unmatched routes and serves index.html
_static_dir = Path(__file__).parent.parent / "static"
if _static_dir.exists():
    app.mount("/", StaticFiles(directory=str(_static_dir), html=True), name="frontend")
