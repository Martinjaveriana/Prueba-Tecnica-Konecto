"""LangChain tools over the catalog. The logic lives in app/catalog.py, tested without an LLM."""

from functools import wraps

import psycopg
from langchain_core.tools import tool
from pydantic import ValidationError

from app import catalog
from app.catalog import Requirements, Service


def _report_database_errors(function):
    """Let the agent tell the user the data is unavailable instead of failing the whole turn."""

    @wraps(function)
    def wrapper(*args, **kwargs) -> dict:
        try:
            return function(*args, **kwargs)
        except psycopg.OperationalError:
            return {"status": "error", "message": "The actuator data is temporarily unavailable."}

    return wrapper


@tool
@_report_database_errors
def get_actuator_specs(
    identifier: str,
    voltage_v: int | None = None,
    phases: int | None = None,
    service: Service | None = None,
    convert_torque: bool = False,
) -> dict:
    """Get the exact technical data of one Series 76 actuator.

    Use it whenever the user names a model, and to answer follow-up questions about it. The result
    also has the allowed voltage and frequency ranges and the datasheet notes.

    Args:
        identifier: The Base Part Number as the user wrote it, complete or partial, or a short alias such as 1A or 5X.
        voltage_v: Supply voltage in volts, to choose among several models.
        phases: Number of phases, to choose among several models.
        service: Service type, to choose among several models.
        convert_torque: True only if the user asked for this model's torque in ft-lbs or kgf-m.
    """
    return catalog.find_actuator(identifier, voltage_v=voltage_v, phases=phases, service=service, convert_torque=convert_torque)


@tool(args_schema=Requirements)
@_report_database_errors
def recommend_actuators(**requirements) -> dict:
    """Find Series 76 actuators that meet technical requirements, tightest fit first.

    Pass only what the user asked for, with torque in the unit the user stated. Each match says
    under which service and frequency it qualifies. If nothing qualifies, it returns the closest
    models and how each one differs.
    """
    return catalog.recommend(Requirements(**requirements))


@tool
@_report_database_errors
def list_available_options() -> dict:
    """List the enclosures, power supplies, services, torque ranges, certifications, hazardous area
    classifications and datasheet notes that exist.

    Use it for questions about what is available, or to offer valid choices.
    """
    return catalog.available_options()


def _explain_invalid_arguments(error: ValidationError) -> str:
    return "Invalid arguments: " + "; ".join(detail["msg"] for detail in error.errors())


TOOLS = [get_actuator_specs, recommend_actuators, list_available_options]

# An invalid argument goes back to the agent as a message it can act on.
for _tool in TOOLS:
    _tool.handle_validation_error = _explain_invalid_arguments
