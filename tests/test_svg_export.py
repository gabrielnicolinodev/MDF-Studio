import itertools
import math

import pytest

from app.core.box_geometry import PanelId
from app.core.box_parameters import BoxParameters, BoxType
from app.core.geometry import Contour, Point
from app.core.layout import LayoutParameters, PanelLayout, PlacedPanel
from app.export.svg_exporter import (
    ExportError, SvgExportOptions, SvgMetadata, build_reference_svg, build_svg,
    reference_square_layout, validate_contour,
)
from app.generators.box_generator import BoxGenerator
from tests.svg_helpers import NS, bbox, cut_paths, parse_mm, parse_path, parse_svg

EPS = 1e-6


def layout_for(**kw):
    lp = kw.pop("lp", LayoutParameters())
    r = BoxGenerator().generate(BoxParameters(**kw), lp)
    assert r.ok
    return r.layout


def sq(x, y, s):
    return Contour((Point(x, y), Point(x + s, y), Point(x + s, y + s), Point(x, y + s)))


def panel(pid, c, label="p"):
    return PlacedPanel(pid, label, 1, 1, c, c, c.bbox(), ())


def custom_layout(*placed):
    return PanelLayout(tuple(placed), LayoutParameters(), (0, 0, 1, 1), True, ())


# ------------------------------------------------------------ validade/escala
def test_svg_is_valid_xml_with_expected_root():
    root = parse_svg(build_svg(layout_for()).text)
    assert root.tag == "{http://www.w3.org/2000/svg}svg"
    assert root.get("version") == "1.1"


@pytest.mark.parametrize("margin", [0, 5, 12.5])
def test_width_height_viewbox_are_explicit_mm_and_consistent(margin):
    layout = layout_for()
    doc = build_svg(layout, SvgExportOptions(outer_margin=margin))
    root = parse_svg(doc.text)
    w, h = parse_mm(root.get("width")), parse_mm(root.get("height"))
    vb = [float(v) for v in root.get("viewBox").split()]
    assert vb[:2] == [0, 0] and (vb[2], vb[3]) == (w, h)             # 1 unidade = 1 mm
    assert w == pytest.approx(layout.used_width + 2 * margin, abs=1e-5)
    assert h == pytest.approx(layout.used_height + 2 * margin, abs=1e-5)
    assert (doc.width, doc.height) == (w, h)


def test_no_transform_or_implicit_scaling_anywhere():
    text = build_svg(layout_for(kerf=0.2), SvgExportOptions(include_labels=True,
                                                            include_guides=True)).text
    root = parse_svg(text)
    assert all("transform" not in el.attrib for el in root.iter())


def test_scale_reference_square_is_exactly_100_by_100_mm():
    doc = build_reference_svg(100.0)
    root = parse_svg(doc.text)
    assert root.get("width") == "100mm" and root.get("height") == "100mm"
    assert root.get("viewBox") == "0 0 100 100"
    pts, closed = cut_paths(root)["painel-base"]
    x0, y0, x1, y1 = bbox(pts)
    assert (x1 - x0, y1 - y0) == (100.0, 100.0) and closed
    assert len(pts) == 4


def test_scale_reference_with_margin_declares_the_larger_canvas():
    root = parse_svg(build_reference_svg(100.0, SvgExportOptions(outer_margin=5)).text)
    assert root.get("width") == "110mm" and root.get("viewBox") == "0 0 110 110"
    x0, y0, x1, y1 = bbox(cut_paths(root)["painel-base"][0])
    assert (x0, y0, x1 - x0, y1 - y0) == (5.0, 5.0, 100.0, 100.0)


def test_reference_square_rejects_bad_size():
    for bad in (0, -5, float("nan"), float("inf")):
        with pytest.raises(ExportError):
            reference_square_layout(bad)


# ------------------------------------------------------------ fidelidade
@pytest.mark.parametrize("kwargs", [dict(), dict(box_type=BoxType.OPEN), dict(finger_count=5),
                                    dict(kerf=0.2, clearance=0.1), dict(width=60, depth=45, height=30)])
