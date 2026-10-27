import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication

from app.core.box_parameters import BoxType, DimensionMode
from app.storage.settings_store import SettingsStore
from app.ui.generators_catalog import PLANNED_GENERATORS
from app.ui.main_window import NAV_ITEMS, MainWindow
from app.ui.theme import apply_dark_theme


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    apply_dark_theme(app)
    return app


@pytest.fixture
def window(qapp, tmp_path):
    win = MainWindow(SettingsStore(tmp_path / "s.json"))
    win.show()
    return win


def box_page(win):
    return win._pages["generators"].box_page


def test_available_generators_and_the_rest_stay_in_development():
    # Etapa 04 acrescentou "Caixa com tampa deslizante"; os seis módulos originais continuam.
    available = [g.key for g in PLANNED_GENERATORS if g.available]
    assert available == ["rect_box", "sliding_lid_box"]
    assert len(PLANNED_GENERATORS) == 7
    in_development = [g.key for g in PLANNED_GENERATORS if not g.available]
    assert in_development == ["lid_box", "drawers", "organizers", "polygon_box", "dividers"]


def test_stage1_navigation_unchanged(window):
    assert window.stack.count() == len(NAV_ITEMS)
    for key, _ in NAV_ITEMS:
        window._nav_buttons[key].click()
        assert window.current_page_key() == key


def test_catalog_opens_box_page_and_back_button_returns(window):
    window._nav_buttons["generators"].click()
    gp = window._pages["generators"]
    assert gp.current_generator_key() is None
    gp.open_generator("rect_box")
    assert gp.current_generator_key() == "rect_box"
    box_page(window).back_requested.emit()
    assert gp.current_generator_key() is None
    assert window.stack.count() == len(NAV_ITEMS)  # nenhuma página extra no menu


def test_home_card_opens_box_generator(window):
    window.open_generator("rect_box")
    assert window.current_page_key() == "generators"
    assert window._pages["generators"].current_generator_key() == "rect_box"


def test_generate_with_defaults_draws_the_computed_layout(window):
    page = box_page(window)
    result = page.generate()
    assert result.ok
    assert page.viewer.layout_data is result.layout  # a vista usa a MESMA geometria calculada
    assert "Externas" in page.summary.text() and "100,00" in page.summary.text()
    assert len(result.layout.placed) == 6


def test_open_box_and_internal_mode_from_ui(window):
    page = box_page(window)
    page.type_combo.setCurrentIndex(page.type_combo.findData(BoxType.OPEN.value))
    page.mode_combo.setCurrentIndex(page.mode_combo.findData(DimensionMode.INTERNAL.value))
    result = page.generate()
    assert result.ok and len(result.layout.placed) == 5
    assert result.geometry.dimensions.int_width == 100.0


def test_decimal_comma_is_accepted(window):
    page = box_page(window)
    page.set_value("width", "120,5")
    assert page.generate().geometry.dimensions.ext_width == 120.5


@pytest.mark.parametrize("field,text", [("width", "abc"), ("width", "nan"), ("height", "-4"),
                                        ("thickness", "0"), ("depth", "inf")])
def test_invalid_input_shows_message_and_clears_preview(window, field, text):
    page = box_page(window)
    page.generate()
    page.set_value(field, text)
    page.generate()
    assert page.viewer.layout_data is None
    assert "Erro" in page.messages.text()
    assert page.summary.text() == ""


def test_incompatible_geometry_message_is_shown(window):
    page = box_page(window)
    page.set_value("width", "12")
    page.set_value("thickness", "5")
    page.generate()
    assert "Junta" in page.messages.text()


def test_manual_finger_count_enables_field_and_is_validated(window):
    page = box_page(window)
    assert not page.fields["finger_count"].isEnabled()
    page.finger_mode.setCurrentIndex(page.finger_mode.findData("manual"))
    assert page.fields["finger_count"].isEnabled()
    page.set_value("finger_count", "4")
    page.generate()
    assert "ímpar" in page.messages.text()
    page.set_value("finger_count", "7")
    assert page.generate().ok
    assert all(j.finger_count == 7 for j in page.last_result.geometry.joints)


def test_kerf_status_is_explicit_in_ui(window):
    page = box_page(window)
    page.generate()
    assert "sem compensação" in page.summary.text()
    page.set_value("kerf", "0,15")
    page.generate()
    assert "compensação ativa" in page.summary.text()


def test_workspace_overflow_is_reported(window):
    page = box_page(window)
    page.set_value("workspace_width", "120")
    page.set_value("workspace_height", "100")
    result = page.generate()
    assert not result.ok
    assert "não cabem" in page.messages.text()
    assert page.viewer.layout_data is result.layout   # peças continuam visíveis
    assert page.summary.text() == ""


def test_zoom_and_resize_do_not_fail(window, qapp):
    page = box_page(window)
    page.generate()
    v = page.viewer
    z0 = v.zoom
    v.zoom_in(); assert v.zoom > z0
    v.zoom_out(); v.zoom_out(); assert v.zoom < z0
    v.fit(); assert v.zoom == 1.0
    window._pages["generators"].open_generator("rect_box")
    for w, h in ((720, 480), (1400, 900)):
        window.resize(w, h)
        qapp.processEvents()
        v.grab()  # força paintEvent


def test_form_and_viewer_do_not_overlap_at_minimum_window_size(window, qapp):
    page = box_page(window)
    page.generate()
    window._pages["generators"].open_generator("rect_box")
    window.resize(window.minimumWidth(), window.minimumHeight())
    qapp.processEvents(); qapp.processEvents()
    splitter = page.findChildren(type(page.findChild(__import__("PySide6.QtWidgets", fromlist=["QSplitter"]).QSplitter)))[0]
    left, right = splitter.widget(0), splitter.widget(1)
    assert left.geometry().right() < right.geometry().left()
    assert right.width() >= page.viewer.minimumWidth()
