import itertools
import random

import pytest

from app.core.assembly import owners_at
from app.core.box_geometry import (
    PanelId, build_box_geometry, compute_dimensions,
)
from app.core.box_parameters import BoxParameters, BoxType, DimensionMode


def geom(**kw):
    return build_box_geometry(BoxParameters(**kw))


def test_closed_box_has_six_panels():
    g = geom(box_type=BoxType.CLOSED)
    assert [p.id for p in g.panels] == [PanelId.BASE, PanelId.TOP, PanelId.FRONT,
                                        PanelId.BACK, PanelId.LEFT, PanelId.RIGHT]


def test_open_box_has_five_panels_without_top():
    g = geom(box_type=BoxType.OPEN)
    assert len(g.panels) == 5
    assert PanelId.TOP not in [p.id for p in g.panels]


def test_external_dimensions_are_the_requested_ones():
    d = compute_dimensions(BoxParameters(width=120, depth=90, height=60, thickness=4))
    assert (d.ext_width, d.ext_depth, d.ext_height) == (120, 90, 60)
    assert (d.int_width, d.int_depth, d.int_height) == (112, 82, 52)  # fechada: -2t em z


def test_internal_dimensions_are_the_requested_ones():
    p = BoxParameters(width=100, depth=80, height=40, thickness=3,
                      dimension_mode=DimensionMode.INTERNAL)
    d = compute_dimensions(p)
    assert (d.int_width, d.int_depth, d.int_height) == (100, 80, 40)
    assert (d.ext_width, d.ext_depth, d.ext_height) == (106, 86, 46)


def test_open_box_internal_height_loses_only_one_thickness():
    d = compute_dimensions(BoxParameters(height=50, thickness=3, box_type=BoxType.OPEN))
    assert d.int_height == 47
    d2 = compute_dimensions(BoxParameters(height=50, thickness=3, box_type=BoxType.OPEN,
                                          dimension_mode=DimensionMode.INTERNAL))
    assert d2.ext_height == 53


@pytest.mark.parametrize("t", [2.0, 3.0, 4.5, 6.0])
def test_panel_rectangles_and_bounding_boxes(t):
    g = geom(width=150, depth=110, height=70, thickness=t)
    expected = {PanelId.BASE: (150, 110), PanelId.TOP: (150, 110),
                PanelId.FRONT: (150, 70), PanelId.BACK: (150, 70),
                PanelId.LEFT: (110, 70), PanelId.RIGHT: (110, 70)}
    for p in g.panels:
        w, h = expected[p.id]
        assert (p.width, p.height, p.thickness) == (w, h, t)
        assert p.contour.bbox() == (0.0, 0.0, w, h)  # recortes tocam a borda: caixa = retângulo


def test_contours_are_closed_ccw_without_zero_length_segments():
    for kwargs in (dict(), dict(box_type=BoxType.OPEN), dict(finger_count=5),
                   dict(clearance=0.2, kerf=0.1)):
        for p in geom(**kwargs).panels:
            for c in (p.contour, p.cut_path):
                assert c.problems() == []
                assert c.signed_area() > 0
                pts = c.points
                assert len(set(pts)) == len(pts)            # sem vértices repetidos
                for a, b in c.segments():                    # só arestas ortogonais
                    assert a.x == b.x or a.y == b.y


def test_no_consecutive_collinear_vertices():
    for p in geom().panels:
        pts = p.contour.points
        n = len(pts)
        for i in range(n):
            a, b, c = pts[i - 1], pts[i], pts[(i + 1) % n]
            assert (b.x - a.x) * (c.y - b.y) - (b.y - a.y) * (c.x - b.x) != 0


def test_geometry_is_deterministic():
    p = BoxParameters(width=133.3, depth=77.7, height=41.1, thickness=3.2,
                      clearance=0.15, kerf=0.12)
    assert build_box_geometry(p) == build_box_geometry(p)