def test_exported_coordinates_equal_layout_coordinates_plus_translation(kwargs):
    layout = layout_for(**kwargs)
    doc = build_svg(layout, SvgExportOptions(outer_margin=7.0))
    dx, dy = doc.offset
    paths = cut_paths(parse_svg(doc.text))
    for placed in layout.placed:
        pts, closed = paths[f"painel-{placed.id.value}"]
        assert closed and len(pts) == len(placed.cut_path.points)       # vértices preservados
        for (ex, ey), p in zip(pts, placed.cut_path.points):             # e na mesma ordem
            assert ex == pytest.approx(p.x + dx, abs=2e-6)
            assert ey == pytest.approx(p.y + dy, abs=2e-6)


def test_translation_only_normalization_keeps_every_dimension():
    layout = layout_for(lp=LayoutParameters(spacing=9.0))
    a = cut_paths(parse_svg(build_svg(layout, SvgExportOptions(outer_margin=0)).text))
    b = cut_paths(parse_svg(build_svg(layout, SvgExportOptions(outer_margin=20)).text))
    for pid in a:
        ba, bb = bbox(a[pid][0]), bbox(b[pid][0])
        assert (ba[2] - ba[0], ba[3] - ba[1]) == pytest.approx((bb[2] - bb[0], bb[3] - bb[1]), abs=1e-6)
        assert bb[0] - ba[0] == pytest.approx(20.0, abs=1e-5)       # só deslocou


def test_canvas_starts_at_outer_margin_and_nothing_leaves_the_canvas():
    doc = build_svg(layout_for(kerf=0.3), SvgExportOptions(outer_margin=6.0))
    root = parse_svg(doc.text)
    allpts = [p for pts, _ in cut_paths(root).values() for p in pts]
    x0, y0, x1, y1 = bbox(allpts)
    assert (x0, y0) == pytest.approx((6.0, 6.0), abs=1e-5)
    assert x1 == pytest.approx(doc.width - 6.0, abs=1e-5) and y1 == pytest.approx(doc.height - 6.0, abs=1e-5)


def test_nominal_panel_dimensions_are_preserved_when_kerf_is_zero():
    layout = layout_for(width=120, depth=90, height=60, thickness=4)
    paths = cut_paths(parse_svg(build_svg(layout).text))
    expected = {"painel-base": (120, 90), "painel-top": (120, 90), "painel-front": (120, 60),
                "painel-back": (120, 60), "painel-left": (90, 60), "painel-right": (90, 60)}
    for pid, (w, h) in expected.items():
        x0, y0, x1, y1 = bbox(paths[pid][0])
        assert (x1 - x0, y1 - y0) == pytest.approx((w, h), abs=1e-5)


def test_fingers_are_preserved_in_the_exported_path():
    layout = layout_for()
    pts, _ = cut_paths(parse_svg(build_svg(layout).text))["painel-front"]
    assert len(pts) == len(layout.placed[2].cut_path.points) > 40
    for a, b in zip(pts, pts[1:] + pts[:1]):
        assert math.isclose(a[0], b[0], abs_tol=1e-6) or math.isclose(a[1], b[1], abs_tol=1e-6)


# ------------------------------------------------------------ painéis/contornos
@pytest.mark.parametrize("box_type,count", [(BoxType.CLOSED, 6), (BoxType.OPEN, 5)])
def test_all_panels_present_with_stable_ids(box_type, count):
    paths = cut_paths(parse_svg(build_svg(layout_for(box_type=box_type)).text))
    assert len(paths) == count
    assert set(paths) == {f"painel-{p.value}" for p in PanelId
                          if box_type is BoxType.CLOSED or p is not PanelId.TOP}


def test_contours_are_closed_without_repeated_closing_point_or_duplicates():
    paths = cut_paths(parse_svg(build_svg(layout_for(kerf=0.15)).text))
    for pts, closed in paths.values():
        assert closed
        assert pts[0] != pts[-1]                      # o fechamento é o 'Z', sem ponto repetido
        assert all(a != b for a, b in zip(pts, pts[1:] + pts[:1]))


def test_no_duplicate_segments_in_the_whole_file():
    paths = cut_paths(parse_svg(build_svg(layout_for()).text))
    seen = set()
    for pts, _ in paths.values():
        for a, b in zip(pts, pts[1:] + pts[:1]):
            key = tuple(sorted((a, b)))
            assert key not in seen
            seen.add(key)


def test_exported_panels_do_not_overlap_each_other():
    paths = cut_paths(parse_svg(build_svg(layout_for()).text))
    boxes = [bbox(p) for p, _ in paths.values()]
    for a, b in itertools.combinations(boxes, 2):
        assert a[2] < b[0] or b[2] < a[0] or a[3] < b[1] or b[3] < a[1]


