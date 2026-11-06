"""Deterministic queries over the actuator tables. No LLM takes part in anything here.

Rows come from PostgreSQL with fixed queries, and requirements are evaluated in one Python
function. Matching a model and explaining why another one does not match use the same code,
so the two answers cannot disagree.
"""

import difflib
import re
from decimal import Decimal
from enum import StrEnum
from itertools import product
from typing import Literal

import psycopg
from psycopg.rows import dict_row
from pydantic import BaseModel, Field, model_validator

from app.config import settings

MAX_OPTIONS = 12
MAX_SUGGESTIONS = 3
MAX_CLOSEST = 3
DEFAULT_LIMIT = 5

ALIAS = re.compile(r"[1-7][A-Z]")
# "76" is the whole series; from "761" on, a text can name a group of models.
MIN_PREFIX_LENGTH = 3
FIXED_CONDITIONS = {"enclosure", "voltage_v", "phases", "current_type", "service", "certification"}

NOTE_NO_DATA = "The table lists this model as N/A: it exists, but the PDF gives no values for it."
NOTE_NOT_CSA = "Sizes 6 and 7 are not CSA Certified."
NOTE_SERVICE_UNSPECIFIED = (
    "The table gives a single rating and does not say whether it applies to On/Off or Modulating."
)
NOTE_SERVICE_REQUESTED = "The table does not say whether this rating applies to {service}."
NOTE_NO_FREQUENCY = "The table for this model does not depend on the power frequency."
SERVICE_NAMES = {"on_off": "On/Off", "modulating": "Modulating"}


class TorqueUnit(StrEnum):
    NM = "nm"
    IN_LBS = "in_lbs"
    FT_LBS = "ft_lbs"
    KGF_M = "kgf_m"


class Service(StrEnum):
    ON_OFF = "on_off"
    MODULATING = "modulating"


class Enclosure(StrEnum):
    WEATHERPROOF = "weatherproof"
    EXPLOSIONPROOF = "explosionproof"


class Current(StrEnum):
    AC = "AC"
    DC = "DC"


class Certification(StrEnum):
    CSA = "CSA"
    CE = "CE"
    UKCA = "UKCA"


class Requirements(BaseModel):
    """Technical requirements for choosing an actuator. Leave out what the user did not ask for."""

    min_torque: float | None = Field(None, gt=0, description="Minimum output torque, in torque_unit.")
    torque_unit: TorqueUnit | None = Field(None, description="Unit of min_torque, as the user stated it.")
    service: Service | None = Field(None, description="Service type, if the user stated one.")
    enclosure: Enclosure | None = Field(None, description="explosionproof for hazardous areas.")
    voltage_v: int | None = Field(None, description="Supply voltage in volts.")
    phases: int | None = Field(None, description="Number of power phases: 1 or 3.")
    current_type: Current | None = Field(None, description="AC or DC.")
    frequency_hz: Literal[50, 60] | None = Field(None, description="Power frequency. The tables only list 50 and 60 Hz.")
    max_speed_sec: float | None = Field(None, gt=0, description="Maximum time for a 90-degree turn, in seconds.")
    min_duty_cycle_pct: float | None = Field(None, gt=0, description="Minimum duty cycle, as a percentage.")
    min_cycles_per_hour: int | None = Field(None, gt=0, description="Minimum On/Off cycles per hour.")
    min_starts_per_hour: int | None = Field(None, gt=0, description="Minimum Modulating starts per hour.")
    max_fla_a: float | None = Field(None, gt=0, description="Maximum full load current, in amps.")
    max_lra_a: float | None = Field(None, gt=0, description="Maximum locked rotor current, in amps.")
    max_motor_power_w: int | None = Field(None, gt=0, description="Maximum motor power, in watts.")
    certification: Certification | None = Field(None, description="Certification the model must have.")
    limit: int = Field(DEFAULT_LIMIT, gt=0, le=20, description="Maximum number of models to return.")

    @model_validator(mode="after")
    def torque_needs_a_unit(self) -> "Requirements":
        if self.min_torque is not None and self.torque_unit is None:
            raise ValueError("torque_unit is required with min_torque: ask the user for the unit")
        return self

    def is_empty(self) -> bool:
        return not self.model_dump(exclude_none=True, exclude={"limit"})


