"""Main Tkinter window for the radio logbook."""
from __future__ import annotations

from datetime import datetime, timezone
import logging
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from adif_export import export_adif
from backup import create_backup
from database import Database
from excel_export import export_excel
from models import QSO
from validators import validate_qso
from .operator_profile_window import OperatorProfileWindow
from .qso_form import QSOForm
from .repeater_window import RepeaterWindow
from .tooltip import Tooltip


class MainWindow(tk.Tk):
    """Coordinate QSO entry, selection, persistence, and export actions."""

    def __init__(self, db: Database, config: dict[str, str]) -> None:
        super().__init__()
        self.db, self.app_config = db, config
        self.operator_profile = self.db.get_operator_profile()
        self.title("Radio Logbook")
        self.geometry("1250x760")
        self._menu()
        self.clock = ttk.Label(self)
        self.clock.pack(anchor="e", padx=8)
        self._clock()
        self._filters()
        self.form = QSOForm(self, self.db.list_repeaters, self.save, self.operator_profile.default_power_w)
        self.form.pack(fill="x", padx=8)
        self._actions()
        self._table()
        self.bind_all("<Control-n>", lambda event: self.cancel_edit())
        self.bind_all("<Control-s>", lambda event: self.save())
        self.bind_all("<Delete>", lambda event: self.delete())
        self.bind_all("<Escape>", lambda event: self.cancel_edit())
        self.bind_all("<Control-f>", lambda event: self.search.focus_set())
        self.refresh()

    def _menu(self) -> None:
        menu = tk.Menu(self)
        settings = tk.Menu(menu, tearoff=False)
        settings.add_command(label="Date operator", command=self.open_operator_profile)
        menu.add_cascade(label="Setări", menu=settings)
        self.config(menu=menu)

    def _clock(self) -> None:
        now, utc = datetime.now().astimezone(), datetime.now(timezone.utc)
        self.clock.config(text=f"Local: {now:%Y-%m-%d %H:%M:%S %Z} | UTC: {utc:%Y-%m-%d %H:%M:%S}")
        self.after(1000, self._clock)

    def _filters(self) -> None:
        bar = ttk.Frame(self)
        bar.pack(fill="x", padx=8)
        self.search, self.band, self.mode = tk.StringVar(), tk.StringVar(), tk.StringVar()
        self.rep, self.date_from, self.date_to = tk.StringVar(), tk.StringVar(), tk.StringVar()
        fields = (("Indicativ", self.search, "Filtrează rapid QSO-urile după indicativ."),
                  ("Bandă", self.band, "Filtrează QSO-urile după bandă."),
                  ("Mod", self.mode, "Filtrează QSO-urile după modul de lucru."),
                  ("Repetor ID", self.rep, "Filtrează QSO-urile după repetor."),
                  ("De la", self.date_from, "Afișează QSO-uri de la această dată."),
                  ("Până la", self.date_to, "Afișează QSO-uri până la această dată."))
        for label, variable, tip in fields:
            ttk.Label(bar, text=label).pack(side="left")
            entry = ttk.Entry(bar, textvariable=variable, width=12)
            entry.pack(side="left")
            Tooltip(entry, tip)
        buttons = (("Caută", self.refresh, "Filtrează rapid QSO-urile după indicativ.", "left"),
                   ("Reset", self.reset, "Șterge toate filtrele de căutare.", "left"),
                   ("Repetoare", lambda: RepeaterWindow(self, self.db, self.repeater_changed), "Administrează lista de repetoare.", "right"),
                   ("Date operator", self.open_operator_profile, "Configurează informațiile personale ale proprietarului logbook-ului.", "right"),
                   ("Backup", self.backup, "Creează un backup al bazei de date SQLite.", "right"),
                   ("Excel", self.excel, "Exportă toate QSO-urile într-un fișier Excel.", "right"),
                   ("ADIF", self.adif, "Exportă logbook-ul în format ADIF compatibil cu alte aplicații.", "right"))
        for text, command, tip, side in buttons:
            button = ttk.Button(bar, text=text, command=command)
            button.pack(side=side)
            Tooltip(button, tip)

    def _actions(self) -> None:
        actions = ttk.Frame(self)
        actions.pack()
        self.save_button = ttk.Button(actions, text="Salvează QSO", command=self.save)
        self.save_button.pack(side="left")
        Tooltip(self.save_button, "Salvează QSO-ul în baza de date sau modificările efectuate asupra acestuia.")
        new = ttk.Button(actions, text="QSO nou", command=self.cancel_edit)
        new.pack(side="left")
        Tooltip(new, "Golește formularul și pregătește introducerea unei noi legături.")
        self.cancel_button = ttk.Button(actions, text="Anulează editarea", command=self.cancel_edit, state="disabled")
        self.cancel_button.pack(side="left")
        Tooltip(self.cancel_button, "Renunță la modificările nesalvate.")
        self.edit_button = ttk.Button(actions, text="Editează", command=self.edit, state="disabled")
        self.edit_button.pack(side="left")
        Tooltip(self.edit_button, "Încarcă QSO-ul selectat pentru modificare.")
        self.delete_button = ttk.Button(actions, text="Șterge", command=self.delete, state="disabled")
        self.delete_button.pack(side="left")
        Tooltip(self.delete_button, "Șterge definitiv QSO-ul selectat după confirmare.")

    def _table(self) -> None:
        columns = ("id", "date", "time", "callsign", "name", "freq", "band", "mode", "repeater", "sent", "received", "qsl")
        self.tree = ttk.Treeview(self, columns=columns, show="headings")
        for column in columns:
            self.tree.heading(column, text=column.upper())
        self.tree.pack(fill="both", expand=True, padx=8, pady=8)
        self.tree.bind("<<TreeviewSelect>>", self.selection_changed)
        Tooltip(self.tree, "Lista QSO-urilor salvate. Selectează un rând pentru editare sau ștergere.")

    def filters(self) -> dict[str, str]:
        return {"callsign": self.search.get(), "band": self.band.get(), "mode": self.mode.get(), "repeater_id": self.rep.get(), "date_from": self.date_from.get(), "date_to": self.date_to.get()}

    def refresh(self) -> None:
        self.tree.delete(*self.tree.get_children())
        for row in self.db.list_qsos(self.filters()):
            dt = row["qso_start_utc"]
            self.tree.insert("", "end", iid=row["id"], values=(row["id"], dt[:10], dt[11:19], row["callsign"], row["operator_name"], row["frequency_mhz"], row["band"], row["mode"], row["repeater_name"] or "", row["rst_sent"], row["rst_received"], row["qsl_status"]))
        self.selection_changed()

    def selection_changed(self, event: object = None) -> None:
        state = "normal" if self.tree.selection() else "disabled"
        self.edit_button.config(state=state)
        self.delete_button.config(state=state)

    def edit(self) -> None:
        """Load selected QSO in edit mode while retaining its database ID."""
        if self.tree.selection():
            self.form.load(self.db.get_qso(int(self.tree.selection()[0])))
            self.save_button.config(text="Actualizează QSO")
            self.cancel_button.config(state="normal")

    def cancel_edit(self) -> None:
        """Discard unsaved data and restore a new QSO form."""
        self.form.new()
        self.save_button.config(text="Salvează QSO")
        self.cancel_button.config(state="disabled")
        self.tree.selection_remove(self.tree.selection())

    def save(self) -> None:
        try:
            qso = self.form.value()
            if qso.id is None:
                # Snapshot the operator's locator for historical ADIF accuracy.
                qso.my_grid_square = self.db.get_operator_profile().grid_square
            qso.qso_end_utc = qso.qso_end_utc or datetime.now(timezone.utc).replace(microsecond=0).isoformat()
            validate_qso(qso)
            if self.db.possible_duplicate(qso) and not messagebox.askyesno("Posibil duplicat", "Există un QSO similar în ±2 minute. Salvați totuși?"):
                return
            editing = qso.id is not None
            self.db.save_qso(qso)
            self.refresh()
            self.cancel_edit()
            messagebox.showinfo("Succes", "QSO actualizat." if editing else "QSO salvat.")
        except Exception as exc:
            logging.exception("QSO save error")
            messagebox.showerror("Eroare", str(exc))

    def delete(self) -> None:
        """Delete selected QSO only after a detailed confirmation."""
        if not self.tree.selection():
            return
        qso = self.db.get_qso(int(self.tree.selection()[0]))
        when = qso.qso_start_utc.replace("T", " ")[:19] + " UTC"
        prompt = f"Sigur dorești ștergerea acestui QSO?\n\n{qso.callsign}\n{qso.frequency_mhz:.3f} MHz\n{when}"
        if messagebox.askyesno("Confirmare ștergere", prompt):
            self.db.delete_qso(qso.id)
            self.refresh()
            self.cancel_edit()

    def reset(self) -> None:
        for variable in (self.search, self.band, self.mode, self.rep, self.date_from, self.date_to):
            variable.set("")
        self.refresh()

    def selected_qsos(self) -> list[QSO]:
        return [QSO(**{key: row[key] for key in QSO.__dataclass_fields__ if key in row.keys()}) for row in self.db.list_qsos(self.filters())]

    def open_operator_profile(self) -> None:
        OperatorProfileWindow(self, self.db)

    def adif(self) -> None:
        self._export("ADIF", ".adi", [("ADIF", "*.adi")], lambda qsos, destination: export_adif(qsos, destination=destination, profile=self.db.get_operator_profile()))

    def excel(self) -> None:
        self._export("Excel", ".xlsx", [("Excel", "*.xlsx")], export_excel)

    def _export(self, title: str, extension: str, filetypes: list[tuple[str, str]], exporter: object) -> None:
        try:
            filename = filedialog.asksaveasfilename(initialdir="exports", defaultextension=extension, filetypes=filetypes)
            if filename:
                result = exporter(self.selected_qsos(), destination=Path(filename))
                messagebox.showinfo(title, f"Export creat: {result}")
        except Exception as exc:
            logging.exception("%s export", title)
            messagebox.showerror("Eroare export", str(exc))

    def backup(self) -> None:
        try:
            messagebox.showinfo("Backup", f"Backup creat: {create_backup(self.db.path)}")
        except Exception as exc:
            logging.exception("Backup")
            messagebox.showerror("Eroare backup", str(exc))

    def repeater_changed(self) -> None:
        self.form.repeaters = self.db.list_repeaters
