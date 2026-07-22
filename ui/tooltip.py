"""Reusable delayed tooltips for Tkinter and ttk widgets."""
from __future__ import annotations

import tkinter as tk
from collections.abc import Callable


TooltipText = str | Callable[[], str]


class Tooltip:
    """Show a small help window after the pointer rests on *widget*.

    ``text`` may also be a callable, which makes it suitable for displaying
    values that change while the application is running.
    """

    def __init__(self, widget: tk.Misc, text: TooltipText, delay: int = 500):
        self.widget = widget
        self.text = text
        self.delay = delay
        self._after_id: str | None = None
        self._state_after_id: str | None = None
        self._window: tk.Toplevel | None = None
        self._pointer: tuple[int, int] = (0, 0)
        self._bindings: list[tuple[tk.Misc, str, str]] = []

        self._bind(widget, "<Enter>", self._schedule)
        self._bind(widget, "<Leave>", self._hide)
        self._bind(widget, "<Motion>", self._cancel)
        self._bind(widget, "<ButtonPress>", self._hide)
        self._bind(widget, "<Destroy>", self._destroy)
        # FocusOut on the owning window also handles Alt-Tab and window changes.
        self._bind(widget.winfo_toplevel(), "<FocusOut>", self._hide)

    def _bind(self, target: tk.Misc, sequence: str, callback: Callable) -> None:
        binding_id = target.bind(sequence, callback, add="+")
        if binding_id:
            self._bindings.append((target, sequence, binding_id))

    def _schedule(self, event: tk.Event) -> None:
        self._hide()
        self._pointer = (event.x_root, event.y_root)
        if self._enabled():
            self._after_id = self.widget.after(self.delay, self._show)

    def _cancel(self, _event: tk.Event | None = None) -> None:
        if self._after_id is not None:
            try:
                self.widget.after_cancel(self._after_id)
            except tk.TclError:
                pass
            self._after_id = None

    def _enabled(self) -> bool:
        try:
            if str(self.widget.cget("state")) == "disabled":
                return False
            state = getattr(self.widget, "state", None)
            return state is None or "disabled" not in state()
        except tk.TclError:
            return False

    def _message(self) -> str:
        return self.text() if callable(self.text) else self.text

    def _show(self) -> None:
        self._after_id = None
        if not self._enabled() or self._window is not None:
            return
        try:
            message = self._message()
            if not message:
                return
            window = tk.Toplevel(self.widget)
            window.withdraw()
            window.overrideredirect(True)
            window.attributes("-topmost", True)
            label = tk.Label(
                window, text=message, justify="left", wraplength=300,
                background="#fff9d9", foreground="#111111", font=("TkDefaultFont", 10),
                relief="solid", borderwidth=1, padx=8, pady=5,
            )
            label.pack()
            x, y = self._pointer
            window.geometry(f"+{x + 14}+{y + 18}")
            window.deiconify()
            self._window = window
            self._watch_enabled()
        except tk.TclError:
            self._window = None

    def _watch_enabled(self) -> None:
        if self._window is None:
            return
        if not self._enabled():
            self._hide()
            return
        try:
            self._state_after_id = self.widget.after(100, self._watch_enabled)
        except tk.TclError:
            self._state_after_id = None

    def _hide(self, _event: tk.Event | None = None) -> None:
        self._cancel()
        if self._state_after_id is not None:
            try:
                self.widget.after_cancel(self._state_after_id)
            except tk.TclError:
                pass
            self._state_after_id = None
        if self._window is not None:
            try:
                self._window.destroy()
            except tk.TclError:
                pass
            self._window = None

    def _destroy(self, _event: tk.Event | None = None) -> None:
        self._hide()
        for target, sequence, binding_id in self._bindings:
            try:
                target.unbind(sequence, binding_id)
            except tk.TclError:
                pass
        self._bindings.clear()
        self.widget = None  # type: ignore[assignment]
