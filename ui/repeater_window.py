"""Minimal repeater manager window."""
import tkinter as tk
from tkinter import ttk, messagebox
from models import Repeater
from .tooltip import Tooltip
class RepeaterWindow(tk.Toplevel):
 def __init__(self,parent,db,on_change):
  super().__init__(parent);self.db=db;self.on_change=on_change;self.title("Administrare repetoare");self.vars={k:tk.StringVar() for k in ("name","output_frequency_mhz","input_frequency_mhz","shift_mhz","tone_hz","mode","location","grid_square")};self.selected=None
  tips={"name":"Numele sau indicativul repetorului.","output_frequency_mhz":"Frecvența de emisie a repetorului, în MHz.","input_frequency_mhz":"Frecvența de intrare a repetorului, în MHz.","shift_mhz":"Diferența dintre frecvența de intrare și ieșire, în MHz.","tone_hz":"Tonul CTCSS, în Hz, dacă este necesar.","mode":"Modul de lucru al repetorului.","location":"Locația repetorului.","grid_square":"Locatorul Maidenhead al repetorului."}
  for i,(key,var) in enumerate(self.vars.items()):ttk.Label(self,text=key.replace("_"," ")).grid(row=i,column=0,sticky="w");entry=ttk.Entry(self,textvariable=var);entry.grid(row=i,column=1,sticky="ew");Tooltip(entry,tips[key])
  self.notes=tk.Text(self,height=3);self.notes.grid(row=8,columnspan=2);Tooltip(self.notes,"Observații suplimentare despre repetor.");save=ttk.Button(self,text="Salvează",command=self.save);save.grid(row=9,column=0);Tooltip(save,"Salvează repetorul în baza de date.");delete=ttk.Button(self,text="Șterge",command=self.delete);delete.grid(row=9,column=1);Tooltip(delete,"Șterge repetorul selectat după confirmare.");self.tree=ttk.Treeview(self,columns=("id","name","freq","location"),show="headings");[self.tree.heading(x,text=x) for x in ("id","name","freq","location")];self.tree.grid(row=0,column=2,rowspan=10);self.tree.bind("<<TreeviewSelect>>",self.select);Tooltip(self.tree,"Lista repetoarelor. Selectează un rând pentru editare.");self.refresh()
 def refresh(self):
  self.tree.delete(*self.tree.get_children())
  for r in self.db.list_repeaters():self.tree.insert("","end",iid=r["id"],values=(r["id"],r["name"],r["output_frequency_mhz"],r["location"]))
 def select(self,_):
  if not self.tree.selection():return
  r=next(x for x in self.db.list_repeaters() if x["id"]==int(self.tree.selection()[0]));self.selected=r["id"]
  for k,v in self.vars.items():v.set(r[k] or "")
  self.notes.delete("1.0","end");self.notes.insert("1.0",r["notes"] or "")
 def save(self):
  try:
   vals={k:v.get() for k,v in self.vars.items()};r=Repeater(id=self.selected,name=vals["name"],output_frequency_mhz=float(vals["output_frequency_mhz"]),input_frequency_mhz=float(vals["input_frequency_mhz"]) if vals["input_frequency_mhz"] else None,shift_mhz=float(vals["shift_mhz"]) if vals["shift_mhz"] else None,tone_hz=float(vals["tone_hz"]) if vals["tone_hz"] else None,mode=vals["mode"],location=vals["location"],grid_square=vals["grid_square"],notes=self.notes.get("1.0","end-1c"));self.db.save_repeater(r);self.refresh();self.on_change()
  except ValueError:messagebox.showerror("Eroare","Numele și frecvența de ieșire sunt obligatorii.")
 def delete(self):
  if self.selected and messagebox.askyesno("Confirmare","Ștergeți repetorul?"):self.db.delete_repeater(self.selected);self.refresh();self.on_change()
