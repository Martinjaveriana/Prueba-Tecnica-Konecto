"""REST API. Open http://localhost:8000/docs to try it."""

import json
import logging
import time
from contextlib import asynccontextmanager
from datetime import datetime
from decimal import Decimal
from typing import Annotated, Any
from uuid import UUID

import openai
import psycopg
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from langchain_core.language_models import BaseChatModel
from langgraph.errors import GraphRecursionError
from pydantic import BaseModel, Field, StringConstraints

from app import conversations
from app.agent import build_chat_model, run_turn
from app.config import BACKEND_DIR, settings

# Uvicorn already configures this logger, so its messages show in the container logs.
logger = logging.getLogger("uvicorn.error")

PROCESSED_PATH = BACKEND_DIR / "data" / "processed" / "actuators.json"
STARTUP_ATTEMPTS = 15


def load_data() -> None:
    """Create the tables and load the reviewed data, so nobody needs to run ingest.py by hand."""
    from ingestion.load import load

    actuators = json.loads(PROCESSED_PATH.read_text(encoding="utf-8"), parse_float=Decimal)
    for attempt in range(1, STARTUP_ATTEMPTS + 1):
        try:
            counts = load(actuators)
            logger.info("Loaded %s", counts)
            return
        except psycopg.OperationalError:
            if attempt == STARTUP_ATTEMPTS:
                raise
            time.sleep(2)


@asynccontextmanager
async def lifespan(app: FastAPI):
    load_data()
    yield


app = FastAPI(
    title="Series 76 Technical Assistant",
    description="Ask about Series 76 electric actuators by part number, or get recommendations from requirements.",
    lifespan=lifespan,
)


class ConversationRequest(BaseModel):
    session_id: UUID | None = Field(None, description="Leave out to start a new conversation.")
    # Spaces are stripped first, so a blank question is rejected before it spends budget.
    query: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)] = Field(
        ..., description="The user's question."
    )


class ConversationResponse(BaseModel):
    session_id: UUID
    answer: str
    products: list[dict[str, Any]] = Field(description="Models from the tools, each with its role in the answer.")
    needs_clarification: bool = Field(description="True when the user must give more information.")
    debug: dict[str, Any] = Field(description="Tools called, their arguments and results. Hidden from end users.")
    message_id: int
    created_at: datetime


class SessionSummary(BaseModel):
    id: UUID
    title: str
    created_at: datetime
    updated_at: datetime
    message_count: int


class Message(BaseModel):
    id: int
    role: str
    content: str
    products: list[dict[str, Any]]
    needs_clarification: bool
    debug: dict[str, Any] | None
    created_at: datetime


class SessionDetail(BaseModel):
    id: UUID
    title: str
    created_at: datetime
    updated_at: datetime
    messages: list[Message]


def get_chat_model() -> BaseChatModel | None:
    # Returns None instead of failing here, so an invalid request is reported as such first.
    return build_chat_model() if settings.has_openrouter_key() else None


@app.exception_handler(psycopg.OperationalError)
def database_unavailable(request: Request, error: psycopg.OperationalError) -> JSONResponse:
    logger.error("Database unavailable: %s", error)
    return JSONResponse(status_code=503, content={"detail": "The database is not available. Try again in a moment."})


@app.post("/api/conversation", response_model=ConversationResponse)
def converse(request: ConversationRequest, model: BaseChatModel | None = Depends(get_chat_model)) -> dict:
    """Ask a question. Without session_id a new conversation starts and its id is returned."""
    if model is None:
        raise HTTPException(503, "The language model is not configured. Set OPENROUTER_API_KEY in .env.")
    if request.session_id and not conversations.session_exists(request.session_id):
        raise HTTPException(404, "Conversation not found.")
    history = conversations.history(request.session_id) if request.session_id else []

    try:
        result = run_turn(request.query, history, model)
    except openai.APIStatusError as error:
        logger.error("Language model error %s: %s", error.status_code, error.message)
        raise HTTPException(503, f"The language model could not answer (HTTP {error.status_code}). Try again.")
    except (openai.APIConnectionError, openai.APITimeoutError):
        raise HTTPException(503, "The language model did not respond. Try again in a moment.")
    except GraphRecursionError:
        raise HTTPException(503, "The question could not be answered in a reasonable number of steps. Try rephrasing it.")

    saved = conversations.save_turn(
        request.session_id, request.query, result.answer, result.products, result.needs_clarification, result.debug
    )
    return {
        "session_id": saved["session_id"],
        "answer": result.answer,
        "products": result.products,
        "needs_clarification": result.needs_clarification,
        "debug": result.debug,
        "message_id": saved["message_id"],
        "created_at": saved["created_at"],
    }


@app.get("/api/sessions", response_model=list[SessionSummary])
def sessions() -> list[dict]:
    """Saved conversations, most recent first."""
    return conversations.list_sessions()


@app.get("/api/sessions/{session_id}/messages", response_model=SessionDetail)
def session_messages(session_id: UUID) -> dict:
    """A conversation with its messages, to resume it."""
    session = conversations.get_session(session_id)
    if session is None:
        raise HTTPException(404, "Conversation not found.")
    return session


@app.get("/health")
def health() -> dict:
    with psycopg.connect(settings.database_url, connect_timeout=3) as conn:
        conn.execute("SELECT 1")
    return {"status": "ok", "database": "ok", "language_model_configured": settings.has_openrouter_key()}
