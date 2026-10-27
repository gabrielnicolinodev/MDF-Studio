"""Modelo geométrico da caixa retangular com finger joints.

CONVENÇÃO GEOMÉTRICA (milímetros)
---------------------------------
Mundo 3D: x = largura (0..W), y = profundidade (0..D, a FRENTE está em y=0),
z = altura (0..H, a BASE está em z=0). W, D, H são as medidas EXTERNAS.

Cada painel é uma placa de espessura `t` cujo retângulo externo cobre toda a
face da caixa (retângulo cheio), com recortes de profundidade `t` nas arestas
de junta:

    base/tampa    W x D   (u=x, v=y)      base: z em [0,t]; tampa: z em [H-t,H]
    frente/trás   W x H   (u=x, v=z)      frente: y em [0,t]; trás: y em [D-t,D]
    laterais      D x H   (u=y, v=z)      esq.: x em [0,t]; dir.: x em [W-t,W]

Sistema local de cada painel: origem no canto inferior esquerdo, u para a
direita, v para cima, sentido anti-horário (área > 0). O dicionário
`PanelFrame` mapeia (u, v, s) para o mundo: ponto = origem + u*u_axis +
v*v_axis + s*normal, com s em [0, t].

Medidas internas: externas menos 2t em x e y; em z, menos 2t (fechada) ou menos
t (aberta, sem tampa). No modo "internas", as externas = internas + 2t (idem).

Posse dos cantos: os 4 cantos de baixo (e os de cima, se fechada) pertencem à
base/tampa; nas juntas verticais esses trechos são NEUTROS (recorte nos dois
painéis). Nas juntas verticais, frente e traseira têm os dentes das pontas;
numa caixa aberta o topo da junta vertical é livre (sem zona de canto).

KERF: o contorno `contour` é sempre o NOMINAL (dimensões da peça). O
`cut_path` é o caminho de corte deslocado para fora por kerf/2 (igual ao
nominal quando kerf = 0). O deslocamento é aplicado uma única vez, aqui.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from app.core.box_parameters import BoxParameters, BoxType, DimensionMode
from app.core.geometry import Contour, offset_rectilinear, rect_minus_rects
from app.core.joints import (
    EdgeRef,
    Joint,
    Owner,
    build_finger_joint,
    complement_intervals,
    narrowed_tabs,
)
from app.core.validation import (
    GeometryError,
    Severity,
    ValidationIssue,
    has_errors,
    validate_parameters,
)


class PanelId(str, Enum):
    BASE = "base"
    TOP = "top"
    FRONT = "front"
    BACK = "back"
    LEFT = "left"
    RIGHT = "right"


class Edge(str, Enum):
    BOTTOM = "bottom"  # v = 0
    TOP = "top"        # v = altura do painel
    LEFT = "left"      # u = 0
    RIGHT = "right"    # u = largura do painel


PANEL_LABELS = {
    PanelId.BASE: "Base",
    PanelId.TOP: "Tampa",
    PanelId.FRONT: "Frente",
    PanelId.BACK: "Traseira",
    PanelId.LEFT: "Lateral esquerda",
    PanelId.RIGHT: "Lateral direita",
}

_CLOSED_ORDER = (PanelId.BASE, PanelId.TOP, PanelId.FRONT, PanelId.BACK,
                 PanelId.LEFT, PanelId.RIGHT)
_OPEN_ORDER = (PanelId.BASE, PanelId.FRONT, PanelId.BACK, PanelId.LEFT, PanelId.RIGHT)


@dataclass(frozen=True)
class BoxDimensions:
    ext_width: float
    ext_depth: float
    ext_height: float
    int_width: float
    int_depth: float
    int_height: float
    thickness: float


@dataclass(frozen=True)
class PanelFrame:
    origin: tuple[float, float, float]
    u_axis: tuple[int, int, int]
    v_axis: tuple[int, int, int]
    normal: tuple[int, int, int]


@dataclass(frozen=True)
class Panel:
    id: PanelId
    label: str
    width: float          # extensão em u (retângulo externo)
    height: float         # extensão em v
    thickness: float
    contour: Contour      # contorno NOMINAL (coordenadas locais)
    cut_path: Contour     # caminho de corte (nominal + kerf/2); == contour se kerf=0
    frame: PanelFrame
    joint_edges: tuple[Edge, ...]  # arestas com junta (para linhas de referência)


@dataclass(frozen=True)
class BoxGeometry:
    params: BoxParameters
    dimensions: BoxDimensions
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


def compute_dimensions(p: BoxParameters) -> BoxDimensions:
    t = p.thickness
    closed = p.box_type is BoxType.CLOSED
    z_loss = 2 * t if closed else t
    if p.dimension_mode is DimensionMode.EXTERNAL:
        ew, ed, eh = p.width, p.depth, p.height
        iw, idp, ih = ew - 2 * t, ed - 2 * t, eh - z_loss
    else:
        iw, idp, ih = p.width, p.depth, p.height
        ew, ed, eh = iw + 2 * t, idp + 2 * t, ih + z_loss
    return BoxDimensions(ew, ed, eh, iw, idp, ih, t)


def _panel_extent(pid: PanelId, d: BoxDimensions) -> tuple[float, float]:
    if pid in (PanelId.BASE, PanelId.TOP):
        return d.ext_width, d.ext_depth
    if pid in (PanelId.FRONT, PanelId.BACK):
        return d.ext_width, d.ext_height
    return d.ext_depth, d.ext_height


def _panel_frame(pid: PanelId, d: BoxDimensions) -> PanelFrame:
    t = d.thickness
    if pid is PanelId.BASE:
        return PanelFrame((0, 0, 0), (1, 0, 0), (0, 1, 0), (0, 0, 1))
    if pid is PanelId.TOP:
        return PanelFrame((0, 0, d.ext_height - t), (1, 0, 0), (0, 1, 0), (0, 0, 1))
    if pid is PanelId.FRONT:
        return PanelFrame((0, 0, 0), (1, 0, 0), (0, 0, 1), (0, 1, 0))
    if pid is PanelId.BACK:
        return PanelFrame((0, d.ext_depth - t, 0), (1, 0, 0), (0, 0, 1), (0, 1, 0))
    if pid is PanelId.LEFT:
        return PanelFrame((0, 0, 0), (0, 1, 0), (0, 0, 1), (1, 0, 0))
    return PanelFrame((d.ext_width - t, 0, 0), (0, 1, 0), (0, 0, 1), (1, 0, 0))


def _edge_length(edge: Edge, width: float, height: float) -> float:
    return width if edge in (Edge.BOTTOM, Edge.TOP) else height


def plan_joints(p: BoxParameters, d: BoxDimensions) -> list[Joint]:
    """Define explicitamente todas as juntas (quem une com quem e como)."""
    t = d.thickness
    closed = p.box_type is BoxType.CLOSED
    joints: list[Joint] = []

    def label(pid: PanelId) -> str:
        return PANEL_LABELS[pid]

    # Juntas horizontais: base (e tampa) com as quatro paredes. A face é dona dos cantos.
    faces = [(PanelId.BASE, Edge.BOTTOM)] + ([(PanelId.TOP, Edge.TOP)] if closed else [])
    for face, wall_edge in faces:
        for face_edge, wall, length in (
            (Edge.BOTTOM, PanelId.FRONT, d.ext_width),
            (Edge.TOP, PanelId.BACK, d.ext_width),
            (Edge.LEFT, PanelId.LEFT, d.ext_depth),
            (Edge.RIGHT, PanelId.RIGHT, d.ext_depth),
        ):
            joints.append(build_finger_joint(
                f"{label(face)}–{label(wall)}",
                EdgeRef(face.value, face_edge.value), EdgeRef(wall.value, wall_edge.value),
                length, t, Owner.A, Owner.A, p.finger_count))

    # Juntas verticais: frente/traseira com laterais. Cantos de baixo (e de cima) são neutros.
    end_zone = Owner.NEUTRAL if closed else None
    for wall, wall_edge, side, side_edge in (
        (PanelId.FRONT, Edge.LEFT, PanelId.LEFT, Edge.LEFT),
        (PanelId.FRONT, Edge.RIGHT, PanelId.RIGHT, Edge.LEFT),
        (PanelId.BACK, Edge.LEFT, PanelId.LEFT, Edge.RIGHT),
        (PanelId.BACK, Edge.RIGHT, PanelId.RIGHT, Edge.RIGHT),
    ):
        joints.append(build_finger_joint(
            f"{label(wall)}–{label(side)}",
            EdgeRef(wall.value, wall_edge.value), EdgeRef(side.value, side_edge.value),
            d.ext_height, t, Owner.NEUTRAL, end_zone, p.finger_count))
    return joints


def _notch_rects(pid: PanelId, width: float, height: float, t: float,
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


def build_box_geometry(p: BoxParameters) -> BoxGeometry:
    """Gera a geometria completa. Lança GeometryError se inviável/inválida."""
    problems = validate_parameters(p)
    if has_errors(problems):
        raise GeometryError(problems[0].message, field=problems[0].field)

    d = compute_dimensions(p)
    t = d.thickness
    if min(d.int_width, d.int_depth, d.int_height) <= 0:
        raise GeometryError(
            "As dimensões são pequenas demais para a espessura escolhida: o vão "
            f"interno ficaria {min(d.int_width, d.int_depth, d.int_height):.2f} mm.")

    joints = plan_joints(p, d)
    order = _CLOSED_ORDER if p.box_type is BoxType.CLOSED else _OPEN_ORDER

    # Recortes por (painel, aresta), calculados a partir dos dentes de cada lado.
    notches: dict[PanelId, dict[Edge, list[tuple[float, float]]]] = {pid: {} for pid in order}
    for joint in joints:
        for side, ref in ((Owner.A, joint.a), (Owner.B, joint.b)):
            pid, edge = PanelId(ref.panel), Edge(ref.edge)
            tabs = narrowed_tabs(joint.tab_intervals(side), joint.length,
                                 p.clearance, joint.name)
            notches[pid][edge] = complement_intervals(tabs, joint.length)

    panels = []
    for pid in order:
        w, h = _panel_extent(pid, d)
        for edge, intervals in notches[pid].items():
            assert abs(_edge_length(edge, w, h) - next(
                j.length for j in joints
                for r in (j.a, j.b) if (r.panel, r.edge) == (pid.value, edge.value))) < 1e-6
        rects = _notch_rects(pid, w, h, t, notches[pid])
        contour = rect_minus_rects(w, h, rects)
        bad = contour.problems()
        if bad:
            raise GeometryError(f"Painel {PANEL_LABELS[pid]} inválido: {bad[0]}.")
        cut = offset_rectilinear(contour, p.kerf / 2.0) if p.kerf > 0 else contour
        panels.append(Panel(pid, PANEL_LABELS[pid], w, h, t, contour, cut,
                            _panel_frame(pid, d), tuple(notches[pid].keys())))

    issues = _collect_warnings(p, joints, t)
    return BoxGeometry(p, d, tuple(panels), tuple(joints), tuple(issues))


def _collect_warnings(p: BoxParameters, joints: list[Joint], t: float) -> list[ValidationIssue]:
    out: list[ValidationIssue] = []
    min_w = min(j.finger_width for j in joints)
    if min_w < t:
        out.append(ValidationIssue(
            Severity.WARNING, "finger_count",
            f"Há dedos mais estreitos ({min_w:.2f} mm) que a espessura ({t:g} mm); "
            "podem ficar frágeis no MDF."))
    if p.kerf > 0 or p.clearance > 0:
        # Sem esta checagem, kerf/folga grandes corromperiam os dentes.
        if min_w < 4 * (p.kerf + p.clearance):
            raise GeometryError(
                f"Kerf ({p.kerf:g} mm) e folga ({p.clearance:g} mm) são grandes demais "
                f"para a largura de dedo de {min_w:.2f} mm. Reduza-os ou use dedos mais largos.",
                field="kerf")
    if p.kerf > 0:
        out.append(ValidationIssue(
            Severity.INFO, "kerf",
            f"Compensação de kerf ativa: o caminho de corte está {p.kerf / 2:g} mm "
            "para fora do contorno nominal. Não aplique outra compensação no LightBurn."))
    else:
        out.append(ValidationIssue(
            Severity.INFO, "kerf",
            "Kerf = 0: nenhuma compensação aplicada ao caminho de corte."))
    return out
