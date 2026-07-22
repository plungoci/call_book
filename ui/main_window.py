"""Main, task-oriented window for the radio logbook."""
from __future__ import annotations

from datetime import datetime, timezone
import logging
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from application_controller import DuplicateQsoCancelled, LogbookController
from config import PROPAGATION_REFRESH_INTERVALS, save_config
from database import Database
from models import QSO
from .common_widgets import attach_tree_scrollbars
from .operator_profile_window import OperatorProfileWindow
from .propagation_panel import PropagationPanel
from .qso_form import QSOForm
from .repeater_window import RepeaterWindow
from .theme import COLORS, apply_dark_theme
from .tooltip import Tooltip


class MainWindow(tk.Tk):
    """Coordinate existing logbook actions inside a calm, tabbed workspace."""

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
        self.geometry("1440x900")
        self.minsize(1024, 700)
        apply_dark_theme(self)
        self.create_menu_bar()
        self._build_shell()
        self._schedule_propagation_auto_refresh()
        self.protocol("WM_DELETE_WINDOW", self.close_application)
        self.bind_all("<Control-n>", lambda event: self.cancel_edit())
        self.bind_all("<Control-s>", lambda event: self.save())
        self.bind_all("<Delete>", lambda event: self.delete())
        self.bind_all("<Escape>", lambda event: self.cancel_edit())
        self.bind_all("<Control-f>", self.focus_search)
        self.refresh()

    def _build_shell(self) -> None:
        toolbar = ttk.Frame(self, style="Surface.TFrame", padding=(16, 10))
        toolbar.pack(fill="x")
        ttk.Label(toolbar, text="Radio Logbook", style="Title.TLabel").pack(side="left")
        ttk.Label(toolbar, text="Jurnal radioamator • operare locală", style="Muted.TLabel").pack(side="left", padx=(12, 0))
        ttk.Button(toolbar, text="⌕  Caută", command=self.toggle_search_panel).pack(side="right", padx=(6, 0))
        self.quick_save = ttk.Button(toolbar, text="Salvează QSO", style="Accent.TButton", command=self.save)
        self.quick_save.pack(side="right")
        self.clock = ttk.Label(toolbar, style="Muted.TLabel")
        self.clock.pack(side="right", padx=18)
        self._clock()

        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill="both", expand=True, padx=12, pady=12)
        self.log_tab = ttk.Frame(self.notebook, padding=12)
        self.propagation_tab = ttk.Frame(self.notebook, padding=12)
        self.location_tab = ttk.Frame(self.notebook, padding=12)
        self.settings_tab = ttk.Frame(self.notebook, padding=12)
        self.notebook.add(self.log_tab, text="⌨  Jurnal QSO")
        self.notebook.add(self.propagation_tab, text="☀  Propagare")
        self.notebook.add(self.location_tab, text="🌍  Locație")
        self.notebook.add(self.settings_tab, text="⚙  Setări")
        self._build_log_tab()
        self._build_propagation_tab()
        self._build_location_tab()
        self._build_settings_tab()
        self._build_status_bar()

    def _build_log_tab(self) -> None:
        self._filters()
        self.form = QSOForm(self.log_tab, self.db.list_repeaters, self.save, self.operator_profile.default_power_w, self.propagation_context_changed)
        self.form.pack(fill="x", pady=(0, 10))
        self._actions()
        table_card = ttk.Frame(self.log_tab, style="Card.TFrame", padding=10)
        table_card.pack(fill="both", expand=True, pady=(10, 0))
        header = ttk.Frame(table_card, style="Surface.TFrame")
        header.pack(fill="x", pady=(0, 7))
        ttk.Label(header, text="Jurnal QSO", style="Section.TLabel").pack(side="left")
        ttk.Label(header, text="Selectează un rând pentru editare sau ștergere.", style="CardMuted.TLabel").pack(side="left", padx=10)
        self._table(table_card)

    def _build_propagation_tab(self) -> None:
        intro = ttk.Frame(self.propagation_tab, style="Card.TFrame", padding=12)
        intro.pack(fill="x", pady=(0, 10))
        ttk.Label(intro, text="Condiții de propagare", style="Title.TLabel").pack(anchor="w")
        ttk.Label(intro, text="Estimări locale bazate pe date space weather; nu reprezintă predicții garantate.", style="CardMuted.TLabel").pack(anchor="w", pady=(3, 0))
        self.propagation_panel = PropagationPanel(self.propagation_tab)
        self.propagation_panel.pack(fill="both", expand=True)
        if self.app_config.get("show_propagation_panel", "true").lower() != "true":
            self.notebook.hide(self.propagation_tab)

    def _build_location_tab(self) -> None:
        card = ttk.Frame(self.location_tab, style="Card.TFrame", padding=20)
        card.pack(fill="x", anchor="n")
        ttk.Label(card, text="🌍  Poziția stației", style="Title.TLabel").pack(anchor="w")
        ttk.Label(card, text="Locatorul Maidenhead și datele stației sunt păstrate local în profilul operatorului.", style="CardMuted.TLabel").pack(anchor="w", pady=(4, 16))
        profile = self.operator_profile
        details = (("Locator Maidenhead", profile.grid_square or profile.maidenhead_locator or "Nesetat"), ("Latitudine", "—" if profile.latitude is None else f"{profile.latitude:.6f}°"), ("Longitudine", "—" if profile.longitude is None else f"{profile.longitude:.6f}°"), ("Sursă", profile.location_source or "Nesetată"))
        grid = ttk.Frame(card, style="Surface.TFrame")
        grid.pack(fill="x")
        for index, (label, value) in enumerate(details):
            item = ttk.Frame(grid, style="Card.TFrame", padding=12)
            item.grid(row=0, column=index, sticky="nsew", padx=(0, 8) if index < 3 else 0)
            ttk.Label(item, text=label, style="CardMuted.TLabel").pack(anchor="w")
            ttk.Label(item, text=value, style="Metric.TLabel").pack(anchor="w", pady=(3, 0))
            grid.columnconfigure(index, weight=1)
        ttk.Button(card, text="Deschide profilul operatorului", style="Accent.TButton", command=self.open_operator_profile).pack(anchor="w", pady=(18, 0))

    def _build_settings_tab(self) -> None:
        ttk.Label(self.settings_tab, text="Setări și administrare", style="Title.TLabel").pack(anchor="w")
        ttk.Label(self.settings_tab, text="Acțiunile sunt grupate pe domenii, fără a aglomera zona de operare.", style="Muted.TLabel").pack(anchor="w", pady=(3, 14))
        grid = ttk.Frame(self.settings_tab)
        grid.pack(fill="x", anchor="n")
        cards = (("General", "Profil, indicativ și echipament", "Date operator", self.open_operator_profile), ("Repetoare", "Frecvențe, shift, CTCSS și locator", "Administrează repetoare", self.open_repeaters), ("Propagare", "Surse și interval de actualizare", "Setări propagare", self.open_propagation_settings), ("Date", "Exportă jurnalul sau creează o copie", "Creează backup", self.backup))
        for index, (title, description, action, command) in enumerate(cards):
            card = ttk.Frame(grid, style="Card.TFrame", padding=16)
            card.grid(row=index // 2, column=index % 2, sticky="nsew", padx=(0, 10) if index % 2 == 0 else 0, pady=(0, 10))
            ttk.Label(card, text=title, style="Section.TLabel").pack(anchor="w")
            ttk.Label(card, text=description, style="CardMuted.TLabel", wraplength=340).pack(anchor="w", pady=(5, 16))
            ttk.Button(card, text=action, command=command).pack(anchor="w")
        grid.columnconfigure(0, weight=1); grid.columnconfigure(1, weight=1)

    def _build_status_bar(self) -> None:
        status = ttk.Frame(self, style="Surface.TFrame", padding=(14, 6))
        status.pack(fill="x", side="bottom")
        self.status_message = tk.StringVar(value="Gata pentru un QSO nou.")
        ttk.Label(status, textvariable=self.status_message, style="Muted.TLabel").pack(side="left")
        ttk.Label(status, text="● Local", foreground=COLORS["success"], style="Muted.TLabel").pack(side="right")
        ttk.Label(status, text="NOAA la cerere", style="Muted.TLabel").pack(side="right", padx=16)
        ttk.Label(status, text="Radio Logbook", style="Muted.TLabel").pack(side="right")

    def create_menu_bar(self) -> None:
        menu = tk.Menu(self); file_menu = tk.Menu(menu, tearoff=False)
        file_menu.add_command(label="Exportă Excel", command=self.excel); file_menu.add_command(label="Exportă ADIF", command=self.adif); file_menu.add_separator(); file_menu.add_command(label="Creează backup", command=self.backup); file_menu.add_separator(); file_menu.add_command(label="Ieșire", command=self.close_application); menu.add_cascade(label="Fișier", menu=file_menu)
        settings = tk.Menu(menu, tearoff=False); settings.add_command(label="Date operator", command=self.open_operator_profile); settings.add_command(label="Repetoare", command=self.open_repeaters); settings.add_command(label="Setări condiții propagare", command=self.open_propagation_settings); menu.add_cascade(label="Setări", menu=settings)
        if "app_config" in self.__dict__:
            view = tk.Menu(menu, tearoff=False); self.show_propagation_panel_var = tk.BooleanVar(value=self.app_config.get("show_propagation_panel", "true").lower() == "true"); view.add_checkbutton(label="Condiții propagare", variable=self.show_propagation_panel_var, command=self.toggle_propagation_panel); view.add_command(label="Actualizează condițiile propagării", command=self.refresh_propagation_panel); menu.add_cascade(label="Vizualizare", menu=view)
        self.config(menu=menu)

    def open_propagation_settings(self) -> None:
        window = tk.Toplevel(self); window.title("Setări condiții propagare"); window.transient(self); window.configure(background=COLORS["background"])
        enabled = tk.BooleanVar(value=self.app_config.get("propagation_auto_refresh_minutes", "15") in PROPAGATION_REFRESH_INTERVALS); interval = tk.StringVar(value=self.app_config.get("propagation_auto_refresh_minutes", "15"))
        card = ttk.Frame(window, style="Card.TFrame", padding=16); card.pack(fill="both", expand=True, padx=12, pady=12)
        ttk.Label(card, text="Actualizare propagare", style="Section.TLabel").pack(anchor="w"); ttk.Label(card, text="Datele sunt descărcate din surse instituționale și oferă o estimare orientativă.", style="CardMuted.TLabel", wraplength=480).pack(anchor="w", pady=(5, 12)); ttk.Checkbutton(card, text="Actualizare automată condiții", variable=enabled).pack(anchor="w")
        row = ttk.Frame(card, style="Surface.TFrame"); row.pack(fill="x", pady=10); ttk.Label(row, text="Interval:", style="Card.TLabel").pack(side="left"); ttk.Combobox(row, textvariable=interval, values=("10", "15", "30", "60"), state="readonly", width=8).pack(side="left", padx=6); ttk.Label(row, text="minute", style="Card.TLabel").pack(side="left")
        def save_settings() -> None:
            self.app_config["propagation_auto_refresh_minutes"] = interval.get() if enabled.get() else "0"; save_config(self.app_config)
            if self._propagation_auto_after_id:
                try: self.after_cancel(self._propagation_auto_after_id)
                except tk.TclError: pass
            self._schedule_propagation_auto_refresh(); self._set_status("Setările de propagare au fost actualizate."); window.destroy()
        ttk.Button(card, text="Salvează", style="Accent.TButton", command=save_settings).pack(anchor="e")

    def propagation_context_changed(self, band: str, frequency: str) -> None:
        try: value = float(frequency) if frequency.strip() else None
        except ValueError: value = None
        if "propagation_panel" in self.__dict__ and self.show_propagation_panel_var.get(): self.propagation_panel.schedule(band, value)
    def refresh_propagation_panel(self) -> None: self.propagation_panel.refresh(force=True)
    def toggle_propagation_panel(self) -> None:
        visible = self.show_propagation_panel_var.get(); self.app_config["show_propagation_panel"] = "true" if visible else "false"; save_config(self.app_config)
        if visible: self.notebook.add(self.propagation_tab, text="☀  Propagare"); self.refresh_propagation_panel()
        else: self.notebook.hide(self.propagation_tab)
    def _schedule_propagation_auto_refresh(self) -> None:
        try: minutes = int(self.app_config.get("propagation_auto_refresh_minutes", "15"))
        except ValueError: minutes = 15
        if str(minutes) in PROPAGATION_REFRESH_INTERVALS: self._propagation_auto_after_id = self.after(minutes * 60 * 1000, self._automatic_propagation_refresh)
    def _automatic_propagation_refresh(self) -> None:
        if self.show_propagation_panel_var.get() and self.form.vars["band"].get(): self.refresh_propagation_panel()
        self._schedule_propagation_auto_refresh()
    def _clock(self) -> None:
        now, utc = datetime.now().astimezone(), datetime.now(timezone.utc); self.clock.config(text=f"Local {now:%H:%M:%S}  |  UTC {utc:%H:%M:%S}"); self._clock_after_id = self.after(1000, self._clock)

    def _filters(self) -> None:
        self.search_panel = ttk.Frame(self.log_tab, style="Card.TFrame", padding=10); self.search, self.band, self.mode = tk.StringVar(), tk.StringVar(), tk.StringVar(); self.rep, self.date_from, self.date_to = tk.StringVar(), tk.StringVar(), tk.StringVar()
        fields = (("Indicativ", self.search), ("Bandă", self.band), ("Mod", self.mode), ("Repetor ID", self.rep), ("De la", self.date_from), ("Până la", self.date_to))
        for label, variable in fields:
            group = ttk.Frame(self.search_panel, style="Surface.TFrame"); group.pack(side="left", fill="x", expand=True, padx=3); ttk.Label(group, text=label, style="CardMuted.TLabel").pack(anchor="w"); entry = ttk.Entry(group, textvariable=variable); entry.pack(fill="x"); Tooltip(entry, f"Filtrează QSO-urile după {label.lower()}.")
            if variable is self.search: self.search_entry = entry
        ttk.Button(self.search_panel, text="Aplică", command=self.refresh).pack(side="left", padx=(8, 3)); ttk.Button(self.search_panel, text="Resetează", command=self.reset).pack(side="left")
    def _actions(self) -> None:
        actions = ttk.Frame(self.log_tab); actions.pack(fill="x")
        self.save_button = ttk.Button(actions, text="Salvează QSO", style="Accent.TButton", command=self.save); self.save_button.pack(side="left"); Tooltip(self.save_button, "Salvează QSO-ul în baza de date.")
        for name, command, attr, state in (("QSO nou", self.cancel_edit, None, "normal"), ("Anulează editarea", self.cancel_edit, "cancel_button", "disabled"), ("Editează", self.edit, "edit_button", "disabled"), ("Șterge", self.delete, "delete_button", "disabled")):
            button = ttk.Button(actions, text=name, command=command, state=state); button.pack(side="left", padx=(6, 0));
            if attr: setattr(self, attr, button)
        self.search_toggle_button = ttk.Button(actions, text="Filtrează", command=self.toggle_search_panel); self.search_toggle_button.pack(side="right")
    def toggle_search_panel(self) -> None:
        if self.search_panel_visible:
            self.search_panel.pack_forget(); self.search_toggle_button.config(text="Filtrează"); self.search_panel_visible = False; return
        self.search_panel.pack(fill="x", padx=8, before=self.form); self.search_toggle_button.config(text="Ascunde filtrele"); self.search_panel_visible = True; self.search_entry.focus_set()
    def focus_search(self, event: object = None) -> str:
        if not self.search_panel_visible: self.toggle_search_panel()
        else: self.search_entry.focus_set()
        return "break"
    def _table(self, parent: tk.Misc) -> None:
        columns = ("id", "date", "time", "callsign", "name", "freq", "band", "mode", "repeater", "sent", "received", "qsl"); self.tree = ttk.Treeview(parent, columns=columns, show="headings")
        for column in columns: self.tree.heading(column, text=column.upper()); self.tree.column(column, width=105, minwidth=70, stretch=True)
        self.table_container = attach_tree_scrollbars(parent, self.tree); self.table_container.pack(fill="both", expand=True); self.tree.bind("<<TreeviewSelect>>", self.selection_changed); Tooltip(self.tree, "Lista QSO-urilor salvate.")
    def filters(self) -> dict[str, str]: return {"callsign": self.search.get(), "band": self.band.get(), "mode": self.mode.get(), "repeater_id": self.rep.get(), "date_from": self.date_from.get(), "date_to": self.date_to.get()}
    def refresh(self) -> None:
        self.tree.delete(*self.tree.get_children())
        for row in self.db.list_qsos(self.filters()):
            dt = row["qso_start_utc"]; self.tree.insert("", "end", iid=row["id"], values=(row["id"], dt[:10], dt[11:19], row["callsign"], row["operator_name"], row["frequency_mhz"], row["band"], row["mode"], row["repeater_name"] or "", row["rst_sent"], row["rst_received"], row["qsl_status"]))
        self.selection_changed(); self._set_status(f"{len(self.tree.get_children())} QSO-uri afișate.")
    def selection_changed(self, event: object = None) -> None:
        state = "normal" if self.tree.selection() else "disabled"; self.edit_button.config(state=state); self.delete_button.config(state=state)
    def edit(self) -> None:
        if self.tree.selection(): self.form.load(self.db.get_qso(int(self.tree.selection()[0]))); self.save_button.config(text="Actualizează QSO"); self.quick_save.config(text="Actualizează QSO"); self.cancel_button.config(state="normal"); self.notebook.select(self.log_tab)
    def cancel_edit(self) -> None:
        self.form.new(); self.save_button.config(text="Salvează QSO"); self.quick_save.config(text="Salvează QSO"); self.cancel_button.config(state="disabled"); self.tree.selection_remove(self.tree.selection()); self._set_status("Gata pentru un QSO nou.")
    def save(self) -> None:
        try:
            _, editing = self.controller.save_qso(self.form.value(), lambda _: messagebox.askyesno("Posibil duplicat", "Există un QSO similar în ±2 minute. Salvați totuși?")); self.refresh(); self.cancel_edit(); self._set_status("QSO actualizat." if editing else "QSO salvat.")
        except DuplicateQsoCancelled: return
        except (ValueError, OSError, KeyError) as exc: logging.exception("QSO save error"); messagebox.showerror("Eroare", str(exc))
    def delete(self) -> None:
        if not self.tree.selection(): return
        qso = self.db.get_qso(int(self.tree.selection()[0])); when = qso.qso_start_utc.replace("T", " ")[:19] + " UTC"; prompt = f"Sigur dorești ștergerea acestui QSO?\n\n{qso.callsign}\n{qso.frequency_mhz:.3f} MHz\n{when}"
        if messagebox.askyesno("Confirmare ștergere", prompt): self.db.delete_qso(qso.id); self.refresh(); self.cancel_edit(); self._set_status("QSO șters.")
    def reset(self) -> None:
        for variable in (self.search, self.band, self.mode, self.rep, self.date_from, self.date_to): variable.set("")
        self.refresh()
    def selected_qsos(self) -> list[QSO]: return self.controller.list_qsos(self.filters())
    def open_operator_profile(self) -> None:
        if self._raise_window(self.operator_profile_window): return
        self.operator_profile_window = OperatorProfileWindow(self, self.db)
    def open_repeaters(self) -> None:
        if self._raise_window(self.repeater_window): return
        self.repeater_window = RepeaterWindow(self, self.db, self.repeater_changed)
    @staticmethod
    def _raise_window(window: tk.Toplevel | None) -> bool:
        if window is not None and window.winfo_exists(): window.lift(); window.focus_force(); return True
        return False
    def adif(self) -> None: self._export("ADIF", ".adi", [("ADIF", "*.adi")], self.controller.export_adif)
    def excel(self) -> None: self._export("Excel", ".xlsx", [("Excel", "*.xlsx")], self.controller.export_excel)
    def _export(self, title: str, extension: str, filetypes: list[tuple[str, str]], exporter: object) -> None:
        try:
            filename = filedialog.asksaveasfilename(initialdir="exports", defaultextension=extension, filetypes=filetypes)
            if filename: self._set_status(f"Export {title} creat: {exporter(self.selected_qsos(), destination=Path(filename))}")
        except Exception as exc: logging.exception("%s export", title); messagebox.showerror("Eroare export", str(exc))
    def backup(self) -> None:
        try: self._set_status(f"Backup creat: {self.controller.create_backup()}")
        except Exception as exc: logging.exception("Backup"); messagebox.showerror("Eroare backup", str(exc))
    def repeater_changed(self) -> None: self.form.repeaters = self.db.list_repeaters
    def _set_status(self, message: str) -> None:
        if hasattr(self, "status_message"): self.status_message.set(message)
    def close_application(self) -> None:
        self.propagation_panel.shutdown()
        for after_id in (self._propagation_auto_after_id, self._clock_after_id):
            if after_id:
                try: self.after_cancel(after_id)
                except tk.TclError: pass
        for window in (self.operator_profile_window, self.repeater_window):
            if window is not None and window.winfo_exists(): window.destroy()
        self.destroy()
