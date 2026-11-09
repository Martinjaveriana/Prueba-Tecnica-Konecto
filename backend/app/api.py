"""REST API. Open http://localhost:8000/docs to try it."""

import json
import logging
import threading
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
from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from app import conversations
from app.products import Focus, Product, focus_from, readable
from app.agent import build_chat_model, run_turn
from app.config import BACKEND_DIR, settings
from ingestion.load import load

# Uvicorn already configures this logger, so its messages show in the container logs.
logger = logging.getLogger("uvicorn.error")

PROCESSED_PATH = BACKEND_DIR / "data" / "processed" / "actuators.json"
FIRST_RETRY_SEC = 2
MAX_RETRY_SEC = 30
DATABASE_STARTING = "The database is not available yet. Try again in a moment."

# Set once the tables exist and hold the catalog. Until then every endpoint answers 503.
data_ready = threading.Event()


def try_load_data(actuators: list[dict]) -> bool:
    """Create the tables and load the reviewed data, so nobody needs to run ingest.py by hand."""
    try:
        counts = load(actuators)
    except psycopg.OperationalError as error:
        logger.warning("Database not available, will retry: %s", str(error).strip().splitlines()[0])
        return False
    logger.info("Loaded %s", counts)
    data_ready.set()
    return True


def keep_trying(actuators: list[dict], stop: threading.Event) -> None:
    # The backend stays up while the database is down: crashing would only make Docker restart it in a loop.
    delay = FIRST_RETRY_SEC
    while not stop.wait(delay):
        if try_load_data(actuators):
            return
        delay = min(delay * 2, MAX_RETRY_SEC)


@asynccontextmanager
async def lifespan(app: FastAPI):
    data_ready.clear()
    actuators = json.loads(PROCESSED_PATH.read_text(encoding="utf-8"), parse_float=Decimal)
    stop = threading.Event()
    if not try_load_data(actuators):
        threading.Thread(target=keep_trying, args=(actuators, stop), daemon=True).start()
    yield
    stop.set()


def require_database() -> None:
    if not data_ready.is_set():
        raise HTTPException(503, DATABASE_STARTING)


app = FastAPI(
    title="Series 76 Technical Assistant",
    description="Ask about Series 76 electric actuators by part number, or get recommendations from requirements.",
    lifespan=lifespan,
)


class ConversationRequest(BaseModel):
    # The example in /docs must work as is: a made-up session_id would answer 404.
    model_config = ConfigDict(
        json_schema_extra={"examples": [{"query": "What is the output torque of 762A00-11300000/A?"}]}
    )

    session_id: UUID | None = Field(
        None, description="Leave out to start a new conversation. To continue one, use the session_id it returned."
    )
    # Spaces are stripped first, so a blank question is rejected before it spends budget.
    query: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)] = Field(
        ..., description="The user's question."
    )


class ConversationResponse(BaseModel):
    session_id: UUID
    answer: str
    products: list[Product] = Field(
        description="Models the answer is about, always with every field, built by code from the database."
    )
    needs_clarification: bool = Field(description="True when the user must give more information.")
    focus: Focus = Field(description="Service and frequency the question was about, for the app's comparison table.")
    debug: dict[str, Any] = Field(description="Tools called, their arguments and results. Hidden from end users.")
    message_id: int
    created_at: datetime


class ErrorResponse(BaseModel):
    detail: str


NOT_FOUND = {404: {"model": ErrorResponse, "description": "The conversation does not exist."}}
UNAVAILABLE = {503: {"model": ErrorResponse, "description": "The language model or the database is not available."}}


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
    products: list[Product]
    needs_clarification: bool
    focus: Focus
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


@app.post("/api/conversation", response_model=ConversationResponse, responses={**NOT_FOUND, **UNAVAILABLE})
def converse(request: ConversationRequest, model: BaseChatModel | None = Depends(get_chat_model)) -> dict:
    """Ask a question. Without session_id a new conversation starts and its id is returned."""
    if model is None:
        raise HTTPException(503, "The language model is not configured. Set OPENROUTER_API_KEY in .env.")
    require_database()
    if request.session_id and not conversations.session_exists(request.session_id):
        raise HTTPException(404, "Conversation not found.")
    history = conversations.history(request.session_id) if request.session_id else []
    omitted = conversations.omitted_turns(request.session_id) if request.session_id else 0

    try:
        result = run_turn(request.query, history, model, omitted_turns=omitted)
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
        "focus": result.focus,
        "debug": result.debug,
        "message_id": saved["message_id"],
        "created_at": saved["created_at"],
    }


@app.get("/api/sessions", response_model=list[SessionSummary], responses=UNAVAILABLE)
def sessions() -> list[dict]:
    """Saved conversations, most recent first."""
    require_database()
    return conversations.list_sessions()


@app.get("/api/sessions/{session_id}/messages", response_model=SessionDetail, responses={**NOT_FOUND, **UNAVAILABLE})
def session_messages(session_id: UUID) -> dict:
    """A conversation with its messages, to resume it."""
    require_database()
    session = conversations.get_session(session_id)
    if session is None:
        raise HTTPException(404, "Conversation not found.")
    for message in session["messages"]:
        message["products"] = readable(message["products"])
        message["focus"] = focus_from((message["debug"] or {}).get("tool_calls", []))
    return session


@app.get("/health", responses={503: {"description": "The database is down or the catalog is not loaded yet."}})
def health() -> JSONResponse:
    """200 when the API can answer. Docker marks the container unhealthy on 503, without restarting it."""
    database = "ok"
    if not data_ready.is_set():
        database = "starting"
    else:
        try:
            with psycopg.connect(settings.database_url, connect_timeout=3) as conn:
                conn.execute("SELECT 1")
        except psycopg.OperationalError:
            database = "unavailable"
    ok = database == "ok"
    body = {
        "status": "ok" if ok else "unavailable",
        "database": database,
        "language_model_configured": settings.has_openrouter_key(),
    }
    return JSONResponse(status_code=200 if ok else 503, content=body)
