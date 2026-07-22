from PySide6.QtWidgets import *
from models import Repeater
REPEATER_FIELDS=(("Nume","name"),("Frecvență ieșire (MHz)","output_frequency_mhz"),("Frecvență intrare (MHz)","input_frequency_mhz"),("Shift (MHz)","shift_mhz"),("CTCSS (Hz)","tone_hz"),("Mod","mode"),("Locație","location"),("Locator","grid_square"))
class RepeaterWindow(QDialog):
 def __init__(self,parent,db,on_change):
  super().__init__(parent);self.db=db;self.on_change=on_change;self.selected=None;self.setWindowTitle('Administrare repetoare');self.resize(850,480);l=QHBoxLayout(self);form=QFormLayout();self.fields={}
  for label,key in REPEATER_FIELDS:e=QLineEdit();form.addRow(label,e);self.fields[key]=e
  self.notes=QTextEdit();form.addRow('Observații',self.notes)
  for text,fn in [('Salvează',self.save),('Șterge',self.delete),('Nou',self.clear)]:b=QPushButton(text);b.clicked.connect(fn);form.addRow(b)
  l.addLayout(form);self.table=QTableWidget();self.table.setColumnCount(4);self.table.setHorizontalHeaderLabels(('ID','Nume','Frecvență','Locație'));self.table.itemSelectionChanged.connect(self.select);l.addWidget(self.table);self.refresh()
 def refresh(self):
  rows=self.db.list_repeaters();self.table.setRowCount(len(rows))
  for i,r in enumerate(rows):
   for j,k in enumerate(('id','name','output_frequency_mhz','location')):self.table.setItem(i,j,QTableWidgetItem(str(r[k] or '')))
 def select(self):
  rows=self.table.selectionModel().selectedRows()
  if not rows:return
  r=next(x for x in self.db.list_repeaters() if x['id']==int(self.table.item(rows[0].row(),0).text()));self.selected=r['id']
  for k,e in self.fields.items():e.setText(str(r[k] or ''))
  self.notes.setPlainText(r['notes'] or '')
 def clear(self):self.selected=None;[x.clear() for x in self.fields.values()];self.notes.clear();self.table.clearSelection()
 def save(self):
  try:
   v={k:e.text().strip() for k,e in self.fields.items()};self.db.save_repeater(Repeater(id=self.selected,name=v['name'],output_frequency_mhz=float(v['output_frequency_mhz']),input_frequency_mhz=float(v['input_frequency_mhz']) if v['input_frequency_mhz'] else None,shift_mhz=float(v['shift_mhz']) if v['shift_mhz'] else None,tone_hz=float(v['tone_hz']) if v['tone_hz'] else None,mode=v['mode'],location=v['location'],grid_square=v['grid_square'],notes=self.notes.toPlainText()));self.refresh();self.on_change();self.clear()
  except ValueError:QMessageBox.critical(self,'Eroare','Numele și frecvența de ieșire sunt obligatorii.')
 def delete(self):
  if self.selected and QMessageBox.question(self,'Confirmare','Ștergeți repetorul?')==QMessageBox.StandardButton.Yes:self.db.delete_repeater(self.selected);self.refresh();self.on_change();self.clear()
