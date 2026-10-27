import math
import random

import pytest

from app.core.assembly import owners_at
from app.core.box_geometry import Edge, PanelId
from app.core.box_parameters import DimensionMode
from app.core.joints import Owner
from app.core.sliding_box import (
    LID_LABEL, build_sliding_box_geometry, compute_sliding_dimensions,
    validate_sliding_parameters,
)
from app.core.sliding_box_parameters import SlidingLidBoxParameters
from app.core.validation import GeometryError, Severity, has_errors


def P(**kw):
    return SlidingLidBoxParameters(**kw)


def geom(**kw):
    return build_sliding_box_geometry(P(**kw))


# ------------------------------------------------------------------ validação
@pytest.mark.parametrize("field", ["width", "depth", "height", "thickness"])
@pytest.mark.parametrize("bad", [0, -1, float("nan"), float("inf"), float("-inf")])
def test_non_positive_or_non_finite_dimensions_rejected(field, bad):
    issues = validate_sliding_parameters(P(**{field: bad}))
    assert has_errors(issues) and any(i.field == field for i in issues)
    with pytest.raises(GeometryError):
        build_sliding_box_geometry(P(**{field: bad}))


@pytest.mark.parametrize("kwargs,field", [
    (dict(lid_clearance=0), "lid_clearance"), (dict(lid_clearance=-0.2), "lid_clearance"),
    (dict(lid_clearance=float("nan")), "lid_clearance"), (dict(lid_clearance=2.0), "lid_clearance"),
    (dict(thickness=3, lid_clearance=3.5), "lid_clearance"),        # maior que a espessura
    (dict(rail_height=1.5), "rail_height"),                          # menor que a espessura
    (dict(rail_height=float("inf")), "rail_height"),
    (dict(stop_width=2.0), "stop_width"), (dict(stop_width=-4), "stop_width"),
    (dict(lid_length=1), "lid_length"), (dict(lid_length=float("nan")), "lid_length"),
    (dict(finger_count=4), "finger_count"), (dict(kerf=2), "kerf"),
])
def test_invalid_lid_and_shared_parameters_rejected(kwargs, field):
    issues = validate_sliding_parameters(P(**kwargs))
    assert any(i.field == field and i.severity is Severity.ERROR for i in issues)


def test_defaults_are_valid_and_optionals_mean_auto():
    assert validate_sliding_parameters(P()) == []
    d = compute_sliding_dimensions(P(thickness=4))
    assert d.rail_height == 8 and d.stop_width == 8                  # 2 x espessura


@pytest.mark.parametrize("kwargs", [
    dict(height=15),                         # frente baixa demais para as juntas
    dict(depth=18),                          # canaleta curta demais
    dict(width=14, thickness=5),             # junta/tampa inviável
    dict(lid_length=500),                    # tampa maior que a caixa (limite do campo)
    dict(lid_length=76.8),                   # acima do máximo para depth=80
    dict(clearance=1.0, kerf=0.6, width=20, depth=40, height=40),
])
def test_incompatible_geometry_is_rejected_with_message(kwargs):
    with pytest.raises(GeometryError) as exc:
        build_sliding_box_geometry(P(**kwargs))
    assert len(str(exc.value)) > 20


# -------------------------------------------------------------------- peças
def test_six_panels_with_stable_ids_and_lid_label():
    g = geom()
    assert [p.id for p in g.panels] == [PanelId.BASE, PanelId.FRONT, PanelId.BACK,
                                        PanelId.LEFT, PanelId.RIGHT, PanelId.TOP]
    assert g.panel(PanelId.TOP).label == LID_LABEL == "Tampa deslizante"
    assert len({p.id for p in g.panels}) == 6