# ------------------------------------------------------------ kerf
def test_kerf_is_not_compensated_twice():
    nominal = layout_for()
    with_kerf = layout_for(kerf=0.2)
    p0 = cut_paths(parse_svg(build_svg(nominal).text))
    pk = cut_paths(parse_svg(build_svg(with_kerf).text))
    for pid in p0:
        b0, bk = bbox(p0[pid][0]), bbox(pk[pid][0])
        # offset UMA vez: cada dimensão cresce exatamente kerf (0.2), não 0.4
        assert (bk[2] - bk[0]) - (b0[2] - b0[0]) == pytest.approx(0.2, abs=1e-5)
        assert (bk[3] - bk[1]) - (b0[3] - b0[1]) == pytest.approx(0.2, abs=1e-5)


def test_exporter_uses_the_engine_cut_path_verbatim():
    layout = layout_for(kerf=0.25)
    doc = build_svg(layout, SvgExportOptions(outer_margin=0))
    dx, dy = doc.offset
    for placed in layout.placed:
        pts, _ = cut_paths(parse_svg(doc.text))[f"painel-{placed.id.value}"]
        expect = [c for p in placed.cut_path.points for c in (p.x + dx, p.y + dy)]
        assert [c for pt in pts for c in pt] == pytest.approx(expect, abs=2e-6)


def test_metadata_reports_kerf_state_without_changing_geometry():
    layout = layout_for(kerf=0.2)
    a = build_svg(layout, metadata=SvgMetadata("x", kerf=0.2))
    b = build_svg(layout, metadata=SvgMetadata("x", kerf=0.0))
    assert "já aplicado" in a.text and "sem compensação" in b.text
    assert cut_paths(parse_svg(a.text)) == cut_paths(parse_svg(b.text))


# ------------------------------------------------------------ identificações/auxiliares
def group_ids(root):
    return [g.get("id") for g in root.findall("s:g", NS)]


def test_default_export_has_only_the_cut_group():
    root = parse_svg(build_svg(layout_for()).text)
    assert group_ids(root) == ["corte"]
    assert not root.findall(".//s:text", NS)


def test_labels_go_in_a_separate_group_never_in_the_cut_group():
    root = parse_svg(build_svg(layout_for(), SvgExportOptions(include_labels=True)).text)
    assert group_ids(root) == ["corte", "identificacao"]
    assert not root.find("s:g[@id='corte']", NS).findall(".//s:text", NS)
    texts = [t.text for t in root.find("s:g[@id='identificacao']", NS).findall("s:text", NS)]
    assert len(texts) == 6 and any("Frente 100.0 x 50.0 mm" in t for t in texts)


def test_guides_go_in_a_separate_group_and_are_dashed():
    layout = layout_for()
    root = parse_svg(build_svg(layout, SvgExportOptions(include_guides=True)).text)
    assert group_ids(root) == ["corte", "auxiliares"]
    guides = root.find("s:g[@id='auxiliares']", NS)
    assert guides.get("stroke-dasharray")
    assert len(guides.findall("s:path", NS)) == sum(len(p.reference_lines) for p in layout.placed)
    assert all(not p.get("id") for p in guides.findall("s:path", NS))


def test_cut_geometry_is_identical_with_and_without_labels_and_guides():
    layout = layout_for(kerf=0.1)
    plain = cut_paths(parse_svg(build_svg(layout).text))
    full = cut_paths(parse_svg(build_svg(layout, SvgExportOptions(include_labels=True,
                                                                  include_guides=True)).text))
    assert plain == full


def test_colors_are_configurable_and_groups_are_identified_by_id_not_only_color():
    o = SvgExportOptions(include_labels=True, include_guides=True, cut_color="#112233",
                         label_color="#445566", guide_color="#778899")
    root = parse_svg(build_svg(layout_for(), o).text)
    assert root.find("s:g[@id='corte']", NS).get("stroke") == "#112233"
    assert root.find("s:g[@id='identificacao']", NS).get("fill") == "#445566"
    assert root.find("s:g[@id='auxiliares']", NS).get("stroke") == "#778899"


def test_no_forbidden_or_unsupported_elements():
    text = build_svg(layout_for(), SvgExportOptions(include_labels=True, include_guides=True)).text
    tags = {el.tag.split("}")[1] for el in parse_svg(text).iter()}
    assert tags <= {"svg", "title", "desc", "g", "path", "text"}
    assert "<image" not in text and "<script" not in text and "<filter" not in text
    assert "<style" not in text and "http" not in text.replace("http://www.w3.org/2000/svg", "")


