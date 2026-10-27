"""Gerador da caixa com tampa deslizante: validação, geometria e disposição.

Reutiliza `BoxResult`, `layout_panels` e o exportador SVG sem alterá-los.
"""
from __future__ import annotations

from dataclasses import dataclass

from app.core.layout import LayoutParameters, layout_panels
from app.core.sliding_box import (
    SlidingLidBoxParameters,
    build_sliding_box_geometry,
    validate_sliding_parameters,
)
from app.core.validation import GeometryError, has_errors
from app.generators.box_generator import BoxGenerator, BoxResult, BoxSummary


@dataclass(frozen=True)
class SlidingBoxSummary(BoxSummary):
    front_height: float
    channel_height: float
    rail_height: float
    stop_width: float
    lid_size: tuple[float, float]      # largura x comprimento da parte central
    lid_clearance: float
    open_gap_at_back: float            # abertura que sobra com a tampa fechada (0 = fechada)


class SlidingLidBoxGenerator:
    key = "sliding_lid_box"
    name = "Caixa com tampa deslizante"

    def generate(self, params: SlidingLidBoxParameters,
                 layout_params: LayoutParameters | None = None) -> BoxResult:
        lp = layout_params or LayoutParameters()
        problems = validate_sliding_parameters(params)
        if has_errors(problems):
            return BoxResult(params, lp, None, None, tuple(problems))
        try:
            geometry = build_sliding_box_geometry(params)
            layout = layout_panels(geometry, lp)
        except GeometryError as exc:
            return BoxResult(params, lp, None, None, (exc.issue,))
        return BoxResult(params, lp, geometry, layout,
                         tuple(geometry.issues) + tuple(layout.issues))

    @staticmethod
    def summarize(result: BoxResult) -> SlidingBoxSummary:
        base = BoxGenerator.summarize(result)      # painéis, juntas, disposição, kerf
        d = result.geometry.dimensions
        fields = {name: getattr(base, name) for name in base.__dataclass_fields__}
        fields.update(
            external=(d.ext_width, d.ext_depth, d.ext_height),
            internal=(d.int_width, d.int_depth, d.int_height))
        return SlidingBoxSummary(
            **fields, front_height=d.front_height, channel_height=d.channel_height,
            rail_height=d.rail_height, stop_width=d.stop_width,
            lid_size=(d.lid_width, d.lid_length), lid_clearance=d.lid_clearance,
            open_gap_at_back=max(0.0, d.lid_max_length - d.lid_length))
