"""Thread-safe Qt propagation dashboard."""
from datetime import datetime, timezone
from PySide6.QtCore import QObject, QThread, QTimer, Signal
from PySide6.QtWidgets import QGridLayout,QGroupBox,QHBoxLayout,QLabel,QPushButton,QTableWidget,QTableWidgetItem,QVBoxLayout,QWidget
from services.propagation_estimator import PropagationEstimator
from services.space_weather_service import SpaceWeatherService
class Worker(QObject):
    finished=Signal(object); failed=Signal()
    def __init__(self,force): super().__init__(); self.force=force
    def run(self):
        try:self.finished.emit(SpaceWeatherService().fetch(self.force))
        except Exception:self.failed.emit()
class PropagationPanel(QGroupBox):
    def __init__(self,parent=None):
        super().__init__('Condiții de propagare',parent); self.estimator=PropagationEstimator(); self.timer=QTimer(self); self.timer.setSingleShot(True); self.timer.timeout.connect(lambda:self.refresh(False)); l=QVBoxLayout(self); top=QHBoxLayout(); self.status=QLabel('Selectează o bandă pentru actualizare.'); self.button=QPushButton('Actualizează'); self.button.clicked.connect(lambda:self.refresh(True)); top.addWidget(self.status);top.addStretch();top.addWidget(self.button);l.addLayout(top); self.metrics=QGridLayout(); box=QGroupBox('Space Weather');box.setLayout(self.metrics);l.addWidget(box); self.metric_labels={};
        for i,name in enumerate(('SFI','SSN','K Index','A Index','X-Ray Flux','Proton Flux','Electron Flux','Auroral Activity','Bz','Bt','Solar Wind','Densitate','Temperatură','Ap')):
            label=QLabel(f'<b>{name}</b><br>—');label.setWordWrap(True);self.metrics.addWidget(label,i//4,i%4);self.metric_labels[name]=label
        self.table=QTableWidget(5,5);self.table.setHorizontalHeaderLabels(('Bandă','Zi','Noapte','Scor','Încredere'));self.table.setVerticalHeaderLabels(('80m','40m','20m','15m','10m'));self.table.verticalHeader().setVisible(False);l.addWidget(self.table)
    def schedule(self,band,frequency=None,delay=700):
        if band.strip():self.timer.start(delay)
    def refresh(self,force=True):
        self.button.setEnabled(False);self.status.setText('Se descarcă date…');self.thread=QThread(self);self.worker=Worker(force);self.worker.moveToThread(self.thread);self.thread.started.connect(self.worker.run);self.worker.finished.connect(self.update_values);self.worker.finished.connect(self.thread.quit);self.worker.failed.connect(lambda:self.status.setText('Ultima actualizare nu a reușit.'));self.worker.failed.connect(self.thread.quit);self.thread.finished.connect(lambda:self.button.setEnabled(True));self.thread.start()
    def update_values(self,w):
        self.status.setText(f'Actualizat · {w.observed_at_utc.astimezone(timezone.utc):%d-%m-%Y %H:%M UTC}'); vals={'SFI':w.solar_flux,'SSN':w.sunspot_number,'K Index':w.kp_index,'A Index':w.a_index,'X-Ray Flux':w.xray_flux,'Proton Flux':w.proton_flux,'Electron Flux':w.electron_flux,'Auroral Activity':w.auroral_activity,'Bz':w.bz,'Bt':w.bt,'Solar Wind':w.solar_wind_speed,'Densitate':w.solar_wind_density,'Temperatură':w.solar_wind_temperature,'Ap':w.ap_index}
        for k,v in vals.items():self.metric_labels[k].setText(f'<b>{k}</b><br>{"N/A" if v is None else v}')
        for r,(band,(day,night)) in enumerate(self.estimator.calculate_hf(w,datetime.now(timezone.utc)).items()):
            for c,v in enumerate((band,day.rating,night.rating,f'{(day.score+night.score)/2:.0f}/100',day.confidence.capitalize())):self.table.setItem(r,c,QTableWidgetItem(v))
    def shutdown(self):
        if hasattr(self,'thread') and self.thread.isRunning():self.thread.quit();self.thread.wait(1000)
