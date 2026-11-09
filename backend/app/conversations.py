"""Conversations stored in PostgreSQL, so they survive a restart of the backend."""

from uuid import UUID

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from app.config import settings

TITLE_LENGTH = 60
# The agent sees the last turns only. Beyond this it is told that some are missing (see agent.py),
# because a model that cannot see the first turn takes the oldest one it can see for the first.
HISTORY_TURNS = 20


def _connect() -> psycopg.Connection:
    return psycopg.connect(settings.database_url, row_factory=dict_row)


def make_title(query: str) -> str:
    """The first question, shortened. No LLM call is spent on titles."""
    text = " ".join(query.split())
    return text if len(text) <= TITLE_LENGTH else text[: TITLE_LENGTH - 1].rstrip() + "…"


def session_exists(session_id: UUID) -> bool:
    with _connect() as conn:
        return conn.execute("SELECT 1 FROM sessions WHERE id = %s", (session_id,)).fetchone() is not None


def list_sessions() -> list[dict]:
    with _connect() as conn:
        return conn.execute(
            """
            SELECT s.id, s.title, s.created_at, s.updated_at, count(m.id) AS message_count
            FROM sessions s
            LEFT JOIN messages m ON m.session_id = s.id
            GROUP BY s.id
            ORDER BY s.updated_at DESC
            """
        ).fetchall()


def get_session(session_id: UUID) -> dict | None:
    with _connect() as conn:
        session = conn.execute(
            "SELECT id, title, created_at, updated_at FROM sessions WHERE id = %s", (session_id,)
        ).fetchone()
        if session is None:
            return None
        session["messages"] = conn.execute(
            """
            SELECT id, role, content, products, needs_clarification, debug, created_at
            FROM messages WHERE session_id = %s ORDER BY id
            """,
            (session_id,),
        ).fetchall()
    return session


def omitted_turns(session_id: UUID) -> int:
    """How many turns of this conversation are too old to reach the agent."""
    with _connect() as conn:
        total = conn.execute("SELECT count(*) AS n FROM messages WHERE session_id = %s", (session_id,)).fetchone()["n"]
    return max(0, total // 2 - HISTORY_TURNS)


def history(session_id: UUID) -> list[dict]:
    """The latest turns, oldest first, with the part numbers each answer looked up."""
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT role, content, debug -> 'part_numbers_consulted' AS part_numbers
            FROM (
                SELECT * FROM messages WHERE session_id = %s ORDER BY id DESC LIMIT %s
            ) latest
            ORDER BY id
            """,
            (session_id, HISTORY_TURNS * 2),
        ).fetchall()
    return [{**row, "part_numbers": row["part_numbers"] or []} for row in rows]


def save_turn(
    session_id: UUID | None,
    query: str,
    answer: str,
    products: list[dict],
    needs_clarification: bool,
    debug: dict,
) -> dict:
    """Save the question and its answer in one transaction: a turn is stored whole or not at all."""
    with _connect() as conn, conn.transaction():
        if session_id is None:
            session_id = conn.execute(
                "INSERT INTO sessions (title) VALUES (%s) RETURNING id", (make_title(query),)
            ).fetchone()["id"]
        else:
            conn.execute("UPDATE sessions SET updated_at = now() WHERE id = %s", (session_id,))
        conn.execute(
            "INSERT INTO messages (session_id, role, content) VALUES (%s, 'user', %s)", (session_id, query)
        )
        message = conn.execute(
            """
            INSERT INTO messages (session_id, role, content, products, needs_clarification, debug)
            VALUES (%s, 'assistant', %s, %s, %s, %s)
            RETURNING id, created_at
            """,
            (session_id, answer, Jsonb(products), needs_clarification, Jsonb(debug)),
        ).fetchone()
    return {"session_id": session_id, "message_id": message["id"], "created_at": message["created_at"]}