def test_no_negative_dimensions_and_every_contour_is_valid():
    for kw in (dict(), dict(kerf=0.2, clearance=0.1), dict(finger_count=5),
               dict(width=60, depth=50, height=40, thickness=2.5, lid_clearance=0.2),
               dict(dimension_mode=DimensionMode.INTERNAL, width=90, depth=70, height=40),
               dict(lid_length=50)):
        for p in geom(**kw).panels:
            assert p.width > 0 and p.height > 0 and p.thickness > 0
            for c in (p.contour, p.cut_path):
                assert c.problems() == [] and c.signed_area() > 0     # fechado, sem segmento nulo
                assert all(math.isfinite(v) for pt in c.points for v in pt)
                assert len(set(c.points)) == len(c.points)
            x0, y0, x1, y1 = p.contour.bbox()
            assert (x0, y0) == (0.0, 0.0) and x1 <= p.width + 1e-9 and y1 <= p.height + 1e-9


def test_geometry_is_deterministic():
    p = P(width=133.3, depth=97.7, height=61.1, thickness=3.2, clearance=0.1, kerf=0.12,
          lid_clearance=0.35)
    assert build_sliding_box_geometry(p) == build_sliding_box_geometry(p)


# ----------------------------------------------- guias, canaletas e recortes
def test_side_panels_have_an_open_front_channel_cut_through():
    g = geom()
    d = g.dimensions
    for pid in (PanelId.LEFT, PanelId.RIGHT):
        c = g.panel(pid).contour
        mid_z = d.front_height + d.channel_height / 2
        assert not c.contains(0.2, mid_z)                          # aberto na frente
        assert not c.contains(d.slot_end / 2, mid_z)                # vazio ao longo da canaleta
        assert not c.contains(d.slot_end - 0.2, mid_z)
        assert c.contains(d.slot_end + 0.2, mid_z)                  # ponte traseira (batente)
        assert c.contains(d.slot_end / 2, d.front_height - 0.5)     # corpo abaixo = piso
        assert c.contains(d.slot_end / 2, d.front_height + d.channel_height + 0.5)  # trilho
        assert c.contains(0.2, d.front_height + d.channel_height + 0.5)  # trilho chega à frente
        assert c.problems() == []


def test_channel_dimensions_follow_the_parameters():
    d = geom(thickness=4, lid_clearance=0.4, rail_height=7, stop_width=9).dimensions
    assert d.channel_height == pytest.approx(4.4)                   # t + folga
    assert d.front_height == pytest.approx(d.ext_height - 7 - 4.4)  # H - trilho - canaleta
    assert d.slot_end == pytest.approx(d.ext_depth - 4 - 9)         # D - t - batente


def test_front_is_lower_and_its_top_edge_is_plain():
    g = geom()
    front = g.panel(PanelId.FRONT)
    assert front.height == pytest.approx(g.dimensions.front_height)
    assert front.height < g.panel(PanelId.BACK).height
    top_y = max(p.y for p in front.contour.points)
    top_pts = [p for p in front.contour.points if p.y == top_y]
    assert len(top_pts) >= 2                                        # borda superior lisa (a tampa passa)
    assert Edge.TOP not in front.joint_edges


def test_lid_has_rear_corner_cutouts_and_rides_in_the_channel():
    g = geom()
    d = g.dimensions
    lid = g.panel(PanelId.TOP)
    assert (lid.width, lid.height) == pytest.approx((d.ext_width - d.lid_clearance, d.lid_length))
    assert len(lid.contour.points) == 8
    w, ln, ear, t = lid.width, lid.height, d.lid_ear_length, d.thickness
    assert not lid.contour.contains(0.3, ln - 0.3)                   # recorte traseiro esquerdo
    assert not lid.contour.contains(w - 0.3, ln - 0.3)               # e direito
    assert lid.contour.contains(w / 2, ln - 0.3)                     # corpo central cobre o fundo
    assert lid.contour.contains(0.3, ear - 1) and lid.contour.contains(w - 0.3, ear - 1)  # orelhas
    # encaixe com a canaleta: folga vertical total = folga da tampa, lateral = folga/2 por lado
    assert d.channel_height - t == pytest.approx(d.lid_clearance)
    assert d.lid_z - d.front_height == pytest.approx(d.lid_clearance / 2)
    assert lid.frame.origin[0] == pytest.approx(d.lid_clearance / 2)
    assert d.lid_ear_length == pytest.approx(d.slot_end - d.lid_clearance)
    assert d.lid_length == pytest.approx(d.ext_depth - t - d.lid_clearance)


