"""Compare the reviewed data with an independent reading by a vision model.

This is a one-time check during development, not part of the normal flow. The model never
changes the data: each difference is a cell for a person to check against the PDF image.
Docling reads the tables through RapidOCR, so a second OCR would not be independent.
"""

import json
import time
from decimal import Decimal, InvalidOperation
from pathlib import Path

import pymupdf
from google import genai
from google.genai import errors, types
from pydantic import BaseModel

from app.config import settings

from .spec import DC_MODULATING, DC_ON_OFF, TABLES, THREE_PHASE, TableSpec

RENDER_DPI = 200
MAX_ATTEMPTS = 4

PROMPT = """Transcribe every table on this page of a datasheet, exactly as printed.

- Do not correct, complete or infer anything. Copy each value as you see it.
- part_number: the Base Part Number, including any trailing asterisk.
- cells: the values of that row from left to right, without the part number and without Motor Power.
- If a row says N/A, return an empty cells list.
- motor_power: the Watts value that applies to the row. It is a merged cell spanning several rows, delimited by
  horizontal lines, so repeat it on every row of its block. Use an empty string for N/A rows.
"""


class RowReading(BaseModel):
    part_number: str
    cells: list[str]
    motor_power: str


class TableReading(BaseModel):
    title: str
    rows: list[RowReading]


class PageReading(BaseModel):
    tables: list[TableReading]


def read_page(client: genai.Client, png: bytes) -> PageReading:
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            response = client.models.generate_content(
                model=settings.audit_model,
                contents=[types.Part.from_bytes(data=png, mime_type="image/png"), PROMPT],
                config=types.GenerateContentConfig(
                    temperature=0,
                    response_mime_type="application/json",
                    response_schema=PageReading,
                ),
            )
            return PageReading.model_validate_json(response.text)
        except errors.APIError as error:
            if error.code not in (429, 500, 503) or attempt == MAX_ATTEMPTS:
                raise
            time.sleep(30 * attempt)
    raise RuntimeError("unreachable")


def expected_cells(spec: TableSpec, actuator: dict) -> dict[str, object]:
    """Lay out a reviewed record in the same order as its printed row."""
    services = {rating["service"]: rating for rating in actuator["service_ratings"]}
    electrical = {rating["frequency_hz"]: rating for rating in actuator["electrical_ratings"]}

    def service_cells(service: str, rate_field: str) -> list:
        rating = services[service]
        return [rating["torque_in_lbs"], rating["torque_nm"], rating["duty_cycle_pct"], rating[rate_field]]

    if spec.layout == THREE_PHASE:
        rating = services["unspecified"]
        values = [rating["torque_in_lbs"], rating["torque_nm"], rating["duty_cycle_pct"],
                  rating["cycles_per_hour"], rating["starts_per_hour"]]
    elif spec.layout == DC_ON_OFF:
        values = service_cells("on_off", "cycles_per_hour")
    elif spec.layout == DC_MODULATING:
        values = service_cells("modulating", "starts_per_hour")
    else:
        values = service_cells("on_off", "cycles_per_hour") + service_cells("modulating", "starts_per_hour")

    if spec.layout in (DC_ON_OFF, DC_MODULATING):
        only = electrical[None]
        values += [only["speed_sec"], only["fla_a"], only["lra_a"]]
    else:
        values += [electrical[60]["speed_sec"], electrical[50]["speed_sec"],
                   electrical[60]["fla_a"], electrical[50]["fla_a"],
                   electrical[60]["lra_a"], electrical[50]["lra_a"]]
    return dict(zip(spec.layout, values))


def same_number(ours: object, theirs: str) -> bool:
    try:
        return Decimal(str(ours)) == Decimal(theirs.strip().replace(",", ""))
    except InvalidOperation:
        return False


def compare(actuators: list[dict], rows: dict[str, RowReading]) -> list[dict]:
    by_part = {actuator["part_number"]: actuator for actuator in actuators}
    differences = []

    def report(part: str, field: str, ours: object, theirs: object) -> None:
        differences.append({"part_number": part, "field": field, "ours": ours, "model": theirs})

    for spec in TABLES:
        for alias in spec.aliases:
            part = spec.part_number(alias)
            actuator = by_part[part]
            row = rows.get(part)
            if row is None:
                report(part, "row", "present", "missing")
                continue
            if not actuator["has_data"]:
                if row.cells:
                    report(part, "row", "N/A", row.cells)
                continue
            expected = expected_cells(spec, actuator)
            if len(row.cells) != len(expected):
                report(part, "cell_count", len(expected), len(row.cells))
                continue
            for (field, ours), theirs in zip(expected.items(), row.cells):
                if not same_number(ours, theirs):
                    report(part, field, ours, theirs)
            if not same_number(actuator["motor_power_w"], row.motor_power):
                report(part, "motor_power_w", actuator["motor_power_w"], row.motor_power)

    for part in sorted(set(rows) - set(by_part)):
        report(part, "row", "absent", "present")
    return differences


def audit(pdf_path: Path, processed_path: Path, report_path: Path) -> int:
    if not settings.google_api_key:
        print("Set GOOGLE_API_KEY in .env to run the audit.")
        return 2

    client = genai.Client(api_key=settings.google_api_key)
    actuators = json.loads(processed_path.read_text(encoding="utf-8"))

    # Each page read is kept, so a failure does not spend the free quota on it again.
    pages_dir = report_path.parent / "pages"
    pages_dir.mkdir(parents=True, exist_ok=True)

    rows: dict[str, RowReading] = {}
    readings = []
    for number, page in enumerate(pymupdf.open(pdf_path), 1):
        saved = pages_dir / f"{settings.audit_model}_page_{number}.json"
        if saved.exists():
            reading = PageReading.model_validate_json(saved.read_text(encoding="utf-8"))
        else:
            print(f"Reading page {number} with {settings.audit_model}...")
            try:
                reading = read_page(client, page.get_pixmap(dpi=RENDER_DPI).tobytes("png"))
            except errors.APIError as error:
                print(f"The model did not answer ({error.code}): {error.message}. Try again later or change AUDIT_MODEL.")
                return 3
            saved.write_text(reading.model_dump_json(indent=1), encoding="utf-8")
        readings.append({"page": number, **reading.model_dump()})
        for table in reading.tables:
            for row in table.rows:
                rows[row.part_number.replace(" ", "").rstrip("*")] = row

    differences = compare(actuators, rows)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(
            {"model": settings.audit_model, "rows_read": len(rows), "differences": differences, "readings": readings},
            indent=1,
            ensure_ascii=False,
        ) + "\n",
        encoding="utf-8",
    )

    print(f"{len(rows)} rows read, {len(differences)} differences -> {report_path}")
    for difference in differences:
        print(f"  - {difference['part_number']}.{difference['field']}: ours {difference['ours']}, model {difference['model']}")
    return 1 if differences else 0
