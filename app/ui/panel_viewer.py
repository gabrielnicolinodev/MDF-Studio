"""Visualização 2D das peças. Desenha EXATAMENTE os contornos do PanelLayout."""
from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QPainter, QPen, QPolygonF
from PySide6.QtWidgets import QWidget

from app.core.layout import PanelLayout
from app.ui import theme


def _fmt(value: float) -> str:
    return f"{value:.1f}".replace(".", ",")


class PanelViewer(QWidget):
    """Mostra a disposição. Roda do mouse = zoom; arrastar = mover."""

    MIN_ZOOM, MAX_ZOOM = 0.2, 20.0

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setMinimumSize(170, 160)
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        self._layout: PanelLayout | None = None
        self._show_reference = True
        self._zoom = 1.0
        self._pan = QPointF(0, 0)
        self._drag_from: QPointF | None = None

    # --- API pública -----------------------------------------------------
    def set_layout(self, layout: PanelLayout | None) -> None:
        self._layout = layout
        self.fit()

    def set_show_reference(self, show: bool) -> None:
        self._show_reference = show
        self.update()

    def fit(self) -> None:
        self._zoom, self._pan = 1.0, QPointF(0, 0)
        self.update()

    def zoom_in(self) -> None:
        self._set_zoom(self._zoom * 1.25)

    def zoom_out(self) -> None:
        self._set_zoom(self._zoom / 1.25)

    @property
    def zoom(self) -> float:
        return self._zoom

    @property
    def layout_data(self) -> PanelLayout | None:
        return self._layout

    # --- interação -------------------------------------------------------
    def _set_zoom(self, value: float) -> None:
        self._zoom = max(self.MIN_ZOOM, min(self.MAX_ZOOM, value))
        self.update()

    def wheelEvent(self, event) -> None:
        self._set_zoom(self._zoom * (1.15 if event.angleDelta().y() > 0 else 1 / 1.15))

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_from = event.position()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)

    def mouseMoveEvent(self, event) -> None:
        if self._drag_from is not None:
            self._pan += event.position() - self._drag_from
            self._drag_from = event.position()
            self.update()

    def mouseReleaseEvent(self, event) -> None:
        self._drag_from = None
        self.setCursor(Qt.CursorShape.OpenHandCursor)

    # --- desenho ---------------------------------------------------------
    def _transform(self):
        """(escala, origem x, origem y): ajusta o conjunto usado à área, mantendo proporção."""
        x0, y0, x1, y1 = self._layout.used_bbox
        pad = 28
        avail_w, avail_h = max(1, self.width() - 2 * pad), max(1, self.height() - 2 * pad)
        w, h = max(x1 - x0, 1e-6), max(y1 - y0, 1e-6)
        scale = min(avail_w / w, avail_h / h) * self._zoom
        ox = self.width() / 2 + self._pan.x() - scale * (x0 + x1) / 2
        oy = self.height() / 2 + self._pan.y() - scale * (y0 + y1) / 2
        return scale, ox, oy

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor(theme.SIDEBAR))
        if self._layout is None:
            painter.setPen(QColor(theme.TEXT_MUTED))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter,
                             "Preencha os parâmetros e clique em “Gerar projeto”.")
            return

        scale, ox, oy = self._transform()
        lp = self._layout.params

        def pt(p):
            return QPointF(ox + scale * p[0], oy + scale * p[1])

        # Área de trabalho (referência; NÃO é a chapa de MDF).
        painter.setPen(QPen(QColor(theme.CARD_BORDER), 1, Qt.PenStyle.DashLine))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(QRectF(pt((0, 0)), pt((lp.workspace_width, lp.workspace_height))))
        painter.setPen(QColor(theme.TEXT_MUTED))
        painter.drawText(pt((0, 0)) + QPointF(4, -4),
                         f"Área de trabalho {_fmt(lp.workspace_width)} × "
                         f"{_fmt(lp.workspace_height)} mm (não é a chapa)")

        for placed in self._layout.placed:
            poly = QPolygonF([pt(p) for p in placed.contour.points])
            painter.setPen(QPen(QColor(theme.ACCENT), 1.6))
            painter.setBrush(QBrush(QColor(36, 48, 68, 235)))
            painter.drawPolygon(poly)

            if placed.cut_path != placed.contour:  # kerf ativo: mostra o caminho de corte
                painter.setPen(QPen(QColor("#f59e0b"), 1, Qt.PenStyle.DotLine))
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawPolygon(QPolygonF([pt(p) for p in placed.cut_path.points]))

            if self._show_reference:
                painter.setPen(QPen(QColor("#6b7280"), 1, Qt.PenStyle.DashLine))
                for a, b in placed.reference_lines:
                    painter.drawLine(pt(a), pt(b))

            x0, y0, x1, y1 = placed.bbox
            top_left, bottom_right = pt((x0, y0)), pt((x1, y1))
            box = QRectF(top_left, bottom_right)
            if box.width() > 70 and box.height() > 34:
                painter.setPen(QColor(theme.TEXT))
                painter.drawText(box, Qt.AlignmentFlag.AlignCenter,
                                 f"{placed.label}\n{_fmt(placed.width)} × {_fmt(placed.height)} mm")
            elif box.width() > 24 and box.height() > 12:
                painter.setPen(QColor(theme.TEXT))
                painter.drawText(box, Qt.AlignmentFlag.AlignCenter, placed.label.split()[0])
