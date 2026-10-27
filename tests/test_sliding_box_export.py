import itertools

import pytest

from app.core.box_geometry import PanelId
from app.core.layout import LayoutParameters
from app.core.sliding_box_parameters import SlidingLidBoxParameters
from app.export.svg_exporter import SvgExportOptions, SvgMetadata, build_svg, write_svg
from app.generators.sliding_box_generator import SlidingLidBoxGenerator
from tests.svg_helpers import bbox, cut_paths, parse_mm, parse_svg

WIDE = LayoutParameters(workspace_width=900, workspace_height=900)


def gen(lp=None, **kw):
    r = SlidingLidBoxGenerator().generate(SlidingLidBoxParameters(**kw), lp or WIDE)
    assert r.ok, [i.message for i in r.issues]
    return r


def separated(a, b, gap):
    return (a[2] + gap <= b[0] + 1e-6 or b[2] + gap <= a[0] + 1e-6
            or a[3] + gap <= b[1] + 1e-6 or b[3] + gap <= a[1] + 1e-6)


# ---------------------------------------------------------- gerador / prévia
def test_generator_returns_six_placed_panels_in_the_preview_layout():
    r = gen()
    assert [p.id for p in r.layout.placed] == [PanelId.BASE, PanelId.FRONT, PanelId.BACK,
                                               PanelId.LEFT, PanelId.RIGHT, PanelId.TOP]
    assert r.layout.fits and len(r.geometry.joints) == 8


@pytest.mark.parametrize("spacing", [1.0, 5.0, 12.0])
def test_layout_has_no_overlaps_and_respects_spacing(spacing):
    r = gen(LayoutParameters(spacing=spacing, workspace_width=900, workspace_height=900))
    for a, b in itertools.combinations(r.layout.placed, 2):
        assert separated(a.bbox, b.bbox, spacing), (a.label, b.label)
    for p in r.layout.placed:
        assert p.bbox[0] >= spacing - 1e-6 and p.bbox[2] <= 900 - spacing + 1e-6


def test_invalid_parameters_return_errors_without_raising():
    for kw in (dict(width=float("nan")), dict(height=15), dict(lid_clearance=0), dict(depth=12)):
        r = SlidingLidBoxGenerator().generate(SlidingLidBoxParameters(**kw))
        assert not r.ok and r.geometry is None and r.issues


def test_summary_reports_lid_channel_and_open_gap():
    s = SlidingLidBoxGenerator.summarize(gen())
    assert len(s.panels) == 6 and s.lid_size == pytest.approx((99.7, 76.7))
    assert s.channel_height == pytest.approx(3.3) and s.open_gap_at_back == 0
    short = SlidingLidBoxGenerator.summarize(gen(lid_length=50))
    assert short.open_gap_at_back == pytest.approx(76.7 - 50)
    assert short.external == (100.0, 80.0, 60.0)


# ------------------------------------------------- SVG = prévia (mesma geometria)
@pytest.mark.parametrize("kw", [dict(), dict(kerf=0.15, clearance=0.1), dict(lid_length=50),
                                dict(width=150, depth=110, height=80, thickness=4, finger_count=7)])
def test_exported_svg_matches_the_preview_geometry(kw):
    r = gen(**kw)
    doc = build_svg(r.layout, SvgExportOptions(outer_margin=8.0))
    root = parse_svg(doc.text)
    dx, dy = doc.offset
    paths = cut_paths(root)
    assert set(paths) == {f"painel-{p.value}" for p in
                          (PanelId.BASE, PanelId.FRONT, PanelId.BACK, PanelId.LEFT,
                           PanelId.RIGHT, PanelId.TOP)}
    for placed in r.layout.placed:                         # exatamente o que a prévia desenha
        pts, closed = paths[f"painel-{placed.id.value}"]
        assert closed and len(pts) == len(placed.cut_path.points)
        expect = [c for p in placed.cut_path.points for c in (p.x + dx, p.y + dy)]
        assert [c for pt in pts for c in pt] == pytest.approx(expect, abs=2e-6)


def test_svg_declares_consistent_physical_size_in_mm():
    r = gen()
    doc = build_svg(r.layout, SvgExportOptions(outer_margin=5.0))
    root = parse_svg(doc.text)
    w, h = parse_mm(root.get("width")), parse_mm(root.get("height"))
    vb = [float(v) for v in root.get("viewBox").split()]
    assert vb == [0, 0, w, h]
    assert w == pytest.approx(r.layout.used_width + 10, abs=1e-5)
    assert h == pytest.approx(r.layout.used_height + 10, abs=1e-5)


def test_svg_piece_dimensions_are_the_nominal_ones_without_kerf():
    r = gen(width=120, depth=90, height=70)
    paths = cut_paths(parse_svg(build_svg(r.layout).text))
    expected = {"base": (120, 90), "left": (90, 70), "right": (90, 70), "back": (120, 70),
                "front": (120, r.geometry.dimensions.front_height),
                "top": (120 - 0.3, 90 - 3 - 0.3)}                   # tampa
    for pid, (w, h) in expected.items():
        x0, y0, x1, y1 = bbox(paths[f"painel-{pid}"][0])
        assert (x1 - x0, y1 - y0) == pytest.approx((w, h), abs=1e-5), pid


def test_svg_keeps_the_channel_and_lid_cutouts():
    r = gen()
    paths = cut_paths(parse_svg(build_svg(r.layout).text))
    assert len(paths["painel-top"][0]) == 8                         # tampa com os dois recortes
    side = len(r.layout.placed[3].cut_path.points)
    assert len(paths["painel-left"][0]) == side > len(paths["painel-front"][0]) * 0.5


def test_kerf_is_applied_exactly_once_in_the_svg():
    nominal = cut_paths(parse_svg(build_svg(gen().layout).text))
    kerf = cut_paths(parse_svg(build_svg(gen(kerf=0.2).layout).text))
    for pid in nominal:
        a, b = bbox(nominal[pid][0]), bbox(kerf[pid][0])
        assert (b[2] - b[0]) - (a[2] - a[0]) == pytest.approx(0.2, abs=1e-5)
        assert (b[3] - b[1]) - (a[3] - a[1]) == pytest.approx(0.2, abs=1e-5)


def test_svg_has_no_duplicate_segments_and_labels_use_the_lid_name():
    r = gen()
    root = parse_svg(build_svg(r.layout, SvgExportOptions(include_labels=True),
                               SvgMetadata("x", kerf=0.0)).text)
    seen = set()
    for pts, closed in cut_paths(root).values():
        assert closed
        for a, b in zip(pts, pts[1:] + pts[:1]):
            key = tuple(sorted((a, b)))
            assert key not in seen
            seen.add(key)
    texts = [t.text for t in root.iter("{http://www.w3.org/2000/svg}text")]
    assert any(t.startswith("Tampa deslizante") for t in texts) and len(texts) == 6


def test_export_to_disk_roundtrip(tmp_path):
    r = gen(kerf=0.1)
    doc = build_svg(r.layout)
    target = write_svg(tmp_path / "caixa_tampa.svg", doc)
    assert len(cut_paths(parse_svg(target.read_bytes()))) == 6