def test_no_power_speed_or_pass_settings_are_written():
    text = build_svg(layout_for()).text.lower()
    for word in ("power", "speed", "passes", "potencia"):
        assert word not in text.replace("potência", "")
    assert "configure as operações no lightburn" in text


def test_export_is_deterministic_byte_for_byte():
    a = build_svg(layout_for(kerf=0.1, clearance=0.1), SvgExportOptions(include_labels=True)).to_bytes()
    b = build_svg(layout_for(kerf=0.1, clearance=0.1), SvgExportOptions(include_labels=True)).to_bytes()
    assert a == b


def test_text_in_labels_is_xml_escaped():
    c = sq(0, 0, 10)
    p = PlacedPanel(PanelId.BASE, 'A&B <"x">', 10, 10, c, c, c.bbox(), ())
    root = parse_svg(build_svg(custom_layout(p), SvgExportOptions(include_labels=True)).text)
    assert 'A&B <"x">' in root.find(".//s:text", NS).text


# ------------------------------------------------------------ desenhos inválidos
def test_negative_coordinates_are_normalized_without_changing_size():
    c = sq(-20, -30, 10)
    doc = build_svg(custom_layout(panel(PanelId.BASE, c)), SvgExportOptions(outer_margin=2))
    pts, _ = cut_paths(parse_svg(doc.text))["painel-base"]
    assert bbox(pts) == (2.0, 2.0, 12.0, 12.0) and (doc.width, doc.height) == (14.0, 14.0)


def test_empty_layout_is_rejected():
    with pytest.raises(ExportError, match="painéis"):
        build_svg(custom_layout())


def test_open_or_degenerate_contour_is_rejected():
    two = Contour((Point(0, 0), Point(5, 0)))
    with pytest.raises(ExportError):
        build_svg(custom_layout(panel(PanelId.BASE, two)))
    repeated = Contour((Point(0, 0), Point(5, 0), Point(5, 5), Point(0, 5), Point(0, 0)))  # repete o 1º ponto
    with pytest.raises(ExportError, match="inválido"):
        build_svg(custom_layout(panel(PanelId.BASE, repeated)))


def test_non_finite_coordinates_are_rejected():
    bad = Contour((Point(0, 0), Point(float("nan"), 0), Point(5, 5), Point(0, 5)))
    with pytest.raises(ExportError, match="finitas"):
        build_svg(custom_layout(panel(PanelId.BASE, bad)))


def test_self_intersecting_contour_is_rejected():
    # Autointersectante COM área não nula: exercita a checagem de interseção.
    crossed = Contour((Point(0, 0), Point(10, 10), Point(10, 0), Point(0, 4)))
    assert crossed.area() > 1e-9
    with pytest.raises(ExportError, match="autointersectante"):
        build_svg(custom_layout(panel(PanelId.BASE, crossed)))
    # A gravata-borboleta simétrica (área zero) também é rejeitada, por outro motivo.
    bowtie = Contour((Point(0, 0), Point(10, 10), Point(10, 0), Point(0, 10)))
    with pytest.raises(ExportError):
        validate_contour("x", bowtie)


def test_overlapping_or_touching_panels_are_rejected():
    a, b = panel(PanelId.BASE, sq(0, 0, 10)), panel(PanelId.TOP, sq(5, 5, 10))
    with pytest.raises(ExportError, match="sobrep"):
        build_svg(custom_layout(a, b))
    touching = panel(PanelId.TOP, sq(10, 0, 10))
    with pytest.raises(ExportError):
        build_svg(custom_layout(a, touching))


def test_duplicate_panel_ids_are_rejected():
    with pytest.raises(ExportError, match="duplicados"):
        build_svg(custom_layout(panel(PanelId.BASE, sq(0, 0, 5)), panel(PanelId.BASE, sq(20, 0, 5))))


@pytest.mark.parametrize("opts", [
    dict(outer_margin=-1), dict(outer_margin=float("nan")), dict(outer_margin=500),
    dict(stroke_width=0), dict(cut_color="red"), dict(cut_color="#12345"),
    dict(label_font_size=float("inf")),
])
def test_invalid_options_are_rejected(opts):
    with pytest.raises(ExportError):
        build_svg(layout_for(), SvgExportOptions(**opts))