def test_short_lid_is_a_plain_rectangle_and_warns():
    g = geom(lid_length=50)
    lid = g.panel(PanelId.TOP)
    assert len(lid.contour.points) == 4 and lid.height == 50
    assert g.dimensions.lid_notch_depth == 0
    assert any(i.field == "lid_length" and i.severity is Severity.WARNING for i in g.issues)


def test_all_eight_joints_are_explicit_and_complementary_on_the_real_contours():
    g = geom()
    assert len(g.joints) == 8
    t = g.dimensions.thickness

    def solid_at(panel, edge, s):
        u, v = {Edge.BOTTOM: (s, t / 2), Edge.TOP: (s, panel.height - t / 2),
                Edge.LEFT: (t / 2, s), Edge.RIGHT: (panel.width - t / 2, s)}[edge]
        return panel.contour.contains(u, v)

    for j in g.joints:
        pa, pb = g.panel(PanelId(j.a.panel)), g.panel(PanelId(j.b.panel))
        for seg in j.segments:
            s = (seg.start + seg.end) / 2
            sa, sb = solid_at(pa, Edge(j.a.edge), s), solid_at(pb, Edge(j.b.edge), s)
            if seg.owner is Owner.NEUTRAL:
                assert not sa and not sb
            else:
                assert sa != sb and sa == (seg.owner is Owner.A)


# ---------------------------------------- montagem 3D: sem interferências
def expected_wall(d, x, y, z):
    """Modelo 3D independente: onde DEVE haver material de parede (sem a tampa)."""
    t, W, D, zf = d.thickness, d.ext_width, d.ext_depth, d.front_height
    if z < t:
        return True
    if x < t or x > W - t:
        return not (y < d.slot_end and zf < z < zf + d.channel_height)
    if y > D - t:
        return True
    if y < t:
        return z <= zf
    return False


def in_lid(d, x, y, z):
    c, t, W = d.lid_clearance, d.thickness, d.ext_width
    if not (d.lid_z < z < d.lid_z + t and c / 2 < x < W - c / 2 and 0 < y < d.lid_length):
        return False
    return not (y > d.lid_ear_length and (x < t + c / 2 or x > W - t - c / 2))


CASES = [
    dict(), dict(clearance=0.2, kerf=0.1),
    dict(dimension_mode=DimensionMode.INTERNAL, width=90, depth=70, height=40),
    dict(width=200, depth=150, height=100, thickness=6, finger_count=7),
    dict(width=60, depth=50, height=40, thickness=2.5, lid_clearance=0.2),
    dict(lid_length=50), dict(rail_height=10, stop_width=12),
]


@pytest.mark.parametrize("kwargs", CASES)
def test_assembly_has_no_interference_no_holes_and_lid_sits_in_the_channel(kwargs):
    g = geom(**kwargs)
    d, t = g.dimensions, g.dimensions.thickness
    rng = random.Random(5)
    seen = {"wall": 0, "lid": 0, "void": 0}
    for _ in range(4500):
        xr = rng.choice([(1e-4, t - 1e-4), (d.ext_width - t + 1e-4, d.ext_width - 1e-4),
                         (t - .5, t + .5), (1e-4, d.ext_width - 1e-4)])
        yr = rng.choice([(1e-4, d.ext_depth - 1e-4), (1e-4, t), (d.slot_end - 2, d.slot_end + 2),
                         (d.ext_depth - t - 1, d.ext_depth - 1e-4)])
        zr = rng.choice([(1e-4, d.ext_height - 1e-4),
                         (d.front_height - 1, d.front_height + d.channel_height + 1),
                         (d.lid_z - .2, d.lid_z + t + .2)])
        x, y, z = rng.uniform(*xr), rng.uniform(*yr), rng.uniform(*zr)
        if not (0 < x < d.ext_width and 0 < y < d.ext_depth and 0 < z < d.ext_height):
            continue
        owners = owners_at(g, x, y, z)
        lid, wall = in_lid(d, x, y, z), expected_wall(d, x, y, z)
        assert not (lid and wall), "tampa invadindo parede"
        if lid:
            seen["lid"] += 1
            assert owners == [PanelId.TOP]
        elif wall:
            seen["wall"] += 1
            assert len(owners) <= 1 and owners != [PanelId.TOP]       # nunca sobreposição
            if kwargs.get("clearance", 0) == 0:
                assert len(owners) == 1                                # sem folga de junta: sem buracos
        else:
            seen["void"] += 1
            assert owners == []
    assert min(seen.values()) > 100                                   # amostragem cobre os 3 casos


