"""Load the reviewed actuators into PostgreSQL.

Everything runs in one transaction and replaces the previous rows, so the script can run
any number of times and a failure leaves the old data intact.
"""

import psycopg

from app.config import BACKEND_DIR, settings

SCHEMA_PATH = BACKEND_DIR / "app" / "schema.sql"

INSERT_ACTUATOR = """
    INSERT INTO actuators (
        part_number, alias, size, enclosure, voltage_v, phases, current_type, motor_power_w,
        certifications, hazardous_classification, has_data, source_page
    ) VALUES (
        %(part_number)s, %(alias)s, %(size)s, %(enclosure)s, %(voltage_v)s, %(phases)s, %(current_type)s,
        %(motor_power_w)s, %(certifications)s, %(hazardous_classification)s, %(has_data)s, %(source_page)s
    )
"""
INSERT_SERVICE = """
    INSERT INTO service_ratings (
        part_number, service, torque_in_lbs, torque_nm, duty_cycle_pct, cycles_per_hour, starts_per_hour
    ) VALUES (
        %(part_number)s, %(service)s, %(torque_in_lbs)s, %(torque_nm)s, %(duty_cycle_pct)s,
        %(cycles_per_hour)s, %(starts_per_hour)s
    )
"""
INSERT_ELECTRICAL = """
    INSERT INTO electrical_ratings (part_number, frequency_hz, speed_sec, fla_a, lra_a)
    VALUES (%(part_number)s, %(frequency_hz)s, %(speed_sec)s, %(fla_a)s, %(lra_a)s)
"""


def load(actuators: list[dict]) -> dict[str, int]:
    with psycopg.connect(settings.database_url) as conn:
        conn.execute(SCHEMA_PATH.read_text(encoding="utf-8"))
        conn.execute("TRUNCATE actuators CASCADE")
        with conn.cursor() as cursor:
            for actuator in actuators:
                part = actuator["part_number"]
                cursor.execute(INSERT_ACTUATOR, actuator)
                cursor.executemany(INSERT_SERVICE, [{**r, "part_number": part} for r in actuator["service_ratings"]])
                cursor.executemany(INSERT_ELECTRICAL, [{**r, "part_number": part} for r in actuator["electrical_ratings"]])
        return {
            table: conn.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
            for table in ("actuators", "service_ratings", "electrical_ratings")
        }
