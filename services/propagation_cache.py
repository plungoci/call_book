"""Local cache for public NOAA space-weather data."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path


class PropagationCache:
    def __init__(self, root: Path = Path("cache")) -> None:
        self.root = root
        (root / "space_weather").mkdir(parents=True, exist_ok=True)

    def weather_path(self) -> Path:
        return self.root / "space_weather" / "latest.json"

    def read_json(self, path: Path, max_age_seconds: int) -> dict | None:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            fetched = datetime.fromisoformat(data["fetched_at_utc"])
            if (datetime.now(timezone.utc) - fetched).total_seconds() <= max_age_seconds:
                return data
        except (OSError, ValueError, KeyError, json.JSONDecodeError):
            pass
        return None

    def write_json(self, path: Path, data: dict) -> None:
        data["fetched_at_utc"] = data.get("fetched_at_utc", datetime.now(timezone.utc).isoformat())
        path.write_text(json.dumps(data), encoding="utf-8")