def _connect() -> psycopg.Connection:
    return psycopg.connect(settings.database_url, row_factory=dict_row)


def _plain(row: dict) -> dict:
    """Decimal values become plain numbers so tool results serialize to JSON."""
    return {key: float(value) if isinstance(value, Decimal) else value for key, value in row.items()}


def _load_actuators() -> list[dict]:
    with _connect() as conn:
        actuators = conn.execute(
            """
            SELECT part_number, alias, enclosure, voltage_v, phases, current_type, motor_power_w,
                   certifications, hazardous_classification, has_data, source_page
            FROM actuators
            ORDER BY part_number
            """
        ).fetchall()
        services = conn.execute(
            """
            SELECT part_number, service, torque_in_lbs, torque_nm, duty_cycle_pct, cycles_per_hour, starts_per_hour
            FROM service_ratings
            ORDER BY part_number, service
            """
        ).fetchall()
        electrical = conn.execute(
            """
            SELECT part_number, frequency_hz, speed_sec, fla_a, lra_a
            FROM electrical_ratings
            ORDER BY part_number, frequency_hz DESC
            """
        ).fetchall()

    by_part = {a["part_number"]: {**a, "service_ratings": [], "electrical_ratings": []} for a in actuators}
    for row in services:
        part = row.pop("part_number")
        by_part[part]["service_ratings"].append(row)
    for row in electrical:
        part = row.pop("part_number")
        by_part[part]["electrical_ratings"].append(_plain(row))
    return list(by_part.values())


def _base_notes(actuator: dict) -> list[str]:
    notes = []
    if not actuator["has_data"]:
        notes.append(NOTE_NO_DATA)
    if actuator["alias"][0] in "67":
        notes.append(NOTE_NOT_CSA)
    if any(r["service"] == "unspecified" for r in actuator["service_ratings"]):
        notes.append(NOTE_SERVICE_UNSPECIFIED)
    return notes


def _record(actuator: dict) -> dict:
    return {**actuator, "notes": _base_notes(actuator)}


def _summary(actuator: dict) -> dict:
    return {
        "part_number": actuator["part_number"],
        "alias": actuator["alias"],
        "enclosure": actuator["enclosure"],
        "voltage_v": actuator["voltage_v"],
        "phases": actuator["phases"],
        "current_type": actuator["current_type"],
        "services": [r["service"] for r in actuator["service_ratings"]],
        "has_data": actuator["has_data"],
    }


def _compact(text: str) -> str:
    """Accept lowercase, spaces, a missing hyphen, the footnote mark and the letter O for zero."""
    clean = re.sub(r"[\s*-]", "", text).upper()
    # The first 4 characters may hold letters; after them, only the C of the 3-phase code does.
    return clean[:4] + clean[4:].replace("O", "0")


