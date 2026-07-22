"""Main Tkinter window for the radio logbook."""
from __future__ import annotations

from datetime import datetime, timezone
import logging
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from application_controller import DuplicateQsoCancelled, LogbookController
from config import PROPAGATION_REFRESH_INTERVALS, save_config
from database import Database
from excel_export import export_excel
from models import QSO
from .operator_profile_window import OperatorProfileWindow
from .qso_form import QSOForm
from .repeater_window import RepeaterWindow
from .tooltip import Tooltip
from .propagation_panel import PropagationPanel
from .common_widgets import attach_tree_scrollbars


class MainWindow(tk.Tk):
    """Coordinate QSO entry, selection, persistence, and export actions."""

    def __init__(self, db: Database, config: dict[str, str]) -> None:
        super().__init__()
        self.db, self.app_config = db, config
        self.controller = LogbookController(db)
        self.operator_profile = self.db.get_operator_profile()
        self.search_panel_visible = False
        self.operator_profile_window: OperatorProfileWindow | None = None
        self.repeater_window: RepeaterWindow | None = None
        self._clock_after_id: str | None = None
        self._propagation_auto_after_id: str | None = None
        self.title("Radio Logbook")
        self.geometry("1250x760")
        self.create_menu_bar()
        self.clock = ttk.Label(self)
        self.clock.pack(anchor="e", padx=8)
        self._clock()
        self._filters()
        self.form = QSOForm(self, self.db.list_repeaters, self.save, self.operator_profile.default_power_w, self.propagation_context_changed)
        self.form.pack(fill="x", padx=8)
        self.propagation_panel = PropagationPanel(self)
        self.propagation_panel.pack(fill="both", expand=False, padx=8, pady=(4,0))
        if self.app_config.get("show_propagation_panel", "true").lower() != "true": self.propagation_panel.pack_forget()
        self._schedule_propagation_auto_refresh()
        self._actions()
        self._table()
        self.protocol("WM_DELETE_WINDOW", self.close_application)
        self.bind_all("<Control-n>", lambda event: self.cancel_edit())
        self.bind_all("<Control-s>", lambda event: self.save())
        self.bind_all("<Delete>", lambda event: self.delete())
        self.bind_all("<Escape>", lambda event: self.cancel_edit())
        self.bind_all("<Control-f>", self.focus_search)
        self.refresh()

    def create_menu_bar(self) -> None:
        """Create the standard Tk menu bar without duplicating action logic."""
        menu = tk.Menu(self)
        file_menu = tk.Menu(menu, tearoff=False)
        file_menu.add_command(label="Exportă Excel", command=self.excel)
        file_menu.add_command(label="Exportă ADIF", command=self.adif)
        file_menu.add_separator()
        file_menu.add_command(label="Creează backup", command=self.backup)
        file_menu.add_separator()
        file_menu.add_command(label="Ieșire", command=self.close_application)
        menu.add_cascade(label="Fișier", menu=file_menu)
        settings = tk.Menu(menu, tearoff=False)
        settings.add_command(label="Date operator", command=self.open_operator_profile)
        settings.add_command(label="Repetoare", command=self.open_repeaters)
        settings.add_command(label="Setări condiții propagare", command=self.open_propagation_settings)
        menu.add_cascade(label="Setări", menu=settings)
        # Keep menu construction usable by the headless logic tests as well.
        if "app_config" in self.__dict__:
            view = tk.Menu(menu, tearoff=False)
            self.show_propagation_panel_var = tk.BooleanVar(value=self.app_config.get("show_propagation_panel", "true").lower() == "true")
            view.add_checkbutton(label="Condiții propagare", variable=self.show_propagation_panel_var, command=self.toggle_propagation_panel)
            view.add_command(label="Actualizează condițiile propagării", command=self.refresh_propagation_panel)
            menu.add_cascade(label="Vizualizare", menu=view)
        self.config(menu=menu)

    def open_propagation_settings(self) -> None:
        window = tk.Toplevel(self); window.title("Setări condiții propagare"); window.transient(self)
        enabled = tk.BooleanVar(value=self.app_config.get("propagation_auto_refresh_minutes", "15") in PROPAGATION_REFRESH_INTERVALS)
        interval = tk.StringVar(value=self.app_config.get("propagation_auto_refresh_minutes", "15"))
        ttk.Label(window, text="Datele meteo spațiale sunt descărcate de pe internet. Panoul afișează estimarea locală bazată pe datele NOAA SWPC.", wraplength=480, justify="left").pack(padx=12, pady=(12,6))
        ttk.Checkbutton(window, text="Actualizare automată condiții", variable=enabled).pack(anchor="w", padx=12)
        row=ttk.Frame(window);row.pack(fill="x",padx=12,pady=6);ttk.Label(row,text="Interval:").pack(side="left");ttk.Combobox(row,textvariable=interval,values=("10","15","30","60"),state="readonly",width=8).pack(side="left");ttk.Label(row,text="minute").pack(side="left")
        def save_settings() -> None:
            self.app_config["propagation_auto_refresh_minutes"] = interval.get() if enabled.get() else "0"
            save_config(self.app_config)
            if self._propagation_auto_after_id:
                try: self.after_cancel(self._propagation_auto_after_id)
                except tk.TclError: pass
            self._schedule_propagation_auto_refresh(); window.destroy()
        ttk.Button(window,text="Salvează",command=save_settings).pack(pady=(0,12))

    def propagation_context_changed(self, band: str, frequency: str) -> None:
        """Debounce band/frequency changes; QSO typing never starts HTTP directly."""
        try: value = float(frequency) if frequency.strip() else None
        except ValueError: value = None
        if "propagation_panel" in self.__dict__ and self.show_propagation_panel_var.get(): self.propagation_panel.schedule(band, value)

    def refresh_propagation_panel(self) -> None:
        self.propagation_panel.refresh(force=True)

    def toggle_propagation_panel(self) -> None:
        visible = self.show_propagation_panel_var.get()
        self.app_config["show_propagation_panel"] = "true" if visible else "false"
        save_config(self.app_config)
        if visible:
            if "tree" in self.__dict__: self.propagation_panel.pack(fill="both", expand=False, padx=8, pady=(4,0), before=self.tree)
            else: self.propagation_panel.pack(fill="both", expand=False, padx=8, pady=(4,0))
            self.refresh_propagation_panel()
        else: self.propagation_panel.pack_forget()

    def _schedule_propagation_auto_refresh(self) -> None:
        try: minutes=int(self.app_config.get("propagation_auto_refresh_minutes", "15"))
        except ValueError: minutes=15
        if str(minutes) not in PROPAGATION_REFRESH_INTERVALS: return
        self._propagation_auto_after_id=self.after(minutes*60*1000, self._automatic_propagation_refresh)

    def _automatic_propagation_refresh(self) -> None:
        if self.show_propagation_panel_var.get() and self.form.vars["band"].get(): self.refresh_propagation_panel()
        self._schedule_propagation_auto_refresh()

    def _clock(self) -> None:
        now, utc = datetime.now().astimezone(), datetime.now(timezone.utc)
        self.clock.config(text=f"Local: {now:%Y-%m-%d %H:%M:%S %Z} | UTC: {utc:%Y-%m-%d %H:%M:%S}")
        self._clock_after_id = self.after(1000, self._clock)

    def _filters(self) -> None:
        self.search_panel = ttk.Frame(self)
        self.search_panel.pack(fill="x", padx=8)
        self.search, self.band, self.mode = tk.StringVar(), tk.StringVar(), tk.StringVar()
        self.rep, self.date_from, self.date_to = tk.StringVar(), tk.StringVar(), tk.StringVar()
        fields = (("Indicativ", self.search, "Filtrează rapid QSO-urile după indicativ."),
                  ("Bandă", self.band, "Filtrează QSO-urile după bandă."),
                  ("Mod", self.mode, "Filtrează QSO-urile după modul de lucru."),
                  ("Repetor ID", self.rep, "Filtrează QSO-urile după repetor."),
                  ("De la", self.date_from, "Afișează QSO-uri de la această dată."),
                  ("Până la", self.date_to, "Afișează QSO-uri până la această dată."))
        for label, variable, tip in fields:
            ttk.Label(self.search_panel, text=label).pack(side="left")
            entry = ttk.Entry(self.search_panel, textvariable=variable, width=12)
            entry.pack(side="left")
            Tooltip(entry, tip)
            if variable is self.search:
                self.search_entry = entry
        buttons = (("Caută", self.refresh, "Filtrează rapid QSO-urile după indicativ."),
                   ("Resetează filtrele", self.reset, "Șterge toate filtrele de căutare."))
        for text, command, tip in buttons:
            button = ttk.Button(self.search_panel, text=text, command=command)
            button.pack(side="left")
            Tooltip(button, tip)
        # Keep the panel's pack configuration, but start with it out of view.
        self.search_panel.pack_forget()

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
        self.search_toggle_button = ttk.Button(actions, text="Caută / Filtrează", command=self.toggle_search_panel)
        self.search_toggle_button.pack(side="left")
        Tooltip(self.search_toggle_button, "Afișează sau ascunde opțiunile de căutare și filtrare a QSO-urilor.")

    def toggle_search_panel(self) -> None:
        """Show or hide filters without changing their values or active results."""
        if self.search_panel_visible:
            self.search_panel.pack_forget()
            self.search_toggle_button.config(text="Caută / Filtrează")
            self.search_panel_visible = False
            return
        self.search_panel.pack(fill="x", padx=8, before=self.form)
        self.search_toggle_button.config(text="Ascunde căutarea")
        self.search_panel_visible = True
        self.search_entry.focus_set()

    def focus_search(self, event: object = None) -> str:
        """Handle Ctrl+F: display filters if necessary, then focus callsign."""
        if not self.search_panel_visible:
            self.toggle_search_panel()
        else:
            self.search_entry.focus_set()
        return "break"

    def _table(self) -> None:
        columns = ("id", "date", "time", "callsign", "name", "freq", "band", "mode", "repeater", "sent", "received", "qsl")
        self.tree = ttk.Treeview(self, columns=columns, show="headings")
        for column in columns:
            self.tree.heading(column, text=column.upper())
            self.tree.column(column, width=105, minwidth=70, stretch=True)
        self.table_container = attach_tree_scrollbars(self, self.tree)
        self.table_container.pack(fill="both", expand=True, padx=8, pady=8)
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
            _, editing = self.controller.save_qso(
                self.form.value(),
                lambda _: messagebox.askyesno("Posibil duplicat", "Există un QSO similar în ±2 minute. Salvați totuși?"),
            )
            self.refresh()
            self.cancel_edit()
            messagebox.showinfo("Succes", "QSO actualizat." if editing else "QSO salvat.")
        except DuplicateQsoCancelled:
            return
        except (ValueError, OSError, KeyError) as exc:
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
        return self.controller.list_qsos(self.filters())

    def open_operator_profile(self) -> None:
        if self._raise_window(self.operator_profile_window):
            return
        self.operator_profile_window = OperatorProfileWindow(self, self.db)

    def open_repeaters(self) -> None:
        """Open the existing repeater manager, reusing it when already open."""
        if self._raise_window(self.repeater_window):
            return
        self.repeater_window = RepeaterWindow(self, self.db, self.repeater_changed)

    @staticmethod
    def _raise_window(window: tk.Toplevel | None) -> bool:
        if window is not None and window.winfo_exists():
            window.lift()
            window.focus_force()
            return True
        return False

    def adif(self) -> None:
        self._export("ADIF", ".adi", [("ADIF", "*.adi")], self.controller.export_adif)

    def excel(self) -> None:
        self._export("Excel", ".xlsx", [("Excel", "*.xlsx")], self.controller.export_excel)

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
            messagebox.showinfo("Backup", f"Backup creat: {self.controller.create_backup()}")
        except Exception as exc:
            logging.exception("Backup")
            messagebox.showerror("Eroare backup", str(exc))

    def repeater_changed(self) -> None:
        self.form.repeaters = self.db.list_repeaters

    def close_application(self) -> None:
        """Stop scheduled UI work and close child dialogs before destroying Tk."""
        self.propagation_panel.shutdown()
        if self._propagation_auto_after_id is not None:
            try: self.after_cancel(self._propagation_auto_after_id)
            except tk.TclError: pass
            self._propagation_auto_after_id = None
        if self._clock_after_id is not None:
            try:
                self.after_cancel(self._clock_after_id)
            except tk.TclError:
                pass
            self._clock_after_id = None
        for window in (self.operator_profile_window, self.repeater_window):
            if window is not None and window.winfo_exists():
                window.destroy()
        self.destroy()
