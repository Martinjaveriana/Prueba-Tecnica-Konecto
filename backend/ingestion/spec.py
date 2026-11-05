"""The known structure of the 7 tables in series_76_electric_data.pdf.

The PDF is a single fixed document, so its structure is declared instead of inferred.
A wrong guess about a column would silently corrupt data; a declared structure makes
any mismatch with what Docling read fail loudly.

Motor power is declared too: it is a merged cell spanning several rows, and Docling only
reports its value on the middle row. The build step checks that value against these groups.
"""

from dataclasses import dataclass

TWO_SERVICES = (
    "on_off_in_lbs", "on_off_nm", "on_off_duty", "on_off_cycles",
    "mod_in_lbs", "mod_nm", "mod_duty", "mod_starts",
    "speed_60", "speed_50", "fla_60", "fla_50", "lra_60", "lra_50",
)
THREE_PHASE = (
    "in_lbs", "nm", "duty", "cycles", "starts",
    "speed_60", "speed_50", "fla_60", "fla_50", "lra_60", "lra_50",
)
DC_ON_OFF = ("in_lbs", "nm", "duty", "cycles", "speed", "fla", "lra")
DC_MODULATING = ("in_lbs", "nm", "duty", "starts", "speed", "fla", "lra")

ENCLOSURE_CODE = {"weatherproof": "00", "explosionproof": "30"}
ENCLOSURE_TITLE = {"weatherproof": "WEATHERPROOF", "explosionproof": "EXPLOSIONPROOF"}

HAZARDOUS_CLASSIFICATION = (
    "Class I, Division 1, Groups C, D; T4",
    "Ex d IIB T4 Gb",
    "Class I, Zone 1, AEx d IIB T4 Gb",
)
# Footnote on page 1: "Sizes 6 and 7 are not CSA Certified".
SIZES_WITHOUT_CSA = {6, 7}


@dataclass(frozen=True)
class TableSpec:
    index: int
    page: int
    title: str
    enclosure: str
    voltage_v: int
    phases: int
    current_type: str
    code: str
    layout: tuple[str, ...]
    power_groups: tuple[tuple[int, tuple[str, ...]], ...]
    no_data: tuple[str, ...] = ()

    @property
    def aliases(self) -> tuple[str, ...]:
        return self.no_data + tuple(alias for _, group in self.power_groups for alias in group)

    def part_number(self, alias: str) -> str:
        return f"76{alias}{ENCLOSURE_CODE[self.enclosure]}-{self.code}/A"

    def power_of(self, alias: str) -> int | None:
        for watts, group in self.power_groups:
            if alias in group:
                return watts
        return None


_WEATHERPROOF_GROUPS = (
    (15, ("1A", "1B")),
    (40, ("2A", "2B", "3A")),
    (90, ("3B", "3C")),
    (180, ("4A", "4B", "5A", "5B")),
)

TABLES = (
    TableSpec(
        index=0, page=1, title="110V - Single Phase Power", enclosure="weatherproof",
        voltage_v=110, phases=1, current_type="AC", code="11300000", layout=TWO_SERVICES,
        power_groups=_WEATHERPROOF_GROUPS,
    ),
    TableSpec(
        index=1, page=1, title="220V - Single Phase Power", enclosure="weatherproof",
        voltage_v=220, phases=1, current_type="AC", code="11320000", layout=TWO_SERVICES,
        power_groups=_WEATHERPROOF_GROUPS + ((700, ("6A", "6B", "7A", "7B", "7C")),),
    ),
    TableSpec(
        index=2, page=2, title="220V - 3 Phase Power", enclosure="weatherproof",
        voltage_v=220, phases=3, current_type="AC", code="11330C00", layout=THREE_PHASE,
        no_data=("1A", "1B", "2A", "2B"),
        power_groups=((40, ("3A",)), (90, ("3B", "3C")), (180, ("4A", "4B", "5A", "5B"))),
    ),
    TableSpec(
        index=3, page=3, title="24V AC/DC Power - On/Off", enclosure="explosionproof",
        voltage_v=24, phases=1, current_type="AC/DC", code="11380000", layout=DC_ON_OFF,
        power_groups=((40, ("1X", "1Y", "2X", "2Y", "3X")),),
    ),
    TableSpec(
        index=4, page=3, title="24V DC Power - Modulating", enclosure="explosionproof",
        voltage_v=24, phases=1, current_type="DC", code="11370000", layout=DC_MODULATING,
        power_groups=((40, ("1X", "1Y", "2X", "2Y", "3X")),),
    ),
    TableSpec(
        index=5, page=4, title="110V - Single Phase Power", enclosure="explosionproof",
        voltage_v=110, phases=1, current_type="AC", code="11300000", layout=TWO_SERVICES,
        power_groups=(
            (15, ("1X", "1Y")),
            (40, ("2X", "2Y", "3X")),
            (90, ("3Y", "4X")),
            (180, ("4Y", "5X", "5Y")),
        ),
    ),
    TableSpec(
        index=6, page=4, title="220V - Single Phase Power", enclosure="explosionproof",
        voltage_v=220, phases=1, current_type="AC", code="11320000", layout=TWO_SERVICES,
        power_groups=(
            (15, ("1X", "1Y")),
            (40, ("2X", "2Y", "3X")),
            (90, ("3Y",)),
            (180, ("4X", "4Y", "5X", "5Y")),
        ),
    ),
)
