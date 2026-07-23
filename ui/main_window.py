"""Modern PySide6 application shell."""
from datetime import datetime, timezone
from pathlib import Path
from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import *
from application_controller import DuplicateQsoCancelled,LogbookController
from config import PROPAGATION_REFRESH_INTERVALS,save_config
from models import QSO
from .qso_form import QSOForm
from .propagation_panel import PropagationPanel
from .operator_profile_window import OperatorProfileWindow
from .repeater_window import RepeaterWindow
DARK='''QWidget{background:#171b22;color:#e6edf3;font:10pt "Segoe UI"} QLineEdit,QTextEdit,QComboBox,QTableWidget{background:#222833;border:1px solid #394454;border-radius:5px;padding:5px} QPushButton{background:#2f81f7;border:0;border-radius:5px;padding:7px 12px} QPushButton:disabled{background:#394454;color:#8b949e} QGroupBox{border:1px solid #394454;border-radius:7px;margin-top:10px;padding-top:8px;font-weight:bold} QTabBar::tab{padding:9px 18px;background:#222833} QHeaderView::section{background:#222833;padding:6px;border:0}'''
class MainWindow(QMainWindow):
 def __init__(self,db,config):
  super().__init__();self.db=db;self.app_config=config;self.controller=LogbookController(db);self.operator_profile=db.get_operator_profile();self.setWindowTitle('Radio Logbook');self.resize(1440,900);self.setMinimumSize(1024,700);self.setStyleSheet(DARK);self._menu();self._build();self.clock_timer=QTimer(self);self.clock_timer.timeout.connect(self._clock);self.clock_timer.start(1000);self._clock();self.refresh()
 def _menu(self):
  file=self.menuBar().addMenu('Fișier');
  for title,fn in [('Exportă Excel',self.excel),('Exportă ADIF',self.adif),('Creează backup',self.backup),('Ieșire',self.close)]:file.addAction(QAction(title,self,triggered=fn))
  settings=self.menuBar().addMenu('Setări');settings.addAction('Date operator',self.open_operator_profile);settings.addAction('Repetoare',self.open_repeaters);settings.addAction('Setări propagare',self.open_propagation_settings)
 def _build(self):
  central=QWidget();self.setCentralWidget(central);root=QVBoxLayout(central);bar=QHBoxLayout();bar.addWidget(QLabel('<h2>Radio Logbook</h2>'));self.station_locator=QLabel();bar.addWidget(self.station_locator);self._update_station_locator();bar.addStretch();self.clock=QLabel();bar.addWidget(self.clock);root.addLayout(bar);self.tabs=QTabWidget();root.addWidget(self.tabs);self.log=QWidget();self.propagation_tab=QWidget();self.location=QWidget();self.settings=QWidget();self.tabs.addTab(self.log,'Jurnal QSO');self.tabs.addTab(self.propagation_tab,'Propagare');self.tabs.addTab(self.location,'Locație');self.tabs.addTab(self.settings,'Setări');self._log();self._propagation();self._location();self._settings();self.status=QLabel('Gata pentru un QSO nou.');root.addWidget(self.status)
 def _log(self):
  l=QVBoxLayout(self.log); self.filters_edits={};filters=QHBoxLayout()
  for key,label in [('callsign','Indicativ'),('band','Bandă'),('mode','Mod'),('repeater_id','Repetor ID'),('date_from','De la'),('date_to','Până la')]: e=QLineEdit();e.setPlaceholderText(label);filters.addWidget(e);self.filters_edits[key]=e
  b=QPushButton('Aplică filtre');b.clicked.connect(self.refresh);filters.addWidget(b);l.addLayout(filters);self.form=QSOForm(self.db.list_repeaters,self.operator_profile.default_power_w);self.form.contextChanged.connect(self.propagation_context_changed);l.addWidget(self.form);actions=QHBoxLayout()
  for name,fn in [('Salvează QSO',self.save),('QSO nou',self.cancel_edit),('Editează',self.edit),('Șterge',self.delete)]:b=QPushButton(name);b.clicked.connect(fn);actions.addWidget(b)
  actions.addStretch();l.addLayout(actions);self.table=QTableWidget(0,12);self.table.setHorizontalHeaderLabels(('ID','Dată','Ora','Indicativ','Nume','MHz','Bandă','Mod','Repetor','RST T','RST R','QSL'));self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows);self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers);self.table.horizontalHeader().setStretchLastSection(True);l.addWidget(self.table)
 def _propagation(self):l=QVBoxLayout(self.propagation_tab);self.propagation_panel=PropagationPanel();l.addWidget(self.propagation_panel)
 def _location(self):
  l=QVBoxLayout(self.location);p=self.operator_profile;l.addWidget(QLabel(f'<h2>Poziția stației</h2><p>Locator: <b>{p.grid_square or p.maidenhead_locator or "Nesetat"}</b></p><p>Latitudine: {p.latitude or "—"} · Longitudine: {p.longitude or "—"}</p>'));b=QPushButton('Deschide profilul operatorului');b.clicked.connect(self.open_operator_profile);l.addWidget(b);l.addStretch()
 def _settings(self):
  l=QVBoxLayout(self.settings)
  for text,fn in [('Date operator',self.open_operator_profile),('Administrează repetoare',self.open_repeaters),('Setări propagare',self.open_propagation_settings),('Creează backup',self.backup)]:b=QPushButton(text);b.clicked.connect(fn);l.addWidget(b)
  l.addStretch()
 def filters(self):return {k:e.text() for k,e in self.filters_edits.items()}
 def refresh(self):
  rows=self.db.list_qsos(self.filters());self.table.setRowCount(len(rows))
  for i,r in enumerate(rows):
   dt=r['qso_start_utc'];vals=(r['id'],dt[:10],dt[11:19],r['callsign'],r['operator_name'],r['frequency_mhz'],r['band'],r['mode'],r['repeater_name'] or '',r['rst_sent'],r['rst_received'],r['qsl_status'])
   for j,v in enumerate(vals):self.table.setItem(i,j,QTableWidgetItem(str(v)))
  self.status.setText(f'{len(rows)} QSO-uri afișate.')
 def current_id(self):
  rows=self.table.selectionModel().selectedRows();return int(self.table.item(rows[0].row(),0).text()) if rows else None
 def edit(self):
  if (i:=self.current_id()) is not None:self.form.load(self.db.get_qso(i));self.tabs.setCurrentWidget(self.log)
 def cancel_edit(self):self.form.new();self.table.clearSelection();self.status.setText('Gata pentru un QSO nou.')
 def save(self):
  try:
   _,editing=self.controller.save_qso(self.form.value(),lambda _:QMessageBox.question(self,'Posibil duplicat','Există un QSO similar. Salvați?')==QMessageBox.StandardButton.Yes);self.refresh();self.cancel_edit();self.status.setText('QSO actualizat.' if editing else 'QSO salvat.')
  except DuplicateQsoCancelled:pass
  except (ValueError,OSError,KeyError) as e:QMessageBox.critical(self,'Eroare',str(e))
 def delete(self):
  if (i:=self.current_id()) is not None and QMessageBox.question(self,'Confirmare','Ștergeți QSO-ul?')==QMessageBox.StandardButton.Yes:self.db.delete_qso(i);self.refresh();self.cancel_edit()
 def propagation_context_changed(self,band,freq):self.propagation_panel.schedule(band)
 def _update_station_locator(self):
  locator=self.operator_profile.grid_square or self.operator_profile.maidenhead_locator
  self.station_locator.setText(f'<h2>{locator}</h2>' if locator else '')
 def open_operator_profile(self):
  d=OperatorProfileWindow(self,self.db);d.exec();self.operator_profile=self.db.get_operator_profile();self._update_station_locator()
 def open_repeaters(self):d=RepeaterWindow(self,self.db,self.form.refresh_repeaters);d.exec()
 def open_propagation_settings(self):
  d=QDialog(self);l=QFormLayout(d);enabled=QCheckBox('Actualizare automată');interval=QComboBox();interval.addItems(('10','15','30','60'));enabled.setChecked(self.app_config.get('propagation_auto_refresh_minutes','15') in PROPAGATION_REFRESH_INTERVALS);l.addRow(enabled);l.addRow('Interval (minute)',interval);b=QPushButton('Salvează');b.clicked.connect(lambda:(self.app_config.__setitem__('propagation_auto_refresh_minutes',interval.currentText() if enabled.isChecked() else '0'),save_config(self.app_config),d.accept()));l.addRow(b);d.exec()
 def _export(self,title,extension,exporter):
  name,_=QFileDialog.getSaveFileName(self,f'Export {title}','exports',f'{title} (*{extension})')
  if name:
   try:self.status.setText(f'Export creat: {exporter(self.controller.list_qsos(self.filters()),Path(name))}')
   except Exception as e:QMessageBox.critical(self,'Eroare export',str(e))
 def excel(self):self._export('Excel','.xlsx',self.controller.export_excel)
 def adif(self):self._export('ADIF','.adi',self.controller.export_adif)
 def backup(self):
  try:self.status.setText(f'Backup creat: {self.controller.create_backup()}')
  except Exception as e:QMessageBox.critical(self,'Eroare backup',str(e))
 def _clock(self):self.clock.setText(f'Local {datetime.now():%H:%M:%S}  |  UTC {datetime.now(timezone.utc):%H:%M:%S}')
 def closeEvent(self,event):self.propagation_panel.shutdown();event.accept()