def test_material_area_is_conserved_by_joints_without_clearance():
    # Cada recorte de um painel é preenchido por um dente do vizinho: com folga 0
    # o volume total das peças é exatamente o da casca.
    g = geom(width=100, depth=80, height=50, thickness=3)
    d = g.dimensions
    shell = (d.ext_width * d.ext_depth * d.ext_height
             - d.int_width * d.int_depth * d.int_height)
    assert sum(p.contour.area() * p.thickness for p in g.panels) == pytest.approx(shell, rel=1e-9)


def test_open_box_volume_matches_open_shell():
    g = geom(box_type=BoxType.OPEN)
    d = g.dimensions
    shell = d.ext_width * d.ext_depth * d.ext_height - d.int_width * d.int_depth * (d.ext_height - d.thickness)
    assert sum(p.contour.area() * p.thickness for p in g.panels) == pytest.approx(shell, rel=1e-9)


def _sample(rng, length, t):
    r = rng.random()
    if r < 0.3:
        return rng.uniform(1e-4, t - 1e-4)
    if r < 0.6:
        return rng.uniform(length - t + 1e-4, length - 1e-4)
    return rng.uniform(1e-4, length - 1e-4)


@pytest.mark.parametrize("kwargs", [
    dict(), dict(box_type=BoxType.OPEN),
    dict(width=60, depth=45, height=30, thickness=2.5),
    dict(width=200, depth=150, height=120, thickness=6, finger_count=7),
    dict(dimension_mode=DimensionMode.INTERNAL, box_type=BoxType.OPEN, finger_count=5),
    dict(width=90, depth=90, height=90, thickness=3, finger_count=3),
])
def test_assembly_has_no_overlaps_and_no_holes(kwargs):
    """Teste 3D: todo ponto da casca pertence a exatamente um painel; nenhum
    painel invade a cavidade interna."""
    g = geom(**kwargs)
    d, t = g.dimensions, g.dimensions.thickness
    closed = g.params.box_type is BoxType.CLOSED
    rng = random.Random(7)
    for _ in range(4000):
        x, y, z = (_sample(rng, d.ext_width, t), _sample(rng, d.ext_depth, t),
                   _sample(rng, d.ext_height, t))
        cavity = (t < x < d.ext_width - t and t < y < d.ext_depth - t
                  and t < z < (d.ext_height - t if closed else d.ext_height))
        owners = owners_at(g, x, y, z)
        assert len(owners) == (0 if cavity else 1), (x, y, z, owners)


def test_assembly_with_clearance_never_overlaps():
    g = geom(clearance=0.3)
    d, t = g.dimensions, g.dimensions.thickness
    rng = random.Random(11)
    uncovered = shell = 0
    for _ in range(4000):
        x, y, z = (_sample(rng, d.ext_width, t), _sample(rng, d.ext_depth, t),
                   _sample(rng, d.ext_height, t))
        owners = owners_at(g, x, y, z)
        assert len(owners) <= 1
        inside_cavity = (t < x < d.ext_width - t and t < y < d.ext_depth - t
                         and t < z < d.ext_height - t)
        if not inside_cavity:
            shell += 1
            uncovered += not owners
    assert 0 < uncovered / shell < 0.05  # folgas existem, mas são pequenas


def test_clearance_does_not_change_outer_dimensions():
    base = geom()
    loose = geom(clearance=0.3)
    for a, b in zip(base.panels, loose.panels):
        assert a.contour.bbox() == b.contour.bbox()
        assert (a.width, a.height) == (b.width, b.height)
    assert base.dimensions == loose.dimensions


def test_clearance_makes_slots_wider_than_tabs():
    base, loose = geom(), geom(clearance=0.3)
    for a, b in zip(base.panels, loose.panels):
        assert b.contour.area() < a.contour.area()


def test_thickness_changes_notch_depth():
    for t in (2.0, 5.0):
        g = geom(thickness=t)
        front = g.panel(PanelId.FRONT).contour
        ys = sorted({p.y for p in front.points})
        assert ys[0] == 0.0 and ys[1] == pytest.approx(t)  # profundidade do recorte = espessura
