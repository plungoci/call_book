"""Scrollable repeater management dialog."""
from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk

from models import Repeater
from .common_widgets import attach_tree_scrollbars
from .tooltip import Tooltip


REPEATER_FIELDS = (
    ("Nume", "name"), ("Frecvență ieșire (MHz)", "output_frequency_mhz"),
    ("Frecvență intrare (MHz)", "input_frequency_mhz"), ("Shift (MHz)", "shift_mhz"),
    ("CTCSS (Hz)", "tone_hz"), ("Mod", "mode"), ("Locație", "location"),
    ("Locator", "grid_square"),
)
REPEATER_TIPS = {"name":"Numele sau indicativul repetorului.", "output_frequency_mhz":"Frecvența de emisie a repetorului, în MHz.", "input_frequency_mhz":"Frecvența de intrare a repetorului, în MHz.", "shift_mhz":"Diferența dintre frecvența de intrare și ieșire, în MHz.", "tone_hz":"Tonul CTCSS, în Hz, dacă este necesar.", "mode":"Modul de lucru al repetorului.", "location":"Locația repetorului.", "grid_square":"Locatorul Maidenhead al repetorului."}


class RepeaterWindow(tk.Toplevel):
    def __init__(self, parent: tk.Misc, db: object, on_change: object) -> None:
        super().__init__(parent); self.db, self.on_change = db, on_change
        self.title("Administrare repetoare"); self.geometry("850x480"); self.minsize(620, 360)
        self.vars = {key: tk.StringVar() for _, key in REPEATER_FIELDS}; self.selected: int | None = None
        self._build(); self.refresh()

    def _build(self) -> None:
        self.columnconfigure(1, weight=1); self.rowconfigure(0, weight=1)
        form = ttk.Frame(self, padding=10); form.grid(row=0, column=0, sticky="ns")
        for row, (label, key) in enumerate(REPEATER_FIELDS):
            ttk.Label(form, text=label).grid(row=row, column=0, sticky="w", pady=2)
            entry = ttk.Entry(form, textvariable=self.vars[key], width=28); entry.grid(row=row, column=1, sticky="ew", pady=2)
            Tooltip(entry, REPEATER_TIPS[key])
        ttk.Label(form, text="Observații").grid(row=len(REPEATER_FIELDS), column=0, sticky="nw", pady=2)
        self.notes = tk.Text(form, height=4, width=28, wrap="word"); self.notes.grid(row=len(REPEATER_FIELDS), column=1, sticky="ew", pady=2)
        buttons = ttk.Frame(form); buttons.grid(row=len(REPEATER_FIELDS)+1, columnspan=2, pady=6)
        ttk.Button(buttons, text="Salvează", command=self.save).pack(side="left", padx=3)
        ttk.Button(buttons, text="Șterge", command=self.delete).pack(side="left", padx=3)
        ttk.Button(buttons, text="Nou", command=self.clear).pack(side="left", padx=3)
        self.table_container, self.tree = attach_tree_scrollbars(self, columns=("id", "name", "freq", "location"), show="headings")
        for key, label, width in (("id", "ID", 55), ("name", "Nume", 180), ("freq", "Frecvență", 120), ("location", "Locație", 170)):
            self.tree.heading(key, text=label); self.tree.column(key, width=width, stretch=True)
        self.table_container.grid(row=0, column=1, sticky="nsew", padx=(0, 10), pady=10)
        self.tree.bind("<<TreeviewSelect>>", self.select); Tooltip(self.tree, "Lista repetoarelor. Selectează un rând pentru editare.")

    def refresh(self) -> None:
        self.tree.delete(*self.tree.get_children())
        for repeater in self.db.list_repeaters(): self.tree.insert("", "end", iid=repeater["id"], values=(repeater["id"], repeater["name"], repeater["output_frequency_mhz"], repeater["location"]))

    def select(self, _: object = None) -> None:
        if not self.tree.selection(): return
        repeater = next(item for item in self.db.list_repeaters() if item["id"] == int(self.tree.selection()[0])); self.selected = repeater["id"]
        for key, variable in self.vars.items(): variable.set(repeater[key] or "")
        self.notes.delete("1.0", "end"); self.notes.insert("1.0", repeater["notes"] or "")

    def clear(self) -> None:
        self.selected = None
        for variable in self.vars.values(): variable.set("")
        self.notes.delete("1.0", "end"); self.tree.selection_remove(self.tree.selection())

    def save(self) -> None:
        try:
            values = {key: value.get().strip() for key, value in self.vars.items()}
            repeater = Repeater(id=self.selected, name=values["name"], output_frequency_mhz=float(values["output_frequency_mhz"]), input_frequency_mhz=float(values["input_frequency_mhz"]) if values["input_frequency_mhz"] else None, shift_mhz=float(values["shift_mhz"]) if values["shift_mhz"] else None, tone_hz=float(values["tone_hz"]) if values["tone_hz"] else None, mode=values["mode"], location=values["location"], grid_square=values["grid_square"], notes=self.notes.get("1.0", "end-1c"))
            self.db.save_repeater(repeater); self.refresh(); self.on_change(); self.clear()
        except ValueError: messagebox.showerror("Eroare", "Numele și frecvența de ieșire sunt obligatorii.", parent=self)

    def delete(self) -> None:
        if self.selected and messagebox.askyesno("Confirmare", "Ștergeți repetorul?", parent=self):
            self.db.delete_repeater(self.selected); self.refresh(); self.on_change(); self.clear()
