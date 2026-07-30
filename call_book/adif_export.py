"""ADIF export with byte-accurate field lengths."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from .models import QSO, OperatorProfile
from .propagation import ADIF_PROPAGATION_MODES


def adif_field(name: str, value: object) -> str:
    value = str(value)
    return f"<{name}:{len(value.encode('utf-8'))}>{value}"


def adif_record(q: QSO, profile: OperatorProfile | None = None) -> str:
    # QSO_DATE/TIME_ON are mandatory ADIF fields; per-QSO start/end times were
    # removed from the model, so the log timestamp is used instead.
    logged = datetime.fromisoformat(q.created_at) if q.created_at else datetime.now(UTC)
    values = {
        "CALL": q.callsign,
        "QSO_DATE": logged.strftime("%Y%m%d"),
        "TIME_ON": logged.strftime("%H%M%S"),
        "FREQ": f"{q.frequency_mhz:.6f}",
        "BAND": q.band,
        "MODE": q.mode,
        "NAME": q.operator_name,
        "GRIDSQUARE": q.grid_square,
        "COMMENT": q.notes,
    }
    if q.my_grid_square:
        values["MY_GRIDSQUARE"] = q.my_grid_square
    elif profile and profile.grid_square:
        values["MY_GRIDSQUARE"] = profile.grid_square
    if profile and profile.callsign:
        values["STATION_CALLSIGN"] = profile.callsign
    if q.propagation_mode in ADIF_PROPAGATION_MODES:
        values["PROP_MODE"] = ADIF_PROPAGATION_MODES[q.propagation_mode]
    # ADIF has only one general comment field; preserve existing QSO notes first.
    if q.propagation_notes:
        values["COMMENT"] = "\n".join(x for x in (q.notes, q.propagation_notes) if x)
    return "\n".join(adif_field(k, v) for k, v in values.items() if v not in (None, "")) + "\n<EOR>\n"


def export_adif(
    qsos: list[QSO],
    directory: Path = Path("exports"),
    destination: Path | None = None,
    profile: OperatorProfile | None = None,
) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    path = destination or directory / f"logbook_{datetime.now().strftime('%Y%m%d_%H%M%S')}.adi"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "Radio Logbook ADIF Export\n<EOH>\n" + "".join(adif_record(q, profile) for q in qsos), encoding="utf-8"
    )
    return path
