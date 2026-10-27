"""Parâmetros da caixa retangular (sem dependência de Qt)."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class DimensionMode(str, Enum):
    EXTERNAL = "external"
    INTERNAL = "internal"


class BoxType(str, Enum):
    OPEN = "open"
    CLOSED = "closed"


class JointType(str, Enum):
    FINGER = "finger"


# Limites aceitos (mm). Fonte única usada pela validação e pela interface.
LIMITS: dict[str, tuple[float, float]] = {
    "width": (5.0, 1000.0),
    "depth": (5.0, 1000.0),
    "height": (5.0, 1000.0),
    "thickness": (1.0, 25.0),
    "clearance": (0.0, 1.0),
    "kerf": (0.0, 0.6),
}
FINGER_COUNT_LIMITS = (3, 99)  # segmentos por junta (ímpar)

FIELD_LABELS: dict[str, str] = {
    "width": "Largura",
    "depth": "Profundidade",
    "height": "Altura",
    "thickness": "Espessura do material",
    "clearance": "Folga de montagem",
    "kerf": "Kerf",
    "finger_count": "Número de dedos",
}


@dataclass(frozen=True)
class BoxParameters:
    """Entradas do gerador. Todas as medidas em milímetros.

    `thickness` é a espessura REAL medida do material, `clearance` é a folga
    desejada entre dedo e encaixe e `kerf` é a largura removida pelo laser.
    São três grandezas distintas e nunca são somadas numa única variável.
    """

    width: float = 100.0
    depth: float = 80.0
    height: float = 50.0
    thickness: float = 3.0
    dimension_mode: DimensionMode = DimensionMode.EXTERNAL
    box_type: BoxType = BoxType.CLOSED
    joint_type: JointType = JointType.FINGER
    finger_count: int | None = None  # None = automático; senão, nº ímpar >= 3
    clearance: float = 0.0
    kerf: float = 0.0
