"""SQLite repository; every connection enables foreign keys."""
from __future__ import annotations
from contextlib import contextmanager
from datetime import datetime, timezone, timedelta
from pathlib import Path
import sqlite3
from models import QSO, Repeater
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
CREATE TABLE IF NOT EXISTS qsos (id INTEGER PRIMARY KEY AUTOINCREMENT,callsign TEXT NOT NULL,qso_start_utc TEXT NOT NULL,qso_end_utc TEXT,frequency_mhz REAL NOT NULL,band TEXT,mode TEXT NOT NULL,repeater_id INTEGER,rst_sent TEXT,rst_received TEXT,operator_name TEXT,grid_square TEXT,power_w REAL,notes TEXT,qsl_status TEXT DEFAULT 'NOT_SENT',created_at TEXT NOT NULL,updated_at TEXT, FOREIGN KEY(repeater_id) REFERENCES repeaters(id) ON DELETE SET NULL);
CREATE TABLE IF NOT EXISTS stations (id INTEGER PRIMARY KEY AUTOINCREMENT,name TEXT NOT NULL,callsign TEXT NOT NULL,location TEXT,grid_square TEXT,equipment TEXT,antenna TEXT);""")
 def save_qso(self,q:QSO)->int:
  fields="callsign,qso_start_utc,qso_end_utc,frequency_mhz,band,mode,repeater_id,rst_sent,rst_received,operator_name,grid_square,power_w,notes,qsl_status"; vals=[getattr(q,x) for x in fields.split(",")]; now=datetime.now(timezone.utc).isoformat()
  with self.connect() as c:
   if q.id: c.execute(f"UPDATE qsos SET {','.join(f'{x}=?' for x in fields.split(','))},updated_at=? WHERE id=?",vals+[now,q.id]); return q.id
   cur=c.execute(f"INSERT INTO qsos ({fields},created_at) VALUES ({','.join('?'*15)})",vals+[now]); return cur.lastrowid
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
