"""The models an answer shows, always with the same fields, so the app can draw them as cards or a table.

Each tool returns what the LLM needs: a lookup returns one full record, an ambiguous part number
returns short summaries. The app should not care which tool produced a model, so every product is
completed with the model's full record from the database and checked against `Product`.
"""

from typing import Any, Literal

from pydantic import BaseModel, Field

from app import catalog

Role = Literal["specs", "match", "alternative", "option", "suggestion", "no_data"]


class ServiceRating(BaseModel):
    service: Literal["on_off", "modulating", "unspecified"] = Field(
        description="unspecified: the 3-phase table does not say whether it applies to On/Off or Modulating."
    )
    torque_in_lbs: int
    torque_nm: int
    duty_cycle_pct: int
    cycles_per_hour: int | None = Field(description="On/Off rating. null when the table has no value.")
    starts_per_hour: int | None = Field(description="Modulating rating. null when the table has no value.")


class ElectricalRating(BaseModel):
    frequency_hz: int | None = Field(description="50 or 60. null for 24 V models, whose tables have one value.")
    speed_sec: int = Field(description="Seconds for a 90 degree turn.")
    fla_a: float = Field(description="Full load current, in amps.")
    lra_a: float = Field(description="Locked rotor current, in amps.")


class Difference(BaseModel):
    """Why an alternative does not meet one requirement."""

    requirement: str = Field(description="The requirement, such as min_torque or voltage_v.")
    requested: Any
    actual: Any
    requested_unit: str | None = Field(None, description="For min_torque: the unit the user asked in.")
    table_unit: str | None = Field(None, description="For min_torque: the table column it was compared in.")
    required_in_table_unit: float | None = None


class Product(BaseModel):
    role: Role = Field(
        description=(
            "specs: the model asked for. match: meets the requirements. alternative: closest option "
            "when nothing matches, or a model to look at instead of one without data. option: one of "
            "several models a partial part number names. suggestion: a similar part number. "
            "no_data: listed as N/A in the tables."
        )
    )
    part_number: str
    alias: str = Field(description="Short name such as 2A. Not unique: 2A names several models.")
    enclosure: Literal["weatherproof", "explosionproof"]
    voltage_v: int
    phases: int
    current_type: Literal["AC", "DC", "AC/DC"]
    motor_power_w: int | None
    certifications: list[str]
    hazardous_classification: list[str]
    has_data: bool = Field(description="false: the model exists but the tables give no values (N/A).")
    source_page: int = Field(description="Page of series_76_electric_data.pdf the values come from.")
    service_ratings: list[ServiceRating]
    electrical_ratings: list[ElectricalRating]
    notes: list[str] = Field(description="Caveats to show next to the model, such as a missing CSA certification.")
    differences: list[Difference] = Field(default_factory=list, description="Only for alternatives.")


def roles_from(output: object) -> list[dict]:
    """The models a tool result shows, each with its role, as the tool returned them."""
    if not isinstance(output, dict):
        return []
    match output.get("status"):
        case "found":
            return [{"role": "specs", **output["actuator"]}]
        case "no_data":
            return [{"role": "no_data", **output["actuator"]}] + [
                {"role": "alternative", **model} for model in output.get("alternatives", [])
            ]
        case "ambiguous":
            return [{"role": "option", **model} for model in output["options"]]
        case "not_found":
            return [{"role": "suggestion", **model} for model in output["suggestions"]]
        case "matches":
            return [{"role": "match", **model} for model in output["matches"]]
        case "no_matches":
            return [{"role": "alternative", **model} for model in output["closest"]]
    return []


def complete(found: list[dict]) -> list[dict]:
    """Give every product the same fields, from the model's record in the database."""
    records = catalog.records(p["part_number"] for p in found)
    products = []
    for product in found:
        record = records.get(product["part_number"])
        if record is None:
            continue
        products.append(Product.model_validate({
            **record,
            "role": product["role"],
            # A recommendation writes its own notes, such as "the table does not say whether it applies to Modulating".
            "notes": product.get("notes", record["notes"]),
            "differences": product.get("differences", []),
        }).model_dump(mode="json"))
    return products


def readable(saved: list[dict]) -> list[dict]:
    """Products of a saved message. Messages saved before `Product` existed are completed when read."""
    try:
        return [Product.model_validate(p).model_dump(mode="json") for p in saved]
    except ValueError:
        return complete(saved)


class Focus(BaseModel):
    """Which service and frequency the user asked about, so the app's table opens there.

    Taken by code from the arguments of the last lookup or recommendation, never from the LLM's text.
    null means the user did not say: the app then opens On/Off at 60 Hz.
    """

    service: Literal["on_off", "modulating"] | None = None
    frequency_hz: Literal[50, 60] | None = None


FOCUS_TOOLS = {"get_actuator_specs", "recommend_actuators"}


def focus_from(tool_calls: list[dict]) -> dict:
    for call in reversed(tool_calls):
        # A call the tool rejected comes back as text; its arguments were not used.
        if call["name"] in FOCUS_TOOLS and isinstance(call.get("output"), dict):
            args = call["args"]
            return Focus(service=args.get("service"), frequency_hz=args.get("frequency_hz")).model_dump()
    return Focus().model_dump()
