"""SQLite repository; every connection enables foreign keys."""
from __future__ import annotations
from contextlib import contextmanager
from datetime import datetime, timezone, timedelta
from pathlib import Path
import sqlite3
from models import OperatorProfile, QSO, Repeater
class Database:
 def __init__(self, path: Path=Path("data/logbook.db")): self.path=path; path.parent.mkdir(parents=True,exist_ok=True); self.initialize()
 @contextmanager
 def connect(self):
  con=sqlite3.connect(self.path); con.row_factory=sqlite3.Row; con.execute("PRAGMA foreign_keys = ON")
  try: yield con; con.commit()
  except Exception: con.rollback(); raise
  finally: con.close()
 def initialize(self):
  with self.connect() as c: c.executescript("""CREATE TABLE IF NOT EXISTS repeaters (id INTEGER PRIMARY KEY AUTOINCREMENT,name TEXT NOT NULL,output_frequency_mhz REAL NOT NULL,input_frequency_mhz REAL,shift_mhz REAL,tone_hz REAL,mode TEXT,location TEXT,grid_square TEXT,notes TEXT);
CREATE TABLE IF NOT EXISTS qsos (id INTEGER PRIMARY KEY AUTOINCREMENT,callsign TEXT NOT NULL,qso_start_utc TEXT NOT NULL,qso_end_utc TEXT,frequency_mhz REAL NOT NULL,band TEXT,mode TEXT NOT NULL,repeater_id INTEGER,rst_sent TEXT,rst_received TEXT,operator_name TEXT,grid_square TEXT,my_grid_square TEXT,power_w REAL,notes TEXT,qsl_status TEXT DEFAULT 'NOT_SENT',created_at TEXT NOT NULL,updated_at TEXT, FOREIGN KEY(repeater_id) REFERENCES repeaters(id) ON DELETE SET NULL);
CREATE TABLE IF NOT EXISTS stations (id INTEGER PRIMARY KEY AUTOINCREMENT,name TEXT NOT NULL,callsign TEXT NOT NULL,location TEXT,grid_square TEXT,equipment TEXT,antenna TEXT);""")
  with self.connect() as c:
   c.execute("""CREATE TABLE IF NOT EXISTS operator_profile (id INTEGER PRIMARY KEY CHECK (id = 1), callsign TEXT NOT NULL DEFAULT '', full_name TEXT NOT NULL DEFAULT '', maidenhead_locator TEXT NOT NULL DEFAULT '', locality TEXT NOT NULL DEFAULT '', county TEXT NOT NULL DEFAULT '', country TEXT NOT NULL DEFAULT '', address TEXT NOT NULL DEFAULT '', email TEXT NOT NULL DEFAULT '', phone TEXT NOT NULL DEFAULT '', radio_equipment TEXT NOT NULL DEFAULT '', antenna TEXT NOT NULL DEFAULT '', default_power_w REAL, radio_club TEXT NOT NULL DEFAULT '', club_callsign TEXT NOT NULL DEFAULT '', notes TEXT NOT NULL DEFAULT '')""")
   self._add_missing_columns(c, "operator_profile", {"callsign":"TEXT NOT NULL DEFAULT ''", "full_name":"TEXT NOT NULL DEFAULT ''", "maidenhead_locator":"TEXT NOT NULL DEFAULT ''", "locality":"TEXT NOT NULL DEFAULT ''", "county":"TEXT NOT NULL DEFAULT ''", "country":"TEXT NOT NULL DEFAULT ''", "address":"TEXT NOT NULL DEFAULT ''", "email":"TEXT NOT NULL DEFAULT ''", "phone":"TEXT NOT NULL DEFAULT ''", "radio_equipment":"TEXT NOT NULL DEFAULT ''", "antenna":"TEXT NOT NULL DEFAULT ''", "default_power_w":"REAL", "radio_club":"TEXT NOT NULL DEFAULT ''", "club_callsign":"TEXT NOT NULL DEFAULT ''", "notes":"TEXT NOT NULL DEFAULT ''", "latitude":"REAL", "longitude":"REAL", "location_accuracy_m":"REAL", "location_source":"TEXT", "location_updated_at":"TEXT", "grid_square":"TEXT"})
   self._add_missing_columns(c, "qsos", {"my_grid_square":"TEXT"})
 def _add_missing_columns(self, connection, table, columns):
  """Safely migrate old local databases without rebuilding any table."""
  existing={row["name"] for row in connection.execute(f"PRAGMA table_info({table})")}
  for name, definition in columns.items():
   if name not in existing: connection.execute(f"ALTER TABLE {table} ADD COLUMN {name} {definition}")
 def get_operator_profile(self)->OperatorProfile:
  """Return the persisted singleton profile, or an empty one."""
  with self.connect() as c:
   row=c.execute("SELECT * FROM operator_profile WHERE id=1").fetchone()
  return OperatorProfile(**{key: row[key] for key in OperatorProfile.__dataclass_fields__}) if row else OperatorProfile()
 def save_operator_profile(self, profile:OperatorProfile)->None:
  """Insert or replace the singleton operator profile without touching QSOs."""
  fields=list(OperatorProfile.__dataclass_fields__); values=[getattr(profile, field) for field in fields]
  assignments=", ".join(f"{field}=excluded.{field}" for field in fields)
  with self.connect() as c:c.execute(f"INSERT INTO operator_profile (id,{','.join(fields)}) VALUES ({','.join('?'*(len(fields)+1))}) ON CONFLICT(id) DO UPDATE SET {assignments}",[1,*values])
 def save_qso(self,q:QSO)->int:
  fields="callsign,qso_start_utc,qso_end_utc,frequency_mhz,band,mode,repeater_id,rst_sent,rst_received,operator_name,grid_square,my_grid_square,power_w,notes,qsl_status"; vals=[getattr(q,x) for x in fields.split(",")]; now=datetime.now(timezone.utc).isoformat()
  with self.connect() as c:
   if q.id: c.execute(f"UPDATE qsos SET {','.join(f'{x}=?' for x in fields.split(','))},updated_at=? WHERE id=?",vals+[now,q.id]); return q.id
   cur=c.execute(f"INSERT INTO qsos ({fields},created_at) VALUES ({','.join('?'*16)})",vals+[now]); return cur.lastrowid
 def get_qso(self,id:int)->QSO: return QSO(**dict(self._one("SELECT * FROM qsos WHERE id=?",(id,))))
 def list_qsos(self, filters:dict[str,str]|None=None)->list[sqlite3.Row]:
  filters=filters or {}; where=[]; values=[]
  for key,col in (("callsign","q.callsign"),("band","q.band"),("mode","q.mode"),("repeater_id","q.repeater_id")):
   if filters.get(key): where.append(f"{col} LIKE ?" if key=="callsign" else f"{col}=?"); values.append(f"%{filters[key].upper()}%" if key=="callsign" else filters[key])
  for key,op in (("date_from",">="),("date_to","<=")):
   if filters.get(key): where.append(f"q.qso_start_utc {op} ?"); values.append(filters[key]+("T23:59:59+00:00" if key=="date_to" else "T00:00:00+00:00"))
  sql="SELECT q.*, r.name repeater_name FROM qsos q LEFT JOIN repeaters r ON r.id=q.repeater_id"+(" WHERE "+" AND ".join(where) if where else "")+" ORDER BY q.qso_start_utc DESC"
  with self.connect() as c:return c.execute(sql,values).fetchall()
 def possible_duplicate(self,q:QSO)->bool:
  start=(datetime.fromisoformat(q.qso_start_utc)-timedelta(minutes=2)).isoformat(); end=(datetime.fromisoformat(q.qso_start_utc)+timedelta(minutes=2)).isoformat()
  sql="SELECT 1 FROM qsos WHERE callsign=? AND frequency_mhz=? AND mode=? AND qso_start_utc BETWEEN ? AND ?"+(" AND id != ?" if q.id else "")
  with self.connect() as c:return c.execute(sql,[q.callsign,q.frequency_mhz,q.mode,start,end]+([q.id] if q.id else [])).fetchone() is not None
 def delete_qso(self,id:int):
  with self.connect() as c:c.execute("DELETE FROM qsos WHERE id=?",(id,))
 def _one(self,sql,values):
  with self.connect() as c:
   row=c.execute(sql,values).fetchone()
   if not row: raise KeyError("Înregistrare inexistentă")
   return row
 def list_repeaters(self, term=""):
  with self.connect() as c:return c.execute("SELECT * FROM repeaters WHERE name LIKE ? OR location LIKE ? ORDER BY name",(f"%{term}%",f"%{term}%")).fetchall()
 def save_repeater(self,r:Repeater)->int:
  names="name,output_frequency_mhz,input_frequency_mhz,shift_mhz,tone_hz,mode,location,grid_square,notes"; vals=[getattr(r,x) for x in names.split(",")]
  with self.connect() as c:
   if r.id:c.execute(f"UPDATE repeaters SET {','.join(x+'=?' for x in names.split(','))} WHERE id=?",vals+[r.id]);return r.id
   return c.execute(f"INSERT INTO repeaters ({names}) VALUES ({','.join('?'*9)})",vals).lastrowid
 def delete_repeater(self,id:int):
  # ON DELETE SET NULL deliberately retains historic QSO records.
  with self.connect() as c:c.execute("DELETE FROM repeaters WHERE id=?",(id,))
