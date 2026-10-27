"""Catalogo dos geradores planejados (dados, sem logica de geracao)."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PlannedGenerator:
    key: str
    name: str
    description: str
    available: bool = False


PLANNED_GENERATORS: tuple[PlannedGenerator, ...] = (
    PlannedGenerator("rect_box", "Caixa retangular",
                     "Caixa com encaixes tipo dedo para MDF.", available=True),
    PlannedGenerator("sliding_lid_box", "Caixa com tampa deslizante",
                     "Caixa com tampa que desliza em canaletas das laterais.", available=True),
    PlannedGenerator("lid_box", "Caixa com tampa",
                     "Caixa com tampa removível ou articulada."),
    PlannedGenerator("drawers", "Gavetas",
                     "Gavetas dimensionadas para o espaço desejado."),
    PlannedGenerator("organizers", "Organizadores",
                     "Organizadores de mesa e bandejas modulares."),
    PlannedGenerator("polygon_box", "Caixas poligonais",
                     "Caixas com base poligonal (hexagonal, octogonal...)."),
    PlannedGenerator("dividers", "Divisórias e compartimentos",
                     "Divisórias internas configuráveis."),
)