def find_actuator(
    identifier: str,
    voltage_v: int | None = None,
    phases: int | None = None,
    service: str | None = None,
) -> dict:
    """Look up one model by full or partial part number, or by alias."""
    query = _compact(identifier)
    if not query:
        return {"status": "invalid", "message": "No part number was given."}

    actuators = _load_actuators()
    if ALIAS.fullmatch(query):
        matches = [a for a in actuators if a["alias"] == query]
    elif len(query) < MIN_PREFIX_LENGTH:
        matches = []
    else:
        matches = [a for a in actuators if _compact(a["part_number"]).startswith(query)]

    if not matches:
        names = {_compact(a["part_number"]): a for a in actuators}
        close = difflib.get_close_matches(query, names, n=MAX_SUGGESTIONS, cutoff=0.6)
        return {
            "status": "not_found",
            "query": identifier,
            "message": "That part number is not in the Series 76 tables.",
            "suggestions": [_summary(names[name]) for name in close],
        }

    narrowed = [
        a for a in matches
        if (voltage_v is None or a["voltage_v"] == voltage_v)
        and (phases is None or a["phases"] == phases)
        and (service is None or any(r["service"] in (service, "unspecified") for r in a["service_ratings"]))
    ]
    if not narrowed:
        return {
            "status": "not_found",
            "query": identifier,
            "message": "That model exists, but not with the requested voltage, phases or service.",
            "suggestions": [_summary(a) for a in matches[:MAX_OPTIONS]],
        }

    if len(narrowed) > 1:
        return {
            "status": "ambiguous",
            "query": identifier,
            "message": "Several models match. Show them or ask which voltage and service the user needs.",
            "total": len(narrowed),
            "options": [_summary(a) for a in narrowed[:MAX_OPTIONS]],
        }

    actuator = narrowed[0]
    if actuator["has_data"]:
        return {"status": "found", "actuator": _record(actuator)}
    return {
        "status": "no_data",
        "actuator": _record(actuator),
        "alternatives": [_summary(a) for a in _alternatives_to_no_data(actuator, actuators)],
    }


def _alternatives_to_no_data(actuator: dict, actuators: list[dict]) -> list[dict]:
    """Same model with another supply, then the smallest model with data on the same supply.

    They are offered as options to look at, not as equivalents: the PDF does not say why the
    model has no data.
    """
    with_data = [a for a in actuators if a["has_data"]]
    same_alias = [a for a in with_data if a["alias"] == actuator["alias"]]
    same_supply = [
        a for a in with_data
        if all(a[key] == actuator[key] for key in ("enclosure", "voltage_v", "phases", "current_type"))
    ]
    return same_alias + sorted(same_supply, key=lambda a: a["alias"])[:1]


def _required_torque(req: Requirements) -> tuple[str, Decimal]:
    """Compare in the column of the requested unit: the PDF rounds each column on its own.

    Only units the PDF does not have are converted, and only with exact factors.
    """
    value = Decimal(str(req.min_torque))
    match req.torque_unit:
        case TorqueUnit.NM:
            return "torque_nm", value
        case TorqueUnit.IN_LBS:
            return "torque_in_lbs", value
        case TorqueUnit.FT_LBS:
            return "torque_in_lbs", value * 12
        case TorqueUnit.KGF_M:
            return "torque_nm", value * Decimal("9.80665")
    raise ValueError(req.torque_unit)


def _difference(requirement: str, requested: object, actual: object) -> dict:
    return {"requirement": requirement, "requested": requested, "actual": actual}


def _model_differences(actuator: dict, req: Requirements) -> list[dict]:
    differences = []
    if req.enclosure and actuator["enclosure"] != req.enclosure:
        differences.append(_difference("enclosure", req.enclosure.value, actuator["enclosure"]))
    if req.voltage_v is not None and actuator["voltage_v"] != req.voltage_v:
        differences.append(_difference("voltage_v", req.voltage_v, actuator["voltage_v"]))
    if req.phases is not None and actuator["phases"] != req.phases:
        differences.append(_difference("phases", req.phases, actuator["phases"]))
    if req.current_type and actuator["current_type"] not in (req.current_type.value, "AC/DC"):
        differences.append(_difference("current_type", req.current_type.value, actuator["current_type"]))
    if req.max_motor_power_w is not None and actuator["motor_power_w"] > req.max_motor_power_w:
        differences.append(_difference("max_motor_power_w", req.max_motor_power_w, actuator["motor_power_w"]))
    if req.certification and req.certification.value not in actuator["certifications"]:
        differences.append(_difference("certification", req.certification.value, actuator["certifications"]))
    return differences


