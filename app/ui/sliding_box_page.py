"""Página do gerador de caixa com tampa deslizante.

Reaproveita toda a página da caixa retangular (formulário, prévia 2D, exportação SVG)
e acrescenta apenas a seção da tampa.
"""
from __future__ import annotations

from PySide6.QtWidgets import QWidget

from app.core.box_parameters import FIELD_LABELS, DimensionMode
from app.core.sliding_box_parameters import (
    SLIDING_LABELS,
    SLIDING_LIMITS,
    SlidingLidBoxParameters,
)
from app.core.validation import Severity, ValidationIssue, parse_number
from app.generators.sliding_box_generator import SlidingLidBoxGenerator
from app.ui.box_generator_page import BoxGeneratorPage, _fmt

_AUTO_WORDS = ("", "auto", "automático", "automatico")


class SlidingLidBoxPage(BoxGeneratorPage):
    TITLE = "Caixa com tampa deslizante"
    FILE_PREFIX = "caixa_tampa_deslizante"
    HAS_BOX_TYPE = False

    def __init__(self, export_dir_provider=None, parent=None) -> None:
        super().__init__(generator=SlidingLidBoxGenerator(),
                         export_dir_provider=export_dir_provider, parent=parent)
        # A base preenche os campos comuns com os padrões da caixa retangular.
        self.set_value("height", _fmt(SlidingLidBoxParameters().height))

    def _build_extra_sections(self) -> list[QWidget]:
        defaults = SlidingLidBoxParameters()
        frame, form, outer = self._section("Tampa deslizante")
        form.addRow("Folga da tampa (mm)", self._line(
            "lid_clearance", _fmt(defaults.lid_clearance, 2),
            "Folga de deslizamento: vertical total e lateral total"))
        form.addRow("Comprimento da tampa (mm)", self._line(
            "lid_length", "auto", "“auto” = o máximo que cabe; ou informe um valor menor"))
        form.addRow("Altura do trilho (mm)", self._line(
            "rail_height", "auto", "Material acima da canaleta; “auto” = 2 × espessura"))
        form.addRow("Batente traseiro (mm)", self._line(
            "stop_width", "auto", "Ponte que prende o trilho e para a tampa; “auto” = 2 × espessura"))
        outer.addWidget(self._hint(
            "A tampa entra pela frente e desliza em canaletas (rasgos vazados) nas duas "
            "laterais, até o batente traseiro. A frente é mais baixa para a tampa passar. "
            "“Altura” é a das laterais (modo externo) ou a altura livre até o piso da "
            "canaleta (modo interno). Corte uma peça de teste para ajustar a folga da tampa."))
        return [frame]

    def _read_optional(self, name: str, errors: list[ValidationIssue]) -> float | None:
        text = self.fields[name].text().strip().lower()
        if text in _AUTO_WORDS:
            return None
        try:
            return parse_number(text)
        except ValueError:
            errors.append(ValidationIssue(
                Severity.ERROR, name,
                f"{SLIDING_LABELS[name]}: valor inválido “{self.fields[name].text()}” "
                "(use um número ou “auto”)."))
            return float("nan")

    def _make_parameters(self, values: dict, finger_count, errors):
        lid_clearance = self._read_number("lid_clearance", SLIDING_LABELS["lid_clearance"], errors)
        return SlidingLidBoxParameters(
            dimension_mode=DimensionMode(self.mode_combo.currentData()),
            finger_count=finger_count, lid_clearance=lid_clearance,
            rail_height=self._read_optional("rail_height", errors),
            stop_width=self._read_optional("stop_width", errors),
            lid_length=self._read_optional("lid_length", errors),
            **values)

    def _extra_summary_rows(self, s) -> list[str]:
        mm = lambda v: _fmt(v, 2)
        rows = [
            f"<b>Tampa:</b> {mm(s.lid_size[0])} × {mm(s.lid_size[1])} mm "
            f"(folga {mm(s.lid_clearance)} mm)",
            f"<b>Canaleta:</b> {mm(s.channel_height)} mm de altura; trilho {mm(s.rail_height)} mm; "
            f"batente traseiro {mm(s.stop_width)} mm",
            f"<b>Frente:</b> altura {mm(s.front_height)} mm (piso da canaleta); "
            "a tampa entra por cima dela",
        ]
        if s.open_gap_at_back > 0:
            rows.append(f"<b>Atenção:</b> com a tampa fechada sobra uma abertura de "
                        f"{mm(s.open_gap_at_back)} mm nos fundos.")
        return rows
