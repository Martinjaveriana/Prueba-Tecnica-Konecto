"""Tools and edge cases, without an LLM. Require the database: docker compose up -d --wait db

Expected values were read from the PDF tables, not from the code's output.
"""

import json
from decimal import Decimal

import psycopg
import pytest
from pydantic import ValidationError

from app import catalog
from app.catalog import Requirements, find_actuator, recommend
from app.config import settings
from app.tools import TOOLS, get_actuator_specs, list_available_options, recommend_actuators
from ingest import PROCESSED_PATH
from ingestion.load import load


@pytest.fixture(scope="module", autouse=True)
def loaded_database():
    load(json.loads(PROCESSED_PATH.read_text(encoding="utf-8"), parse_float=Decimal))


def parts(result: dict) -> list[str]:
    return [model["part_number"] for model in result["matches"]]


def req(**fields) -> Requirements:
    return Requirements(limit=20, **fields)


WEATHERPROOF_110 = {"enclosure": "weatherproof", "voltage_v": 110, "phases": 1}


# ---------- Looking up a model ----------


@pytest.mark.parametrize(
    "text",
    [
        "761A00-11300000/A",
        "761a00-11300000/a",
        "  761A00 - 11300000/A ",
        "761A0011300000/A",
        "761A00-11300000/A*",
        "761A00-11300000",
        "761A00-113OOOOO/A",
    ],
)
def test_a_part_number_is_found_however_it_is_written(text):
    result = find_actuator(text)
    assert result["status"] == "found"
    assert result["actuator"]["part_number"] == "761A00-11300000/A"


def test_found_model_has_the_exact_values_of_the_table():
    actuator = find_actuator("762A00-11300000/A")["actuator"]
    on_off = next(r for r in actuator["service_ratings"] if r["service"] == "on_off")
    sixty = next(r for r in actuator["electrical_ratings"] if r["frequency_hz"] == 60)
    assert on_off["torque_nm"] == 150
    assert on_off["cycles_per_hour"] == 42
    assert sixty == {"frequency_hz": 60, "speed_sec": 18, "fla_a": 2.3, "lra_a": 2.5}
    assert actuator["motor_power_w"] == 40


@pytest.mark.parametrize("text, count", [("1A", 3), ("1a", 3), ("761A00", 3), ("1X", 4), ("761X30", 4)])
def test_an_alias_or_partial_number_with_several_models_is_ambiguous(text, count):
    result = find_actuator(text)
    assert result["status"] == "ambiguous"
    assert result["total"] == count
    assert "actuator" not in result


def test_an_alias_with_a_single_model_is_found():
    assert find_actuator("6A")["actuator"]["part_number"] == "766A00-11320000/A"


def test_voltage_resolves_the_ambiguity():
    assert find_actuator("1A", voltage_v=110)["actuator"]["part_number"] == "761A00-11300000/A"


def test_service_resolves_the_24v_ambiguity():
    assert find_actuator("1X", voltage_v=24, service="modulating")["actuator"]["part_number"] == "761X30-11370000/A"


def test_a_filter_no_model_has_is_not_found_and_lists_what_exists():
    result = find_actuator("6A", voltage_v=110)
    assert result["status"] == "not_found"
    assert [s["part_number"] for s in result["suggestions"]] == ["766A00-11320000/A"]


def test_na_model_exists_but_has_no_data():
    result = find_actuator("761A00-11330C00/A")
    assert result["status"] == "no_data"
    assert result["actuator"]["service_ratings"] == []
    assert catalog.NOTE_NO_DATA in result["actuator"]["notes"]


def test_a_mistyped_number_is_not_corrected_silently():
    result = find_actuator("761800-11300000/A")
    assert result["status"] == "not_found"
    assert "actuator" not in result
    assert result["suggestions"][0]["part_number"] == "761B00-11300000/A"


def test_the_example_of_the_summary_is_not_in_the_tables():
    result = find_actuator("761A00-11380000/A")
    assert result["status"] == "not_found"
    assert all(s["part_number"] != "761A00-11380000/A" for s in result["suggestions"])