def _condition_differences(service: dict, electrical: dict, req: Requirements) -> list[dict]:
    differences = []
    if req.min_torque is not None:
        column, required = _required_torque(req)
        if service[column] < required:
            # Name both units: 79,700 in-lbs must not read as a value in the ft-lb the user asked for.
            differences.append({
                **_difference("min_torque", req.min_torque, service[column]),
                "requested_unit": req.torque_unit.value,
                "required_in_table_unit": float(required),
                "table_unit": column.removeprefix("torque_"),
            })
    if req.min_duty_cycle_pct is not None and service["duty_cycle_pct"] < req.min_duty_cycle_pct:
        differences.append(_difference("min_duty_cycle_pct", req.min_duty_cycle_pct, service["duty_cycle_pct"]))
    for field, column in (("min_cycles_per_hour", "cycles_per_hour"), ("min_starts_per_hour", "starts_per_hour")):
        required_rate = getattr(req, field)
        if required_rate is not None and (service[column] is None or service[column] < required_rate):
            differences.append(_difference(field, required_rate, service[column]))
    for field, column in (("max_speed_sec", "speed_sec"), ("max_fla_a", "fla_a"), ("max_lra_a", "lra_a")):
        limit = getattr(req, field)
        if limit is not None and electrical[column] > limit:
            differences.append(_difference(field, limit, electrical[column]))
    return differences


def _evaluate(actuator: dict, req: Requirements) -> dict:
    """Check every combination of service and frequency that the request leaves open."""
    services = [r for r in actuator["service_ratings"] if not req.service or r["service"] in (req.service, "unspecified")]
    model_differences = _model_differences(actuator, req)
    if not services:
        have = [r["service"] for r in actuator["service_ratings"]]
        model_differences.append(_difference("service", req.service.value, have))
        services = actuator["service_ratings"]

    electrical = [e for e in actuator["electrical_ratings"] if not req.frequency_hz or e["frequency_hz"] in (req.frequency_hz, None)]

    meets, fails = [], []
    for service, current in product(services, electrical):
        condition = {"service": service["service"], "frequency_hz": current["frequency_hz"]}
        differences = model_differences + _condition_differences(service, current, req)
        if differences:
            fails.append({**condition, "differences": differences, "_service": service})
        else:
            meets.append({
                **condition,
                "torque_nm": service["torque_nm"],
                "torque_in_lbs": service["torque_in_lbs"],
                "speed_sec": current["speed_sec"],
                "_service": service,
            })
    return {"meets": meets, "fails": fails}


def _torque_for_sorting(condition: dict, req: Requirements) -> int:
    column = _required_torque(req)[0] if req.min_torque is not None else "torque_nm"
    return condition["_service"][column]


def _public(condition: dict) -> dict:
    return {key: value for key, value in condition.items() if key != "_service"}


def _match_notes(actuator: dict, req: Requirements, evaluation: dict) -> list[str]:
    notes = _base_notes(actuator)
    if req.service and any(c["service"] == "unspecified" for c in evaluation["meets"]):
        notes.remove(NOTE_SERVICE_UNSPECIFIED)
        notes.append(NOTE_SERVICE_REQUESTED.format(service=SERVICE_NAMES[req.service]))
    if req.frequency_hz and any(c["frequency_hz"] is None for c in evaluation["meets"]):
        notes.append(NOTE_NO_FREQUENCY)
    return notes


def _is_fixed(difference: dict) -> bool:
    """Something the plant cannot adjust, or a value this rating does not have at all."""
    return difference["requirement"] in FIXED_CONDITIONS or difference["actual"] is None


def _relative_gap(difference: dict) -> float:
    if _is_fixed(difference):
        return 0
    requested = difference.get("required_in_table_unit", difference["requested"])
    return abs(float(requested) - float(difference["actual"])) / float(requested)


