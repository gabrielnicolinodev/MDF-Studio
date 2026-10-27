"""Primitivas geométricas 2D em milímetros (sem dependência de Qt).

Os contornos são polígonos FECHADOS representados por uma lista de vértices
SEM repetir o primeiro ponto (o fechamento é implícito). Os contornos locais
dos painéis usam sistema com y para cima e sentido anti-horário (área > 0).
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Iterable, Iterator, NamedTuple

from app.core.validation import GeometryError

EPS = 1e-9
MICRO = 1_000_000  # a grade interna usa 1e-6 mm


class Point(NamedTuple):
    x: float
    y: float


def snap(value: float) -> float:
    """Arredonda para 1e-6 mm (determinismo) evitando -0.0."""
    return round(value * MICRO) / MICRO + 0.0


@dataclass(frozen=True)
class Contour:
    points: tuple[Point, ...]

    def segments(self) -> Iterator[tuple[Point, Point]]:
        n = len(self.points)
        for i in range(n):
            yield self.points[i], self.points[(i + 1) % n]

    def signed_area(self) -> float:
        total = 0.0
        for p, q in self.segments():
            total += p.x * q.y - q.x * p.y
        return total / 2.0

    def area(self) -> float:
        return abs(self.signed_area())

    def perimeter(self) -> float:
        return sum(math.hypot(q.x - p.x, q.y - p.y) for p, q in self.segments())

    def bbox(self) -> tuple[float, float, float, float]:
        xs = [p.x for p in self.points]
        ys = [p.y for p in self.points]
        return min(xs), min(ys), max(xs), max(ys)

    def contains(self, x: float, y: float) -> bool:
        """Ponto dentro do polígono (ray casting; bordas não são garantidas)."""
        inside = False
        for p, q in self.segments():
            if (p.y > y) != (q.y > y):
                x_cross = p.x + (y - p.y) * (q.x - p.x) / (q.y - p.y)
                if x < x_cross:
                    inside = not inside
        return inside

    def map_points(self, fn) -> "Contour":
        return Contour(tuple(Point(*fn(p)) for p in self.points))

    def problems(self) -> list[str]:
        """Lista de defeitos: vazio = contorno válido (fechado, sem segmento nulo)."""
        out: list[str] = []
        if len(self.points) < 3:
            out.append("contorno com menos de 3 vértices")
            return out
        for p, q in self.segments():
            if not all(math.isfinite(v) for v in (*p, *q)):
                out.append("coordenada não finita")
            elif math.hypot(q.x - p.x, q.y - p.y) <= EPS:
                out.append(f"segmento de comprimento zero em {tuple(p)}")
        if self.area() <= EPS:
            out.append("área nula")
        return out


def rect_minus_rects(width: float, height: float,
                     rects: Iterable[tuple[float, float, float, float]]) -> Contour:
    """Contorno do retângulo [0,width]x[0,height] menos retângulos (recortes).

    Os recortes são (x0, y0, x1, y1) em mm e devem tocar a borda, de modo que o
    resultado seja um polígono simples. O cálculo usa uma grade inteira de
    1e-6 mm (exato e determinístico). Devolve vértices em sentido anti-horário,
    começando pelo vértice de menor (x, y), sem pontos colineares.
    """
    W, H = round(width * MICRO), round(height * MICRO)
    cuts = []
    for x0, y0, x1, y1 in rects:
        a, b = max(0, min(round(x0 * MICRO), W)), max(0, min(round(y0 * MICRO), H))
        c, d = max(0, min(round(x1 * MICRO), W)), max(0, min(round(y1 * MICRO), H))
        if c > a and d > b:
            cuts.append((a, b, c, d))

    xs = sorted({0, W} | {r[0] for r in cuts} | {r[2] for r in cuts})
    ys = sorted({0, H} | {r[1] for r in cuts} | {r[3] for r in cuts})
    xi = {v: i for i, v in enumerate(xs)}
    yi = {v: i for i, v in enumerate(ys)}
    nx, ny = len(xs) - 1, len(ys) - 1
    filled = [[True] * ny for _ in range(nx)]
    for a, b, c, d in cuts:
        for i in range(xi[a], xi[c]):
            for j in range(yi[b], yi[d]):
                filled[i][j] = False

    def is_filled(i: int, j: int) -> bool:
        return 0 <= i < nx and 0 <= j < ny and filled[i][j]

    edges: dict[tuple[int, int], tuple[int, int]] = {}

    def add(start: tuple[int, int], end: tuple[int, int]) -> None:
        if start in edges:
            raise GeometryError(
                "O contorno da peça se tocaria em um único ponto (dente de largura "
                "nula). Ajuste folga, número de dedos ou dimensões.")
        edges[start] = end

    for i in range(nx):
        for j in range(ny):
            if not filled[i][j]:
                continue
            x0, x1, y0, y1 = xs[i], xs[i + 1], ys[j], ys[j + 1]
            if not is_filled(i, j - 1):
                add((x0, y0), (x1, y0))
            if not is_filled(i + 1, j):
                add((x1, y0), (x1, y1))
            if not is_filled(i, j + 1):
                add((x1, y1), (x0, y1))
            if not is_filled(i - 1, j):
                add((x0, y1), (x0, y0))

    if not edges:
        raise GeometryError("A peça ficou sem material após os recortes.")
    start = min(edges)
    loop = [start]
    cur = edges[start]
    while cur != start:
        loop.append(cur)
        cur = edges[cur]
        if len(loop) > len(edges):
            raise GeometryError("Contorno inconsistente (laço não fecha).")
    if len(loop) != len(edges):
        raise GeometryError("Os recortes isolaram uma região da peça (contorno com furo).")

    pts = []
    n = len(loop)
    for k in range(n):
        p, c, q = loop[k - 1], loop[k], loop[(k + 1) % n]
        cross = (c[0] - p[0]) * (q[1] - c[1]) - (c[1] - p[1]) * (q[0] - c[0])
        if cross != 0:
            pts.append(Point(c[0] / MICRO, c[1] / MICRO))
    return Contour(tuple(pts))


def offset_rectilinear(contour: Contour, distance: float) -> Contour:
    """Desloca para FORA um contorno retilíneo anti-horário por `distance` mm.

    Exato para polígonos com arestas ortogonais (cada vértice se move
    `distance` em x e em y). Valores negativos deslocam para dentro. Exige que
    cada elemento (dente/recorte) seja maior que 2*|distance|.
    """
    if distance == 0:
        return contour
    pts = contour.points
    n = len(pts)
    if contour.signed_area() <= 0:
        raise GeometryError("Contorno com orientação inválida para compensação de kerf.")
    dirs = []
    for p, q in contour.segments():
        dx, dy = q.x - p.x, q.y - p.y
        if abs(dx) > EPS and abs(dy) > EPS:
            raise GeometryError("A compensação de kerf só é suportada para contornos ortogonais.")
        length = abs(dx) + abs(dy)
        if length <= EPS:
            raise GeometryError("Segmento de comprimento zero no contorno.")
        dirs.append((dx / length, dy / length))
    out = []
    for i in range(n):
        a, b = dirs[i - 1], dirs[i]
        na, nb = (a[1], -a[0]), (b[1], -b[0])  # normais externas (contorno anti-horário)
        out.append(Point(snap(pts[i].x + distance * (na[0] + nb[0])),
                         snap(pts[i].y + distance * (na[1] + nb[1]))))
    return Contour(tuple(out))
