from __future__ import annotations

import pytest

from diskgoup.core.treemap import Rect, squarify, treemap


def test_tiles_fill_the_canvas() -> None:
    rects = treemap([10.0, 20.0, 30.0], 100.0, 100.0)

    assert len(rects) == 3
    total = sum(rect.area for rect in rects)
    assert total == pytest.approx(10000.0, rel=0.01)


def test_zero_values_get_an_empty_rectangle() -> None:
    rects = treemap([10.0, 0.0, 20.0], 100.0, 100.0)

    assert len(rects) == 3
    assert rects[1].area == 0.0
    assert rects[0].area > 0
    assert rects[2].area > 0


def test_largest_item_gets_the_largest_area() -> None:
    rects = treemap([1.0, 100.0, 1.0], 200.0, 200.0)

    areas = [rect.area for rect in rects]
    assert areas[1] == max(areas)


def test_rects_stay_inside_the_bounds() -> None:
    bounds = Rect(0.0, 0.0, 80.0, 60.0)
    rects = squarify([5.0, 3.0, 2.0, 1.0], bounds)

    for rect in rects:
        assert rect.x >= bounds.x - 0.01
        assert rect.y >= bounds.y - 0.01
        assert rect.right <= bounds.right + 0.01
        assert rect.bottom <= bounds.bottom + 0.01


def test_empty_input_returns_no_rectangles() -> None:
    assert treemap([], 100.0, 100.0) == []
    assert squarify([0.0, 0.0], Rect(0.0, 0.0, 10.0, 10.0)) == [
        Rect(0.0, 0.0, 0.0, 0.0),
        Rect(0.0, 0.0, 0.0, 0.0),
    ]
