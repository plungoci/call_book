"""JSON configuration management."""

from __future__ import annotations

import json
import logging
from pathlib import Path

from .services.dx_cluster import DEFAULT_HOST as DEFAULT_DX_CLUSTER_HOST
from .services.dx_cluster import DEFAULT_PORT as DEFAULT_DX_CLUSTER_PORT

CONFIG_PATH = Path("config.json")
DEFAULT_CONFIG = {
    "user_callsign": "",
    "operator_name": "",
    "grid_square": "",
    "location": "",
    "equipment": "",
    "antenna": "",
    "default_power_w": "",
    "export_directory": "exports",
    "backup_directory": "backups",
    "show_propagation_panel": "true",
    "show_dx_cluster_panel": "true",
    "propagation_auto_refresh_minutes": "15",
    "local_weather_auto_refresh_minutes": "30",
    "dx_cluster_host": DEFAULT_DX_CLUSTER_HOST,
    "dx_cluster_port": str(DEFAULT_DX_CLUSTER_PORT),
}
REFRESH_INTERVAL_OPTIONS = ("1", "5", "10", "15", "30", "60")
REFRESH_INTERVALS = frozenset(REFRESH_INTERVAL_OPTIONS)


def dx_cluster_node(config: dict[str, str]) -> tuple[str, int]:
    """Return the configured cluster node, falling back to the default port."""
    host = (config.get("dx_cluster_host") or DEFAULT_DX_CLUSTER_HOST).strip()
    try:
        port = int(config.get("dx_cluster_port") or DEFAULT_DX_CLUSTER_PORT)
    except ValueError:
        port = DEFAULT_DX_CLUSTER_PORT
    if not 1 <= port <= 65535:
        port = DEFAULT_DX_CLUSTER_PORT
    return host or DEFAULT_DX_CLUSTER_HOST, port


def load_config(path: Path = CONFIG_PATH) -> dict[str, str]:
    if not path.exists():
        path.write_text(json.dumps(DEFAULT_CONFIG, indent=2), encoding="utf-8")
        return DEFAULT_CONFIG.copy()
    try:
        stored = json.loads(path.read_text(encoding="utf-8"))
        if "show_propagation_panel" not in stored and "show_propagation_map" in stored:
            stored["show_propagation_panel"] = stored["show_propagation_map"]
        return DEFAULT_CONFIG | stored
    except (OSError, json.JSONDecodeError):
        logging.exception("Config invalid; defaults used")
        return DEFAULT_CONFIG.copy()


def save_config(config: dict[str, str], path: Path = CONFIG_PATH) -> None:
    """Persist only known settings, keeping the local JSON predictable."""
    values = DEFAULT_CONFIG | {key: str(value) for key, value in config.items() if key in DEFAULT_CONFIG}
    path.write_text(json.dumps(values, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
