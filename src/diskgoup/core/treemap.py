"""Squarified treemap layout.

Implements Bruls, Huizing & van Wijk's *squarified* treemap: rectangles are
laid out so that each keeps an aspect ratio close to 1, which keeps large items
readable instead of producing long slivers.

Reference: https://www.win.tue.nl/~vanwijk/stm.pdf
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True, frozen=True)
class Rect:
    """An axis-aligned rectangle in layout space."""

    x: float
    y: float
    width: float
    height: float

    @property
    def area(self) -> float:
        return self.width * self.height

    @property
    def right(self) -> float:
        return self.x + self.width

    @property
    def bottom(self) -> float:
        return self.y + self.height

    def to_dict(self) -> dict[str, float]:
        return {
            "x": round(self.x, 4),
            "y": round(self.y, 4),
            "width": round(self.width, 4),
            "height": round(self.height, 4),
        }


def _worst_ratio(row: list[float], length: float, scale: float) -> float:
    """The aspect ratio of the worst rectangle in ``row``.

    ``length`` is the length of the side the row is laid out along, ``scale`` is
    the area unit (total area / total value).
    """
    if not row or length <= 0 or scale <= 0:
        return float("inf")
    total = sum(row)
    if total <= 0:
        return float("inf")
    # Squared side length of the row if it were a single square.
    side_squared = (length * length * total) / (scale)
    if side_squared <= 0:
        return float("inf")
    best = min(row)
    worst = max(row)
    return max(
        (side_squared * side_squared) / (best * best),
        (worst * worst) / (side_squared * side_squared),
    )


def squarify(values: list[float], bounds: Rect) -> list[Rect]:
    """Lay out ``values`` inside ``bounds`` as squarified rectangles.

    The returned list is the same length as ``values``; entries whose value is
    zero or negative get an empty rectangle at the origin so that callers can
    still index by position.
    """
    empty = Rect(bounds.x, bounds.y, 0.0, 0.0)
    rects: list[Rect] = [empty] * len(values)

    items = [(index, value) for index, value in enumerate(values) if value > 0]
    if not items:
        return rects

    total_value = sum(value for _, value in items)
    total_area = bounds.width * bounds.height
    if total_area <= 0 or total_value <= 0:
        return rects
    scale = total_area / total_value

    remaining = bounds
    index = 0
    while index < len(items):
        # Grow the row while doing so improves the worst aspect ratio.
        row: list[tuple[int, float]] = [items[index]]
        index += 1
        while index < len(items):
            side = min(remaining.width, remaining.height)
            current = _worst_ratio([v for _, v in row], side, scale)
            candidate = _worst_ratio([v for _, v in [*row, items[index]]], side, scale)
            if candidate > current:
                break
            row.append(items[index])
            index += 1

        row_total = sum(value for _, value in row)
        # A wide region takes a column on its left edge; a tall region takes a
        # band along its top edge.
        if remaining.width >= remaining.height:
            thickness = (row_total * scale) / remaining.height if remaining.height else 0.0
            offset = remaining.x
            for item_index, value in row:
                width = (value * scale) / remaining.height if remaining.height else 0.0
                rects[item_index] = Rect(offset, remaining.y, width, remaining.height)
                offset += width
            remaining = Rect(
                remaining.x + thickness,
                remaining.y,
                max(0.0, remaining.width - thickness),
                remaining.height,
            )
        else:
            thickness = (row_total * scale) / remaining.width if remaining.width else 0.0
            offset = remaining.y
            for item_index, value in row:
                height = (value * scale) / remaining.width if remaining.width else 0.0
                rects[item_index] = Rect(remaining.x, offset, remaining.width, height)
                offset += height
            remaining = Rect(
                remaining.x,
                remaining.y + thickness,
                remaining.width,
                max(0.0, remaining.height - thickness),
            )

        if remaining.width <= 0 or remaining.height <= 0:
            break

    return rects


def treemap(
    values: list[float],
    width: float,
    height: float,
    *,
    origin: tuple[float, float] = (0.0, 0.0),
) -> list[Rect]:
    """Convenience wrapper: squarify into a ``width`` x ``height`` canvas."""
    return squarify(values, Rect(origin[0], origin[1], width, height))
