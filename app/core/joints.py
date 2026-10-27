"""Juntas tipo finger joint (definição explícita, independente de Qt).

Uma junta liga a aresta `a` de um painel à aresta `b` de outro e tem um
comprimento `length`. Ao longo da junta (coordenada s, de 0 a length) há
SEGMENTOS, cada um com um dono:

* ``A`` / ``B``: o painel dono tem material (dente); o outro tem recorte
  de profundidade igual à espessura.
* ``NEUTRAL``: cubo de canto pertencente a um TERCEIRO painel; ambos os
  painéis da junta têm recorte ali.

Convenção de dentes: nas extremidades há "zonas" de comprimento igual à
espessura (cantos); a região útil restante é dividida em N segmentos iguais
(N ímpar >= 3) alternando A, B, A, ..., A. Assim os dentes têm largura igual,
sem sobras de arredondamento.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from app.core.geometry import EPS, snap
from app.core.validation import GeometryError

MIN_FINGER_WIDTH = 2.0  # mm, largura mínima de um dedo


class Owner(str, Enum):
    A = "A"
    B = "B"
    NEUTRAL = "neutral"


@dataclass(frozen=True)
class EdgeRef:
    panel: str   # valor de PanelId
    edge: str    # valor de Edge


@dataclass(frozen=True)
class JointSegment:
    start: float
    end: float
    owner: Owner

    @property
    def length(self) -> float:
        return self.end - self.start


@dataclass(frozen=True)
class Joint:
    name: str
    a: EdgeRef
    b: EdgeRef
    length: float
    segments: tuple[JointSegment, ...]
    finger_count: int      # nº de segmentos úteis (ímpar)
    finger_width: float    # largura de cada segmento útil (mm)

    def tab_intervals(self, side: Owner) -> tuple[tuple[float, float], ...]:
        """Intervalos de s com material do painel `side` (A ou B), fundidos."""
        merged: list[list[float]] = []
        for seg in self.segments:
            if seg.owner is not side:
                continue
            if merged and abs(merged[-1][1] - seg.start) <= EPS:
                merged[-1][1] = seg.end
            else:
                merged.append([seg.start, seg.end])
        return tuple((a, b) for a, b in merged)


def auto_finger_target(thickness: float) -> float:
    """Largura alvo de dedo no modo automático (3x a espessura, mín. 6 mm)."""
    return max(3.0 * thickness, 6.0)


def _auto_count(usable: float, target: float) -> int:
    n = int(round((usable / target - 1) / 2)) * 2 + 1
    n = max(3, n)
    while n > 3 and usable / n < MIN_FINGER_WIDTH - EPS:
        n -= 2
    return n


def build_finger_joint(name: str, a: EdgeRef, b: EdgeRef, length: float,
                       thickness: float, start_zone: Owner | None,
                       end_zone: Owner | None, finger_count: int | None) -> Joint:
    """Planeja os segmentos de uma junta. Lança GeometryError se inviável."""
    zs = thickness if start_zone is not None else 0.0
    ze = thickness if end_zone is not None else 0.0
    usable = length - zs - ze
    if usable < 3 * MIN_FINGER_WIDTH - EPS:
        raise GeometryError(
            f"Junta {name}: o comprimento útil ({usable:.2f} mm, já descontadas as "
            f"zonas de canto) não comporta 3 dedos de pelo menos {MIN_FINGER_WIDTH:g} mm. "
            "Aumente a dimensão correspondente ou use um material mais fino.",
            field="geometria")
    if finger_count is None:
        count = _auto_count(usable, auto_finger_target(thickness))
    else:
        count = finger_count
    width = usable / count
    if width < MIN_FINGER_WIDTH - EPS:
        raise GeometryError(
            f"Junta {name}: {count} dedos resultariam em {width:.2f} mm cada "
            f"(mínimo {MIN_FINGER_WIDTH:g} mm). Reduza o número de dedos ou use "
            "o modo automático.", field="finger_count")

    segs: list[JointSegment] = []
    if start_zone is not None:
        segs.append(JointSegment(0.0, snap(zs), start_zone))
    for i in range(count):
        s0 = snap(zs + usable * i / count)
        s1 = snap(zs + usable * (i + 1) / count)
        segs.append(JointSegment(s0, s1, Owner.A if i % 2 == 0 else Owner.B))
    if end_zone is not None:
        segs.append(JointSegment(snap(zs + usable), snap(length), end_zone))
    return Joint(name, a, b, snap(length), tuple(segs), count, width)


def narrowed_tabs(tabs, length: float, clearance: float, name: str):
    """Aplica a folga: cada dente do painel perde clearance/4 de cada lado.

    Os dois painéis da junta estreitam seus próprios dentes, então a folga
    total em cada interface dente/encaixe é `clearance`. Lados que tocam o
    canto do painel (s = 0 ou s = length) não são alterados, para não mudar
    as dimensões externas.
    """
    quarter = clearance / 4.0
    out = []
    for s0, s1 in tabs:
        n0 = s0 if s0 <= EPS else s0 + quarter
        n1 = s1 if s1 >= length - EPS else s1 - quarter
        if n1 - n0 <= EPS:
            raise GeometryError(
                f"Junta {name}: a folga de {clearance:g} mm elimina um dente. "
                "Reduza a folga.", field="clearance")
        out.append((n0, n1))
    return out


def complement_intervals(intervals, length: float):
    """Complemento de intervalos em [0, length] (apenas trechos > EPS)."""
    out = []
    cur = 0.0
    for s0, s1 in sorted(intervals):
        if s0 > cur + EPS:
            out.append((cur, s0))
        cur = max(cur, s1)
    if cur < length - EPS:
        out.append((cur, length))
    return out
