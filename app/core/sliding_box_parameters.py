"""Parâmetros da caixa com tampa deslizante (sem dependência de Qt)."""
from __future__ import annotations

from dataclasses import dataclass

from app.core.box_parameters import DimensionMode, JointType

# Limites (mm) dos parâmetros EXCLUSIVOS da tampa. Os demais (largura, profundidade,
# altura, espessura, folga de junta, kerf) reutilizam LIMITS de box_parameters.
SLIDING_LIMITS: dict[str, tuple[float, float]] = {
    "lid_clearance": (0.05, 1.5),
    "rail_height": (1.0, 50.0),
    "stop_width": (1.0, 50.0),
    "lid_length": (5.0, 1000.0),
}
SLIDING_LABELS: dict[str, str] = {
    "lid_clearance": "Folga da tampa",
    "rail_height": "Altura do trilho",
    "stop_width": "Largura do batente traseiro",
    "lid_length": "Comprimento da tampa",
}


@dataclass(frozen=True)
class SlidingLidBoxParameters:
    """Entradas do gerador de caixa com tampa deslizante (mm).

    `height`: no modo EXTERNO é a altura total das LATERAIS; no modo INTERNO é a
    altura livre do topo da base até o piso da canaleta (nível do topo da frente).

    `clearance` (folga de montagem dos finger joints), `kerf` e `lid_clearance`
    (folga de deslizamento da tampa) são três grandezas independentes.
    Os parâmetros opcionais (None) usam valores automáticos documentados.
    """

    width: float = 100.0
    depth: float = 80.0
    height: float = 60.0
    thickness: float = 3.0
    dimension_mode: DimensionMode = DimensionMode.EXTERNAL
    joint_type: JointType = JointType.FINGER
    finger_count: int | None = None
    clearance: float = 0.0
    kerf: float = 0.0
    lid_clearance: float = 0.3
    rail_height: float | None = None    # material acima da canaleta; auto = 2 x espessura
    stop_width: float | None = None     # ponte/batente traseiro; auto = 2 x espessura
    lid_length: float | None = None     # comprimento da parte central; auto = máximo
