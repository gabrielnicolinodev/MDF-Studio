"""Ponto de entrada do MDF Studio: `python main.py`."""
from __future__ import annotations

import logging
import sys

from PySide6.QtWidgets import QApplication

from app.config import APP_NAME, APP_VERSION, ORGANIZATION_NAME
from app.storage.settings_store import SettingsStore
from app.ui.main_window import MainWindow
from app.ui.theme import apply_dark_theme


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(APP_VERSION)
    app.setOrganizationName(ORGANIZATION_NAME)
    apply_dark_theme(app)

    window = MainWindow(SettingsStore())
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
