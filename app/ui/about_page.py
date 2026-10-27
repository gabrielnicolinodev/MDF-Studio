"""Página Sobre."""
from __future__ import annotations

from app.config import APP_DESCRIPTION, APP_NAME, APP_VERSION
from app.ui.widgets import BasePage, Card


class AboutPage(BasePage):
    def __init__(self, parent=None) -> None:
        super().__init__("Sobre", parent=parent)
        self.body.addWidget(Card(
            f"{APP_NAME} - versão {APP_VERSION}",
            APP_DESCRIPTION + "\n\nEtapa 01: fundação da aplicação.",
        ))
        self.body.addStretch(1)
