"""Exportador SVG (sem Qt). Consome o PanelLayout já calculado.

FORMATO PRODUZIDO
-----------------
* Unidade: milímetros. ``width`` e ``height`` são declarados com ``mm`` e o
  ``viewBox`` usa os MESMOS números (1 unidade de usuário = 1 mm). Não há
  atributo ``transform`` nem escala implícita.
* Coordenadas: origem no canto superior esquerdo do desenho, x para a direita,
  y para BAIXO (convenção do SVG; é a mesma da área de trabalho do projeto).
* Conversão: x_svg = x_layout + dx e y_svg = y_layout + dy, onde
  (dx, dy) = (margem_externa - x_min_usado, margem_externa - y_min_usado).
  É apenas uma TRANSLAÇÃO para que o desenho comece na margem externa; nenhuma
  medida muda. Valores são arredondados a 1e-6 mm (mesma grade do motor).
* Corte: um ``<path>`` fechado (M ... L ... Z) por painel, usando o
  ``cut_path`` do motor, que JÁ inclui a compensação de kerf (aplicada uma só
  vez). O exportador não recebe kerf e nunca desloca contornos.
* Grupos: ``corte`` (sempre), ``identificacao`` e ``auxiliares`` (opcionais,
  desligados por padrão), sempre separados do corte.
* Sem imagens, scripts, filtros, fontes externas ou ``<style>``; só atributos
  de apresentação simples.
"""
from __future__ import annotations

import math
import os
import re
import tempfile
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from xml.sax.saxutils import escape, quoteattr

from app.core.box_geometry import PanelId
from app.core.geometry import EPS, Contour, Point, snap
from app.core.layout import LayoutParameters, PanelLayout, PlacedPanel

SVG_NS = "http://www.w3.org/2000/svg"
_COLOR = re.compile(r"^#[0-9a-fA-F]{6}$")
MAX_MARGIN = 100.0


class ExportError(Exception):
    """Falha de exportação com mensagem em português para o usuário."""


class FileExistsExportError(ExportError):
    """O arquivo de destino já existe e a sobrescrita não foi autorizada."""


@dataclass(frozen=True)
class SvgExportOptions:
    include_labels: bool = False   # identificações (grupo separado)
    include_guides: bool = False   # linhas auxiliares (grupo separado)
    outer_margin: float = 5.0      # mm entre o desenho e a borda do SVG
    cut_color: str = "#FF0000"
    label_color: str = "#0000FF"
    guide_color: str = "#00A000"
    stroke_width: float = 0.1      # mm; só aparência (o LightBurn usa a camada)
    label_font_size: float = 4.0   # mm


@dataclass(frozen=True)
class SvgMetadata:
    title: str = "MDF Studio"
    kerf: float | None = None      # informativo: já aplicado no motor, se > 0
    clearance: float | None = None


@dataclass(frozen=True)
class SvgDocument:
    text: str
    width: float                   # mm (canvas inteiro, com margem externa)
    height: float
    offset: tuple[float, float]    # (dx, dy) da translação aplicada
    panel_count: int
    used_size: tuple[float, float]  # só as peças, sem margem externa

    def to_bytes(self) -> bytes:
        return self.text.encode("utf-8")


# ----------------------------------------------------------------- validação
def validate_options(o: SvgExportOptions) -> None:
    for name, v in (("margem externa", o.outer_margin), ("espessura do traço", o.stroke_width),
                    ("tamanho do texto", o.label_font_size)):
        if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v):
            raise ExportError(f"Opção inválida: {name} deve ser um número finito.")
    if not 0 <= o.outer_margin <= MAX_MARGIN:
        raise ExportError(f"A margem externa deve estar entre 0 e {MAX_MARGIN:g} mm.")
    if not 0.01 <= o.stroke_width <= 2:
        raise ExportError("A espessura do traço deve estar entre 0,01 e 2 mm.")
    if not 0.5 <= o.label_font_size <= 50:
        raise ExportError("O tamanho do texto deve estar entre 0,5 e 50 mm.")
    for name, c in (("de corte", o.cut_color), ("das identificações", o.label_color),
                    ("das linhas auxiliares", o.guide_color)):
        if not isinstance(c, str) or not _COLOR.match(c):
            raise ExportError(f"Cor {name} inválida: use o formato #RRGGBB.")


