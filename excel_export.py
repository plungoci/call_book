"""Read-only Excel export."""
from __future__ import annotations
from datetime import datetime
from pathlib import Path
from openpyxl import Workbook
from openpyxl.styles import Font
from models import QSO
HEADERS=["ID","Callsign","Start UTC","End UTC","Frequency MHz","Band","Mode","Repeater ID","RST Sent","RST Received","Name","Grid","Power W","Notes","QSL"]
def export_excel(qsos:list[QSO], directory:Path=Path("exports"), destination:Path | None=None)->Path:
 directory.mkdir(parents=True,exist_ok=True); path=destination or directory/f"logbook_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"; path.parent.mkdir(parents=True, exist_ok=True); wb=Workbook(); ws=wb.active;ws.title="QSOs";ws.append(HEADERS)
 for cell in ws[1]:cell.font=Font(bold=True)
 for q in qsos: ws.append([q.id,q.callsign,q.qso_start_utc,q.qso_end_utc,q.frequency_mhz,q.band,q.mode,q.repeater_id,q.rst_sent,q.rst_received,q.operator_name,q.grid_square,q.power_w,q.notes,q.qsl_status])
 ws.freeze_panes="A2";ws.auto_filter.ref=ws.dimensions
 for column in ws.columns: ws.column_dimensions[column[0].column_letter].width=min(50,max(12,max(len(str(c.value or "")) for c in column)+2))
 wb.save(path);return path
