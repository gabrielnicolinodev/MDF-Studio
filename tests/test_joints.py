import pytest

from app.core.box_geometry import Edge, PanelId, build_box_geometry, plan_joints, compute_dimensions
from app.core.box_parameters import BoxParameters, BoxType
from app.core.joints import (
    MIN_FINGER_WIDTH, EdgeRef, Owner, build_finger_joint, complement_intervals, narrowed_tabs,
)
from app.core.validation import GeometryError

A, B = EdgeRef("a", "bottom"), EdgeRef("b", "bottom")


def make(length=100.0, t=3.0, sz=Owner.A, ez=Owner.A, count=None):
    return build_finger_joint("teste", A, B, length, t, sz, ez, count)


def test_segments_cover_joint_without_gaps_or_zero_length():
    for length, t, count in [(100, 3, None), (57.3, 2.5, None), (200, 6, 7), (23, 3, 3)]:
        j = make(length, t, count=count)
        assert j.segments[0].start == 0.0
        assert j.segments[-1].end == pytest.approx(length)
        for s1, s2 in zip(j.segments, j.segments[1:]):
            assert s1.end == s2.start
        assert all(s.length > 0 for s in j.segments)


def test_finger_distribution_is_uniform_and_odd():
    j = make(100, 3)
    assert j.finger_count % 2 == 1 and j.finger_count >= 3
    widths = [j.segments[i].length for i in range(1, 1 + j.finger_count)]
    # Coordenadas são arredondadas a 1e-6 mm, então a igualdade vale com essa tolerância.
    assert all(w == pytest.approx(j.finger_width, abs=2e-6) for w in widths)
    owners = [s.owner for s in j.segments[1:1 + j.finger_count]]
    assert owners == [Owner.A if i % 2 == 0 else Owner.B for i in range(j.finger_count)]


def test_user_defined_finger_count_is_respected():
    assert make(150, 3, count=9).finger_count == 9


def test_tabs_of_both_sides_are_complementary():
    j = make(100, 3)
    ta, tb = j.tab_intervals(Owner.A), j.tab_intervals(Owner.B)
    # Disjuntos...
    for a0, a1 in ta:
        for b0, b1 in tb:
            assert a1 <= b0 + 1e-9 or b1 <= a0 + 1e-9
    # ...e juntos cobrem [0, L] (sem zonas neutras neste caso).
    covered = sorted(ta + tb)
    assert covered[0][0] == 0.0 and covered[-1][1] == pytest.approx(100.0)
    assert sum(b - a for a, b in covered) == pytest.approx(100.0)
    assert complement_intervals(ta, 100.0) == [(s0, s1) for s0, s1 in tb]


def test_neutral_zones_are_notched_on_both_sides():
    j = make(50, 3, sz=Owner.NEUTRAL, ez=Owner.NEUTRAL)
    ta, tb = j.tab_intervals(Owner.A), j.tab_intervals(Owner.B)
    for tabs in (ta, tb):
        assert all(s0 >= 3 - 1e-9 and s1 <= 47 + 1e-9 for s0, s1 in tabs)


def test_open_end_has_no_zone():
    j = make(50, 3, sz=Owner.NEUTRAL, ez=None)
    assert j.segments[-1].end == pytest.approx(50.0)
    assert j.segments[-1].owner is Owner.A  # dente da ponta chega ao topo


def test_too_short_joint_is_rejected():
    with pytest.raises(GeometryError):
        make(length=10, t=3)
    # Exatamente o mínimo (2 zonas de 3 mm + 3 dedos de 2 mm) ainda é viável...
    assert make(length=12, t=3).finger_count == 3
    # ...e qualquer valor abaixo disso é rejeitado.
    with pytest.raises(GeometryError):
        make(length=11.9, t=3)


def test_too_many_fingers_are_rejected():
    with pytest.raises(GeometryError):
        make(length=60, t=3, count=51)


def test_clearance_narrows_tabs_but_not_at_panel_corners():
    j = make(100, 3)
    tabs = j.tab_intervals(Owner.A)
    out = narrowed_tabs(tabs, 100.0, 0.4, "t")
    assert out[0][0] == 0.0 and out[-1][1] == 100.0          # cantos preservados
    assert out[0][1] == pytest.approx(tabs[0][1] - 0.1)       # clearance/4 por lado
    assert out[1][0] == pytest.approx(tabs[1][0] + 0.1)
    assert out[1][1] == pytest.approx(tabs[1][1] - 0.1)


def test_clearance_that_removes_a_tab_is_rejected():
    j = make(30, 3, count=3)
    with pytest.raises(GeometryError):
        narrowed_tabs(j.tab_intervals(Owner.B), 30.0, 100.0, "t")


def test_planned_joints_are_explicit_and_complete():
    p = BoxParameters()
    d = compute_dimensions(p)
    joints = plan_joints(p, d)
    assert len(joints) == 12  # 4 base + 4 tampa + 4 verticais
    edges = [(j.a.panel, j.a.edge) for j in joints] + [(j.b.panel, j.b.edge) for j in joints]
    assert len(edges) == len(set(edges))  # cada aresta participa de uma única junta
    open_joints = plan_joints(BoxParameters(box_type=BoxType.OPEN),
                              compute_dimensions(BoxParameters(box_type=BoxType.OPEN)))
    assert len(open_joints) == 8


def test_matching_edges_have_equal_length_and_complementary_geometry():
    """Pela geometria real: o perfil do painel A num ponto da junta é dente
    exatamente onde o de B é recorte (fora das zonas neutras)."""
    g = build_box_geometry(BoxParameters())
    t = g.dimensions.thickness

    def solid_at(panel, edge, s):
        inset = t / 2
        u, v = {Edge.BOTTOM: (s, inset), Edge.TOP: (s, panel.height - inset),
                Edge.LEFT: (inset, s), Edge.RIGHT: (panel.width - inset, s)}[edge]
        return panel.contour.contains(u, v)

    for j in g.joints:
        pa, pb = g.panel(PanelId(j.a.panel)), g.panel(PanelId(j.b.panel))
        ea, eb = Edge(j.a.edge), Edge(j.b.edge)
        for seg in j.segments:
            s = (seg.start + seg.end) / 2
            sa, sb = solid_at(pa, ea, s), solid_at(pb, eb, s)
            if seg.owner is Owner.NEUTRAL:
                assert not sa and not sb
            else:
                assert sa != sb
                assert sa == (seg.owner is Owner.A)