def _orient(a: Point, b: Point, c: Point) -> float:
    return (b.x - a.x) * (c.y - a.y) - (b.y - a.y) * (c.x - a.x)


def _on_segment(a: Point, b: Point, p: Point) -> bool:
    return (min(a.x, b.x) - EPS <= p.x <= max(a.x, b.x) + EPS
            and min(a.y, b.y) - EPS <= p.y <= max(a.y, b.y) + EPS)


def _segments_touch(a: Point, b: Point, c: Point, d: Point) -> bool:
    """True se os segmentos ab e cd têm algum ponto em comum."""
    o1, o2, o3, o4 = _orient(a, b, c), _orient(a, b, d), _orient(c, d, a), _orient(c, d, b)
    if ((o1 > EPS and o2 < -EPS) or (o1 < -EPS and o2 > EPS)) and \
       ((o3 > EPS and o4 < -EPS) or (o3 < -EPS and o4 > EPS)):
        return True
    return ((abs(o1) <= EPS and _on_segment(a, b, c)) or (abs(o2) <= EPS and _on_segment(a, b, d))
            or (abs(o3) <= EPS and _on_segment(c, d, a)) or (abs(o4) <= EPS and _on_segment(c, d, b)))


def _segment_key(p: Point, q: Point):
    a, b = (round(p.x * 1e6), round(p.y * 1e6)), (round(q.x * 1e6), round(q.y * 1e6))
    return (a, b) if a <= b else (b, a)


def validate_contour(label: str, contour: Contour) -> None:
    """Contorno fechado, finito, sem segmentos nulos/duplicados nem autointerseção."""
    pts = contour.points
    if any(not math.isfinite(v) for p in pts for v in p):
        raise ExportError(f"Painel {label}: contém coordenadas não finitas.")
    problems = contour.problems()
    if problems:
        raise ExportError(f"Painel {label}: contorno inválido ({problems[0]}).")
    n = len(pts)
    segs = [(pts[i], pts[(i + 1) % n]) for i in range(n)]
    keys = [_segment_key(a, b) for a, b in segs]
    if len(set(keys)) != n:
        raise ExportError(f"Painel {label}: contém segmentos duplicados.")
    for i in range(n):
        a, b = segs[i]
        nxt = segs[(i + 1) % n]
        # Vértices consecutivos: não podem dobrar de volta sobre si mesmos.
        if abs(_orient(a, b, nxt[1])) <= EPS and \
           (b.x - a.x) * (nxt[1].x - b.x) + (b.y - a.y) * (nxt[1].y - b.y) < 0:
            raise ExportError(f"Painel {label}: contorno dobra sobre si mesmo.")
        for j in range(i + 2, n):
            if i == 0 and j == n - 1:
                continue  # vizinhos pelo fechamento
            if _segments_touch(a, b, *segs[j]):
                raise ExportError(f"Painel {label}: contorno autointersectante.")


def validate_layout(layout: PanelLayout) -> None:
    """Valida o desenho inteiro antes de exportar. Lança ExportError."""
    if not layout.placed:
        raise ExportError("Não há painéis para exportar.")
    ids = [p.id for p in layout.placed]
    if len(set(ids)) != len(ids):
        raise ExportError("Há painéis duplicados no desenho.")
    boxes = []
    all_keys: set = set()
    for p in layout.placed:
        validate_contour(p.label, p.cut_path)
        for a, b in p.cut_path.segments():
            key = _segment_key(a, b)
            if key in all_keys:
                raise ExportError(f"Painel {p.label}: segmento coincide com o de outro painel.")
            all_keys.add(key)
        boxes.append((p.label, p.cut_path.bbox()))
    for i in range(len(boxes)):
        for j in range(i + 1, len(boxes)):
            (la, a), (lb, b) = boxes[i], boxes[j]
            separated = (a[2] < b[0] - EPS or b[2] < a[0] - EPS
                         or a[3] < b[1] - EPS or b[3] < a[1] - EPS)
            if not separated:
                raise ExportError(f"Os painéis {la} e {lb} se sobrepõem ou se tocam no desenho.")


