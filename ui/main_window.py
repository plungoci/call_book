from __future__ import annotations
import logging, tkinter as tk
from tkinter import ttk,messagebox,filedialog
from datetime import datetime,timezone
from database import Database
from models import QSO
from validators import validate_qso
from adif_export import export_adif
from excel_export import export_excel
from backup import create_backup
from .qso_form import QSOForm
from .repeater_window import RepeaterWindow
from .tooltip import Tooltip
class MainWindow(tk.Tk):
 def __init__(self,db:Database,config:dict[str,str]):
  super().__init__();self.db=db;self.config=config;self.title("Radio Logbook");self.geometry("1250x760");self.clock=ttk.Label(self);self.clock.pack(anchor="e",padx=8);self._clock();self._filters();self.form=QSOForm(self,self.db.list_repeaters,self.save);self.form.pack(fill="x",padx=8);actions=ttk.Frame(self);actions.pack();save=ttk.Button(actions,text="Salvează QSO",command=self.save);save.pack(side="left");Tooltip(save,"Salvează QSO-ul în baza de date.");new=ttk.Button(actions,text="QSO nou",command=self.form.new);new.pack(side="left");Tooltip(new,"Golește formularul și pregătește introducerea unei noi legături.");self._table();self.bind_all("<Control-n>",lambda e:self.form.new());self.bind_all("<Control-s>",lambda e:self.save());self.bind_all("<Delete>",lambda e:self.delete());self.bind_all("<Escape>",lambda e:self.form.new());self.bind_all("<Control-f>",lambda e:self.search.focus_set());self.refresh()
 def _clock(self):
  now=datetime.now().astimezone();utc=datetime.now(timezone.utc);self.clock.config(text=f"Local: {now:%Y-%m-%d %H:%M:%S %Z} | UTC: {utc:%Y-%m-%d %H:%M:%S}");self.after(1000,self._clock)
 def _filters(self):
  bar=ttk.Frame(self);bar.pack(fill="x",padx=8);self.search=tk.StringVar();self.band=tk.StringVar();self.mode=tk.StringVar();self.rep=tk.StringVar();self.date_from=tk.StringVar();self.date_to=tk.StringVar()
  for label,var,tip in (("Indicativ",self.search,"Filtrează rapid QSO-urile după indicativ."),("Bandă",self.band,"Filtrează QSO-urile după bandă."),("Mod",self.mode,"Filtrează QSO-urile după modul de lucru."),("Repetor ID",self.rep,"Filtrează QSO-urile după repetor."),("De la",self.date_from,"Afișează QSO-uri de la această dată."),("Până la",self.date_to,"Afișează QSO-uri până la această dată.")):
   ttk.Label(bar,text=label).pack(side="left");entry=ttk.Entry(bar,textvariable=var,width=12);entry.pack(side="left");Tooltip(entry,tip)
  for text,command,tip,side in (("Caută",self.refresh,"Filtrează rapid QSO-urile după indicativ.","left"),("Reset",self.reset,"Șterge toate filtrele de căutare.","left"),("Repetoare",lambda:RepeaterWindow(self,self.db,self.repeater_changed),"Administrează lista de repetoare.","right"),("Backup",self.backup,"Creează un backup al bazei de date SQLite.","right"),("Excel",self.excel,"Exportă toate QSO-urile într-un fișier Excel.","right"),("ADIF",self.adif,"Exportă logbook-ul în format ADIF compatibil cu alte aplicații.","right")):
   button=ttk.Button(bar,text=text,command=command);button.pack(side=side);Tooltip(button,tip)
 def _table(self):
  cols=("id","date","time","callsign","name","freq","band","mode","repeater","sent","received","qsl");self.tree=ttk.Treeview(self,columns=cols,show="headings");[self.tree.heading(c,text=c.upper()) for c in cols];self.tree.pack(fill="both",expand=True,padx=8,pady=8);self.tree.bind("<<TreeviewSelect>>",self.load);Tooltip(self.tree,"Lista QSO-urilor salvate. Selectează un rând pentru a-l încărca în formular.")
 def filters(self):return {"callsign":self.search.get(),"band":self.band.get(),"mode":self.mode.get(),"repeater_id":self.rep.get(),"date_from":self.date_from.get(),"date_to":self.date_to.get()}
 def refresh(self):
  self.tree.delete(*self.tree.get_children())
  for r in self.db.list_qsos(self.filters()):
   dt=r["qso_start_utc"];self.tree.insert("","end",iid=r["id"],values=(r["id"],dt[:10],dt[11:19],r["callsign"],r["operator_name"],r["frequency_mhz"],r["band"],r["mode"],r["repeater_name"] or "",r["rst_sent"],r["rst_received"],r["qsl_status"]))
 def save(self):
  try:
   q=self.form.value();q.qso_end_utc=q.qso_end_utc or datetime.now(timezone.utc).replace(microsecond=0).isoformat();validate_qso(q)
   if self.db.possible_duplicate(q) and not messagebox.askyesno("Posibil duplicat","Există un QSO similar în ±2 minute. Salvați totuși?"):return
   self.db.save_qso(q);self.refresh();self.form.new();messagebox.showinfo("Succes","QSO salvat.")
  except Exception as exc:logging.exception("QSO save error");messagebox.showerror("Eroare",str(exc))
 def load(self,_):
  if self.tree.selection():self.form.load(self.db.get_qso(int(self.tree.selection()[0])))
 def delete(self):
  if self.tree.selection() and messagebox.askyesno("Confirmare","Ștergeți QSO-ul selectat?"):self.db.delete_qso(int(self.tree.selection()[0]));self.refresh();self.form.new()
 def reset(self):
  for v in (self.search,self.band,self.mode,self.rep,self.date_from,self.date_to):v.set("")
  self.refresh()
 def selected_qsos(self):return [QSO(**{k:r[k] for k in QSO.__dataclass_fields__ if k in r.keys()}) for r in self.db.list_qsos(self.filters())]
 def adif(self):
  try:
   filename=filedialog.asksaveasfilename(initialdir="exports",defaultextension=".adi",filetypes=[("ADIF", "*.adi")])
   if filename: messagebox.showinfo("ADIF",f"Export creat: {export_adif(self.selected_qsos(), destination=__import__("pathlib").Path(filename))}")
  except Exception as e:logging.exception("ADIF");messagebox.showerror("Eroare export",str(e))
 def excel(self):
  try:
   filename=filedialog.asksaveasfilename(initialdir="exports",defaultextension=".xlsx",filetypes=[("Excel", "*.xlsx")])
   if filename: messagebox.showinfo("Excel",f"Export creat: {export_excel(self.selected_qsos(), destination=__import__("pathlib").Path(filename))}")
  except Exception as e:logging.exception("Excel");messagebox.showerror("Eroare export",str(e))
 def backup(self):
  try:messagebox.showinfo("Backup",f"Backup creat: {create_backup(self.db.path)}")
  except Exception as e:logging.exception("Backup");messagebox.showerror("Eroare backup",str(e))
 def repeater_changed(self):self.form.repeaters=self.db.list_repeaters
