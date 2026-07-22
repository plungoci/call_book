"""JSON configuration management."""
from __future__ import annotations
import json, logging
from pathlib import Path
CONFIG_PATH = Path("config.json")
DEFAULT_CONFIG = {"user_callsign":"","operator_name":"","grid_square":"","location":"","equipment":"","antenna":"","default_power_w":"","export_directory":"exports","backup_directory":"backups","show_propagation_panel":"true","propagation_auto_refresh_minutes":"15"}
PROPAGATION_REFRESH_INTERVALS = frozenset({"10", "15", "30", "60"})
def load_config(path: Path = CONFIG_PATH) -> dict[str,str]:
    if not path.exists(): path.write_text(json.dumps(DEFAULT_CONFIG, indent=2), encoding="utf-8"); return DEFAULT_CONFIG.copy()
    try:
        stored=json.loads(path.read_text(encoding="utf-8"))
        if "show_propagation_panel" not in stored and "show_propagation_map" in stored:
            stored["show_propagation_panel"] = stored["show_propagation_map"]
        return DEFAULT_CONFIG | stored
    except (OSError,json.JSONDecodeError): logging.exception("Config invalid; defaults used"); return DEFAULT_CONFIG.copy()

def save_config(config: dict[str, str], path: Path = CONFIG_PATH) -> None:
    """Persist only known settings, keeping the local JSON predictable."""
    values = DEFAULT_CONFIG | {key: str(value) for key, value in config.items() if key in DEFAULT_CONFIG}
    path.write_text(json.dumps(values, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
