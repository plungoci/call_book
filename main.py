"""Application entry point."""

import logging

from PySide6.QtWidgets import QApplication

from call_book.config import load_config
from call_book.database import Database
from call_book.ui.main_window import MainWindow


def main():
    logging.basicConfig(
        filename="radio_logbook.log", level=logging.DEBUG, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )
    qt_app = QApplication([])
    qt_app.setStyle("Fusion")
    window = MainWindow(Database(), load_config())
    window.showMaximized()
    qt_app.exec()


if __name__ == "__main__":
    main()
