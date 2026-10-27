"""Caixa retangular com TAMPA DESLIZANTE (módulo independente do gerador de caixa).

CONSTRUÇÃO (6 peças, só cortes 2D vazados)
------------------------------------------
Eixos: x = largura W, y = profundidade D (FRENTE em y=0), z = altura H (base em z=0).
t = espessura, c = folga da tampa, r = altura do trilho, s = largura do batente.

* Fundo (W x D), Traseira (W x H), Frente (W x zf) e Laterais (D x H) têm finger
  joints com a mesma lógica da caixa retangular (juntas, folga e kerf reutilizados).
* A FRENTE é mais baixa: zf = H - r - t - c. Seu topo é o PISO da canaleta, e a
  tampa passa por cima dele ao entrar.
* CANALETA: cada lateral recebe um rasgo vazado, aberto na aresta da frente:
      y de 0 até ys = D - t - s,   z de zf até zf + t + c   (altura da canaleta = t + c)
  A lateral fica com um trilho (z de zf+t+c até H) preso ao corpo pela PONTE traseira
  (y de ys até D-t, sem rasgo), de modo que a lateral continua sendo UM contorno fechado.
* TAMPA: placa de espessura t, largura W - c, plano z de zf + c/2 até zf + c/2 + t.
  Suas "orelhas" (x de c/2 até t e de W-t até W-c/2) correm dentro dos rasgos das
  laterais; o corpo central cobre o interior. Cantos traseiros têm recorte (t de largura)
  para passar pela ponte. Entra pela FRENTE e desliza até o batente traseiro.
  Só um vazado 2D pode ser cortado a laser: não existe ranhura "cega". Por isso a
  tampa fica presa na vertical (trilho e corpo da lateral) mas tem folga lateral
  enquanto desliza; fechada, a ponte a centraliza (folga c/2 de cada lado).
* Kerf: igual à caixa retangular (contorno nominal + caminho de corte deslocado k/2,
  uma única vez). A tampa usa o id de painel TOP (rótulo "Tampa deslizante").
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

from app.core.box_geometry import PANEL_LABELS, Edge, Panel, PanelFrame, PanelId
from app.core.box_parameters import BoxParameters, BoxType, DimensionMode
from app.core.geometry import EPS, Contour, offset_rectilinear, rect_minus_rects, snap
from app.core.joints import (
    MIN_FINGER_WIDTH,
    EdgeRef,
    Joint,
    Owner,
    build_finger_joint,
    complement_intervals,
    narrowed_tabs,
)
from app.core.sliding_box_parameters import (
    SLIDING_LABELS,
    SLIDING_LIMITS,
    SlidingLidBoxParameters,
)
from app.core.validation import (
    GeometryError,
    Severity,
    ValidationIssue,
    has_errors,
    validate_parameters,
)

LID_LABEL = "Tampa deslizante"
MIN_SLOT_LENGTH = 10.0   # mm, comprimento mínimo da canaleta
_ORDER = (PanelId.BASE, PanelId.FRONT, PanelId.BACK, PanelId.LEFT, PanelId.RIGHT, PanelId.TOP)


@dataclass(frozen=True)
class SlidingDimensions:
    ext_width: float
    ext_depth: float
    ext_height: float       # altura das laterais
    int_width: float
    int_depth: float
    int_height: float       # do topo da base ao piso da canaleta
    thickness: float
    front_height: float     # zf: altura da frente (= piso da canaleta)
    channel_height: float    # t + c
    rail_height: float
    stop_width: float
    slot_end: float         # ys
    lid_clearance: float
    lid_width: float
    lid_length: float       # parte central
    lid_max_length: float
    lid_ear_length: float
    lid_notch_depth: float
    lid_z: float            # z da face inferior da tampa


@dataclass(frozen=True)
class SlidingBoxGeometry:
    params: SlidingLidBoxParameters
    dimensions: SlidingDimensions
    panels: tuple[Panel, ...]
    joints: tuple[Joint, ...]
    issues: tuple[ValidationIssue, ...] = field(default_factory=tuple)

    @property
    def kerf_active(self) -> bool:
        return self.params.kerf > 0

    def panel(self, pid: PanelId) -> Panel:
        for p in self.panels:
            if p.id is pid:
                return p
        raise KeyError(pid)


# ------------------------------------------------------------------ validação
def _num(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def validate_sliding_parameters(p: SlidingLidBoxParameters) -> list[ValidationIssue]:
    """Tipos, finitude e limites. Reutiliza a validação da caixa para os campos comuns."""
    issues = validate_parameters(BoxParameters(
        width=p.width, depth=p.depth, height=p.height, thickness=p.thickness,
        dimension_mode=p.dimension_mode, box_type=BoxType.OPEN, joint_type=p.joint_type,
        finger_count=p.finger_count, clearance=p.clearance, kerf=p.kerf))

    def err(field_name: str, msg: str) -> None:
        issues.append(ValidationIssue(Severity.ERROR, field_name, msg))

    t_ok = _num(p.thickness) and p.thickness > 0
    for name in ("lid_clearance", "rail_height", "stop_width", "lid_length"):
        value = getattr(p, name)
        label = SLIDING_LABELS[name]
        lo, hi = SLIDING_LIMITS[name]
        if value is None and name != "lid_clearance":
            continue                                    # automático
        if not _num(value):
            err(name, f"{label}: informe um número finito (NaN e infinito não são aceitos).")
        elif value < lo or value > hi:
            err(name, f"{label}: deve estar entre {lo:g} e {hi:g} mm (recebido {value:g}).")
        elif t_ok and name in ("rail_height", "stop_width") and value < p.thickness:
            err(name, f"{label}: não pode ser menor que a espessura ({p.thickness:g} mm).")
        elif t_ok and name == "lid_clearance" and value > p.thickness:
            err(name, f"{label}: deve ser menor que a espessura ({p.thickness:g} mm), "
                      "senão as orelhas da tampa ficam finas demais.")
    return issues


# ----------------------------------------------------------------- dimensões
def compute_sliding_dimensions(p: SlidingLidBoxParameters) -> SlidingDimensions:
    t, c = p.thickness, p.lid_clearance
    r = p.rail_height if p.rail_height is not None else 2.0 * t
    s = p.stop_width if p.stop_width is not None else 2.0 * t
    if p.dimension_mode is DimensionMode.EXTERNAL:
        ew, ed, eh = p.width, p.depth, p.height
        zf = eh - r - t - c
    else:
        ew, ed = p.width + 2 * t, p.depth + 2 * t
        zf = t + p.height
        eh = zf + t + c + r
    ys = ed - t - s
    lid_max = ed - t - c
    lid_len = p.lid_length if p.lid_length is not None else lid_max
    ear = min(lid_len, ys - c)
    return SlidingDimensions(
        ext_width=ew, ext_depth=ed, ext_height=eh,
        int_width=ew - 2 * t, int_depth=ed - 2 * t, int_height=zf - t,
        thickness=t, front_height=zf, channel_height=t + c, rail_height=r, stop_width=s,
        slot_end=ys, lid_clearance=c, lid_width=ew - c, lid_length=lid_len,
        lid_max_length=lid_max, lid_ear_length=ear, lid_notch_depth=lid_len - ear,
        lid_z=zf + c / 2.0)


def _check_dimensions(d: SlidingDimensions) -> None:
    t = d.thickness
    min_front = t + 3 * MIN_FINGER_WIDTH
    if d.front_height < min_front - EPS:
        raise GeometryError(
            f"A altura é pequena demais: a frente ficaria com {d.front_height:.2f} mm "
            f"(mínimo {min_front:.2f} mm para as juntas). Aumente a altura ou reduza o "
            "trilho, a folga da tampa ou a espessura.", field="height")
    if min(d.int_width, d.int_depth, d.int_height) <= 0:
        raise GeometryError("As dimensões são pequenas demais para a espessura escolhida.")
    if d.slot_end < MIN_SLOT_LENGTH - EPS:
        raise GeometryError(
            f"A canaleta ficaria com {d.slot_end:.2f} mm de comprimento (mínimo "
            f"{MIN_SLOT_LENGTH:g} mm). Aumente a profundidade ou reduza o batente traseiro.",
            field="depth")
    if d.lid_length > d.lid_max_length + EPS:
        raise GeometryError(
            f"Comprimento da tampa: no máximo {d.lid_max_length:.2f} mm para esta profundidade.",
            field="lid_length")
    if d.lid_width - 2 * t <= EPS:
        raise GeometryError("A largura é pequena demais para a tampa.", field="width")


# ----------------------------------------------------------------- geometria
def _plan_joints(p: SlidingLidBoxParameters, d: SlidingDimensions) -> list[Joint]:
    t, W, D = d.thickness, d.ext_width, d.ext_depth
    label = PANEL_LABELS
    joints: list[Joint] = []
    for face_edge, wall, length in ((Edge.BOTTOM, PanelId.FRONT, W), (Edge.TOP, PanelId.BACK, W),
                                    (Edge.LEFT, PanelId.LEFT, D), (Edge.RIGHT, PanelId.RIGHT, D)):
        joints.append(build_finger_joint(
            f"{label[PanelId.BASE]}–{label[wall]}",
            EdgeRef(PanelId.BASE.value, face_edge.value), EdgeRef(wall.value, Edge.BOTTOM.value),
            length, t, Owner.A, Owner.A, p.finger_count))
    # Verticais: topo livre (caixa aberta em cima). Frente só tem altura zf.
    for wall, wall_edge, side, side_edge, length in (
        (PanelId.FRONT, Edge.LEFT, PanelId.LEFT, Edge.LEFT, d.front_height),
        (PanelId.FRONT, Edge.RIGHT, PanelId.RIGHT, Edge.LEFT, d.front_height),
        (PanelId.BACK, Edge.LEFT, PanelId.LEFT, Edge.RIGHT, d.ext_height),
        (PanelId.BACK, Edge.RIGHT, PanelId.RIGHT, Edge.RIGHT, d.ext_height),
    ):
        joints.append(build_finger_joint(
            f"{label[wall]}–{label[side]}",
            EdgeRef(wall.value, wall_edge.value), EdgeRef(side.value, side_edge.value),
            length, t, Owner.NEUTRAL, None, p.finger_count))
    return joints


def _edge_rects(width: float, height: float, t: float,
                edge_notches: dict[Edge, list[tuple[float, float]]]):
    rects = []
    for edge, intervals in edge_notches.items():
        for s0, s1 in intervals:
            if edge is Edge.BOTTOM:
                rects.append((s0, 0.0, s1, t))
            elif edge is Edge.TOP:
                rects.append((s0, height - t, s1, height))
            elif edge is Edge.LEFT:
                rects.append((0.0, s0, t, s1))
            else:
                rects.append((width - t, s0, width, s1))
    return rects


def _frames(d: SlidingDimensions) -> dict[PanelId, PanelFrame]:
    t = d.thickness
    return {
        PanelId.BASE: PanelFrame((0, 0, 0), (1, 0, 0), (0, 1, 0), (0, 0, 1)),
        PanelId.FRONT: PanelFrame((0, 0, 0), (1, 0, 0), (0, 0, 1), (0, 1, 0)),
        PanelId.BACK: PanelFrame((0, d.ext_depth - t, 0), (1, 0, 0), (0, 0, 1), (0, 1, 0)),
        PanelId.LEFT: PanelFrame((0, 0, 0), (0, 1, 0), (0, 0, 1), (1, 0, 0)),
        PanelId.RIGHT: PanelFrame((d.ext_width - t, 0, 0), (0, 1, 0), (0, 0, 1), (1, 0, 0)),
        PanelId.TOP: PanelFrame((d.lid_clearance / 2.0, 0, d.lid_z), (1, 0, 0), (0, 1, 0), (0, 0, 1)),
    }


def _extent(pid: PanelId, d: SlidingDimensions) -> tuple[float, float]:
    if pid is PanelId.BASE:
        return d.ext_width, d.ext_depth
    if pid is PanelId.FRONT:
        return d.ext_width, d.front_height
    if pid is PanelId.BACK:
        return d.ext_width, d.ext_height
    if pid is PanelId.TOP:
        return d.lid_width, d.lid_length
    return d.ext_depth, d.ext_height


def build_sliding_box_geometry(p: SlidingLidBoxParameters) -> SlidingBoxGeometry:
    """Gera a geometria completa. Lança GeometryError se inválida ou inviável."""
    problems = validate_sliding_parameters(p)
    if has_errors(problems):
        raise GeometryError(problems[0].message, field=problems[0].field)
    d = compute_sliding_dimensions(p)
    _check_dimensions(d)
    t = d.thickness
    joints = _plan_joints(p, d)

    notches: dict[PanelId, dict[Edge, list[tuple[float, float]]]] = {pid: {} for pid in _ORDER}
    for joint in joints:
        for side, ref in ((Owner.A, joint.a), (Owner.B, joint.b)):
            tabs = narrowed_tabs(joint.tab_intervals(side), joint.length, p.clearance, joint.name)
            notches[PanelId(ref.panel)][Edge(ref.edge)] = complement_intervals(tabs, joint.length)

    frames = _frames(d)
    panels: list[Panel] = []
    for pid in _ORDER:
        w, h = _extent(pid, d)
        if pid is PanelId.TOP:
            rects = []
            if d.lid_notch_depth > EPS:   # recortes traseiros que passam pela ponte
                rects = [(0.0, d.lid_ear_length, t, h), (w - t, d.lid_ear_length, w, h)]
            label = LID_LABEL
        else:
            rects = _edge_rects(w, h, t, notches[pid])
            if pid in (PanelId.LEFT, PanelId.RIGHT):   # canaleta vazada, aberta na frente
                rects.append((0.0, d.front_height, d.slot_end, d.front_height + d.channel_height))
            label = PANEL_LABELS[pid]
        try:
            contour = rect_minus_rects(w, h, rects)
        except GeometryError as exc:
            raise GeometryError(f"Painel {label}: {exc}") from None
        bad = contour.problems()
        if bad:
            raise GeometryError(f"Painel {label} inválido: {bad[0]}.")
        cut = offset_rectilinear(contour, p.kerf / 2.0) if p.kerf > 0 else contour
        panels.append(Panel(pid, label, w, h, t, contour, cut, frames[pid],
                            tuple(notches[pid].keys())))
    return SlidingBoxGeometry(p, d, tuple(panels), tuple(joints),
                              tuple(_collect_notes(p, d, joints)))


def _collect_notes(p: SlidingLidBoxParameters, d: SlidingDimensions,
                   joints: list[Joint]) -> list[ValidationIssue]:
    out: list[ValidationIssue] = []
    min_w = min(j.finger_width for j in joints)
    if min_w < d.thickness:
        out.append(ValidationIssue(
            Severity.WARNING, "finger_count",
            f"Há dedos mais estreitos ({min_w:.2f} mm) que a espessura ({d.thickness:g} mm); "
            "podem ficar frágeis no MDF."))
    if (p.kerf > 0 or p.clearance > 0) and min_w < 4 * (p.kerf + p.clearance):
        raise GeometryError(
            f"Kerf ({p.kerf:g} mm) e folga ({p.clearance:g} mm) são grandes demais para a "
            f"largura de dedo de {min_w:.2f} mm. Reduza-os ou use dedos mais largos.", field="kerf")
    if d.lid_length < d.lid_max_length - EPS:
        out.append(ValidationIssue(
            Severity.WARNING, "lid_length",
            f"A tampa é {d.lid_max_length - d.lid_length:.1f} mm mais curta que o máximo: "
            "com ela fechada sobra uma abertura nos fundos da caixa."))
    if d.rail_height < 2 * d.thickness - EPS:
        out.append(ValidationIssue(
            Severity.WARNING, "rail_height",
            f"Trilho de {d.rail_height:g} mm (menos que 2× a espessura): fino e flexível no MDF."))
    ear = d.thickness - d.lid_clearance / 2.0
    if ear < 1.5:
        out.append(ValidationIssue(
            Severity.WARNING, "lid_clearance",
            f"As orelhas da tampa ficam com {ear:.2f} mm de largura: frágeis."))
    out.append(ValidationIssue(
        Severity.INFO, "lid",
        "A tampa entra pela FRENTE, por cima da frente baixa, e desliza nas canaletas das "
        "laterais até o batente traseiro. Teste o deslizamento num corte de prova."))
    if p.kerf > 0:
        out.append(ValidationIssue(
            Severity.INFO, "kerf",
            f"Compensação de kerf ativa: o caminho de corte está {p.kerf / 2:g} mm para fora "
            "do contorno nominal. Não aplique outra compensação no LightBurn."))
    else:
        out.append(ValidationIssue(
            Severity.INFO, "kerf", "Kerf = 0: nenhuma compensação aplicada ao caminho de corte."))
    return out
