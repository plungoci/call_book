"""JSON configuration management."""
from __future__ import annotations
import json, logging
from pathlib import Path
DEFAULT_CONFIG={"user_callsign":"","operator_name":"","grid_square":"","location":"","equipment":"","antenna":"","default_power_w":"","export_directory":"exports","backup_directory":"backups","show_propagation_panel":"true","propagation_auto_refresh_minutes":"15"}
def load_config(path: Path = Path("config.json")) -> dict[str,str]:
    if not path.exists(): path.write_text(json.dumps(DEFAULT_CONFIG, indent=2), encoding="utf-8"); return DEFAULT_CONFIG.copy()
    try:
        stored=json.loads(path.read_text(encoding="utf-8"))
        if "show_propagation_panel" not in stored and "show_propagation_map" in stored:
            stored["show_propagation_panel"] = stored["show_propagation_map"]
        return DEFAULT_CONFIG | stored
    except (OSError,json.JSONDecodeError): logging.exception("Config invalid; defaults used"); return DEFAULT_CONFIG.copy()
