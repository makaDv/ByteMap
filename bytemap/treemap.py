"""Squarified treemap layout (Bruls, Huizing, van Wijk). Pure Python, no dependencies."""

from __future__ import annotations


def squarify(sizes: list[float], x: float, y: float, w: float, h: float) -> list[tuple[float, float, float, float]]:
    """Lay out ``sizes`` (sorted largest first) inside the rectangle.

    Returns one ``(x, y, w, h)`` per size, in the same order. Zero sizes get empty rectangles.
    """
    total = sum(sizes)
    rects: list[tuple[float, float, float, float]] = [(x, y, 0.0, 0.0)] * len(sizes)
    if total <= 0 or w <= 0 or h <= 0:
        return rects
    scale = w * h / total
    items = [(i, s * scale) for i, s in enumerate(sizes) if s > 0]

    def worst(row: list[tuple[int, float]], side: float) -> float:
        s = sum(a for _, a in row)
        big = max(a for _, a in row)
        small = min(a for _, a in row)
        return max(side * side * big / (s * s), (s * s) / (side * side * small))

    while items:
        side = min(w, h)
        row = [items[0]]
        rest = items[1:]
        while rest and worst(row + [rest[0]], side) <= worst(row, side):
            row.append(rest.pop(0))
        thick = sum(a for _, a in row) / side
        offset = 0.0
        for i, area in row:
            length = area / thick
            rects[i] = (x, y + offset, thick, length) if w >= h else (x + offset, y, length, thick)
            offset += length
        if w >= h:
            x, w = x + thick, w - thick
        else:
            y, h = y + thick, h - thick
        items = rest
    return rects
