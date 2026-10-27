import pytest

from app.core.box_geometry import build_box_geometry
from app.core.box_parameters import BoxParameters, BoxType
from app.core.geometry import offset_rectilinear, rect_minus_rects


@pytest.mark.parametrize("kerf", [0.05, 0.1, 0.2, 0.4])
def test_kerf_does_not_change_nominal_dimensions_or_contours(kerf):
    base = build_box_geometry(BoxParameters())
    with_kerf = build_box_geometry(BoxParameters(kerf=kerf))
    assert base.dimensions == with_kerf.dimensions
    for a, b in zip(base.panels, with_kerf.panels):
        assert a.contour == b.contour             # nominal idêntico
        assert (a.width, a.height) == (b.width, b.height)
    assert [j.finger_count for j in base.joints] == [j.finger_count for j in with_kerf.joints]


def test_zero_kerf_means_cut_path_equals_nominal_and_is_reported_inactive():
    g = build_box_geometry(BoxParameters(kerf=0.0))
    assert not g.kerf_active
    assert all(p.cut_path == p.contour for p in g.panels)
    assert any("nenhuma compensação" in i.message for i in g.issues)


def test_active_kerf_offsets_cut_path_outward_by_half_kerf_once():
    k = 0.2
    g = build_box_geometry(BoxParameters(kerf=k))
    assert g.kerf_active
    for p in g.panels:
        x0, y0, x1, y1 = p.cut_path.bbox()
        assert (x0, y0) == (pytest.approx(-k / 2), pytest.approx(-k / 2))
        assert (x1 - x0) == pytest.approx(p.width + k)    # k/2 de cada lado, uma só vez
        assert (y1 - y0) == pytest.approx(p.height + k)
        assert p.cut_path.area() > p.contour.area()
    assert any("Compensação de kerf ativa" in i.message for i in g.issues)


def test_offset_of_a_known_shape_is_exact():
    c = rect_minus_rects(10, 5, [(0, 0, 2, 2), (8, 3, 10, 5)])
    o = offset_rectilinear(c, 0.5)
    assert o.bbox() == (-0.5, -0.5, 10.5, 5.5)
    assert offset_rectilinear(c, 0.0) is c
    # Deslocar para fora e depois para dentro restaura o contorno original.
    assert offset_rectilinear(o, -0.5).points == c.points


def test_cut_path_stays_valid_and_notches_shrink_by_kerf():
    k = 0.2
    g0, gk = build_box_geometry(BoxParameters()), build_box_geometry(BoxParameters(kerf=k))
    for a, b in zip(g0.panels, gk.panels):
        assert b.cut_path.problems() == []
        assert len(b.cut_path.points) == len(a.contour.points)
