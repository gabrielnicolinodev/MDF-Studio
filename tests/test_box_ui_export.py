import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication

import app.export.svg_exporter as svg_mod
from app.storage.settings_store import SettingsStore
from app.ui.main_window import MainWindow
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
    page = win._pages["generators"].box_page
    asked = []
    page.choose_save_path = lambda initial: (asked.append(initial), None)[1]   # padrão: cancela
    return win, page, export_dir, asked


def choose(page, path):
    page.choose_save_path = lambda initial: str(path)


def status(page):
    return page.export_status.text()


def test_export_requires_a_generated_valid_project(env):
    _, page, export_dir, _ = env
    assert page.export_svg() is None
    assert "gere um projeto válido" in status(page)
    assert os.listdir(export_dir) == []


def test_successful_export_writes_a_verified_svg_with_the_real_geometry(env):
    _, page, export_dir, asked = env
    result = page.generate()
    target = export_dir / "minha_caixa.svg"
    choose(page, target)
    written = page.export_svg()
    assert written == target and target.exists()
    root = parse_svg(target.read_bytes())
    assert parse_mm(root.get("width")) > 300
    assert len(cut_paths(root)) == 6
    assert "Arquivo gravado e verificado" in status(page) and "LightBurn" in status(page)
    # as mesmas coordenadas do layout mostrado na tela
    pts, _ = cut_paths(root)["painel-base"]
    base = next(p for p in result.layout.placed if p.id.value == "base")
    assert len(pts) == len(base.cut_path.points)


def test_dialog_starts_in_the_configured_export_folder_with_a_default_name(env):
    _, page, export_dir, asked = env
    page.generate()
    page.export_svg()                                    # chooser padrão do fixture: cancela
    assert asked == [str(export_dir / "caixa_100x80x50mm.svg")]


def test_dialog_falls_back_to_home_when_export_folder_does_not_exist(env, tmp_path):
    win, page, export_dir, asked = env
    win._settings["export_dir"] = str(tmp_path / "nao_existe")
    page.generate()
    page.export_svg()
    assert os.path.dirname(asked[0]) == os.path.expanduser("~")
    assert not (tmp_path / "nao_existe").exists()        # não cria pastas sozinho


def test_cancelled_dialog_writes_nothing_and_says_so(env):
    _, page, export_dir, _ = env
    page.generate()
    assert page.export_svg() is None
    assert "cancelada" in status(page) and os.listdir(export_dir) == []


def test_existing_file_requires_confirmation(env):
    _, page, export_dir, _ = env
    page.generate()
    target = export_dir / "a.svg"
    target.write_text("ORIGINAL")
    choose(page, target)
    page.confirm_overwrite = lambda path: False
    assert page.export_svg() is None
    assert target.read_text() == "ORIGINAL" and "não foi alterado" in status(page)
    page.confirm_overwrite = lambda path: True
    assert page.export_svg() == target
    assert target.read_text().startswith("<?xml")


def test_extension_is_added_when_user_types_a_bare_name(env):
    _, page, export_dir, _ = env
    page.generate()
    choose(page, export_dir / "sem_extensao")
    assert page.export_svg().name == "sem_extensao.svg"


def test_missing_directory_error_is_shown_and_success_is_not_claimed(env, tmp_path):
    _, page, _, _ = env
    page.generate()
    choose(page, tmp_path / "fantasma" / "a.svg")
    assert page.export_svg() is None
    assert "Erro ao exportar" in status(page) and "não existe" in status(page)
    assert "gravado" not in status(page)


def test_write_failure_is_shown_and_success_is_not_claimed(env, monkeypatch):
    _, page, export_dir, _ = env
    page.generate()
    choose(page, export_dir / "a.svg")
    monkeypatch.setattr(svg_mod.os, "replace", lambda *a, **k: (_ for _ in ()).throw(PermissionError()))
    assert page.export_svg() is None
    assert "permissão" in status(page) and "gravado" not in status(page)
    assert os.listdir(export_dir) == []


def test_changed_parameters_block_export_until_regenerated(env):
    _, page, export_dir, _ = env
    page.generate()
    page.set_value("width", "120")
    choose(page, export_dir / "a.svg")
    assert page.export_svg() is None
    assert "Gerar projeto" in status(page) and os.listdir(export_dir) == []
    page.generate()
    assert page.export_svg() is not None


def test_invalid_project_cannot_be_exported(env):
    _, page, export_dir, _ = env
    page.set_value("width", "nan")
    page.generate()
    choose(page, export_dir / "a.svg")
    assert page.export_svg() is None and os.listdir(export_dir) == []


def test_workspace_overflow_blocks_export(env):
    _, page, export_dir, _ = env
    page.set_value("workspace_width", "120")
    page.set_value("workspace_height", "100")
    page.generate()
    choose(page, export_dir / "a.svg")
    assert page.export_svg() is None and os.listdir(export_dir) == []


def test_labels_and_guides_checkboxes_reach_the_file(env):
    _, page, export_dir, _ = env
    page.generate()
    choose(page, export_dir / "plain.svg")
    page.export_svg()
    plain = (export_dir / "plain.svg").read_text(encoding="utf-8")
    assert "identificacao" not in plain and "auxiliares" not in plain
    page.labels_check.setChecked(True)
    page.guides_check.setChecked(True)
    choose(page, export_dir / "full.svg")
    page.export_svg()
    full = (export_dir / "full.svg").read_text(encoding="utf-8")
    assert 'id="identificacao"' in full and 'id="auxiliares"' in full


def test_margin_field_changes_file_size_and_info_label(env):
    _, page, export_dir, _ = env
    page.generate()
    info5 = page.export_info.text()
    page.set_value("export_margin", "20")
    page._update_export_info()
    assert page.export_info.text() != info5 and "não o da chapa" in page.export_info.text()
    choose(page, export_dir / "m.svg")
    page.export_svg()
    root = parse_svg((export_dir / "m.svg").read_bytes())
    assert parse_mm(root.get("width")) == pytest.approx(
        page.last_result.layout.used_width + 40, abs=1e-5)


def test_invalid_margin_is_reported(env):
    _, page, export_dir, _ = env
    page.generate()
    page.set_value("export_margin", "abc")
    choose(page, export_dir / "a.svg")
    assert page.export_svg() is None and "Margem externa" in status(page)
    page.set_value("export_margin", "-3")
    assert page.export_svg() is None and os.listdir(export_dir) == []


def test_dimensions_are_shown_before_saving(env):
    _, page, _, _ = env
    assert "Gere" in page.export_info.text()
    page.generate()
    assert "Arquivo SVG:" in page.export_info.text() and "mm" in page.export_info.text()


def test_scale_reference_export_is_exactly_100_mm(env):
    _, page, export_dir, asked = env
    choose(page, export_dir / "teste_escala_100x100mm.svg")
    assert page.export_scale_reference() is not None             # não exige projeto gerado
    root = parse_svg((export_dir / "teste_escala_100x100mm.svg").read_bytes())
    assert root.get("width") == "100mm" and root.get("viewBox") == "0 0 100 100"


def test_export_section_warns_about_lightburn_operations(env):
    from PySide6.QtWidgets import QLabel
    _, page, _, _ = env
    texts = [l.text() for l in page.findChildren(QLabel)]
    assert any("LightBurn" in t and "potência" in t and "passadas" in t for t in texts)
