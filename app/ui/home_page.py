"""Página inicial."""
from __future__ import annotations

from PySide6.QtWidgets import QLabel

from app.config import APP_DESCRIPTION, APP_NAME
from app.ui.generators_catalog import PLANNED_GENERATORS
from app.ui.widgets import BasePage, Card, ReflowGrid


class HomePage(BasePage):
    def __init__(self, navigate, open_generator=None, parent=None) -> None:
        super().__init__(APP_NAME, APP_DESCRIPTION, parent)

        local = QLabel("Funciona 100% localmente: sem internet, contas ou nuvem.")
        local.setObjectName("statusOk")
        self.body.addWidget(local)

        actions = ReflowGrid(min_card_width=240)
        actions.add(Card("Criar novo projeto",
                         "Escolha um gerador para começar. Os demais módulos "
                         "estão em desenvolvimento.",
                         on_click=lambda: navigate("generators")))
        actions.add(Card("Meus projetos",
                         "Futura biblioteca de projetos salvos.",
                         on_click=lambda: navigate("projects")))
        actions.add(Card("Configurações",
                         "Unidade, tema e pasta de exportação.",
                         on_click=lambda: navigate("settings")))
        self.body.addWidget(actions)

        self.add_section_title("Geradores disponíveis")
        ready = sum(1 for g in PLANNED_GENERATORS if g.available)
        noun = "gerador disponível" if ready == 1 else "geradores disponíveis"
        note = QLabel(f"{ready} {noun}; os demais módulos estão "
                      "planejados para as próximas etapas.")
        note.setObjectName("pageSubtitle")
        note.setWordWrap(True)
        self.body.addWidget(note)

        grid = ReflowGrid(min_card_width=240)
        for gen in PLANNED_GENERATORS:
            if gen.available and open_generator is not None:
                grid.add(Card(gen.name, gen.description, badge="Disponível", badge_ok=True,
                              on_click=lambda k=gen.key: open_generator(k)))
            else:
                grid.add(Card(gen.name, gen.description, badge="Em desenvolvimento"))
        self.body.addWidget(grid)
        self.body.addStretch(1)
