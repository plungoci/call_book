"""Safe SQLite online backups."""
from __future__ import annotations
from datetime import datetime
from pathlib import Path
import sqlite3
def create_backup(source:Path,directory:Path=Path("backups"))->Path:
 directory.mkdir(parents=True,exist_ok=True); target=directory/f"logbook_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
 with sqlite3.connect(source) as original, sqlite3.connect(target) as copy: original.backup(copy)
 return target
