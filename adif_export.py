"""ADIF export with byte-accurate field lengths."""
from __future__ import annotations
from datetime import datetime
from pathlib import Path
from models import QSO
QSL_MAP={"NOT_SENT":("N","N"),"SENT":("Y","N"),"RECEIVED":("N","Y"),"CONFIRMED":("Y","Y")}
def adif_field(name:str,value:object)->str:
 value=str(value); return f"<{name}:{len(value.encode('utf-8'))}>{value}"
def adif_record(q:QSO)->str:
 start=datetime.fromisoformat(q.qso_start_utc); end=datetime.fromisoformat(q.qso_end_utc) if q.qso_end_utc else None; sent,received=QSL_MAP.get(q.qsl_status,("N","N"))
 values={"CALL":q.callsign,"QSO_DATE":start.strftime("%Y%m%d"),"TIME_ON":start.strftime("%H%M%S"),"FREQ":f"{q.frequency_mhz:.6f}","BAND":q.band,"MODE":q.mode,"RST_SENT":q.rst_sent,"RST_RCVD":q.rst_received,"NAME":q.operator_name,"GRIDSQUARE":q.grid_square,"TX_PWR":q.power_w,"COMMENT":q.notes,"QSL_SENT":sent,"QSL_RCVD":received}
 if end: values["TIME_OFF"]=end.strftime("%H%M%S")
 return "\n".join(adif_field(k,v) for k,v in values.items() if v not in (None,""))+"\n<EOR>\n"
def export_adif(qsos:list[QSO], directory:Path=Path("exports"), destination:Path | None=None)->Path:
 directory.mkdir(parents=True,exist_ok=True); path=destination or directory/f"logbook_{datetime.now().strftime('%Y%m%d_%H%M%S')}.adi"; path.parent.mkdir(parents=True, exist_ok=True); path.write_text("Radio Logbook ADIF Export\n<EOH>\n"+"".join(adif_record(q) for q in qsos),encoding="utf-8");return path