@pytest.mark.parametrize("text", ["XYZ", "9Z", "12345678", "76", "hello"])
def test_text_that_is_not_a_part_number_is_not_found(text):
    assert find_actuator(text)["status"] == "not_found"


@pytest.mark.parametrize("text", ["", "   "])
def test_an_empty_identifier_is_invalid(text):
    assert find_actuator(text)["status"] == "invalid"


def test_sql_in_the_identifier_does_nothing():
    assert find_actuator("'; DROP TABLE actuators; --")["status"] == "not_found"
    with psycopg.connect(settings.database_url) as conn:
        assert conn.execute("SELECT count(*) FROM actuators").fetchone()[0] == 68


def test_sizes_6_and_7_say_they_are_not_csa():
    actuator = find_actuator("766A00-11320000/A")["actuator"]
    assert "CSA" not in actuator["certifications"]
    assert catalog.NOTE_NOT_CSA in actuator["notes"]


def test_explosionproof_models_include_the_hazardous_classification():
    actuator = find_actuator("761X30-11300000/A")["actuator"]
    assert "Class I, Division 1, Groups C, D; T4" in actuator["hazardous_classification"]
    assert find_actuator("761A00-11300000/A")["actuator"]["hazardous_classification"] == []


# ---------- Recommending ----------


def test_tightest_fit_comes_first_and_only_what_qualifies_is_returned():
    result = recommend(req(min_torque=500, torque_unit="nm", service="on_off", **WEATHERPROOF_110))
    assert result["status"] == "matches"
    assert parts(result) == [
        "763B00-11300000/A",
        "763C00-11300000/A",
        "764A00-11300000/A",
        "764B00-11300000/A",
        "765A00-11300000/A",
        "765B00-11300000/A",
    ]


def test_modulating_torque_is_lower_than_on_off():
    result = recommend(req(min_torque=500, torque_unit="nm", service="modulating", **WEATHERPROOF_110))
    assert parts(result)[0] == "764A00-11300000/A"
    assert result["total"] == 4


def test_the_limit_caps_the_list_but_not_the_total():
    result = recommend(Requirements(min_torque=500, torque_unit="nm", limit=2, **WEATHERPROOF_110))
    assert len(result["matches"]) == 2
    assert result["total"] == 6


@pytest.mark.parametrize("value, unit", [(100, "nm"), (880, "in_lbs")])
def test_torque_is_compared_in_the_column_of_the_requested_unit(value, unit):
    # 100 Nm is about 885 in-lbs: converting would wrongly discard this model, which the PDF lists as 880 / 100.
    result = recommend(req(min_torque=value, torque_unit=unit, service="on_off", **WEATHERPROOF_110))
    assert parts(result)[0] == "761B00-11300000/A"


def test_a_unit_the_pdf_does_not_have_is_converted_with_code():
    # 70 ft-lb = 840 in-lbs: above 761A (700), below 761B (880).
    result = recommend(req(min_torque=70, torque_unit="ft_lbs", service="on_off", **WEATHERPROOF_110))
    assert parts(result)[0] == "761B00-11300000/A"


def test_a_model_is_shown_with_the_frequency_under_which_it_qualifies():
    result = recommend(req(min_torque=300, torque_unit="nm", service="on_off", max_speed_sec=30, **WEATHERPROOF_110))
    model = result["matches"][0]
    assert model["part_number"] == "763A00-11300000/A"
    assert [c["frequency_hz"] for c in model["meets_under"]] == [60]
    assert [c["frequency_hz"] for c in model["does_not_meet_under"]] == [50]
    assert model["does_not_meet_under"][0]["differences"] == [
        {"requirement": "max_speed_sec", "requested": 30, "actual": 31}
    ]


