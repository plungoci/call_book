from datetime import datetime,timezone
from PySide6.QtCore import QObject,QThread,Signal
from PySide6.QtWidgets import *
from models import OperatorProfile
from services.location_service import LocationService
from utils.maidenhead import coordinates_to_maidenhead
from validators import normalize_callsign,normalize_name
class LocationWorker(QObject):
 done=Signal(object);failed=Signal(str)
 def run(self):
  try:self.done.emit(LocationService().locate())
  except Exception as e:self.failed.emit(str(e))
class OperatorProfileWindow(QDialog):
 FIELDS=(("Indicativ personal","callsign"),("Nume complet","full_name"),("Latitudine","latitude"),("Longitudine","longitude"),("Precizie localizare (m)","location_accuracy_m"),("Sursa localizării","location_source"),("Locator Maidenhead","grid_square"),("Localitate","locality"),("Județ","county"),("Țară","country"),("Adresă","address"),("Email","email"),("Telefon","phone"),("Echipament radio","radio_equipment"),("Antenă","antenna"),("Putere implicită (W)","default_power_w"),("Club radio","radio_club"),("Indicativ club","club_callsign"))
 def __init__(self,parent,db):
  super().__init__(parent);self.db=db;self.setWindowTitle('Date operator');self.resize(610,680);l=QVBoxLayout(self);scroll=QScrollArea();scroll.setWidgetResizable(True);content=QWidget();f=QFormLayout(content);self.fields={}
  for label,key in self.FIELDS:e=QLineEdit();f.addRow(label,e);self.fields[key]=e
  self.notes=QTextEdit();f.addRow('Observații',self.notes);scroll.setWidget(content);l.addWidget(scroll);buttons=QHBoxLayout();
  for text,fn in [('Detectează locația',self.detect),('Recalculează locatorul',self.recalculate),('Salvează',self.save),('Resetează',self.reset)]:b=QPushButton(text);b.clicked.connect(fn);buttons.addWidget(b)
  l.addLayout(buttons);self.load_profile()
 def load_profile(self):
  p=self.db.get_operator_profile()
  for k,e in self.fields.items():e.setText(str((p.maidenhead_locator if k=='grid_square' and not getattr(p,k) else getattr(p,k)) or ''))
  self.notes.setPlainText(p.notes)
 def recalculate(self):
  try:self.fields['grid_square'].setText(coordinates_to_maidenhead(float(self.fields['latitude'].text()),float(self.fields['longitude'].text())).upper())
  except ValueError as e:QMessageBox.critical(self,'Eroare',str(e))
 def detect(self):
  self.thread=QThread(self);self.worker=LocationWorker();self.worker.moveToThread(self.thread);self.thread.started.connect(self.worker.run);self.worker.done.connect(self.apply);self.worker.failed.connect(lambda x:QMessageBox.critical(self,'Localizare',x));self.worker.done.connect(self.thread.quit);self.worker.failed.connect(self.thread.quit);self.thread.start()
 def apply(self,r):
  self.fields['latitude'].setText(f'{r.latitude:.6f}');self.fields['longitude'].setText(f'{r.longitude:.6f}');self.fields['location_accuracy_m'].setText('' if r.accuracy_m is None else str(r.accuracy_m));self.fields['location_source'].setText(r.source);self.recalculate()
 def save(self):
  try:
   v={k:e.text().strip() for k,e in self.fields.items()}
   for k in ('default_power_w','latitude','longitude','location_accuracy_m'):v[k]=float(v[k]) if v[k] else None
   v['callsign']=normalize_callsign(v['callsign']);v['full_name']=normalize_name(v['full_name']);v['club_callsign']=normalize_callsign(v['club_callsign']);v['maidenhead_locator']=v['grid_square'];v['location_updated_at']=datetime.now(timezone.utc).isoformat() if v['latitude'] is not None else ''
   self.db.save_operator_profile(OperatorProfile(**v,notes=self.notes.toPlainText()));QMessageBox.information(self,'Date operator','Datele operatorului au fost salvate.')
  except (ValueError,TypeError) as e:QMessageBox.critical(self,'Eroare',str(e))
 def reset(self):
  if QMessageBox.question(self,'Confirmare','Sigur doriți resetarea?')==QMessageBox.StandardButton.Yes:self.db.save_operator_profile(OperatorProfile());self.load_profile()
