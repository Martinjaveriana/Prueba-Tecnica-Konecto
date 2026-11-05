"""Require the database to be running: docker compose up -d --wait db"""

import json
from decimal import Decimal

import psycopg

from app.config import settings
from ingest import PROCESSED_PATH
from ingestion.load import load


def actuators() -> list[dict]:
    return json.loads(PROCESSED_PATH.read_text(encoding="utf-8"), parse_float=Decimal)


def test_loading_twice_does_not_duplicate_rows():
    expected = {"actuators": 68, "service_ratings": 111, "electrical_ratings": 118}
    assert load(actuators()) == expected
    assert load(actuators()) == expected


def test_a_failed_load_keeps_the_previous_data():
    load(actuators())
    broken = actuators()
    broken[-1]["enclosure"] = "not an enclosure"
    try:
        load(broken)
    except psycopg.errors.CheckViolation:
        pass
    with psycopg.connect(settings.database_url) as conn:
        assert conn.execute("SELECT count(*) FROM actuators").fetchone()[0] == 68


def test_decimal_values_keep_their_exact_value():
    load(actuators())
    with psycopg.connect(settings.database_url) as conn:
        row = conn.execute(
            "SELECT fla_a, lra_a FROM electrical_ratings WHERE part_number = %s AND frequency_hz = 60",
            ("762A00-11300000/A",),
        ).fetchone()
    assert row == (Decimal("2.3"), Decimal("2.5"))


def test_exact_filters_find_models_through_the_three_tables():
    load(actuators())
    with psycopg.connect(settings.database_url) as conn:
        rows = conn.execute(
            """
            SELECT a.part_number
            FROM actuators a
            JOIN service_ratings s USING (part_number)
            JOIN electrical_ratings e USING (part_number)
            WHERE a.enclosure = 'explosionproof' AND a.voltage_v = 110
              AND s.service = 'modulating' AND s.torque_nm >= 800
              AND e.frequency_hz = 60 AND e.speed_sec <= 40
            """
        ).fetchall()
    assert rows == [("764Y30-11300000/A",)]
