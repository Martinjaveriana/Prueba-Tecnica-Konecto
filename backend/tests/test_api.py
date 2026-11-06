"""The REST API with a scripted LLM. Requires the database: docker compose up -d --wait db"""

import threading
from uuid import uuid4

import openai
import httpx
import psycopg
import pytest
from fastapi.testclient import TestClient

from app import api
from app.api import app, get_chat_model
from app.config import settings
from tests.fake_llm import call, say, scripted

# Every question here starts with this mark, so the tests can delete only their own conversations.
MARK = "[test]"


@pytest.fixture(autouse=True)
def clean_test_sessions():
    yield
    app.dependency_overrides.clear()
    with psycopg.connect(settings.database_url) as conn:
        conn.execute("DELETE FROM sessions WHERE title LIKE %s", (MARK + "%",))


def client_with(*replies) -> TestClient:
    model = scripted(*replies)
    app.dependency_overrides[get_chat_model] = lambda: model
    return TestClient(app)


def ask(client: TestClient, query: str, session_id=None):
    body = {"query": f"{MARK} {query}"}
    if session_id:
        body["session_id"] = str(session_id)
    return client.post("/api/conversation", json=body)


def test_a_question_without_session_starts_a_conversation():
    with client_with(call("get_actuator_specs", identifier="762A00-11300000/A"), say("On/Off gives 150 Nm.")) as client:
        response = ask(client, "Torque of 762A00-11300000/A?")
    assert response.status_code == 200
    body = response.json()
    assert body["session_id"]
    assert body["answer"] == "On/Off gives 150 Nm."
    assert body["products"][0]["part_number"] == "762A00-11300000/A"
    assert body["needs_clarification"] is False
    assert body["debug"]["tool_calls"][0]["name"] == "get_actuator_specs"


def test_a_follow_up_continues_the_same_conversation():
    with client_with(
        call("get_actuator_specs", identifier="762A00-11300000/A"), say("On/Off gives 150 Nm."),
        call("get_actuator_specs", "call-2", identifier="762A00-11300000/A"), say("It draws 40 W."),
    ) as client:
        first = ask(client, "Torque of the 2A at 110 V?").json()
        second = ask(client, "And how much power does it draw?", first["session_id"]).json()
        messages = client.get(f"/api/sessions/{first['session_id']}/messages").json()["messages"]

    assert second["session_id"] == first["session_id"]
    assert second["products"][0]["motor_power_w"] == 40
    assert [m["role"] for m in messages] == ["user", "assistant", "user", "assistant"]


def test_conversations_survive_a_restart():
    with client_with(say("I can only help with Series 76 actuators.")) as client:
        session_id = ask(client, "Hello").json()["session_id"]

    # A new client starts the app again: the history must come from the database.
    with TestClient(app) as restarted:
        assert restarted.get(f"/api/sessions/{session_id}/messages").status_code == 200
        assert any(s["id"] == session_id for s in restarted.get("/api/sessions").json())


def test_sessions_list_has_title_and_date():
    with client_with(say("Which voltage?")) as client:
        session_id = ask(client, "What about the 1A? " + "x" * 100).json()["session_id"]
        session = next(s for s in client.get("/api/sessions").json() if s["id"] == session_id)
    assert session["title"].startswith(MARK)
    assert len(session["title"]) <= 60
    assert session["message_count"] == 2
    assert session["created_at"]


def test_messages_keep_products_and_debug_to_resume_the_chat():
    with client_with(call("get_actuator_specs", identifier="1A"), say("Which voltage?")) as client:
        session_id = ask(client, "What about the 1A?").json()["session_id"]
        assistant = client.get(f"/api/sessions/{session_id}/messages").json()["messages"][1]
    assert assistant["needs_clarification"] is True
    assert len(assistant["products"]) == 3
    assert assistant["debug"]["tool_calls"][0]["args"] == {"identifier": "1A"}


def test_an_unknown_conversation_is_not_found():
    with client_with(say("unused")) as client:
        assert ask(client, "Hello", uuid4()).status_code == 404
        assert client.get(f"/api/sessions/{uuid4()}/messages").status_code == 404


