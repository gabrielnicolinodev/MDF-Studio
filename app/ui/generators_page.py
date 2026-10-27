"""Página de geradores: catálogo + página de cada gerador disponível."""
from __future__ import annotations

from PySide6.QtWidgets import QStackedWidget, QVBoxLayout, QWidget

from app.ui.box_generator_page import BoxGeneratorPage
from app.ui.generators_catalog import PLANNED_GENERATORS
from app.ui.widgets import BasePage, Card, ReflowGrid


class GeneratorsCatalogPage(BasePage):
    def __init__(self, open_generator, parent=None) -> None:
        super().__init__(
            "Geradores",
            "Escolha um gerador. Os módulos marcados como “Em desenvolvimento” "
            "ainda não estão funcionais.",
            parent,
        )
        grid = ReflowGrid(min_card_width=260)
        for gen in PLANNED_GENERATORS:
            if gen.available:
                grid.add(Card(gen.name, gen.description, badge="Disponível", badge_ok=True,
                              on_click=lambda k=gen.key: open_generator(k)))
            else:
                grid.add(Card(gen.name, gen.description, badge="Em desenvolvimento"))
        self.body.addWidget(grid)
        self.body.addStretch(1)


class GeneratorsPage(QWidget):
    """Contém o catálogo e as páginas dos geradores sem criar páginas extras no menu."""

    def __init__(self, export_dir_provider=None, parent=None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.stack = QStackedWidget()
        layout.addWidget(self.stack)

        self.catalog = GeneratorsCatalogPage(self.open_generator)
        self.box_page = BoxGeneratorPage(export_dir_provider=export_dir_provider)
        self.box_page.back_requested.connect(self.show_catalog)
        self.stack.addWidget(self.catalog)
        self.stack.addWidget(self.box_page)
        self._pages = {"rect_box": self.box_page}

    def open_generator(self, key: str) -> None:
        page = self._pages.get(key)
        if page is not None:
            self.stack.setCurrentWidget(page)

    def show_catalog(self) -> None:
        self.stack.setCurrentWidget(self.catalog)

    def current_generator_key(self) -> str | None:
        current = self.stack.currentWidget()
        return next((k for k, w in self._pages.items() if w is current), None)
