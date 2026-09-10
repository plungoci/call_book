"""Application entry point."""

import logging

from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QApplication

from call_book.config import load_config
from call_book.database import Database
from call_book.ui.main_window import MainWindow


def main():
    logging.basicConfig(
        filename="radio_logbook.log", level=logging.DEBUG, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )
    # Fractional display scaling (125%, 150%, …) is the normal setting on
    # laptops and 4K monitors; without this the interface is laid out for
    # whole-number factors and ends up either blurry or clipped. It must be
    # set before the QApplication exists.
    QGuiApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    qt_app = QApplication([])
    qt_app.setStyle("Fusion")
    window = MainWindow(Database(), load_config())
    # Still opens maximized, as before; the size computed from the screen is
    # what the window restores to when un-maximized.
    window.showMaximized()
    qt_app.exec()


if __name__ == "__main__":
    main()
