"""Bounded, local cache; no operator identity or exact coordinates are logged."""
from __future__ import annotations
import hashlib, json, shutil
from datetime import datetime, timezone
from pathlib import Path

class PropagationCache:
    def __init__(self, root: Path = Path("cache"), max_files: int = 40) -> None:
        self.root, self.max_files = root, max_files
        (root / "space_weather").mkdir(parents=True, exist_ok=True)
        (root / "propagation_maps").mkdir(parents=True, exist_ok=True)
    @staticmethod
    def key(params: dict) -> str:
        return hashlib.sha256(json.dumps(params, sort_keys=True, default=str).encode()).hexdigest()
    def weather_path(self) -> Path: return self.root / "space_weather" / "latest.json"
    def read_json(self, path: Path, max_age_seconds: int) -> dict | None:
        try:
            data=json.loads(path.read_text(encoding="utf-8")); fetched=datetime.fromisoformat(data["fetched_at_utc"])
            if (datetime.now(timezone.utc)-fetched).total_seconds() <= max_age_seconds: return data
        except (OSError, ValueError, KeyError, json.JSONDecodeError): pass
        return None
    def write_json(self, path: Path, data: dict) -> None:
        data["fetched_at_utc"] = data.get("fetched_at_utc", datetime.now(timezone.utc).isoformat())
        path.write_text(json.dumps(data), encoding="utf-8")
    def map_paths(self, key: str) -> tuple[Path, Path]:
        base=self.root / "propagation_maps" / key
        return base.with_suffix(".png"), base.with_suffix(".json")
    def prune(self) -> None:
        files=sorted((self.root / "propagation_maps").glob("*"), key=lambda p:p.stat().st_mtime, reverse=True)
        for path in files[self.max_files * 2:]: path.unlink(missing_ok=True)
