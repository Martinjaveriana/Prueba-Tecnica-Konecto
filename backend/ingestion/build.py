"""Turn Docling's raw tables into validated actuator records.

Code only fixes reading mistakes that have a single possible answer, such as the letter O
inside a part number. A wrong value is never guessed: it is reported as a problem until an
entry in corrections.json, checked against the PDF image, resolves it.
"""

import re
from decimal import Decimal

from .spec import (
    DC_MODULATING,
    DC_ON_OFF,
    ENCLOSURE_TITLE,
    HAZARDOUS_CLASSIFICATION,
    SIZES_WITHOUT_CSA,
    TABLES,
    THREE_PHASE,
    TableSpec,
)

PART_NUMBER_IN_CELL = re.compile(r"76[1-7][A-Z][0-9O]{2}-[0-9A-Z]{8}/A\*?")
INTEGER = re.compile(r"\d{1,3}(,\d{3})+|\d+")
ONE_DECIMAL = re.compile(r"\d+\.\d")
IN_LBS_TO_NM = Decimal("0.113")
TORQUE_TOLERANCE = Decimal("0.05")


def normalize_part_number(text: str) -> tuple[str, bool]:
    """Return the clean part number and whether it carried the '*' footnote mark."""
    head, _, tail = text.partition("-")
    # After the 4th character these positions only hold digits, or the C of the 3-phase code.
    clean = f"{head[:4]}{head[4:].replace('O', '0')}-{tail.rstrip('*').replace('O', '0')}"
    return clean, text.endswith("*")


def expand_rows(rows: list[list[str]]) -> tuple[dict[str, list[str] | None], set[str]]:
    """Map each part number to its cells, or to None when the table says N/A.

    Docling can merge neighbouring part numbers into one cell. Only the last one owns the
    row's values: the ones before it are the N/A rows above it.
    """
    cells_by_part: dict[str, list[str] | None] = {}
    with_footnote: set[str] = set()
    for row in rows:
        found = PART_NUMBER_IN_CELL.findall(row[0].replace(" ", ""))
        for position, text in enumerate(found):
            part, has_footnote = normalize_part_number(text)
            if has_footnote:
                with_footnote.add(part)
            owns_values = position == len(found) - 1 and "N/A" not in row
            cells_by_part[part] = row[1:] if owns_values else None
    return cells_by_part, with_footnote


def parse_value(field: str, text: str) -> int | Decimal | None:
    text = text.strip()
    if field.startswith(("fla", "lra")):
        return Decimal(text) if ONE_DECIMAL.fullmatch(text) else None
    return int(text.replace(",", "")) if INTEGER.fullmatch(text) else None


def service_ratings(layout: tuple[str, ...], values: dict) -> list[dict]:
    def rating(service: str, prefix: str, cycles: str | None, starts: str | None) -> dict:
        return {
            "service": service,
            "torque_in_lbs": values[f"{prefix}in_lbs"],
            "torque_nm": values[f"{prefix}nm"],
            "duty_cycle_pct": values[f"{prefix}duty"],
            "cycles_per_hour": values[cycles] if cycles else None,
            "starts_per_hour": values[starts] if starts else None,
        }

    if layout == THREE_PHASE:
        return [rating("unspecified", "", "cycles", "starts")]
    if layout == DC_ON_OFF:
        return [rating("on_off", "", "cycles", None)]
    if layout == DC_MODULATING:
        return [rating("modulating", "", None, "starts")]
    return [
        rating("on_off", "on_off_", "on_off_cycles", None),
        rating("modulating", "mod_", None, "mod_starts"),
    ]


def electrical_ratings(layout: tuple[str, ...], values: dict) -> list[dict]:
    if layout in (DC_ON_OFF, DC_MODULATING):
        return [{"frequency_hz": None, "speed_sec": values["speed"], "fla_a": values["fla"], "lra_a": values["lra"]}]
    return [
        {
            "frequency_hz": hz,
            "speed_sec": values[f"speed_{hz}"],
            "fla_a": values[f"fla_{hz}"],
            "lra_a": values[f"lra_{hz}"],
        }
        for hz in (60, 50)
    ]


def check_rules(part: str, services: list[dict], electrical: list[dict]) -> list[str]:
    """Rules only report. They can tell that something is wrong, not which cell is."""
    problems = []
    for rating in services:
        expected_nm = rating["torque_in_lbs"] * IN_LBS_TO_NM
        if abs(expected_nm / rating["torque_nm"] - 1) > TORQUE_TOLERANCE:
            problems.append(
                f"{part}: {rating['torque_in_lbs']} in-lbs and {rating['torque_nm']} Nm do not match ({rating['service']})"
            )
        if not 0 < rating["duty_cycle_pct"] <= 100:
            problems.append(f"{part}: duty cycle {rating['duty_cycle_pct']} out of range")
    for rating in electrical:
        if rating["lra_a"] < rating["fla_a"]:
            problems.append(f"{part}: LRA {rating['lra_a']} below FLA {rating['fla_a']} at {rating['frequency_hz']} Hz")
    if len(electrical) == 2 and electrical[0]["speed_sec"] > electrical[1]["speed_sec"]:
        problems.append(f"{part}: 60 Hz is slower than 50 Hz")
    return problems


