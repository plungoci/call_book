"""Qt uses native QWidget.setToolTip; no custom tooltip implementation is required."""
from PySide6.QtWidgets import QWidget
def Tooltip(widget: QWidget, text: str) -> None:
    widget.setToolTip(text() if callable(text) else text)