def test_a_stated_frequency_is_applied():
    result = recommend(
        req(min_torque=300, torque_unit="nm", service="on_off", max_speed_sec=30, frequency_hz=50, **WEATHERPROOF_110)
    )
    # At 50 Hz nothing from 300 Nm up turns in 30 s: 763A is the closest, at 31 s.
    assert result["status"] == "no_matches"
    closest = result["closest"][0]
    assert closest["part_number"] == "763A00-11300000/A"
    assert closest["closest_condition"]["frequency_hz"] == 50
    assert closest["differences"] == [{"requirement": "max_speed_sec", "requested": 30, "actual": 31}]


def test_alternatives_keep_the_supply_the_user_asked_for():
    result = recommend(
        req(min_torque=300, torque_unit="nm", service="on_off", max_speed_sec=30, frequency_hz=50, **WEATHERPROOF_110)
    )
    assert {model["voltage_v"] for model in result["closest"]} == {110}


def test_a_model_is_shown_with_the_service_under_which_it_qualifies():
    result = recommend(req(min_torque=500, torque_unit="nm", **WEATHERPROOF_110))
    model = result["matches"][0]
    assert model["part_number"] == "763B00-11300000/A"
    assert {c["service"] for c in model["meets_under"]} == {"on_off"}
    assert {c["service"] for c in model["does_not_meet_under"]} == {"modulating"}


def test_three_phase_models_appear_when_filtering_by_service_with_a_warning():
    result = recommend(req(min_torque=400, torque_unit="nm", service="modulating", phases=3))
    model = result["matches"][0]
    assert model["part_number"] == "763B00-11330C00/A"
    assert model["meets_under"][0]["torque_nm"] == 500
    assert model["meets_under"][0]["service"] == "unspecified"
    assert "does not say whether this rating applies to Modulating" in " ".join(model["notes"])


def test_na_models_are_never_recommended():
    result = recommend(req(phases=3))
    assert result["total"] == 7
    assert not any(part.startswith(("761", "762")) for part in parts(result))


def test_24v_on_off_accepts_ac_or_dc_but_modulating_only_dc():
    ac = recommend(req(voltage_v=24, current_type="AC"))
    assert all(part.endswith("11380000/A") for part in parts(ac))
    dc = recommend(req(voltage_v=24, current_type="DC"))
    assert {part[-10:] for part in parts(dc)} == {"11380000/A", "11370000/A"}


def test_24v_models_do_not_depend_on_frequency():
    result = recommend(req(voltage_v=24, service="on_off", frequency_hz=60))
    model = result["matches"][0]
    assert model["meets_under"][0]["frequency_hz"] is None
    assert catalog.NOTE_NO_FREQUENCY in model["notes"]


def test_certification_filter_excludes_sizes_6_and_7():
    result = recommend(req(min_torque=3500, torque_unit="nm", certification="CE"))
    assert parts(result)[0] == "766A00-11320000/A"
    assert recommend(req(min_torque=3500, torque_unit="nm", certification="CSA"))["status"] == "no_matches"


def test_motor_power_filter():
    result = recommend(req(max_motor_power_w=15, voltage_v=110, enclosure="weatherproof"))
    assert parts(result) == ["761A00-11300000/A", "761B00-11300000/A"]


@pytest.mark.parametrize(
    "field, value, included, excluded",
    [
        ("max_fla_a", 2.0, "761A00-11300000/A", "762A00-11300000/A"),
        ("max_lra_a", 2.0, "761A00-11300000/A", "762A00-11300000/A"),
        ("min_duty_cycle_pct", 45, "762A00-11300000/A", "761A00-11300000/A"),
        ("min_cycles_per_hour", 40, "762A00-11300000/A", "761B00-11300000/A"),
        ("min_starts_per_hour", 900, "761A00-11300000/A", "764A00-11300000/A"),
    ],
)
def test_other_numeric_requirements(field, value, included, excluded):
    found = parts(recommend(req(**{field: value}, **WEATHERPROOF_110)))
    assert included in found
    assert excluded not in found


# ---------- When nothing qualifies ----------


def test_impossible_requirements_say_so_and_explain_the_closest():
    result = recommend(req(enclosure="explosionproof", phases=3, min_torque=400, torque_unit="nm"))
    assert result["status"] == "no_matches"
    assert "matches" not in result
    closest = result["closest"][0]
    assert closest["part_number"].startswith("763Y30")
    assert closest["differences"] == [{"requirement": "phases", "requested": 3, "actual": 1}]


