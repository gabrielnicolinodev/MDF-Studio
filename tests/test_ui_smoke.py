import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication

from app.storage.settings_store import SettingsStore
from app.ui.main_window import NAV_ITEMS, MainWindow
from app.ui.theme import apply_dark_theme


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    apply_dark_theme(app)
    return app


def test_navigation_reaches_every_page(qapp, tmp_path):
    win = MainWindow(SettingsStore(tmp_path / "s.json"))
    win.show()
    for key, _ in NAV_ITEMS:
        win._nav_buttons[key].click()
        assert win.current_page_key() == key
    assert win.stack.count() == len(NAV_ITEMS)  # sem paginas duplicadas


def test_resize_does_not_fail(qapp, tmp_path):
    win = MainWindow(SettingsStore(tmp_path / "s.json"))
    win.show()
    for w, h in ((720, 480), (1400, 900), (900, 600)):
        win.resize(w, h)
        qapp.processEvents()


def test_settings_page_persists(qapp, tmp_path):
    store = SettingsStore(tmp_path / "s.json")
    win = MainWindow(store)
    page = win._pages["settings"]
    page.export_edit.setText(str(tmp_path / "saida"))
    idx = page.startup_combo.findData("generators")
    page.startup_combo.setCurrentIndex(idx)
    assert page.save() is True
    reloaded = store.load()
    assert reloaded["export_dir"] == str(tmp_path / "saida")
    assert reloaded["startup_page"] == "generators"
    assert MainWindow(store).current_page_key() == "generators"
