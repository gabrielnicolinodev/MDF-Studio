"""Página de configuração do gerador de caixas retangulares."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Callable

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QFileDialog,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from app.core.box_parameters import (
    FIELD_LABELS,
    LIMITS,
    BoxParameters,
    BoxType,
    DimensionMode,
)
from app.core.layout import LAYOUT_LABELS, LayoutParameters
from app.core.validation import Severity, ValidationIssue, parse_number
from app.export.svg_exporter import (
    ExportError,
    SvgDocument,
    SvgExportOptions,
    SvgMetadata,
    build_reference_svg,
    build_svg,
    write_svg,
)
from app.generators.box_generator import BoxGenerator, BoxResult
from app.ui.panel_viewer import PanelViewer


def _fmt(value: float, digits: int = 1) -> str:
    return f"{value:.{digits}f}".replace(".", ",")


class BoxGeneratorPage(QWidget):
    back_requested = Signal()

    def __init__(self, generator: BoxGenerator | None = None,
                 export_dir_provider: Callable[[], str | None] | None = None,
                 parent=None) -> None:
        super().__init__(parent)
        self._generator = generator or BoxGenerator()
        self._export_dir_provider = export_dir_provider
        self._last_export_dir: str | None = None
        # Pontos de injeção (diálogos): substituíveis em testes.
        self.choose_save_path: Callable[[str], str | None] = self._qt_choose_save_path
        self.confirm_overwrite: Callable[[str], bool] = self._qt_confirm_overwrite
        self.last_result: BoxResult | None = None
        self.fields: dict[str, QLineEdit] = {}

        root = QVBoxLayout(self)
        root.setContentsMargins(20, 16, 20, 16)
        root.setSpacing(12)

        top = QHBoxLayout()
        back = QPushButton("← Geradores")
        back.clicked.connect(self.back_requested.emit)
        title = QLabel("Caixa retangular")
        title.setObjectName("pageTitle")
        top.addWidget(back)
        top.addWidget(title, 1)
        root.addLayout(top)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)
        splitter.addWidget(self._build_form())
        splitter.addWidget(self._build_preview())
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([320, 640])
        root.addWidget(splitter, 1)

    # --- construção da interface ------------------------------------------
    def _line(self, name: str, text: str, tip: str = "") -> QLineEdit:
        edit = QLineEdit(text)
        edit.setAlignment(Qt.AlignmentFlag.AlignRight)
        edit.setToolTip(tip)
        edit.returnPressed.connect(self.generate)
        self.fields[name] = edit
        return edit

    @staticmethod
    def _section(title: str):
        frame = QFrame()
        frame.setObjectName("card")
        outer = QVBoxLayout(frame)
        outer.setContentsMargins(16, 12, 16, 14)
        outer.setSpacing(8)
        label = QLabel(title)
        label.setObjectName("sectionTitle")
        outer.addWidget(label)
        form = QFormLayout()
        form.setSpacing(8)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        # Rótulo acima do campo: a coluna do formulário é estreita e rótulos são longos.
        form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapAllRows)
        outer.addLayout(form)
        return frame, form, outer

    @staticmethod
    def _hint(text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("cardText")
        label.setWordWrap(True)
        return label

    def _build_form(self) -> QWidget:
        defaults = BoxParameters()
        content = QWidget()
        content.setObjectName("pageRoot")
        col = QVBoxLayout(content)
        col.setContentsMargins(0, 0, 8, 0)
        col.setSpacing(12)

        # Dimensões
        frame, form, outer = self._section("Dimensões (mm)")
        self.mode_combo = QComboBox()
        self.mode_combo.addItem("Medidas externas", DimensionMode.EXTERNAL.value)
        self.mode_combo.addItem("Medidas internas", DimensionMode.INTERNAL.value)
        form.addRow("Modo", self.mode_combo)
        self.type_combo = QComboBox()
        self.type_combo.addItem("Fechada (com tampa)", BoxType.CLOSED.value)
        self.type_combo.addItem("Aberta (sem tampa)", BoxType.OPEN.value)
        form.addRow("Tipo de caixa", self.type_combo)
        for name, value in (("width", defaults.width), ("depth", defaults.depth),
                            ("height", defaults.height)):
            lo, hi = LIMITS[name]
            form.addRow(FIELD_LABELS[name],
                        self._line(name, _fmt(value), f"Entre {lo:g} e {hi:g} mm"))
        form.addRow("Espessura", self._line("thickness", _fmt(defaults.thickness),
                                            "Espessura REAL medida do material"))
        outer.addWidget(self._hint(
            "A espessura nominal do MDF (ex.: 3 mm) costuma diferir da real. "
            "Meça a chapa com paquímetro em vários pontos e informe o valor medido."))
        col.addWidget(frame)

        # Encaixes
        frame, form, outer = self._section("Encaixes (finger joint)")
        self.finger_mode = QComboBox()
        self.finger_mode.addItem("Número de dedos automático", "auto")
        self.finger_mode.addItem("Número de dedos definido", "manual")
        self.finger_mode.currentIndexChanged.connect(self._sync_finger_field)
        form.addRow("Dedos", self.finger_mode)
        form.addRow("Segmentos por junta (ímpar)", self._line(
            "finger_count", "9", "Número ímpar de segmentos úteis em cada junta (3 a 99)"))
        form.addRow("Folga de montagem (mm)", self._line(
            "clearance", _fmt(defaults.clearance, 2), "Folga total entre dente e encaixe"))
        form.addRow("Kerf (mm)", self._line(
            "kerf", _fmt(defaults.kerf, 2), "Largura removida pelo laser; 0 = sem compensação"))
        outer.addWidget(self._hint(
            "Folga e kerf são coisas diferentes: a folga afeta o ajuste entre as peças; "
            "o kerf desloca o caminho de corte para fora em metade do valor (0 = desligado). "
            "Não use compensação de kerf aqui e no LightBurn ao mesmo tempo. "
            "Calibre com um corte de teste: não há garantia de ajuste perfeito sem isso."))
        col.addWidget(frame)

        # Disposição
        frame, form, outer = self._section("Disposição das peças")
        lp = LayoutParameters()
        form.addRow("Espaçamento (mm)", self._line("spacing", _fmt(lp.spacing)))
        form.addRow("Área de trabalho larg. (mm)",
                    self._line("workspace_width", _fmt(lp.workspace_width, 0)))
        form.addRow("Área de trabalho alt. (mm)",
                    self._line("workspace_height", _fmt(lp.workspace_height, 0)))
        self.reference_check = QCheckBox("Mostrar linhas de referência")
        self.reference_check.setChecked(True)
        self.reference_check.toggled.connect(lambda on: self.viewer.set_show_reference(on))
        outer.addWidget(self.reference_check)
        outer.addWidget(self._hint(
            "As linhas de referência existem só na visualização e nunca entram no "
            "caminho de corte. A área de trabalho é só uma referência de disposição, "
            "não a chapa real."))
        col.addWidget(frame)

        self.generate_button = QPushButton("Gerar projeto")
        self.generate_button.setObjectName("primary")
        self.generate_button.clicked.connect(self.generate)
        col.addWidget(self.generate_button)

        # Exportação SVG
        frame, form, outer = self._section("Exportação SVG")
        form.addRow("Margem externa do SVG (mm)", self._line(
            "export_margin", "5", "Espaço entre as peças e a borda do desenho"))
        self.labels_check = QCheckBox("Incluir identificações")
        self.guides_check = QCheckBox("Incluir linhas auxiliares")
        outer.addWidget(self.labels_check)
        outer.addWidget(self.guides_check)
        outer.addWidget(self._hint(
            "Identificações e linhas auxiliares vão em grupos separados do corte "
            "(desligados por padrão). O espaçamento entre peças é o definido em "
            "“Disposição das peças”."))
        self.export_info = self._hint("Gere o projeto para ver as dimensões do arquivo.")
        outer.addWidget(self.export_info)
        self.export_button = QPushButton("Exportar SVG…")
        self.export_button.setObjectName("primary")
        self.export_button.clicked.connect(self.export_svg)
        self.scale_button = QPushButton("Teste de escala 100×100")
        self.scale_button.clicked.connect(self.export_scale_reference)
        outer.addWidget(self.export_button)
        outer.addWidget(self.scale_button)
        self.export_status = QLabel("")
        self.export_status.setWordWrap(True)
        self.export_status.setTextFormat(Qt.TextFormat.RichText)
        outer.addWidget(self.export_status)
        outer.addWidget(self._hint(
            "Confira as operações de corte (potência, velocidade e passadas) no "
            "LightBurn antes de cortar: o SVG não define essas configurações."))
        col.addWidget(frame)
        self.fields["export_margin"].editingFinished.connect(self._update_export_info)
        col.addStretch(1)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setMinimumWidth(250)
        scroll.setWidget(content)
        self._sync_finger_field()
        return scroll

    def _build_preview(self) -> QWidget:
        wrap = QWidget()
        col = QVBoxLayout(wrap)
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(8)

        bar = QHBoxLayout()
        for text, slot in (("＋", lambda: self.viewer.zoom_in()),
                           ("－", lambda: self.viewer.zoom_out()),
                           ("Ajustar", lambda: self.viewer.fit())):
            btn = QPushButton(text)
            btn.clicked.connect(slot)
            bar.addWidget(btn)
        bar.addStretch(1)
        col.addLayout(bar)

        self.viewer = PanelViewer()
        col.addWidget(self.viewer, 3)

        self.messages = QLabel("")
        self.messages.setWordWrap(True)
        self.messages.setTextFormat(Qt.TextFormat.RichText)
        self.summary = QLabel("")
        self.summary.setWordWrap(True)
        self.summary.setTextFormat(Qt.TextFormat.RichText)
        self.summary.setAlignment(Qt.AlignmentFlag.AlignTop)
        info = QWidget()
        info_col = QVBoxLayout(info)
        info_col.setContentsMargins(0, 0, 8, 0)
        info_col.addWidget(self.messages)
        info_col.addWidget(self.summary)
        info_col.addStretch(1)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(info)
        scroll.setMinimumHeight(110)
        col.addWidget(scroll, 2)
        return wrap

    def _sync_finger_field(self) -> None:
        self.fields["finger_count"].setEnabled(self.finger_mode.currentData() == "manual")

    # --- leitura e geração ------------------------------------------------
    def set_value(self, name: str, text: str) -> None:
        self.fields[name].setText(text)

    def _read_number(self, name: str, label: str, errors: list[ValidationIssue]) -> float:
        try:
            return parse_number(self.fields[name].text())
        except ValueError:
            errors.append(ValidationIssue(
                Severity.ERROR, name, f"{label}: valor inválido “{self.fields[name].text()}”."))
            return float("nan")

    def read_inputs(self):
        """Devolve (BoxParameters, LayoutParameters, erros de leitura)."""
        errors: list[ValidationIssue] = []
        values = {n: self._read_number(n, FIELD_LABELS[n], errors)
                  for n in ("width", "depth", "height", "thickness", "clearance", "kerf")}
        finger_count = None
        if self.finger_mode.currentData() == "manual":
            raw = self._read_number("finger_count", FIELD_LABELS["finger_count"], errors)
            if raw == raw and raw == int(raw):
                finger_count = int(raw)
            elif raw == raw:
                errors.append(ValidationIssue(
                    Severity.ERROR, "finger_count",
                    "Número de dedos: informe um número inteiro."))
        lp_values = {n: self._read_number(n, LAYOUT_LABELS[n], errors)
                     for n in ("spacing", "workspace_width", "workspace_height")}
        params = BoxParameters(
            # O Qt devolve o valor (str) do combo; convertemos de volta ao enum.
            dimension_mode=DimensionMode(self.mode_combo.currentData()),
            box_type=BoxType(self.type_combo.currentData()),
            finger_count=finger_count, **values)
        return params, LayoutParameters(**lp_values), errors

    def generate(self) -> BoxResult | None:
        params, layout_params, read_errors = self.read_inputs()
        if read_errors:
            self.last_result = None
            self._show_failure(read_errors)
            self._update_export_info()
            return None
        result = self._generator.generate(params, layout_params)
        self.last_result = result
        if result.geometry is None:
            self._show_failure(list(result.issues))
            self._update_export_info()
            return result
        # Com a geometria calculada mostramos as peças mesmo que não caibam na área
        # de trabalho (assim o excesso fica visível); o resumo só existe se ok.
        self.viewer.set_layout(result.layout)
        self._show_messages(result.issues)
        if result.ok:
            self._show_summary(result)
        else:
            self.summary.setText("")
        self._update_export_info()
        return result

    # --- apresentação dos resultados -------------------------------------
    def _show_failure(self, issues) -> None:
        self.viewer.set_layout(None)
        self.summary.setText("")
        self._show_messages(issues)

    def _show_messages(self, issues) -> None:
        colors = {Severity.ERROR: "#f87171", Severity.WARNING: "#fbbf24", Severity.INFO: "#8b919d"}
        prefix = {Severity.ERROR: "Erro", Severity.WARNING: "Aviso", Severity.INFO: "Info"}
        lines = [f'<span style="color:{colors[i.severity]}"><b>{prefix[i.severity]}:</b> '
                 f'{i.message}</span>' for i in issues]
        self.messages.setText("<br>".join(lines))

    def _show_summary(self, result: BoxResult) -> None:
        s = self._generator.summarize(result)
        mm = lambda v: _fmt(v, 2)
        rows = [
            f"<b>Externas:</b> {mm(s.external[0])} × {mm(s.external[1])} × {mm(s.external[2])} mm",
            f"<b>Internas:</b> {mm(s.internal[0])} × {mm(s.internal[1])} × {mm(s.internal[2])} mm",
            f"<b>Espessura:</b> {mm(s.thickness)} mm &nbsp; <b>Folga:</b> {mm(s.clearance)} mm "
            f"&nbsp; <b>Kerf:</b> {mm(s.kerf)} mm "
            f"({'compensação ativa' if s.kerf_active else 'sem compensação'})",
            f"<b>Peças ({len(s.panels)}):</b> "
            + "; ".join(f"{p.label} {mm(p.width)} × {mm(p.height)}" for p in s.panels),
            f"<b>Conjunto:</b> {mm(s.used_size[0])} × {mm(s.used_size[1])} mm "
            f"na área de trabalho de {_fmt(s.workspace[0], 0)} × {_fmt(s.workspace[1], 0)} mm",
            f"<b>Área das peças:</b> {_fmt(s.panels_area / 100, 1)} cm² "
            f"(caixa-limite do conjunto: {_fmt(s.bbox_area / 100, 1)} cm²)",
            "<b>Dedos:</b> " + "; ".join(
                f"{j.name}: {j.finger_count} × {mm(j.finger_width)} mm" for j in s.joints[:4]
            ) + " …",
        ]
        self.summary.setText("<br>".join(rows))

    # --- exportação SVG ---------------------------------------------------
    def _qt_choose_save_path(self, initial: str) -> str | None:
        path, _ = QFileDialog.getSaveFileName(
            self, "Exportar SVG", initial, "SVG (*.svg)",
            options=QFileDialog.Option.DontConfirmOverwrite)
        return path or None

    def _qt_confirm_overwrite(self, path: str) -> bool:
        answer = QMessageBox.question(
            self, "Arquivo já existe",
            f"O arquivo “{Path(path).name}” já existe. Deseja substituí-lo?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No)
        return answer == QMessageBox.StandardButton.Yes

    def _set_export_status(self, text: str, level: str) -> None:
        colors = {"ok": "#6ee7a0", "error": "#f87171", "info": "#8b919d"}
        self.export_status.setText(f'<span style="color:{colors[level]}">{text}</span>')

    def _read_export_options(self) -> SvgExportOptions:
        try:
            margin = parse_number(self.fields["export_margin"].text())
        except ValueError:
            raise ExportError(
                f"Margem externa: valor inválido “{self.fields['export_margin'].text()}”.") from None
        return SvgExportOptions(include_labels=self.labels_check.isChecked(),
                                include_guides=self.guides_check.isChecked(),
                                outer_margin=margin)

    def _metadata(self, result: BoxResult) -> SvgMetadata:
        d = result.geometry.dimensions
        return SvgMetadata(
            title=(f"MDF Studio - Caixa retangular {_fmt(d.ext_width)} x "
                   f"{_fmt(d.ext_depth)} x {_fmt(d.ext_height)} mm (externas)"),
            kerf=result.params.kerf, clearance=result.params.clearance)

    def _update_export_info(self) -> None:
        """Mostra as dimensões do arquivo ANTES de salvar."""
        result = self.last_result
        if result is None or not result.ok:
            self.export_info.setText("Gere um projeto válido para ver as dimensões do arquivo.")
            return
        try:
            doc = build_svg(result.layout, self._read_export_options(), self._metadata(result))
        except ExportError as exc:
            self.export_info.setText(f"Não é possível exportar: {exc}")
            return
        self.export_info.setText(
            f"Arquivo SVG: {_fmt(doc.width, 2)} × {_fmt(doc.height, 2)} mm "
            f"(peças: {_fmt(doc.used_size[0], 2)} × {_fmt(doc.used_size[1], 2)} mm, mais a margem "
            "externa). É o tamanho do desenho, não o da chapa de MDF.")

    def _initial_directory(self) -> str:
        for candidate in (self._last_export_dir,
                          self._export_dir_provider() if self._export_dir_provider else None):
            if candidate and os.path.isdir(candidate):
                return candidate
        return str(Path.home())

    @staticmethod
    def _num_name(value: float) -> str:
        return f"{value:g}"

    def default_file_name(self, result: BoxResult) -> str:
        d = result.geometry.dimensions
        return (f"caixa_{self._num_name(d.ext_width)}x{self._num_name(d.ext_depth)}"
                f"x{self._num_name(d.ext_height)}mm.svg")

    def _save_document(self, doc: SvgDocument, file_name: str) -> Path | None:
        """Pergunta o destino, confirma sobrescrita e grava. Mostra o resultado."""
        initial = os.path.join(self._initial_directory(), file_name)
        chosen = self.choose_save_path(initial)
        if not chosen:
            self._set_export_status("Exportação cancelada. Nenhum arquivo foi gravado.", "info")
            return None
        target = Path(chosen)
        if target.suffix == "":
            target = target.with_name(target.name + ".svg")
        if target.exists() and not self.confirm_overwrite(str(target)):
            self._set_export_status("Exportação cancelada. O arquivo existente não foi alterado.",
                                    "info")
            return None
        try:
            written = write_svg(target, doc, overwrite=True)
        except ExportError as exc:
            self._set_export_status(f"<b>Erro ao exportar:</b> {exc}", "error")
            return None
        self._last_export_dir = str(written.parent)
        self._set_export_status(
            f"<b>Arquivo gravado e verificado:</b> {written} — {_fmt(doc.width, 2)} × "
            f"{_fmt(doc.height, 2)} mm. Antes de cortar, importe no LightBurn, confira as medidas "
            "e configure potência, velocidade e passadas.", "ok")
        return written

    def export_svg(self) -> Path | None:
        result = self.last_result
        if result is None or not result.ok:
            self._set_export_status(
                "<b>Erro:</b> gere um projeto válido (sem erros) antes de exportar.", "error")
            return None
        params, layout_params, read_errors = self.read_inputs()
        if read_errors or params != result.params or layout_params != result.layout_params:
            self._set_export_status(
                "<b>Erro:</b> os parâmetros foram alterados desde a última geração. "
                "Clique em “Gerar projeto” antes de exportar, para que o arquivo "
                "corresponda ao que está na tela.", "error")
            return None
        try:
            doc = build_svg(result.layout, self._read_export_options(), self._metadata(result))
        except ExportError as exc:
            self._set_export_status(f"<b>Erro:</b> {exc}", "error")
            return None
        return self._save_document(doc, self.default_file_name(result))

    def export_scale_reference(self) -> Path | None:
        """Exporta um quadrado 100 x 100 mm para conferir a escala no LightBurn."""
        try:
            doc = build_reference_svg(100.0)
        except ExportError as exc:
            self._set_export_status(f"<b>Erro:</b> {exc}", "error")
            return None
        return self._save_document(doc, "teste_escala_100x100mm.svg")
