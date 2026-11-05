import psycopg

from app.config import settings


def test_can_connect_to_database() -> None:
    """Requires the database to be running: docker compose up -d db"""
    with psycopg.connect(settings.database_url, connect_timeout=5) as conn:
        version = conn.execute("SHOW server_version").fetchone()[0]

    assert version.startswith("16")
