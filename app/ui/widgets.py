"""Widgets reutilizaveis da interface."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)


class Card(QFrame):
    """Cartao com titulo, texto e selo opcional. Clicavel se `on_click` for dado."""

    def __init__(self, title: str, text: str, badge: str | None = None,
                 badge_ok: bool = False, on_click=None, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("card")
        self._on_click = on_click
        self.setProperty("interactive", on_click is not None)
        if on_click is not None:
            self.setCursor(Qt.CursorShape.PointingHandCursor)
            self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(8)

        title_label = QLabel(title)
        title_label.setObjectName("cardTitle")
        title_label.setWordWrap(True)
        layout.addWidget(title_label)

        body = QLabel(text)
        body.setObjectName("cardText")
        body.setWordWrap(True)
        layout.addWidget(body)
        layout.addStretch(1)

        if badge:
            badge_label = QLabel(badge)
            badge_label.setObjectName("badgeOk" if badge_ok else "badge")
            layout.addWidget(badge_label, 0, Qt.AlignmentFlag.AlignLeft)

    def mouseReleaseEvent(self, event) -> None:
        if self._on_click and event.button() == Qt.MouseButton.LeftButton:
            self._on_click()
        super().mouseReleaseEvent(event)

    def keyPressEvent(self, event) -> None:
        if self._on_click and event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space):
            self._on_click()
            return
        super().keyPressEvent(event)


class ReflowGrid(QWidget):
    """Grade de cards que reorganiza o numero de colunas ao redimensionar."""

    def __init__(self, min_card_width: int = 260, parent=None) -> None:
        super().__init__(parent)
        self._min_width = min_card_width
        self._items: list[QWidget] = []
        self._columns = 0
        self._grid = QGridLayout(self)
        self._grid.setContentsMargins(0, 0, 0, 0)
        self._grid.setSpacing(14)

    def add(self, widget: QWidget) -> None:
        self._items.append(widget)
        self._relayout(force=True)

    def _relayout(self, force: bool = False) -> None:
        columns = max(1, self.width() // (self._min_width + self._grid.horizontalSpacing()))
        columns = min(columns, max(1, len(self._items)))
        if columns == self._columns and not force:
            return
        self._columns = columns
        for widget in self._items:
            self._grid.removeWidget(widget)
        for index, widget in enumerate(self._items):
            self._grid.addWidget(widget, index // columns, index % columns)
        for col in range(self._grid.columnCount()):
            self._grid.setColumnStretch(col, 1 if col < columns else 0)
        self._grid.invalidate()
        self.updateGeometry()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._relayout()


class BasePage(QScrollArea):
    """Página rolavel com titulo e subtitulo; conteudo vai em `self.body`."""

    def __init__(self, title: str, subtitle: str = "", parent=None) -> None:
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        root = QWidget()
        root.setObjectName("pageRoot")
        self.setWidget(root)
        self.body = QVBoxLayout(root)
        self.body.setContentsMargins(32, 28, 32, 28)
        self.body.setSpacing(16)

        title_label = QLabel(title)
        title_label.setObjectName("pageTitle")
        self.body.addWidget(title_label)
        if subtitle:
            sub = QLabel(subtitle)
            sub.setObjectName("pageSubtitle")
            sub.setWordWrap(True)
            self.body.addWidget(sub)

    def add_section_title(self, text: str) -> None:
        label = QLabel(text)
        label.setObjectName("sectionTitle")
        self.body.addWidget(label)
