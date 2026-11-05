import copy
import json

import pytest

from ingest import CORRECTIONS_PATH, PROCESSED_PATH, RAW_PATH
from ingestion.build import build, check_rules, expand_rows, normalize_part_number


@pytest.fixture(scope="module")
def raw() -> dict:
    return json.loads(RAW_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def corrections() -> list[dict]:
    return json.loads(CORRECTIONS_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def actuators() -> dict[str, dict]:
    records = json.loads(PROCESSED_PATH.read_text(encoding="utf-8"))
    return {record["part_number"]: record for record in records}


def service(actuator: dict, name: str) -> dict:
    return next(r for r in actuator["service_ratings"] if r["service"] == name)


def electrical(actuator: dict, hz: int | None) -> dict:
    return next(r for r in actuator["electrical_ratings"] if r["frequency_hz"] == hz)


def test_saved_data_matches_a_fresh_build(raw, corrections):
    built, problems = build(raw, corrections)
    assert problems == []
    assert json.loads(json.dumps(built, default=float)) == json.loads(PROCESSED_PATH.read_text(encoding="utf-8"))


def test_every_row_of_the_pdf_is_present(actuators):
    assert len(actuators) == 68
    assert sum(a["has_data"] for a in actuators.values()) == 64


@pytest.mark.parametrize(
    "text, expected",
    [
        ("762B00-1133OC0O/A", ("762B00-11330C00/A", False)),
        ("765AOO-11330CO0/A", ("765A00-11330C00/A", False)),
        ("766A00-11320000/A*", ("766A00-11320000/A", True)),
    ],
)
def test_reading_mistakes_in_part_numbers_are_cleaned(text, expected):
    assert normalize_part_number(text) == expected


def test_merged_part_numbers_keep_values_only_on_the_last_one():
    values = ["2,650", "300"]
    cells, _ = expand_rows([["762B00-1133OC0O/A 763A00-1133OCO0/A", *values]])
    assert cells["762B00-11330C00/A"] is None
    assert cells["763A00-11330C00/A"] == values


def test_a_footnote_stuck_to_a_part_number_is_ignored():
    cells, footnotes = expand_rows([["767C00-11320000/A* * Sizes 6 and 7 are not CSA Certified", "79,700"]])
    assert list(cells) == ["767C00-11320000/A"]
    assert footnotes == {"767C00-11320000/A"}


def find_row(raw: dict, table: int, part_prefix: str) -> list[str]:
    return next(row for row in raw["tables"][table]["rows"] if row[0].startswith(part_prefix))


def test_an_invalid_value_stops_the_build(raw, corrections):
    broken = copy.deepcopy(raw)
    find_row(broken, 0, "761A00")[1] = "7O0"
    actuators, problems = build(broken, corrections)
    assert any("761A00-11300000/A.on_off_in_lbs" in problem for problem in problems)


def test_a_correction_that_no_longer_matches_stops_the_build(raw, corrections):
    stale = copy.deepcopy(corrections)
    stale[0]["read"] = "something else"
    _, problems = build(raw, stale)
    assert any("correction expects" in problem for problem in problems)


def test_a_missing_row_stops_the_build(raw, corrections):
    broken = copy.deepcopy(raw)
    broken["tables"][0]["rows"] = [r for r in broken["tables"][0]["rows"] if not r[0].startswith("761A00")]
    _, problems = build(broken, corrections)
    assert "table 0: 761A00-11300000/A was not found" in problems


def test_a_power_value_outside_its_declared_group_stops_the_build(raw, corrections):
    broken = copy.deepcopy(raw)
    find_row(broken, 0, "761A00")[-1] = "40"
    _, problems = build(broken, corrections)
    assert any("Docling read 40 W" in problem for problem in problems)


def test_torque_rule_catches_a_value_that_looks_valid():
    services = [{"service": "on_off", "torque_in_lbs": 790, "torque_nm": 6, "duty_cycle_pct": 40}]
    assert check_rules("761Y30-11320000/A", services, [])


def test_current_rule_catches_lra_below_fla():
    current = [{"frequency_hz": 60, "speed_sec": 18, "fla_a": 2.3, "lra_a": 1.5}]
    assert check_rules("762A00-11300000/A", [], current)


# Values checked by eye against the PDF images, including the cells that OCR got wrong.
def test_values_match_the_pdf(actuators):
    model = actuators["762A00-11300000/A"]
    assert service(model, "on_off")["torque_nm"] == 150
    assert service(model, "on_off")["cycles_per_hour"] == 42
    assert service(model, "modulating")["torque_nm"] == 130
    assert service(model, "modulating")["starts_per_hour"] == 960
    assert electrical(model, 60) == {"frequency_hz": 60, "speed_sec": 18, "fla_a": 2.3, "lra_a": 2.5}
    assert electrical(model, 50) == {"frequency_hz": 50, "speed_sec": 21, "fla_a": 2.3, "lra_a": 2.4}

    assert service(actuators["761Y30-11320000/A"], "on_off")["torque_nm"] == 90
    assert service(actuators["763A00-11330C00/A"], "unspecified")["cycles_per_hour"] == 39
    assert electrical(actuators["764A00-11320000/A"], 50)["speed_sec"] == 33
    assert electrical(actuators["765Y30-11300000/A"], 60)["speed_sec"] == 93
    assert service(actuators["767C00-11320000/A"], "modulating")["torque_in_lbs"] == 79650


@pytest.mark.parametrize(
    "part, watts",
    [
        ("761A00-11300000/A", 15),
        ("762A00-11300000/A", 40),
        ("763A00-11300000/A", 40),
        ("763B00-11300000/A", 90),
        ("764A00-11300000/A", 180),
        ("767C00-11320000/A", 700),
        ("763A00-11330C00/A", 40),
        ("763X30-11380000/A", 40),
        ("764X30-11300000/A", 90),
        ("764X30-11320000/A", 180),
    ],
)
def test_motor_power_comes_from_the_right_merged_cell(actuators, part, watts):
    assert actuators[part]["motor_power_w"] == watts


def test_summary_example_is_not_in_the_tables(actuators):
    assert "761A00-11380000/A" not in actuators


def test_na_rows_exist_without_values(actuators):
    for prefix in ("761A", "761B", "762A", "762B"):
        model = actuators[f"{prefix}00-11330C00/A"]
        assert model["has_data"] is False
        assert model["motor_power_w"] is None
        assert model["service_ratings"] == []
        assert model["electrical_ratings"] == []


def test_three_phase_rating_is_not_assigned_to_a_service(actuators):
    assert [r["service"] for r in actuators["763B00-11330C00/A"]["service_ratings"]] == ["unspecified"]


def test_24v_models_have_one_service_and_no_frequency(actuators):
    on_off = actuators["761X30-11380000/A"]
    modulating = actuators["761X30-11370000/A"]
    assert on_off["current_type"] == "AC/DC"
    assert modulating["current_type"] == "DC"
    assert [r["service"] for r in on_off["service_ratings"]] == ["on_off"]
    assert [r["service"] for r in modulating["service_ratings"]] == ["modulating"]
    assert [r["frequency_hz"] for r in on_off["electrical_ratings"]] == [None]


def test_sizes_6_and_7_are_not_csa_certified(actuators):
    assert actuators["766A00-11320000/A"]["certifications"] == ["CE", "UKCA"]
    assert actuators["765B00-11320000/A"]["certifications"] == ["CSA", "CE", "UKCA"]


@pytest.mark.parametrize("alias, count", [("1A", 3), ("1X", 4), ("6A", 1)])
def test_an_alias_can_cover_several_models(actuators, alias, count):
    assert sum(a["alias"] == alias for a in actuators.values()) == count
