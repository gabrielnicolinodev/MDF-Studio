import itertools

import pytest

from app.core.box_geometry import build_box_geometry
from app.core.box_parameters import BoxParameters, BoxType
from app.core.layout import LayoutParameters, layout_panels
from app.core.validation import GeometryError, Severity

EPS = 1e-6


def lay(params=None, **lp):
    g = build_box_geometry(params or BoxParameters())
    return g, layout_panels(g, LayoutParameters(**lp))


def separated(a, b, spacing):
    ax0, ay0, ax1, ay1 = a
    bx0, by0, bx1, by1 = b
    return (ax1 + spacing <= bx0 + EPS or bx1 + spacing <= ax0 + EPS
            or ay1 + spacing <= by0 + EPS or by1 + spacing <= ay0 + EPS)


@pytest.mark.parametrize("spacing", [1.0, 5.0, 12.5])
@pytest.mark.parametrize("params", [BoxParameters(), BoxParameters(box_type=BoxType.OPEN),
                                    BoxParameters(width=60, depth=60, height=40, kerf=0.2)])
def test_no_overlaps_and_minimum_spacing_respected(spacing, params):
    _, layout = lay(params, spacing=spacing)
    assert layout.fits
    for a, b in itertools.combinations(layout.placed, 2):
        assert separated(a.bbox, b.bbox, spacing), (a.label, b.label)


def test_all_panels_inside_workspace():
    _, layout = lay(workspace_width=410, workspace_height=400)
    lp = layout.params
    for p in layout.placed:
        x0, y0, x1, y1 = p.bbox
        assert x0 >= lp.spacing - EPS and y0 >= lp.spacing - EPS
        assert x1 <= lp.workspace_width - lp.spacing + EPS
        assert y1 <= lp.workspace_height - lp.spacing + EPS


def test_every_contour_lies_inside_its_bbox():
    _, layout = lay(BoxParameters(kerf=0.2))
    for p in layout.placed:
        x0, y0, x1, y1 = p.bbox
        for c in (p.contour, p.cut_path):
            cx0, cy0, cx1, cy1 = c.bbox()
            assert cx0 >= x0 - EPS and cy0 >= y0 - EPS and cx1 <= x1 + EPS and cy1 <= y1 + EPS


def test_layout_is_deterministic_and_keeps_panel_shape():
    g, l1 = lay()
    _, l2 = lay()
    assert l1 == l2
    for placed, panel in zip(l1.placed, g.panels):
        assert placed.contour.area() == pytest.approx(panel.contour.area())  # só translada/espelha eixo
        assert (placed.width, placed.height) == (panel.width, panel.height)


def test_used_dimensions_match_union_of_placed_panels():
    _, layout = lay()
    x0 = min(p.bbox[0] for p in layout.placed); x1 = max(p.bbox[2] for p in layout.placed)
    y0 = min(p.bbox[1] for p in layout.placed); y1 = max(p.bbox[3] for p in layout.placed)
    assert layout.used_width == pytest.approx(x1 - x0)
    assert layout.used_height == pytest.approx(y1 - y0)


def test_workspace_too_small_is_reported_as_error():
    _, layout = lay(workspace_width=120, workspace_height=100)
    assert not layout.fits
    assert any(i.severity is Severity.ERROR and "não cabem" in i.message for i in layout.issues)


def test_reference_lines_are_separate_from_cut_geometry():
    _, layout = lay()
    for p in layout.placed:
        assert len(p.reference_lines) >= 4
        cut_pts = set(p.cut_path.points)
        # linhas de referência existem apenas como dados de visualização
        assert not hasattr(p.cut_path, "reference_lines")
        assert all(len(set(line)) == 2 for line in p.reference_lines)


@pytest.mark.parametrize("bad", [dict(spacing=0), dict(spacing=-1), dict(spacing=float("nan")),
                                 dict(workspace_width=float("inf")), dict(workspace_height=10)])
def test_invalid_layout_parameters_rejected(bad):
    with pytest.raises(GeometryError):
        lay(**bad)


def test_large_box_still_lays_out_inside_a_large_workspace():
    p = BoxParameters(width=400, depth=300, height=200, thickness=6)
    _, layout = lay(p, workspace_width=1500, workspace_height=1500)
    assert layout.fits
    for a, b in itertools.combinations(layout.placed, 2):
        assert separated(a.bbox, b.bbox, 5.0)