# ------------------------------------------------ atualização com os parâmetros
def test_geometry_updates_when_dimensions_change():
    a, b = geom(), geom(width=120, depth=90, height=70)
    assert (b.dimensions.ext_width, b.dimensions.ext_depth, b.dimensions.ext_height) == (120, 90, 70)
    assert b.panel(PanelId.BASE).width == 120 and b.panel(PanelId.BASE).height == 90
    assert b.panel(PanelId.LEFT).width == 90 and b.panel(PanelId.LEFT).height == 70
    assert b.panel(PanelId.TOP).width == pytest.approx(120 - 0.3)
    assert b.panel(PanelId.TOP).height == pytest.approx(90 - 3 - 0.3)
    assert b.panel(PanelId.FRONT).height > a.panel(PanelId.FRONT).height
    assert a.panel(PanelId.BASE).contour != b.panel(PanelId.BASE).contour


def test_internal_mode_returns_the_requested_internal_dimensions():
    d = geom(dimension_mode=DimensionMode.INTERNAL, width=100, depth=80, height=40).dimensions
    assert (d.int_width, d.int_depth, d.int_height) == pytest.approx((100, 80, 40))
    assert (d.ext_width, d.ext_depth) == (106, 86)
    assert d.ext_height == pytest.approx(d.front_height + d.channel_height + d.rail_height)


def test_thickness_and_lid_clearance_change_the_channel_and_lid():
    a, b = geom(thickness=3).dimensions, geom(thickness=5, width=120, depth=100, height=80).dimensions
    assert b.channel_height > a.channel_height
    c = geom(lid_clearance=0.6).dimensions
    assert c.lid_width == pytest.approx(100 - 0.6) and c.channel_height == pytest.approx(3.6)


# -------------------------------------------------------------------- kerf
def test_kerf_never_changes_nominal_geometry_and_is_applied_once():
    base, kerf = geom(), geom(kerf=0.2)
    assert base.dimensions == kerf.dimensions
    for a, b in zip(base.panels, kerf.panels):
        assert a.contour == b.contour
        ba, bk = a.cut_path.bbox(), b.cut_path.bbox()
        assert (bk[2] - bk[0]) - (ba[2] - ba[0]) == pytest.approx(0.2, abs=1e-6)   # k, e não 2k
        assert (bk[3] - bk[1]) - (ba[3] - ba[1]) == pytest.approx(0.2, abs=1e-6)
    assert all(p.cut_path == p.contour for p in base.panels)


def test_kerf_narrows_the_channel_in_the_cut_path_by_exactly_the_kerf():
    k = 0.2
    g = geom(kerf=k)
    d = g.dimensions
    cut = g.panel(PanelId.LEFT).cut_path
    x = d.slot_end / 2
    lo, hi = d.front_height + k / 2, d.front_height + d.channel_height - k / 2
    assert cut.contains(x, lo - 0.01) and not cut.contains(x, lo + 0.01)
    assert cut.contains(x, hi + 0.01) and not cut.contains(x, hi - 0.01)
    assert hi - lo == pytest.approx(d.channel_height - k)           # o laser abre o resto (kerf)
