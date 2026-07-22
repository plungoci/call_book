"""Dialog used to maintain the logbook owner's personal data."""
from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk

from database import Database
from models import OperatorProfile
from validators import normalize_callsign, normalize_name


class OperatorProfileWindow(tk.Toplevel):
    """A modal editor for the singleton ``operator_profile`` SQLite row."""

    FIELDS = (
        ("Indicativ personal", "callsign"), ("Nume complet", "full_name"),
        ("Locator Maidenhead", "maidenhead_locator"), ("Localitate", "locality"),
        ("Județ", "county"), ("Țară", "country"), ("Adresă", "address"),
        ("Email", "email"), ("Telefon", "phone"),
        ("Echipament radio", "radio_equipment"), ("Antenă", "antenna"),
        ("Putere implicită (W)", "default_power_w"), ("Club radio", "radio_club"),
        ("Indicativ club", "club_callsign"),
    )

    def __init__(self, parent: tk.Misc, db: Database) -> None:
        super().__init__(parent)
        self.db = db
        self.title("Date operator")
        self.resizable(False, False)
        self.transient(parent)
        self.vars = {name: tk.StringVar() for _, name in self.FIELDS}
        self._build()
        self.load_profile()
        self.grab_set()

    def _build(self) -> None:
        content = ttk.Frame(self, padding=12)
        content.pack(fill="both", expand=True)
        for index, (label, name) in enumerate(self.FIELDS):
            ttk.Label(content, text=label).grid(row=index, column=0, sticky="w", pady=2)
            ttk.Entry(content, textvariable=self.vars[name], width=42).grid(row=index, column=1, sticky="ew", pady=2)
        ttk.Label(content, text="Observații").grid(row=len(self.FIELDS), column=0, sticky="nw", pady=2)
        self.notes = tk.Text(content, width=40, height=4)
        self.notes.grid(row=len(self.FIELDS), column=1, sticky="ew", pady=2)
        buttons = ttk.Frame(content)
        buttons.grid(row=len(self.FIELDS) + 1, column=0, columnspan=2, pady=(8, 0))
        ttk.Button(buttons, text="Salvează", command=self.save).pack(side="left", padx=3)
        ttk.Button(buttons, text="Resetează", command=self.reset).pack(side="left", padx=3)
        ttk.Button(buttons, text="Închide", command=self.destroy).pack(side="left", padx=3)

    def load_profile(self) -> None:
        """Load the stored profile into the form."""
        profile = self.db.get_operator_profile()
        for name, variable in self.vars.items():
            value = getattr(profile, name)
            variable.set("" if value is None else str(value))
        self.notes.delete("1.0", "end")
        self.notes.insert("1.0", profile.notes)

    def save(self) -> None:
        """Persist the values entered by the user."""
        values = {name: variable.get().strip() for name, variable in self.vars.items()}
        try:
            values["default_power_w"] = float(values["default_power_w"]) if values["default_power_w"] else None
            if values["default_power_w"] is not None and values["default_power_w"] <= 0:
                raise ValueError("Puterea implicită trebuie să fie pozitivă.")
        except ValueError as exc:
            messagebox.showerror("Eroare", str(exc), parent=self)
            return
        values["callsign"] = normalize_callsign(values["callsign"])
        values["full_name"] = normalize_name(values["full_name"])
        values["club_callsign"] = normalize_callsign(values["club_callsign"])
        self.db.save_operator_profile(OperatorProfile(**values, notes=self.notes.get("1.0", "end-1c")))
        messagebox.showinfo("Date operator", "Datele operatorului au fost salvate.", parent=self)

    def reset(self) -> None:
        """Clear persisted profile data only after explicit confirmation."""
        if messagebox.askyesno("Confirmare", "Sigur doriți resetarea datelor operatorului?", parent=self):
            self.db.save_operator_profile(OperatorProfile())
            self.load_profile()
