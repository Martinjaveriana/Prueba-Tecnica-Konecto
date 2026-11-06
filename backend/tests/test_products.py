"""Every product reaches the app with the same fields, whichever tool found it. Requires the database."""

import psycopg
import pytest
from fastapi.testclient import TestClient

from app import conversations
from app.agent import run_turn
from app.api import app
from app.config import settings
from app.products import Product, complete, readable
from tests.fake_llm import call, say, scripted

FIELDS = set(Product.model_fields)


def products_of(*calls):
    return run_turn("question", [], scripted(*calls, say("answer"))).products


def test_an_ambiguous_part_number_gives_full_options_to_compare():
    # The tool gives the LLM short summaries; the app still gets torque and current for each option.
    products = products_of(call("get_actuator_specs", identifier="761A00"))
    assert len(products) == 3
    for product in products:
        assert set(product) == FIELDS
        assert product["role"] == "option"
        # One of the three is a 3-phase model listed as N/A: it exists, without values.
        assert bool(product["service_ratings"]) == product["has_data"]
    assert sum(p["has_data"] for p in products) == 2


def test_every_role_has_the_same_fields():
    cases = [
        call("get_actuator_specs", identifier="762A00-11300000/A"),                  # specs
        call("get_actuator_specs", "c2", identifier="762A00-11300000/B"),            # suggestion
        call("recommend_actuators", "c3", min_torque=100, torque_unit="nm"),         # match
        call("recommend_actuators", "c4", min_torque=100000, torque_unit="nm"),      # alternative
    ]
    roles = set()
    for case in cases:
        for product in products_of(case):
            assert set(product) == FIELDS
            roles.add(product["role"])
    assert roles == {"specs", "suggestion", "match", "alternative"}


def test_a_model_without_data_keeps_its_empty_ratings():
    with psycopg.connect(settings.database_url) as conn:
        part = conn.execute("SELECT part_number FROM actuators WHERE NOT has_data LIMIT 1").fetchone()[0]
    products = products_of(call("get_actuator_specs", identifier=part))
    assert products[0]["role"] == "no_data"
    assert products[0]["has_data"] is False
    assert products[0]["service_ratings"] == []
    assert any(p["role"] == "alternative" and p["has_data"] for p in products[1:])


def test_an_alternative_says_why_it_does_not_fit():
    products = products_of(call("recommend_actuators", min_torque=100000, torque_unit="nm"))
    difference = products[0]["differences"][0]
    assert difference["requirement"] == "min_torque"
    assert difference["requested"] == 100000


def test_a_match_keeps_the_note_written_for_the_request():
    products = products_of(call("recommend_actuators", phases=3, service="modulating"))
    assert products
    assert all(any("applies to Modulating" in note for note in p["notes"]) for p in products)


def test_numbers_come_from_the_database():
    product = products_of(call("get_actuator_specs", identifier="762A00-11300000/A"))[0]
    assert product["motor_power_w"] == 40
    assert product["source_page"] == 1


def test_a_message_saved_in_the_old_format_is_completed_when_read():
    old = [{"role": "option", "part_number": "762A00-11300000/A", "alias": "2A", "services": ["on_off"]}]
    assert readable(old) == complete(old)
    assert readable(old)[0]["electrical_ratings"]


@pytest.fixture
def old_session():
    saved = conversations.save_turn(
        None, "[test] old format", "Which one?",
        [{"role": "option", "part_number": "762A00-11300000/A", "alias": "2A"}], True, {},
    )
    yield saved["session_id"]
    with psycopg.connect(settings.database_url) as conn:
        conn.execute("DELETE FROM sessions WHERE id = %s", (saved["session_id"],))


def test_the_api_reads_old_messages_without_failing(old_session):
    with TestClient(app) as client:
        response = client.get(f"/api/sessions/{old_session}/messages")
    assert response.status_code == 200
    assert set(response.json()["messages"][1]["products"][0]) == FIELDS


def test_the_docs_describe_every_product_field():
    with TestClient(app) as client:
        schemas = client.get("/openapi.json").json()["components"]["schemas"]
    assert set(schemas["Product"]["properties"]) == FIELDS
    assert "ServiceRating" in schemas and "ElectricalRating" in schemas
