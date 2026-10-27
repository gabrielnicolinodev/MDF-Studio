"""Regressão: o gerador de caixa retangular e o exportador NÃO mudaram na Etapa 04.

Valores de referência registrados a partir dos módulos originais (que não foram
alterados). Se algum deles mudar, a caixa retangular foi modificada.
"""
import hashlib

import pytest

from app.core.box_parameters import BoxParameters, BoxType
from app.export.svg_exporter import SvgExportOptions, build_svg
from app.generators.box_generator import BoxGenerator


def test_closed_box_geometry_is_unchanged():
    g = BoxGenerator().generate(BoxParameters()).geometry
    got = [(p.id.value, len(p.contour.points), p.contour.area()) for p in g.panels]
    want = [("base", 76, 7546.3031), ("top", 76, 7546.3031), ("front", 60, 4550.7636),
            ("back", 60, 4550.7636), ("left", 52, 3558.9333), ("right", 52, 3558.9333)]
    assert [(a, b) for a, b, _ in got] == [(a, b) for a, b, _ in want]
    assert [c for *_, c in got] == pytest.approx([c for *_, c in want], abs=1e-3)
    assert [j.finger_count for j in g.joints] == [11, 11, 9, 9, 11, 11, 9, 9, 5, 5, 5, 5]


def test_open_box_with_kerf_geometry_is_unchanged():
    g = BoxGenerator().generate(BoxParameters(box_type=BoxType.OPEN, kerf=0.15, clearance=0.1,
                                              finger_count=7)).geometry
    got = [(p.id.value, len(p.contour.points), p.contour.area()) for p in g.panels]
    want = [("base", 52, 7566.2), ("front", 44, 4698.5), ("back", 44, 4698.5),
            ("left", 40, 3692.65), ("right", 40, 3692.65)]
    assert [(a, b) for a, b, _ in got] == [(a, b) for a, b, _ in want]
    assert [c for *_, c in got] == pytest.approx([c for *_, c in want], abs=1e-3)


def test_original_box_svg_is_byte_identical_to_the_reference():
    opts = SvgExportOptions(include_labels=True, include_guides=True)
    closed = build_svg(BoxGenerator().generate(BoxParameters()).layout, opts)
    assert (closed.width, closed.height) == (320.0, 145.0)
    assert hashlib.sha256(closed.text.encode()).hexdigest().startswith("7d5cb30bd35c022c")
    opened = build_svg(BoxGenerator().generate(BoxParameters(
        box_type=BoxType.OPEN, kerf=0.15, clearance=0.1, finger_count=7)).layout, opts)
    assert hashlib.sha256(opened.text.encode()).hexdigest().startswith("d1d8669c699d5159")