# ----------------------------------------------------------------- geração
def _n(value: float) -> str:
    s = f"{value:.6f}".rstrip("0").rstrip(".")
    return "0" if s in ("", "-0") else s


def _path_d(contour: Contour, dx: float, dy: float) -> str:
    pts = [(snap(p.x + dx), snap(p.y + dy)) for p in contour.points]
    first, rest = pts[0], pts[1:]
    return (f"M {_n(first[0])},{_n(first[1])} "
            + " ".join(f"L {_n(x)},{_n(y)}" for x, y in rest) + " Z")


def build_svg(layout: PanelLayout, options: SvgExportOptions | None = None,
              metadata: SvgMetadata | None = None) -> SvgDocument:
    """Gera o SVG a partir do layout. Não modifica nem recalcula a geometria."""
    o = options or SvgExportOptions()
    meta = metadata or SvgMetadata()
    validate_options(o)
    validate_layout(layout)

    boxes = [p.cut_path.bbox() for p in layout.placed]
    x0, y0 = min(b[0] for b in boxes), min(b[1] for b in boxes)
    x1, y1 = max(b[2] for b in boxes), max(b[3] for b in boxes)
    dx, dy = snap(o.outer_margin - x0), snap(o.outer_margin - y0)
    used_w, used_h = snap(x1 - x0), snap(y1 - y0)
    width, height = snap(used_w + 2 * o.outer_margin), snap(used_h + 2 * o.outer_margin)
    if width <= 0 or height <= 0:
        raise ExportError("O desenho tem dimensão nula.")

    kerf_text = "não informado"
    if meta.kerf is not None:
        kerf_text = (f"já aplicado ao caminho de corte ({_n(meta.kerf)} mm; não aplique outro "
                     "offset no LightBurn)" if meta.kerf > 0 else "0 mm (sem compensação aplicada)")
    desc = [f"{meta.title}", "Unidade: milímetros (1 unidade de usuário = 1 mm).",
            "Origem no canto superior esquerdo; x para a direita, y para baixo.",
            f"Kerf: {kerf_text}.",
            "Potência, velocidade e passadas NÃO estão definidas neste arquivo: "
            "configure as operações no LightBurn."]
    if meta.clearance is not None:
        desc.insert(3, f"Folga de montagem usada na geometria: {_n(meta.clearance)} mm.")

    out = ['<?xml version="1.0" encoding="UTF-8"?>',
           f'<svg xmlns="{SVG_NS}" version="1.1" width="{_n(width)}mm" height="{_n(height)}mm" '
           f'viewBox="0 0 {_n(width)} {_n(height)}">',
           f"  <title>{escape(meta.title)}</title>",
           f"  <desc>{escape(chr(10).join(desc))}</desc>",
           f'  <g id="corte" fill="none" stroke="{o.cut_color}" stroke-width="{_n(o.stroke_width)}">']
    for p in layout.placed:
        out.append(f'    <path id="painel-{p.id.value}" d="{_path_d(p.cut_path, dx, dy)}"/>')
    out.append("  </g>")

    if o.include_guides:
        out.append(f'  <g id="auxiliares" fill="none" stroke="{o.guide_color}" '
                   f'stroke-width="{_n(o.stroke_width)}" stroke-dasharray="2 1">')
        for p in layout.placed:
            for a, b in p.reference_lines:
                out.append(f'    <path d="M {_n(snap(a.x + dx))},{_n(snap(a.y + dy))} '
                           f'L {_n(snap(b.x + dx))},{_n(snap(b.y + dy))}"/>')
        out.append("  </g>")

    if o.include_labels:
        out.append(f'  <g id="identificacao" fill="{o.label_color}" stroke="none" '
                   f'font-family="sans-serif" font-size="{_n(o.label_font_size)}" '
                   'text-anchor="middle">')
        for p, b in zip(layout.placed, boxes):
            cx, cy = snap((b[0] + b[2]) / 2 + dx), snap((b[1] + b[3]) / 2 + dy)
            text = f"{p.label} {p.width:.1f} x {p.height:.1f} mm"
            out.append(f'    <text id="rotulo-{p.id.value}" x="{_n(cx)}" '
                       f'y="{_n(snap(cy + o.label_font_size * 0.35))}">{escape(text)}</text>')
        out.append("  </g>")
    out.append("</svg>")
    return SvgDocument("\n".join(out) + "\n", width, height, (dx, dy),
                       len(layout.placed), (used_w, used_h))