def test_explosionproof_requests_never_get_a_weatherproof_alternative():
    result = recommend(req(enclosure="explosionproof", phases=3, min_torque=400, torque_unit="nm"))
    assert {model["enclosure"] for model in result["closest"]} == {"explosionproof"}


def test_too_much_torque_offers_the_strongest_model():
    result = recommend(req(enclosure="explosionproof", min_torque=10000, torque_unit="nm", service="on_off"))
    closest = result["closest"][0]
    assert closest["part_number"].startswith("765Y30")
    assert closest["differences"] == [{"requirement": "min_torque_nm", "requested": 10000, "actual": 3000}]


def test_24v_ac_modulating_does_not_exist():
    result = recommend(req(voltage_v=24, current_type="AC", service="modulating"))
    assert result["status"] == "no_matches"


def test_weatherproof_24v_does_not_exist_and_each_alternative_explains_its_difference():
    result = recommend(req(enclosure="weatherproof", voltage_v=24))
    assert result["status"] == "no_matches"
    for model in result["closest"]:
        assert len(model["differences"]) == 1
        assert model["differences"][0]["requirement"] in {"enclosure", "voltage_v"}


def test_no_requirements_asks_for_them():
    assert recommend(Requirements())["status"] == "needs_requirements"


def test_torque_without_a_unit_is_rejected():
    with pytest.raises(ValidationError, match="torque_unit is required"):
        Requirements(min_torque=500)


def test_negative_torque_is_rejected():
    with pytest.raises(ValidationError):
        Requirements(min_torque=-5, torque_unit="nm")


# ---------- Available options ----------


def test_options_list_only_what_exists():
    result = list_available_options.invoke({})
    supplies = {(s["enclosure"], s["voltage_v"], s["phases"], s["current_type"]) for s in result["power_supplies"]}
    assert ("weatherproof", 220, 3, "AC") in supplies
    assert ("explosionproof", 24, 1, "DC") in supplies
    assert ("explosionproof", 220, 3, "AC") not in supplies
    assert ("weatherproof", 24, 1, "DC") not in supplies
    assert result["certifications"] == ["CE", "CSA", "UKCA"]
    assert result["frequencies_hz"] == [50, 60]


# ---------- The LangChain layer ----------


def test_the_tools_are_named_and_described_for_the_agent():
    assert {tool.name for tool in TOOLS} == {"get_actuator_specs", "recommend_actuators", "list_available_options"}
    assert all(tool.description for tool in TOOLS)
    assert "min_torque" in recommend_actuators.args


def test_get_actuator_specs_through_langchain():
    result = get_actuator_specs.invoke({"identifier": "1A", "voltage_v": 110, "service": "on_off"})
    assert result["actuator"]["part_number"] == "761A00-11300000/A"


def test_recommend_through_langchain():
    result = recommend_actuators.invoke({"min_torque": 500, "torque_unit": "nm", "service": "on_off", "voltage_v": 110, "enclosure": "weatherproof"})
    assert result["matches"][0]["part_number"] == "763B00-11300000/A"


def test_tool_results_can_be_serialized_to_json():
    for result in (
        get_actuator_specs.invoke({"identifier": "762A00-11300000/A"}),
        recommend_actuators.invoke({"min_torque": 500, "torque_unit": "nm"}),
        list_available_options.invoke({}),
    ):
        json.dumps(result)


def test_an_invalid_argument_comes_back_as_a_message():
    result = recommend_actuators.invoke({"min_torque": 500})
    assert isinstance(result, str)
    assert "torque_unit is required" in result


def test_a_database_failure_comes_back_as_a_message(monkeypatch):
    monkeypatch.setattr(catalog.settings, "database_url", "postgresql://nobody@127.0.0.1:1/none")
    result = get_actuator_specs.invoke({"identifier": "1A"})
    assert result["status"] == "error"