def _closeness(actuator: dict, condition: dict, req: Requirements) -> tuple:
    """Rank alternatives. Lower is closer.

    A plant can tolerate a slightly slower actuator, but it cannot change its supply voltage. So
    differences in fixed conditions weigh first, with the voltage as the hardest of them, then the
    number of differences, how far each number is from what was asked and finally the excess torque.
    """
    differences = condition["differences"]
    return (
        sum(_is_fixed(d) for d in differences),
        any(d["requirement"] == "voltage_v" for d in differences),
        len(differences),
        sum(_relative_gap(d) for d in differences),
        _torque_for_sorting(condition, req),
        actuator["part_number"],
    )


def _closest(actuators: list[dict], req: Requirements) -> list[dict]:
    # Safety rule: a request for a hazardous area is never answered with a weatherproof model.
    candidates = [
        a for a in actuators
        if a["has_data"] and (req.enclosure != Enclosure.EXPLOSIONPROOF or a["enclosure"] == Enclosure.EXPLOSIONPROOF)
    ]
    ranked = []
    for actuator in candidates:
        fails = _evaluate(actuator, req)["fails"]
        best = min(fails, key=lambda condition: _closeness(actuator, condition, req))
        ranked.append((_closeness(actuator, best, req), actuator, best))
    ranked.sort(key=lambda item: item[0])

    return [
        {**_record(actuator), "closest_condition": _public(best), "differences": best["differences"]}
        for _, actuator, best in ranked[:MAX_CLOSEST]
    ]


def recommend(req: Requirements) -> dict:
    """Models that meet the requirements, tightest fit first. Alternatives only if none does."""
    if req.is_empty():
        return {
            "status": "needs_requirements",
            "message": "No requirements were given. Ask for torque, voltage, service or enclosure.",
        }

    actuators = _load_actuators()
    matches = []
    for actuator in actuators:
        if not actuator["has_data"]:
            continue
        evaluation = _evaluate(actuator, req)
        if evaluation["meets"]:
            matches.append((actuator, evaluation))

    if not matches:
        return {
            "status": "no_matches",
            "message": (
                "No model meets every requirement. Say so first, then offer these as the closest "
                "options and explain each difference."
            ),
            "closest": _closest(actuators, req),
        }

    matches.sort(key=lambda m: (min(_torque_for_sorting(c, req) for c in m[1]["meets"]), m[0]["part_number"]))
    return {
        "status": "matches",
        "total": len(matches),
        "matches": [
            {
                **actuator,
                "notes": _match_notes(actuator, req, evaluation),
                "meets_under": [_public(c) for c in evaluation["meets"]],
                "does_not_meet_under": [_public(c) for c in evaluation["fails"]],
            }
            for actuator, evaluation in matches[:req.limit]
        ],
    }


def available_options() -> dict:
    """What the catalog actually contains, to answer questions and resolve ambiguity."""
    with _connect() as conn:
        supplies = conn.execute(
            """
            SELECT a.enclosure, a.voltage_v, a.phases, a.current_type,
                   count(*) AS models,
                   array_agg(DISTINCT s.service) AS services,
                   min(s.torque_nm) AS min_torque_nm, max(s.torque_nm) AS max_torque_nm,
                   min(s.torque_in_lbs) AS min_torque_in_lbs, max(s.torque_in_lbs) AS max_torque_in_lbs
            FROM actuators a
            JOIN service_ratings s USING (part_number)
            GROUP BY a.enclosure, a.voltage_v, a.phases, a.current_type
            ORDER BY a.enclosure, a.voltage_v, a.phases, a.current_type
            """
        ).fetchall()
        certifications = conn.execute(
            "SELECT DISTINCT unnest(certifications) AS certification FROM actuators ORDER BY 1"
        ).fetchall()
        frequencies = conn.execute(
            "SELECT DISTINCT frequency_hz FROM electrical_ratings WHERE frequency_hz IS NOT NULL ORDER BY 1"
        ).fetchall()
    return {
        "status": "ok",
        "power_supplies": supplies,
        "certifications": [row["certification"] for row in certifications],
        "frequencies_hz": [row["frequency_hz"] for row in frequencies],
    }