# ----------------------------------------------------------------- gravação
def write_svg(path: str | os.PathLike, document: SvgDocument, overwrite: bool = False) -> Path:
    """Grava de forma atômica e CONFIRMA relendo o arquivo. Lança ExportError."""
    target = Path(path)
    if target.suffix == "":
        target = target.with_name(target.name + ".svg")
    elif target.suffix.lower() != ".svg":
        raise ExportError("O arquivo deve ter a extensão .svg.")
    parent = target.parent
    if target.is_dir():
        raise ExportError(f"“{target}” é uma pasta. Informe um nome de arquivo.")
    if not parent.is_dir():
        raise ExportError(f"A pasta “{parent}” não existe.")
    if target.exists() and not overwrite:
        raise FileExistsExportError(f"O arquivo “{target.name}” já existe.")

    data = document.to_bytes()
    tmp_name = None
    try:
        fd, tmp_name = tempfile.mkstemp(dir=parent, prefix=".mdfstudio-", suffix=".tmp")
        with os.fdopen(fd, "wb") as fh:
            fh.write(data)
            fh.flush()
            os.fsync(fh.fileno())
        try:  # mkstemp cria 0600; usa as permissões normais do usuário
            umask = os.umask(0)
            os.umask(umask)
            os.chmod(tmp_name, 0o666 & ~umask)
        except OSError:
            pass
        os.replace(tmp_name, target)
        tmp_name = None
    except PermissionError:
        raise ExportError(f"Sem permissão para gravar em “{parent}”.") from None
    except OSError as exc:
        raise ExportError(f"Falha ao gravar o arquivo: {exc.strerror or exc}.") from None
    finally:
        if tmp_name and os.path.exists(tmp_name):
            try:
                os.remove(tmp_name)
            except OSError:
                pass

    try:
        written = target.read_bytes()
        ET.fromstring(written)
    except (OSError, ET.ParseError):
        raise ExportError("O arquivo foi gravado, mas não pôde ser relido e validado.") from None
    if written != data:
        raise ExportError("O conteúdo gravado não confere com o esperado. "
                          "Tente novamente em outra pasta.")
    return target


# ------------------------------------------------- quadrado de referência
def reference_square_layout(size: float = 100.0) -> PanelLayout:
    """Layout de um quadrado exato `size` x `size` mm, para conferir a escala."""
    if not math.isfinite(size) or size <= 0:
        raise ExportError("O tamanho do quadrado de referência deve ser positivo.")
    pts = (Point(0.0, 0.0), Point(snap(size), 0.0), Point(snap(size), snap(size)),
           Point(0.0, snap(size)))
    c = Contour(pts)
    label = f"Referencia {size:g} x {size:g} mm"
    placed = PlacedPanel(PanelId.BASE, label, size, size, c, c, c.bbox(), ())
    return PanelLayout((placed,), LayoutParameters(), c.bbox(), True, ())


def build_reference_svg(size: float = 100.0, options: SvgExportOptions | None = None) -> SvgDocument:
    opts = options or SvgExportOptions(outer_margin=0.0)
    return build_svg(reference_square_layout(size), opts,
                     SvgMetadata(title=f"MDF Studio - teste de escala {size:g} x {size:g} mm"))
