import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication, QLabel

from app.core.box_parameters import DimensionMode
from app.core.sliding_box_parameters import SlidingLidBoxParameters
from app.storage.settings_store import SettingsStore
from app.ui.box_generator_page import BoxGeneratorPage
from app.ui.main_window import NAV_ITEMS, MainWindow
from app.ui.sliding_box_page import SlidingLidBoxPage
from app.ui.theme import apply_dark_theme
from tests.svg_helpers import cut_paths, parse_mm, parse_svg


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    apply_dark_theme(app)
    return app


@pytest.fixture
def env(qapp, tmp_path):
    export_dir = tmp_path / "exports"
    export_dir.mkdir()
    store = SettingsStore(tmp_path / "s.json")
    settings = store.load()
    settings["export_dir"] = str(export_dir)
    store.save(settings)
    win = MainWindow(store)
    win.show()
    win.open_generator("sliding_lid_box")
    page = win._pages["generators"].sliding_page
    page.choose_save_path = lambda initial: None
    return win, page, export_dir


def choose(page, path):
    page.choose_save_path = lambda initial: str(path)


# ------------------------------------------------------------------ catálogo
def test_catalog_card_opens_the_sliding_page_and_back_returns(env):
    win, page, _ = env
    gp = win._pages["generators"]
    assert win.current_page_key() == "generators"
    assert gp.current_generator_key() == "sliding_lid_box"
    page.back_requested.emit()
    assert gp.current_generator_key() is None
    assert win.stack.count() == len(NAV_ITEMS)                 # menu da Etapa 01 intacto


def test_both_available_generators_are_reachable_and_independent(env):
    win, sliding, _ = env
    gp = win._pages["generators"]
    gp.open_generator("rect_box")
    assert gp.current_generator_key() == "rect_box"
    assert gp.box_page is not sliding and isinstance(sliding, SlidingLidBoxPage)
    assert sliding.TITLE == "Caixa com tampa deslizante" and gp.box_page.TITLE == "Caixa retangular"


def test_original_box_page_is_unchanged_in_behavior(env):
    win, _, _ = env
    box = win._pages["generators"].box_page
    assert type(box) is BoxGeneratorPage and box.HAS_BOX_TYPE and box.type_combo is not None
    result = box.generate()
    assert result.ok and len(result.layout.placed) == 6
    assert box.default_file_name(result) == "caixa_100x80x50mm.svg"
    assert "lid_clearance" not in box.fields


# --------------------------------------------------------------------- prévia
def test_generate_shows_six_pieces_with_the_calculated_geometry(env):
    _, page, _ = env
    result = page.generate()
    assert result.ok and page.viewer.layout_data is result.layout
    assert len(result.layout.placed) == 6
    assert "Tampa" in page.summary.text() and "Canaleta" in page.summary.text()
    assert page.type_combo is None if hasattr(page, "type_combo") else True


def test_preview_updates_when_dimensions_change(env):
    _, page, _ = env
    first = page.generate()
    page.set_value("width", "130")
    page.set_value("depth", "100")
    second = page.generate()
    assert second.layout is not first.layout and page.viewer.layout_data is second.layout
    assert second.geometry.dimensions.ext_width == 130 and second.geometry.dimensions.ext_depth == 100
    assert second.geometry.dimensions.lid_width == pytest.approx(130 - 0.3)


def test_lid_parameters_reach_the_geometry(env):
    _, page, _ = env
    page.set_value("lid_clearance", "0,4")
    page.set_value("rail_height", "8")
    page.set_value("stop_width", "9")
    page.set_value("lid_length", "60")
    r = page.generate()
    d = r.geometry.dimensions
    assert (d.lid_clearance, d.rail_height, d.stop_width, d.lid_length) == (0.4, 8, 9, 60)
    assert "abertura" in page.summary.text()                   # tampa curta: avisa a abertura
    page.set_value("rail_height", "auto")
    page.set_value("lid_length", "")
    r = page.generate()
    # 'auto' volta ao máximo, calculado com a folga ainda definida (0,4): 80 - 3 - 0,4
    assert r.geometry.dimensions.rail_height == 6
    assert r.geometry.dimensions.lid_length == pytest.approx(80 - 3 - 0.4)


def test_internal_mode_from_ui(env):
    _, page, _ = env
    page.mode_combo.setCurrentIndex(page.mode_combo.findData(DimensionMode.INTERNAL.value))
    page.set_value("width", "100"); page.set_value("depth", "80"); page.set_value("height", "40")
    d = page.generate().geometry.dimensions
    assert (d.int_width, d.int_depth) == (100, 80) and d.int_height == pytest.approx(40)


def test_defaults_match_the_model_defaults(env):
    _, page, _ = env
    d = SlidingLidBoxParameters()
    assert page.fields["height"].text() == "60,0"
    assert page.fields["lid_clearance"].text() == "0,30" and d.lid_clearance == 0.3
    assert page.fields["rail_height"].text() == "auto"


