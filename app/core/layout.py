"""Disposição inicial das peças numa área de trabalho 2D (sem Qt).

Coordenadas da área de trabalho: milímetros, origem no canto SUPERIOR
ESQUERDO, x para a direita e y para BAIXO (mesma convenção do SVG, para a
Etapa 03). A área de trabalho NÃO é a chapa de MDF real: o tamanho padrão
(410 x 400 mm) é apenas uma referência configurável.

Transformação local -> trabalho: x = x0 + (u - u_min), y = y0 + (v_max - v),
onde (u_min, v_max) vêm do caixa-limite do `cut_path`. A ordem dos vértices é
preservada, então o contorno continua anti-horário quando visto na tela.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

from app.core.box_geometry import BoxGeometry, Edge, PanelId
from app.core.geometry import EPS, Contour, Point, snap
from app.core.validation import Severity, ValidationIssue

LAYOUT_LIMITS = {
    "spacing": (1.0, 50.0),
    "workspace_width": (50.0, 5000.0),
    "workspace_height": (50.0, 5000.0),
}
LAYOUT_LABELS = {
    "spacing": "Espaçamento entre peças",
    "workspace_width": "Largura da área de trabalho",
    "workspace_height": "Altura da área de trabalho",
}


@dataclass(frozen=True)
class LayoutParameters:
    spacing: float = 5.0
    workspace_width: float = 410.0
    workspace_height: float = 400.0


def validate_layout_parameters(lp: LayoutParameters) -> list[ValidationIssue]:
    out = []
    for name, (lo, hi) in LAYOUT_LIMITS.items():
        value = getattr(lp, name)
        label = LAYOUT_LABELS[name]
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            out.append(ValidationIssue(Severity.ERROR, name,
                                       f"{label}: informe um número finito."))
        elif value < lo or value > hi:
            out.append(ValidationIssue(Severity.ERROR, name,
                                       f"{label}: deve estar entre {lo:g} e {hi:g} mm."))
    return out


@dataclass(frozen=True)
class PlacedPanel:
    id: PanelId
    label: str
    width: float
    height: float
    contour: Contour        # nominal, em coordenadas da área de trabalho
    cut_path: Contour       # caminho de corte (kerf aplicado, se houver)
    bbox: tuple[float, float, float, float]  # do cut_path: x0, y0, x1, y1
    reference_lines: tuple[tuple[Point, Point], ...]  # só visualização, nunca no corte


@dataclass(frozen=True)
class PanelLayout:
    placed: tuple[PlacedPanel, ...]
    params: LayoutParameters
    used_bbox: tuple[float, float, float, float]
    fits: bool
    issues: tuple[ValidationIssue, ...]

    @property
    def used_width(self) -> float:
        return self.used_bbox[2] - self.used_bbox[0]

    @property
    def used_height(self) -> float:
        return self.used_bbox[3] - self.used_bbox[1]


def layout_panels(geometry: BoxGeometry, lp: LayoutParameters) -> PanelLayout:
    """Disposição em prateleiras (shelf), determinística.

    Ordena por altura decrescente (empate: ordem canônica dos painéis), preenche
    linhas da esquerda para a direita e quebra linha quando falta largura.
    Usa o caixa-limite do `cut_path`, portanto o espaçamento vale também com kerf.
    """
    errors = validate_layout_parameters(lp)
    if errors:
        from app.core.validation import GeometryError
        raise GeometryError(errors[0].message, field=errors[0].field)

    margin = lp.spacing
    items = []
    for index, panel in enumerate(geometry.panels):
        bx0, by0, bx1, by1 = panel.cut_path.bbox()
        items.append((-(by1 - by0), index, panel, (bx0, by0, bx1, by1)))
    items.sort(key=lambda it: (it[0], it[1]))

    x = y = margin
    row_h = 0.0
    placed = []
    for _, _, panel, (bx0, by0, bx1, by1) in items:
        w, h = bx1 - bx0, by1 - by0
        if x > margin + EPS and x + w > lp.workspace_width - margin + EPS:
            x = margin
            y += row_h + lp.spacing
            row_h = 0.0

        def to_ws(pt, _x=x, _y=y, _bx0=bx0, _by1=by1):
            return Point(snap(_x + (pt[0] - _bx0)), snap(_y + (_by1 - pt[1])))

        contour = panel.contour.map_points(to_ws)
        cut = panel.cut_path.map_points(to_ws)
        refs = _reference_lines(panel, to_ws)
        placed.append(PlacedPanel(panel.id, panel.label, panel.width, panel.height,
                                  contour, cut,
                                  (snap(x), snap(y), snap(x + w), snap(y + h)), refs))
        x += w + lp.spacing
        row_h = max(row_h, h)

    placed.sort(key=lambda p: [q.id for q in geometry.panels].index(p.id))
    used = (min(p.bbox[0] for p in placed), min(p.bbox[1] for p in placed),
            max(p.bbox[2] for p in placed), max(p.bbox[3] for p in placed))
    fits = all(p.bbox[2] <= lp.workspace_width - margin + EPS
               and p.bbox[3] <= lp.workspace_height - margin + EPS for p in placed)
    issues = []
    if not fits:
        issues.append(ValidationIssue(
            Severity.ERROR, "workspace",
            f"As peças não cabem na área de trabalho de {lp.workspace_width:g} × "
            f"{lp.workspace_height:g} mm com espaçamento de {lp.spacing:g} mm "
            f"(o conjunto ocupa {used[2] - used[0]:.1f} × {used[3] - used[1]:.1f} mm). "
            "Aumente a área de trabalho, reduza o espaçamento ou diminua a caixa."))
    return PanelLayout(tuple(placed), lp, tuple(snap(v) for v in used), fits, tuple(issues))


def _reference_lines(panel, to_ws):
    """Retângulo externo e linhas de base dos recortes (apenas visualização)."""
    w, h, t = panel.width, panel.height, panel.thickness
    corners = [(0, 0), (w, 0), (w, h), (0, h)]
    lines = [(to_ws(corners[i]), to_ws(corners[(i + 1) % 4])) for i in range(4)]
    for edge in panel.joint_edges:
        if edge is Edge.BOTTOM:
            a, b = (0, t), (w, t)
        elif edge is Edge.TOP:
            a, b = (0, h - t), (w, h - t)
        elif edge is Edge.LEFT:
            a, b = (t, 0), (t, h)
        else:
            a, b = (w - t, 0), (w - t, h)
        lines.append((to_ws(a), to_ws(b)))
    return tuple(lines)
