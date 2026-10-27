"""Gerador de caixas retangulares: orquestra validação, geometria e disposição."""
from __future__ import annotations

from dataclasses import dataclass

from app.core.box_geometry import BoxGeometry, build_box_geometry
from app.core.box_parameters import BoxParameters
from app.core.layout import LayoutParameters, PanelLayout, layout_panels
from app.core.validation import (
    GeometryError,
    Severity,
    ValidationIssue,
    has_errors,
    validate_parameters,
)


@dataclass(frozen=True)
class PanelSummary:
    label: str
    width: float
    height: float
    area: float


@dataclass(frozen=True)
class JointSummary:
    name: str
    finger_count: int
    finger_width: float


@dataclass(frozen=True)
class BoxSummary:
    external: tuple[float, float, float]
    internal: tuple[float, float, float]
    thickness: float
    panels: tuple[PanelSummary, ...]
    joints: tuple[JointSummary, ...]
    used_size: tuple[float, float]
    panels_area: float
    bbox_area: float
    workspace: tuple[float, float]
    kerf: float
    kerf_active: bool
    clearance: float


@dataclass(frozen=True)
class BoxResult:
    params: BoxParameters
    layout_params: LayoutParameters
    geometry: BoxGeometry | None
    layout: PanelLayout | None
    issues: tuple[ValidationIssue, ...]

    @property
    def ok(self) -> bool:
        return self.geometry is not None and self.layout is not None \
            and not has_errors(self.issues)


class BoxGenerator:
    key = "rect_box"
    name = "Caixa retangular"

    def generate(self, params: BoxParameters,
                 layout_params: LayoutParameters | None = None) -> BoxResult:
        lp = layout_params or LayoutParameters()
        problems = validate_parameters(params)
        if has_errors(problems):
            return BoxResult(params, lp, None, None, tuple(problems))
        try:
            geometry = build_box_geometry(params)
            layout = layout_panels(geometry, lp)
        except GeometryError as exc:
            return BoxResult(params, lp, None, None, (exc.issue,))
        issues = tuple(geometry.issues) + tuple(layout.issues)
        return BoxResult(params, lp, geometry, layout, issues)

    @staticmethod
    def summarize(result: BoxResult) -> BoxSummary:
        if not result.ok:
            raise ValueError("Não há resumo para um projeto com erros.")
        g, lay = result.geometry, result.layout
        d = g.dimensions
        panels = tuple(PanelSummary(p.label, p.width, p.height, p.contour.area())
                       for p in g.panels)
        return BoxSummary(
            external=(d.ext_width, d.ext_depth, d.ext_height),
            internal=(d.int_width, d.int_depth, d.int_height),
            thickness=d.thickness,
            panels=panels,
            joints=tuple(JointSummary(j.name, j.finger_count, j.finger_width)
                         for j in g.joints),
            used_size=(lay.used_width, lay.used_height),
            panels_area=sum(p.area for p in panels),
            bbox_area=lay.used_width * lay.used_height,
            workspace=(lay.params.workspace_width, lay.params.workspace_height),
            kerf=result.params.kerf,
            kerf_active=g.kerf_active,
            clearance=result.params.clearance,
        )
