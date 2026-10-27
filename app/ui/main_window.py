"""Janela principal com menu lateral e paginas em QStackedWidget."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QButtonGroup,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from app.config import APP_NAME, APP_VERSION
from app.storage.settings_store import SettingsStore
from app.ui.about_page import AboutPage
from app.ui.generators_page import GeneratorsPage
from app.ui.home_page import HomePage
from app.ui.projects_page import ProjectsPage
from app.ui.settings_page import SettingsPage

NAV_ITEMS = (
    ("home", "Início"),
    ("generators", "Geradores"),
    ("projects", "Meus projetos"),
    ("settings", "Configurações"),
    ("about", "Sobre"),
)


class MainWindow(QMainWindow):
    def __init__(self, store: SettingsStore | None = None) -> None:
        super().__init__()
        self._store = store or SettingsStore()
        self._settings = self._store.load()
        self.setWindowTitle(APP_NAME)
        self.resize(1100, 720)
        self.setMinimumSize(720, 480)

        central = QWidget()
        self.setCentralWidget(central)
        layout = QHBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        layout.addWidget(self._build_sidebar())

        self.stack = QStackedWidget()
        layout.addWidget(self.stack, 1)

        self._pages: dict[str, QWidget] = {
            "home": HomePage(self.navigate, self.open_generator),
            "generators": GeneratorsPage(
                export_dir_provider=lambda: self._settings.get("export_dir")),
            "projects": ProjectsPage(),
            "settings": SettingsPage(self._store, self._settings),
            "about": AboutPage(),
        }
        for key, _ in NAV_ITEMS:
            self.stack.addWidget(self._pages[key])
        self._pages["settings"].settings_saved.connect(self._on_settings_saved)

        self.navigate(self._initial_page())

    def _build_sidebar(self) -> QWidget:
        sidebar = QWidget()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(210)
        col = QVBoxLayout(sidebar)
        col.setContentsMargins(12, 18, 12, 14)
        col.setSpacing(4)

        brand = QLabel(APP_NAME)
        brand.setObjectName("brand")
        sub = QLabel("Corte a laser em MDF")
        sub.setObjectName("brandSub")
        col.addWidget(brand)
        col.addWidget(sub)
        col.addSpacing(18)

        self._nav_group = QButtonGroup(self)
        self._nav_group.setExclusive(True)
        self._nav_buttons: dict[str, QPushButton] = {}
        for key, label in NAV_ITEMS:
            button = QPushButton(label)
            button.setObjectName("navButton")
            button.setCheckable(True)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.clicked.connect(lambda _=False, k=key: self.navigate(k))
            self._nav_group.addButton(button)
            self._nav_buttons[key] = button
            col.addWidget(button)

        col.addStretch(1)
        version = QLabel(f"v{APP_VERSION}")
        version.setObjectName("brandSub")
        col.addWidget(version)
        return sidebar

    def _initial_page(self) -> str:
        pref = self._settings["startup_page"]
        page = self._settings["last_page"] if pref == "last" else pref
        return page if page in self._pages else "home"

    def navigate(self, key: str) -> None:
        """Mostra a página `key` reutilizando a instancia existente."""
        if key not in self._pages:
            return
        self.stack.setCurrentWidget(self._pages[key])
        self._nav_buttons[key].setChecked(True)
        self._remember_last_page(key)

    def open_generator(self, key: str) -> None:
        """Vai para Geradores e abre a página do gerador `key`."""
        self.navigate("generators")
        self._pages["generators"].open_generator(key)

    def current_page_key(self) -> str:
        current = self.stack.currentWidget()
        return next(k for k, w in self._pages.items() if w is current)

    def _remember_last_page(self, key: str) -> None:
        if key in ("about",) or key == self._settings.get("last_page"):
            return
        self._settings["last_page"] = key

    def _on_settings_saved(self, data: dict) -> None:
        self._settings = data

    def closeEvent(self, event) -> None:
        if self._settings["startup_page"] == "last":
            self._store.save(self._settings)
        super().closeEvent(event)
