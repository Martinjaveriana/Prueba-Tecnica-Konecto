"""Process series_76_electric_data.pdf into the data the agent's tools query.

    python ingest.py             Load the reviewed data into PostgreSQL (no key, no Docling).
    python ingest.py --build     Rebuild the reviewed data from the saved raw tables.
    python ingest.py --extract   Read the PDF again with Docling, then rebuild.
    python ingest.py --audit     Compare the data with an independent reading by a vision model.
"""

import argparse
import json
import sys
from decimal import Decimal

from app.config import BACKEND_DIR, REPO_ROOT

PDF_PATH = REPO_ROOT / "docs" / "series_76_electric_data.pdf"
RAW_PATH = BACKEND_DIR / "data" / "raw" / "docling_tables.json"
CORRECTIONS_PATH = BACKEND_DIR / "data" / "corrections.json"
PROCESSED_PATH = BACKEND_DIR / "data" / "processed" / "actuators.json"
AUDIT_PATH = BACKEND_DIR / "data" / "audit" / "report.json"


def write_processed(actuators: list[dict]) -> None:
    def encode(value):
        if isinstance(value, Decimal):
            return float(value)
        raise TypeError(value)

    PROCESSED_PATH.parent.mkdir(parents=True, exist_ok=True)
    PROCESSED_PATH.write_text(json.dumps(actuators, indent=1, default=encode) + "\n", encoding="utf-8")


def run_build() -> int:
    from ingestion.build import build

    raw = json.loads(RAW_PATH.read_text(encoding="utf-8"))
    corrections = json.loads(CORRECTIONS_PATH.read_text(encoding="utf-8"))
    actuators, problems = build(raw, corrections)

    if problems:
        print(f"{len(problems)} problems, nothing was written:")
        for problem in problems:
            print(f"  - {problem}")
        return 1

    write_processed(actuators)
    with_data = sum(a["has_data"] for a in actuators)
    print(f"{len(actuators)} actuators ({with_data} with data), {len(corrections)} corrections applied -> {PROCESSED_PATH}")
    return 0


def run_load() -> int:
    from ingestion.load import load

    actuators = json.loads(PROCESSED_PATH.read_text(encoding="utf-8"), parse_float=Decimal)
    counts = load(actuators)
    print("Loaded: " + ", ".join(f"{table}={count}" for table, count in counts.items()))
    return 0


def run_audit() -> int:
    from ingestion.audit import audit

    return audit(PDF_PATH, PROCESSED_PATH, AUDIT_PATH)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--build", action="store_true")
    mode.add_argument("--extract", action="store_true")
    mode.add_argument("--audit", action="store_true")
    args = parser.parse_args()

    if args.extract:
        from ingestion.extract import extract_raw

        extract_raw(PDF_PATH, RAW_PATH)
        print(f"Raw tables -> {RAW_PATH}")
        return run_build()
    if args.build:
        return run_build()
    if args.audit:
        return run_audit()
    return run_load()


if __name__ == "__main__":
    sys.exit(main())
