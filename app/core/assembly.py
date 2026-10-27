"""Verificação 3D da montagem (usada em testes e diagnósticos; sem Qt)."""
from __future__ import annotations

from app.core.box_geometry import BoxGeometry, PanelId


def owners_at(geometry: BoxGeometry, x: float, y: float, z: float) -> list[PanelId]:
    """Painéis que contêm o ponto (x, y, z) do mundo (bordas não são garantidas)."""
    owners = []
    for panel in geometry.panels:
        f = panel.frame
        rel = (x - f.origin[0], y - f.origin[1], z - f.origin[2])
        u = sum(r * a for r, a in zip(rel, f.u_axis))
        v = sum(r * a for r, a in zip(rel, f.v_axis))
        s = sum(r * a for r, a in zip(rel, f.normal))
        if (0 < s < panel.thickness and 0 < u < panel.width and 0 < v < panel.height
                and panel.contour.contains(u, v)):
            owners.append(panel.id)
    return owners
