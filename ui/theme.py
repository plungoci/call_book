"""Shared visual language for the Radio Logbook desktop interface."""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk


COLORS = {
    "background": "#1e1e1e", "surface": "#252526", "control": "#2d2d30",
    "hover": "#37373d", "border": "#3f3f46", "text": "#f0f0f0",
    "muted": "#b0b0b0", "accent": "#007acc", "success": "#3fae6a",
    "warning": "#d9903d", "danger": "#d25c5c", "selection": "#094771",
}


def apply_dark_theme(root: tk.Misc) -> None:
    """Configure ttk once, keeping native widgets readable on long sessions."""
    style = ttk.Style(root)
    style.theme_use("clam")
    root.configure(background=COLORS["background"])
    root.option_add("*Font", ("Segoe UI", 10))
    root.option_add("*Text.background", COLORS["control"])
    root.option_add("*Text.foreground", COLORS["text"])
    root.option_add("*Text.insertBackground", COLORS["text"])
    root.option_add("*Text.selectBackground", COLORS["selection"])
    root.option_add("*Text.highlightThickness", 0)
    style.configure(".", background=COLORS["background"], foreground=COLORS["text"], font=("Segoe UI", 10))
    style.configure("TFrame", background=COLORS["background"])
    style.configure("TLabelframe", background=COLORS["surface"], foreground=COLORS["text"], bordercolor=COLORS["border"], relief="solid", borderwidth=1)
    style.configure("TLabelframe.Label", background=COLORS["surface"], foreground=COLORS["text"], font=("Segoe UI Semibold", 10))
    style.configure("Surface.TFrame", background=COLORS["surface"])
    style.configure("Card.TFrame", background=COLORS["surface"], relief="solid", borderwidth=1)
    style.configure("TLabel", background=COLORS["background"], foreground=COLORS["text"])
    style.configure("Muted.TLabel", foreground=COLORS["muted"])
    style.configure("Title.TLabel", font=("Segoe UI Semibold", 17), foreground=COLORS["text"])
    style.configure("Section.TLabel", font=("Segoe UI Semibold", 11), foreground=COLORS["text"])
    style.configure("Metric.TLabel", font=("Segoe UI Semibold", 15), foreground=COLORS["text"], background=COLORS["surface"])
    style.configure("Card.TLabel", background=COLORS["surface"], foreground=COLORS["text"])
    style.configure("CardMuted.TLabel", background=COLORS["surface"], foreground=COLORS["muted"])
    style.configure("TButton", background=COLORS["control"], foreground=COLORS["text"], bordercolor=COLORS["border"], padding=(10, 6))
    style.map("TButton", background=[("active", COLORS["hover"]), ("disabled", COLORS["surface"])], foreground=[("disabled", "#77777d")])
    style.configure("Accent.TButton", background=COLORS["accent"], bordercolor=COLORS["accent"], font=("Segoe UI Semibold", 10))
    style.map("Accent.TButton", background=[("active", "#1684c6"), ("disabled", COLORS["surface"])])
    style.configure("TEntry", fieldbackground=COLORS["control"], foreground=COLORS["text"], bordercolor=COLORS["border"], insertcolor=COLORS["text"], padding=6)
    style.configure("TCombobox", fieldbackground=COLORS["control"], background=COLORS["control"], foreground=COLORS["text"], arrowcolor=COLORS["text"], padding=5)
    style.map("TCombobox", fieldbackground=[("readonly", COLORS["control"])], selectbackground=[("readonly", COLORS["selection"])])
    style.configure("TNotebook", background=COLORS["background"], borderwidth=0)
    style.configure("TNotebook.Tab", background=COLORS["surface"], foreground=COLORS["muted"], padding=(16, 9), font=("Segoe UI Semibold", 10))
    style.map("TNotebook.Tab", background=[("selected", COLORS["control"]), ("active", COLORS["hover"])], foreground=[("selected", COLORS["text"])])
    style.configure("Treeview", background=COLORS["surface"], fieldbackground=COLORS["surface"], foreground=COLORS["text"], bordercolor=COLORS["border"], rowheight=29)
    style.map("Treeview", background=[("selected", COLORS["selection"])], foreground=[("selected", COLORS["text"])])
    style.configure("Treeview.Heading", background=COLORS["control"], foreground=COLORS["muted"], relief="flat", padding=(7, 7), font=("Segoe UI Semibold", 9))
    style.map("Treeview.Heading", background=[("active", COLORS["hover"])])
    style.configure("TScrollbar", background=COLORS["control"], troughcolor=COLORS["background"], bordercolor=COLORS["background"], arrowcolor=COLORS["muted"])
    style.configure("TSeparator", background=COLORS["border"])
