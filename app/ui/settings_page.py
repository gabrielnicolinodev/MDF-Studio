"""Página de configuracoes."""
from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
)

from app import config
from app.storage.settings_store import SettingsStore
from app.ui.widgets import BasePage

_STARTUP_CHOICES = ("home", "generators", "projects", "settings", "last")


class SettingsPage(BasePage):
    settings_saved = Signal(dict)

    def __init__(self, store: SettingsStore, settings: dict, parent=None) -> None:
        super().__init__("Configurações",
                         "Preferências salvas localmente neste computador.", parent)
        self._store = store
        self._settings = dict(settings)

        card = QFrame()
        card.setObjectName("card")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(20, 18, 20, 18)
        form = QFormLayout()
        form.setSpacing(14)
        card_layout.addLayout(form)

        self.unit_combo = QComboBox()
        for key in config.VALID_UNITS:
            self.unit_combo.addItem(config.UNIT_LABELS[key], key)
        form.addRow("Unidade padrão", self.unit_combo)

        self.theme_combo = QComboBox()
        for key in config.VALID_THEMES:
            self.theme_combo.addItem(config.THEME_LABELS[key], key)
        form.addRow("Tema", self.theme_combo)

        self.export_edit = QLineEdit()
        browse = QPushButton("Escolher...")
        browse.clicked.connect(self._browse)
        row = QHBoxLayout()
        row.addWidget(self.export_edit, 1)
        row.addWidget(browse)
        form.addRow("Pasta de exportação", row)

        self.startup_combo = QComboBox()
        for key in _STARTUP_CHOICES:
            self.startup_combo.addItem(config.STARTUP_LABELS[key], key)
        form.addRow("Ao abrir o MDF Studio", self.startup_combo)

        hint = QLabel("Esta preferência afeta só a página inicial deste "
                      "aplicativo; não altera a inicialização do sistema.")
        hint.setObjectName("cardText")
        hint.setWordWrap(True)
        card_layout.addWidget(hint)
        self.body.addWidget(card)

        buttons = QHBoxLayout()
        self.save_button = QPushButton("Salvar")
        self.save_button.setObjectName("primary")
        self.save_button.clicked.connect(self.save)
        restore = QPushButton("Restaurar padrões")
        restore.clicked.connect(self._restore_defaults)
        buttons.addWidget(self.save_button)
        buttons.addWidget(restore)
        buttons.addStretch(1)
        self.body.addLayout(buttons)

        self.status = QLabel("")
        self.status.setWordWrap(True)
        self.body.addWidget(self.status)
        self.body.addStretch(1)

        self._load_into_form(self._settings)

    def _load_into_form(self, settings: dict) -> None:
        self.unit_combo.setCurrentIndex(max(0, self.unit_combo.findData(settings["unit"])))
        self.theme_combo.setCurrentIndex(max(0, self.theme_combo.findData(settings["theme"])))
        self.export_edit.setText(settings["export_dir"])
        self.startup_combo.setCurrentIndex(
            max(0, self.startup_combo.findData(settings["startup_page"])))

    def _browse(self) -> None:
        start = self.export_edit.text() or config.default_export_dir()
        chosen = QFileDialog.getExistingDirectory(self, "Pasta de exportação", start)
        if chosen:
            self.export_edit.setText(chosen)

    def _restore_defaults(self) -> None:
        defaults = config.default_settings()
        defaults["last_page"] = self._settings.get("last_page", "home")
        self._load_into_form(defaults)
        self._set_status("Padrões carregados. Clique em Salvar para aplicar.", ok=True)

    def collect(self) -> dict:
        data = dict(self._settings)
        data["unit"] = self.unit_combo.currentData()
        data["theme"] = self.theme_combo.currentData()
        data["export_dir"] = self.export_edit.text().strip() or config.default_export_dir()
        data["startup_page"] = self.startup_combo.currentData()
        return config.sanitize_settings(data)

    def save(self) -> bool:
        data = self.collect()
        if self._store.save(data):
            self._settings = data
            self.settings_saved.emit(data)
            self._set_status(f"Configurações salvas em {self._store.path}", ok=True)
            return True
        self._set_status("Não foi possivel salvar as configuracoes "
                         "(verifique permissões de escrita).", ok=False)
        return False

    def _set_status(self, text: str, ok: bool) -> None:
        self.status.setObjectName("statusOk" if ok else "statusError")
        self.status.style().unpolish(self.status)
        self.status.style().polish(self.status)
        self.status.setText(text)