@pytest.mark.parametrize("field,text,expect", [
    ("width", "nan", "Largura"), ("height", "15", "altura"), ("lid_clearance", "0", "Folga da tampa"),
    ("lid_clearance", "abc", "Folga da tampa"), ("rail_height", "xx", "auto"),
    ("rail_height", "1,5", "Altura do trilho"), ("stop_width", "-3", "Largura do batente"),
    ("lid_length", "999", "Comprimento da tampa"), ("depth", "12", "canaleta"),
])
def test_invalid_input_shows_a_clear_message_and_clears_preview(env, field, text, expect):
    _, page, _ = env
    page.generate()
    page.set_value(field, text)
    page.generate()
    assert page.viewer.layout_data is None
    assert "Erro" in page.messages.text() and expect in page.messages.text()
    assert page.summary.text() == ""


def test_lid_section_and_guidance_are_in_the_form(env):
    _, page, _ = env
    texts = [l.text() for l in page.findChildren(QLabel)]
    assert any("Tampa deslizante" == t for t in texts)
    assert any("canaletas" in t and "frente" in t for t in texts)


# ------------------------------------------------------------------- exportação
def test_export_writes_svg_equal_to_the_preview(env):
    _, page, export_dir = env
    result = page.generate()
    target = export_dir / "tampa.svg"
    choose(page, target)
    assert page.export_svg() == target
    root = parse_svg(target.read_bytes())
    paths = cut_paths(root)
    assert len(paths) == 6 and "painel-top" in paths
    # mesma geometria da prévia (translação = margem externa - canto usado)
    shown = page.viewer.layout_data
    margin = 5.0
    dx, dy = margin - shown.used_bbox[0], margin - shown.used_bbox[1]
    for placed in shown.placed:
        pts, _ = paths[f"painel-{placed.id.value}"]
        expect = [c for p in placed.cut_path.points for c in (p.x + dx, p.y + dy)]
        assert [c for pt in pts for c in pt] == pytest.approx(expect, abs=2e-6)
    assert parse_mm(root.get("width")) == pytest.approx(shown.used_width + 2 * margin, abs=1e-5)
    assert "Arquivo gravado e verificado" in page.export_status.text()
    assert result.ok


def test_default_file_name_and_title_identify_the_model(env):
    _, page, export_dir = env
    asked = []
    page.choose_save_path = lambda initial: (asked.append(initial), None)[1]
    r = page.generate()
    page.export_svg()
    assert asked == [str(export_dir / "caixa_tampa_deslizante_100x80x60mm.svg")]
    assert "Caixa com tampa deslizante" in page._metadata(r).title


def test_kerf_from_ui_is_applied_once_in_the_file(env):
    _, page, export_dir = env
    page.generate()
    choose(page, export_dir / "a.svg"); page.export_svg()
    page.set_value("kerf", "0,2")
    page.generate()
    choose(page, export_dir / "b.svg"); page.export_svg()
    a = cut_paths(parse_svg((export_dir / "a.svg").read_bytes()))
    b = cut_paths(parse_svg((export_dir / "b.svg").read_bytes()))
    for pid in a:
        xa = [p[0] for p in a[pid][0]]; xb = [p[0] for p in b[pid][0]]
        assert (max(xb) - min(xb)) - (max(xa) - min(xa)) == pytest.approx(0.2, abs=1e-5)


def test_export_is_blocked_after_editing_and_for_invalid_projects(env):
    _, page, export_dir = env
    page.generate()
    page.set_value("lid_clearance", "0,5")
    choose(page, export_dir / "x.svg")
    assert page.export_svg() is None and "Gerar projeto" in page.export_status.text()
    page.set_value("rail_height", "xx")
    page.generate()
    assert page.export_svg() is None and os.listdir(export_dir) == []


def test_overwrite_still_requires_confirmation(env):
    _, page, export_dir = env
    page.generate()
    target = export_dir / "a.svg"
    target.write_text("ORIGINAL")
    choose(page, target)
    page.confirm_overwrite = lambda path: False
    assert page.export_svg() is None and target.read_text() == "ORIGINAL"
    page.confirm_overwrite = lambda path: True
    assert page.export_svg() == target and target.read_text().startswith("<?xml")


def test_scale_reference_is_available_on_the_new_page(env):
    _, page, export_dir = env
    choose(page, export_dir / "teste_escala_100x100mm.svg")
    assert page.export_scale_reference() is not None
    assert parse_svg((export_dir / "teste_escala_100x100mm.svg").read_bytes()).get("width") == "100mm"


def test_resize_and_zoom_work_on_the_new_page(env, qapp):
    win, page, _ = env
    page.generate()
    for w, h in ((720, 480), (1400, 900)):
        win.resize(w, h)
        qapp.processEvents()
        page.viewer.grab()
    page.viewer.zoom_in(); page.viewer.zoom_out(); page.viewer.fit()
    assert page.viewer.zoom == 1.0