def build_table(spec: TableSpec, raw_table: dict, corrections: dict, used: set) -> tuple[list[dict], list[str]]:
    problems: list[str] = []
    cells_by_part, with_footnote = expand_rows(raw_table["rows"])

    expected = {spec.part_number(alias): alias for alias in spec.aliases}
    for part in sorted(set(expected) - set(cells_by_part)):
        problems.append(f"table {spec.index}: {part} was not found")
    for part in sorted(set(cells_by_part) - set(expected)):
        problems.append(f"table {spec.index}: unexpected part number {part}")

    actuators = []
    for part, alias in expected.items():
        if part not in cells_by_part:
            continue
        cells = cells_by_part[part]
        size = int(alias[0])

        if (part in with_footnote) != (size in SIZES_WITHOUT_CSA):
            problems.append(f"{part}: the '*' mark does not match the sizes without CSA")
        if (cells is None) != (alias in spec.no_data):
            problems.append(f"{part}: N/A in the table does not match the declared structure")

        services: list[dict] = []
        electrical: list[dict] = []
        if cells is not None:
            if len(cells) != len(spec.layout) + 1:
                problems.append(f"{part}: expected {len(spec.layout) + 1} values, found {len(cells)}")
                continue

            values = {}
            for field, text in zip(spec.layout, cells):
                correction = corrections.get((part, field))
                if correction:
                    used.add((part, field))
                    if correction["read"] != text:
                        problems.append(f"{part}.{field}: correction expects {correction['read']!r}, Docling read {text!r}")
                    text = str(correction["value"])
                value = parse_value(field, text)
                if value is None:
                    problems.append(f"{part}.{field}: {text!r} is not a valid value")
                values[field] = value
            if None in values.values():
                continue

            read_power = cells[-1].strip()
            if read_power and read_power != str(spec.power_of(alias)):
                problems.append(f"{part}: Docling read {read_power} W, declared {spec.power_of(alias)} W")

            services = service_ratings(spec.layout, values)
            electrical = electrical_ratings(spec.layout, values)
            problems += check_rules(part, services, electrical)

        certifications = ["CSA", "CE", "UKCA"] if spec.enclosure == "weatherproof" else ["CSA"]
        if size in SIZES_WITHOUT_CSA:
            certifications.remove("CSA")

        actuators.append({
            "part_number": part,
            "alias": alias,
            "size": size,
            "enclosure": spec.enclosure,
            "voltage_v": spec.voltage_v,
            "phases": spec.phases,
            "current_type": spec.current_type,
            "motor_power_w": spec.power_of(alias),
            "certifications": certifications,
            "hazardous_classification": list(HAZARDOUS_CLASSIFICATION) if spec.enclosure == "explosionproof" else [],
            "has_data": cells is not None,
            "source_page": spec.page,
            "service_ratings": services,
            "electrical_ratings": electrical,
        })
    return actuators, problems


def build(raw: dict, correction_entries: list[dict]) -> tuple[list[dict], list[str]]:
    corrections = {(entry["part_number"], entry["field"]): entry for entry in correction_entries}
    used: set = set()
    actuators: list[dict] = []
    problems: list[str] = []

    if len(raw["tables"]) != len(TABLES):
        return [], [f"expected {len(TABLES)} tables, Docling found {len(raw['tables'])}"]

    for spec, raw_table in zip(TABLES, raw["tables"]):
        if raw_table["page"] != spec.page:
            problems.append(f"table {spec.index}: expected on page {spec.page}, found on {raw_table['page']}")
        page_text = " ".join(raw["page_texts"].get(str(spec.page), [])).upper()
        if spec.title.upper() not in page_text or ENCLOSURE_TITLE[spec.enclosure] not in page_text:
            problems.append(f"table {spec.index}: titles for {spec.title!r} not found on page {spec.page}")

        table_actuators, table_problems = build_table(spec, raw_table, corrections, used)
        actuators += table_actuators
        problems += table_problems

    for key in sorted(set(corrections) - used):
        problems.append(f"correction for {key[0]}.{key[1]} was not used")

    duplicates = len(actuators) - len({a["part_number"] for a in actuators})
    if duplicates:
        problems.append(f"{duplicates} repeated part numbers")
    return actuators, problems
