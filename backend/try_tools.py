"""Try the agent's tools by hand, without an LLM and without spending budget.

    uv run python try_tools.py specs 1A
    uv run python try_tools.py specs 1A --voltage 110
    uv run python try_tools.py recommend min_torque=500 torque_unit=nm service=on_off
    uv run python try_tools.py options
    uv run python try_tools.py specs 1A --full      (the complete result, as the agent receives it)
"""

import argparse
import json

from app.tools import get_actuator_specs, list_available_options, recommend_actuators


def describe(model: dict) -> str:
    return f"{model['part_number']}  ({model['enclosure']}, {model['voltage_v']} V, {model['phases']} phase)"


def show_ratings(model: dict) -> None:
    if not model["has_data"]:
        return
    print(f"  Motor power: {model['motor_power_w']} W | Certifications: {', '.join(model['certifications'])}")
    for rating in model["service_ratings"]:
        rate = rating["cycles_per_hour"] or rating["starts_per_hour"]
        print(
            f"  {rating['service']}: {rating['torque_nm']} Nm / {rating['torque_in_lbs']} in-lbs, "
            f"duty {rating['duty_cycle_pct']}%, {rate} per hour"
        )
    for rating in model["electrical_ratings"]:
        frequency = f"{rating['frequency_hz']} Hz" if rating["frequency_hz"] else "No frequency"
        print(f"  {frequency}: {rating['speed_sec']} s, FLA {rating['fla_a']} A, LRA {rating['lra_a']} A")


def show_difference(difference: dict) -> str:
    unit = difference.get("table_unit")
    actual = f"{difference['actual']} {unit}" if unit else difference["actual"]
    wanted = f"{difference['requested']} {difference['requested_unit']}" if unit else difference["requested"]
    return f"{difference['requirement']}: asked {wanted}, has {actual}"


def show_condition(condition: dict) -> str:
    frequency = f"{condition['frequency_hz']} Hz" if condition["frequency_hz"] else "any frequency"
    return f"{condition['service']} at {frequency}"


def show(result: dict | str) -> None:
    if isinstance(result, str):
        print(result)
        return

    print(f"Status: {result['status']}")
    if "message" in result:
        print(result["message"])

    if "actuator" in result:
        print(describe(result["actuator"]))
        show_ratings(result["actuator"])
        for note in result["actuator"]["notes"]:
            print(f"  Note: {note}")

    if "options" in result:
        print(f"{result['total']} models:")
    for model in result.get("options", []) + result.get("suggestions", []):
        print(f"  {describe(model)}")

    if "matches" in result:
        print(f"{result['total']} models qualify, showing {len(result['matches'])}:")
    for model in result.get("matches", []):
        print(describe(model))
        show_ratings(model)
        print("  Qualifies with: " + "; ".join(show_condition(c) for c in model["meets_under"]))
        for condition in model["does_not_meet_under"]:
            reasons = "; ".join(show_difference(d) for d in condition["differences"])
            print(f"  Does not qualify with {show_condition(condition)}: {reasons}")
        for note in model["notes"]:
            print(f"  Note: {note}")

    for model in result.get("closest", []):
        print(describe(model))
        for difference in model["differences"]:
            print(f"  Differs in {show_difference(difference)}")

    for supply in result.get("power_supplies", []):
        print(
            f"  {supply['enclosure']}, {supply['voltage_v']} V, {supply['phases']} phase, {supply['current_type']}: "
            f"{supply['min_torque_nm']} to {supply['max_torque_nm']} Nm, {'/'.join(supply['services'])}"
        )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    tools = parser.add_subparsers(dest="tool", required=True)

    specs = tools.add_parser("specs")
    specs.add_argument("identifier")
    specs.add_argument("--voltage", type=int)
    specs.add_argument("--phases", type=int)
    specs.add_argument("--service")
    specs.add_argument("--full", action="store_true", help="print the complete result")

    recommend = tools.add_parser("recommend")
    recommend.add_argument("requirements", nargs="*", metavar="field=value")
    recommend.add_argument("--full", action="store_true", help="print the complete result")

    options = tools.add_parser("options")
    options.add_argument("--full", action="store_true", help="print the complete result")

    args = parser.parse_args()

    if args.tool == "specs":
        filters = {"voltage_v": args.voltage, "phases": args.phases, "service": args.service}
        arguments = {"identifier": args.identifier, **{k: v for k, v in filters.items() if v is not None}}
        result = get_actuator_specs.invoke(arguments)
    elif args.tool == "recommend":
        result = recommend_actuators.invoke(dict(item.split("=", 1) for item in args.requirements))
    else:
        result = list_available_options.invoke({})

    if args.full:
        print(json.dumps(result, indent=2))
    else:
        show(result)


if __name__ == "__main__":
    main()
