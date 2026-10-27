"""Utilitários de teste: parser de SVG/paths do exportador."""
import re
import xml.etree.ElementTree as ET

NS = {"s": "http://www.w3.org/2000/svg"}
_NUM = r"-?\d+(?:\.\d+)?"


def parse_svg(text):
    return ET.fromstring(text.encode("utf-8") if isinstance(text, str) else text)


def parse_mm(value):
    assert value.endswith("mm"), value
    return float(value[:-2])


def parse_path(d):
    """'M x,y L x,y ... Z' -> (lista de pontos, fechado?)."""
    tokens = d.split()
    assert tokens[0] == "M"
    pts, closed, i = [], False, 0
    for tok in re.findall(r"[MLZ]|" + _NUM + "," + _NUM, d):
        if tok in "MLZ" and len(tok) == 1:
            if tok == "Z":
                closed = True
            continue
        x, y = tok.split(",")
        pts.append((float(x), float(y)))
    return pts, closed


def cut_paths(root):
    group = root.find("s:g[@id='corte']", NS)
    return {p.get("id"): parse_path(p.get("d")) for p in group.findall("s:path", NS)}


def bbox(points):
    xs, ys = [p[0] for p in points], [p[1] for p in points]
    return min(xs), min(ys), max(xs), max(ys)
