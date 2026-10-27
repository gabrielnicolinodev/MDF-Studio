"""Página Meus projetos (placeholder honesto, sem dados ficticios)."""
from __future__ import annotations

from app.ui.widgets import BasePage, Card


class ProjectsPage(BasePage):
    def __init__(self, parent=None) -> None:
        super().__init__("Meus projetos",
                         "Biblioteca dos seus projetos salvos.", parent)
        self.body.addWidget(Card(
            "Nenhum projeto ainda",
            "Os projetos paramétricos serão implementados em uma próxima "
            "etapa. Quando existirem, eles aparecerao aqui.",
        ))
        self.body.addStretch(1)
