import os
import stat

import pytest

import app.export.svg_exporter as svg_mod
from app.core.box_parameters import BoxParameters
from app.export.svg_exporter import (
    ExportError, FileExistsExportError, build_reference_svg, build_svg, write_svg,
)
from app.generators.box_generator import BoxGenerator
from tests.svg_helpers import cut_paths, parse_svg


@pytest.fixture
def doc():
    return build_svg(BoxGenerator().generate(BoxParameters()).layout)


def leftovers(folder):
    return [f for f in os.listdir(folder) if f.startswith(".mdfstudio-")]


def test_write_creates_file_identical_to_the_document(tmp_path, doc):
    target = write_svg(tmp_path / "caixa.svg", doc)
    assert target.read_bytes() == doc.to_bytes()
    assert cut_paths(parse_svg(target.read_bytes()))          # relido e parseável
    assert leftovers(tmp_path) == []


def test_extension_is_appended_when_missing(tmp_path, doc):
    assert write_svg(tmp_path / "caixa", doc).name == "caixa.svg"


def test_wrong_extension_is_rejected_and_nothing_is_written(tmp_path, doc):
    with pytest.raises(ExportError, match=".svg"):
        write_svg(tmp_path / "caixa.txt", doc)
    assert os.listdir(tmp_path) == []


def test_missing_directory_is_reported(tmp_path, doc):
    with pytest.raises(ExportError, match="não existe"):
        write_svg(tmp_path / "nao_existe" / "a.svg", doc)


def test_target_that_is_a_directory_is_reported(tmp_path, doc):
    (tmp_path / "pasta.svg").mkdir()
    with pytest.raises(ExportError, match="pasta"):
        write_svg(tmp_path / "pasta.svg", doc)


def test_existing_file_is_never_overwritten_silently(tmp_path, doc):
    target = tmp_path / "a.svg"
    target.write_text("ORIGINAL")
    with pytest.raises(FileExistsExportError):
        write_svg(target, doc)
    assert target.read_text() == "ORIGINAL"
    write_svg(target, doc, overwrite=True)                       # só com autorização explícita
    assert target.read_bytes() == doc.to_bytes()


def test_permission_error_is_reported_and_original_is_untouched(tmp_path, doc, monkeypatch):
    target = tmp_path / "a.svg"
    target.write_text("ORIGINAL")

    def deny(*a, **k):
        raise PermissionError("negado")
    monkeypatch.setattr(svg_mod.os, "replace", deny)
    with pytest.raises(ExportError, match="permissão"):
        write_svg(target, doc, overwrite=True)
    assert target.read_text() == "ORIGINAL"
    assert leftovers(tmp_path) == []                             # sem temporário órfão


def test_generic_os_error_is_reported(tmp_path, doc, monkeypatch):
    def boom(*a, **k):
        raise OSError(28, "No space left on device")
    monkeypatch.setattr(svg_mod.os, "fsync", boom)
    with pytest.raises(ExportError, match="Falha ao gravar"):
        write_svg(tmp_path / "a.svg", doc)
    assert not (tmp_path / "a.svg").exists() and leftovers(tmp_path) == []


@pytest.mark.skipif(os.geteuid() == 0 if hasattr(os, "geteuid") else True,
                    reason="root ignora permissões de pasta")
def test_read_only_directory_is_reported(tmp_path, doc):
    tmp_path.chmod(stat.S_IRUSR | stat.S_IXUSR)
    try:
        with pytest.raises(ExportError, match="permissão"):
            write_svg(tmp_path / "a.svg", doc)
    finally:
        tmp_path.chmod(stat.S_IRWXU)


def test_corrupted_write_is_detected_by_readback(tmp_path, doc, monkeypatch):
    real_replace = os.replace

    def corrupt(src, dst):
        with open(src, "ab") as fh:
            fh.write(b"lixo")
        real_replace(src, dst)
    monkeypatch.setattr(svg_mod.os, "replace", corrupt)
    with pytest.raises(ExportError):                              # XML inválido ou conteúdo diferente
        write_svg(tmp_path / "a.svg", doc)


def test_reference_svg_roundtrip_on_disk(tmp_path):
    target = write_svg(tmp_path / "teste_escala_100x100mm.svg", build_reference_svg())
    root = parse_svg(target.read_bytes())
    assert root.get("width") == "100mm" and root.get("height") == "100mm"