@pytest.mark.parametrize(
    "body", [{"query": ""}, {"query": "   "}, {"query": "\n\t"}, {}, {"query": "Hi", "session_id": "not-a-uuid"}]
)
def test_invalid_requests_are_rejected(body):
    with client_with(say("unused")) as client:
        assert client.post("/api/conversation", json=body).status_code == 422


def openrouter_error(status: int) -> openai.APIStatusError:
    response = httpx.Response(status, request=httpx.Request("POST", "https://openrouter.ai/api/v1/chat/completions"))
    return openai.APIStatusError("error", response=response, body=None)


@pytest.mark.parametrize(
    "error",
    [
        openrouter_error(402),
        openrouter_error(500),
        openai.APITimeoutError(httpx.Request("POST", "https://openrouter.ai")),
    ],
)
def test_a_language_model_failure_returns_503_and_saves_nothing(error, monkeypatch):
    def failing_turn(*args, **kwargs):
        raise error

    monkeypatch.setattr("app.api.run_turn", failing_turn)
    with client_with(say("unused")) as client:
        before = len(client.get("/api/sessions").json())
        response = ask(client, "Torque of 762A00-11300000/A?")
        after = len(client.get("/api/sessions").json())
    assert response.status_code == 503
    assert "language model" in response.json()["detail"]
    assert after == before


def test_without_a_key_the_api_says_how_to_configure_it(monkeypatch):
    monkeypatch.setattr(settings, "openrouter_api_key", "")
    with TestClient(app) as client:
        response = ask(client, "Hello")
    assert response.status_code == 503
    assert "OPENROUTER_API_KEY" in response.json()["detail"]


def test_without_a_key_an_invalid_request_is_still_reported_as_invalid(monkeypatch):
    monkeypatch.setattr(settings, "openrouter_api_key", "")
    with TestClient(app) as client:
        assert client.post("/api/conversation", json={"query": ""}).status_code == 422


def test_the_example_in_the_docs_starts_a_new_conversation():
    # Pressing Execute in /docs must work: the example cannot carry a made-up session_id.
    with TestClient(app) as client:
        schema = client.get("/openapi.json").json()["components"]["schemas"]["ConversationRequest"]
    assert schema["examples"] == [{"query": "What is the output torque of 762A00-11300000/A?"}]


def test_health_reports_the_database_and_the_key():
    with TestClient(app) as client:
        body = client.get("/health").json()
    assert body["status"] == "ok"
    assert "language_model_configured" in body


# The backend must stay up while the database is down: crashing made Docker restart it in a loop.

def database_down(*args, **kwargs):
    raise psycopg.OperationalError("connection refused")


def test_the_backend_starts_without_the_database_and_answers_503(monkeypatch):
    monkeypatch.setattr("app.api.load", database_down)
    with TestClient(app) as client:
        health = client.get("/health")
        listing = client.get("/api/sessions")
    assert health.status_code == 503
    assert health.json()["database"] == "starting"
    assert listing.status_code == 503
    assert "not available yet" in listing.json()["detail"]


def test_it_keeps_retrying_until_the_database_comes_back(monkeypatch):
    attempts = []

    def comes_back_on_the_third_try(actuators):
        attempts.append(1)
        if len(attempts) < 3:
            raise psycopg.OperationalError("connection refused")
        return {"actuators": len(actuators)}

    monkeypatch.setattr("app.api.load", comes_back_on_the_third_try)
    monkeypatch.setattr("app.api.FIRST_RETRY_SEC", 0.01)
    api.data_ready.clear()
    stop = threading.Event()
    api.keep_trying([], stop)
    assert len(attempts) == 3
    assert api.data_ready.is_set()


def test_health_says_when_the_database_goes_down_after_starting(monkeypatch):
    with TestClient(app) as client:
        monkeypatch.setattr(settings, "database_url", "postgresql://nobody@127.0.0.1:1/none")
        response = client.get("/health")
    assert response.status_code == 503
    assert response.json()["database"] == "unavailable"
