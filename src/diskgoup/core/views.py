"""View layouts.

Each of DiskBOX's eight Explore views is a different projection of the same scan
result. This module turns the folder tree into the geometry each view needs;
rendering (SVG, terminal tables, JSON for the GUI) happens elsewhere.

* **Folders** — the tree as-is.
* **Treemap** — squarified rectangles, one per child.
* **Sunburst** — radial arcs, one per descendant.
* **Flame** — an icicle: depth on the vertical axis, size on the horizontal.
* **Bubbles** — circles packed by area.
* **Mind map** — a radial hub with straight links.
* **Top sizes** — a ranking.
* **Age map** — buckets by modification date.
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass, field

from diskgoup.core.models import Node
from diskgoup.core.treemap import Rect, squarify

#: Default canvas size for the spatial views.
DEFAULT_WIDTH = 1200.0
DEFAULT_HEIGHT = 800.0

#: How deep a spatial view descends before it stops expanding.
DEFAULT_DEPTH = 3


@dataclass(slots=True)
class LayoutNode:
    """A node enriched with the geometry a view assigns to it."""

    path: str
    name: str
    size: int
    kind: str
    depth: int
    is_dir: bool
    protected: bool = False
    #: Path of the parent node, used by the mind map to draw links.
    parent_path: str | None = None
    #: The file kind that dominates this subtree — a folder is coloured by
    #: what is inside it, not by its own name.
    color_kind: str = ""
    children: list[LayoutNode] = field(default_factory=list)
    rect: Rect | None = None
    # Radial views
    start_angle: float = 0.0
    end_angle: float = 0.0
    radius: float = 0.0
    # Point views
    x: float = 0.0
    y: float = 0.0


def to_layout(node: Node, depth: int = 0) -> LayoutNode:
    """Convert a :class:`~diskgoup.core.models.Node` into a :class:`LayoutNode`."""
    return LayoutNode(
        path=str(node.path),
        name=node.name,
        size=node.size,
        kind=str(node.kind),
        depth=depth,
        is_dir=node.is_dir,
        protected=node.protected,
    )


def _build_layout(node: Node, depth: int, max_depth: int) -> LayoutNode:
    """Recursive helper that carries the tree depth down."""
    layout = to_layout(node, depth)
    if not node.is_dir or depth >= max_depth:
        return layout
    layout.children = [
        _build_layout(child, depth + 1, max_depth) for child in node.children if child.size > 0
    ]
    for child in layout.children:
        child.parent_path = layout.path
    return layout


def build_layout(node: Node, *, max_depth: int = DEFAULT_DEPTH) -> LayoutNode:
    """Build a layout tree, expanding directories down to ``max_depth``."""
    root = _build_layout(node, 0, max_depth)
    _apply_colors(root)
    return root


def _leaves(layout: LayoutNode) -> list[LayoutNode]:
    """The deepest expanded nodes — what a treemap draws as its tiles."""
    if not layout.children:
        return [layout]
    result: list[LayoutNode] = []
    for child in layout.children:
        result.extend(_leaves(child))
    return result


def _apply_colors(layout: LayoutNode) -> None:
    """Colour every node by the kind that dominates its subtree."""
    for child in layout.children:
        child.color_kind = dominant_kind(child)
        _apply_colors(child)


def dominant_kind(layout: LayoutNode) -> str:
    """The file kind that accounts for most of a subtree's size.

    Directories are coloured by their contents, so a folder full of videos shows
    up as video rather than as an anonymous "other" bucket.
    """
    totals: dict[str, int] = {}
    stack = list(layout.children)
    while stack:
        node = stack.pop()
        if node.children:
            stack.extend(node.children)
            continue
        totals[node.kind] = totals.get(node.kind, 0) + node.size
    if not totals:
        return layout.kind
    return max(totals.items(), key=lambda item: item[1])[0]


def _children_within(layout: LayoutNode, depth: int) -> list[LayoutNode]:
    """Immediate children of ``layout`` that are still within ``depth``."""
    if depth <= 0:
        return []
    return list(layout.children)


# --------------------------------------------------------------------- treemap


def treemap_view(
    layout: LayoutNode,
    *,
    width: float = DEFAULT_WIDTH,
    height: float = DEFAULT_HEIGHT,
    depth: int = DEFAULT_DEPTH,
) -> list[LayoutNode]:
    """Lay out ``layout``'s descendants as squarified rectangles."""
    children = _children_within(layout, depth)
    if not children:
        return [layout]
    values = [float(child.size) for child in children]
    rects = squarify(values, Rect(0.0, 0.0, width, height))
    for child, rect in zip(children, rects, strict=True):
        child.rect = rect
    return children


# -------------------------------------------------------------------- sunburst


def sunburst_view(
    layout: LayoutNode,
    *,
    depth: int = DEFAULT_DEPTH,
    start_angle: float = 0.0,
    end_angle: float = 2 * math.pi,
) -> list[LayoutNode]:
    """Lay out ``layout``'s descendants as radial arcs."""
    total = sum(child.size for child in layout.children) or 1
    angle = start_angle
    span = end_angle - start_angle

    result: list[LayoutNode] = []
    for child in layout.children:
        child_span = span * (child.size / total)
        child.start_angle = angle
        child.end_angle = angle + child_span
        # Radius == depth keeps the root's children on the innermost ring.
        child.radius = child.depth
        result.append(child)
        if child.children and child.depth < depth:
            result.extend(
                sunburst_view(
                    child,
                    depth=depth,
                    start_angle=child.start_angle,
                    end_angle=child.end_angle,
                )
            )
        angle += child_span
    return result


# ----------------------------------------------------------------------- flame


def flame_view(
    layout: LayoutNode,
    *,
    depth: int = DEFAULT_DEPTH,
    row_height: float = 28.0,
) -> list[LayoutNode]:
    """Lay out ``layout``'s descendants as an icicle (flame graph).

    The vertical axis is depth; the horizontal axis is cumulative size.
    """
    result: list[LayoutNode] = []
    total = layout.size or 1

    def walk(node: LayoutNode, offset: float, extent: float, level: int) -> None:
        node.x = offset
        node.y = level * row_height
        node.radius = extent
        result.append(node)
        if not node.children or level >= depth:
            return
        child_offset = offset
        child_total = sum(child.size for child in node.children) or 1
        for child in node.children:
            child_extent = extent * (child.size / child_total)
            walk(child, child_offset, child_extent, level + 1)
            child_offset += child_extent

    walk(layout, 0.0, float(total), 0)
    return result


# --------------------------------------------------------------------- bubbles


def bubbles_view(
    layout: LayoutNode,
    *,
    width: float = DEFAULT_WIDTH,
    height: float = DEFAULT_HEIGHT,
    depth: int = DEFAULT_DEPTH,
) -> list[LayoutNode]:
    """Pack ``layout``'s descendants into circles.

    Circles are placed on a golden-angle spiral and then pushed apart, which
    gives a deterministic, overlap-free packing without pulling in a physics
    library.
    """
    leaves = [node for node in _leaves(layout) if node.depth <= depth and node.size > 0]
    leaves.sort(key=lambda node: -node.size)
    if not leaves:
        return []

    total = sum(node.size for node in leaves) or 1
    canvas_area = width * height
    # Radius from area, with a little slack so the packing breathes.
    radii = [math.sqrt((node.size / total) * canvas_area / math.pi) * 1.02 for node in leaves]

    golden_angle = math.pi * (3.0 - math.sqrt(5.0))
    centers: list[tuple[float, float]] = []
    for index, radius in enumerate(radii):
        distance = radius * 2.4 * math.sqrt(index + 1)
        angle = index * golden_angle
        centers.append(
            (
                width / 2 + math.cos(angle) * distance,
                height / 2 + math.sin(angle) * distance,
            )
        )

    # Push overlapping circles apart.
    for _ in range(24):
        moved = False
        for i in range(len(centers)):
            for j in range(i + 1, len(centers)):
                dx = centers[j][0] - centers[i][0]
                dy = centers[j][1] - centers[i][1]
                distance = math.hypot(dx, dy)
                overlap = radii[i] + radii[j] - distance
                if overlap <= 0.5:
                    continue
                moved = True
                if distance < 1e-6:
                    dx, dy, distance = 1.0, 0.0, 1.0
                shift = overlap / 2 + 0.5
                ux, uy = dx / distance, dy / distance
                centers[i] = (centers[i][0] - ux * shift, centers[i][1] - uy * shift)
                centers[j] = (centers[j][0] + ux * shift, centers[j][1] + uy * shift)
        if not moved:
            break

    # Scale and translate the packing so every circle stays inside the canvas.
    min_x = min(cx - r for (cx, _), r in zip(centers, radii, strict=True))
    min_y = min(cy - r for (_, cy), r in zip(centers, radii, strict=True))
    max_x = max(cx + r for (cx, _), r in zip(centers, radii, strict=True))
    max_y = max(cy + r for (_, cy), r in zip(centers, radii, strict=True))
    span_x = max(max_x - min_x, 1e-6)
    span_y = max(max_y - min_y, 1e-6)
    padding = 24.0
    factor = min((width - 2 * padding) / span_x, (height - 2 * padding) / span_y)
    factor = min(factor, 1.0)
    offset_x = (width - span_x * factor) / 2 - min_x * factor
    offset_y = (height - span_y * factor) / 2 - min_y * factor

    for node, radius, (cx, cy) in zip(leaves, radii, centers, strict=True):
        node.x = cx * factor + offset_x
        node.y = cy * factor + offset_y
        node.radius = radius * factor
    return leaves


# -------------------------------------------------------------------- mindmap


def mindmap_view(
    layout: LayoutNode,
    *,
    width: float = DEFAULT_WIDTH,
    height: float = DEFAULT_HEIGHT,
    depth: int = DEFAULT_DEPTH,
) -> list[LayoutNode]:
    """Lay out ``layout``'s descendants as a radial hub with straight links.

    Branches are spread around the full circle, and each branch's own subtree
    is fanned out inside the branch's wedge on the next ring.
    """
    result: list[LayoutNode] = []
    root_radius = min(width, height) * 0.06
    layout.x = width / 2
    layout.y = height / 2
    layout.radius = root_radius
    result.append(layout)

    branches = [child for child in layout.children if child.size > 0]
    total = sum(child.size for child in branches) or 1
    angle = -math.pi / 2
    ring = min(width, height) * 0.22

    for branch in branches:
        span = 2 * math.pi * (branch.size / total)
        branch.x = layout.x + math.cos(angle) * ring
        branch.y = layout.y + math.sin(angle) * ring
        branch.start_angle = angle
        branch.end_angle = angle + span
        branch.radius = ring
        result.append(branch)

        if branch.children and branch.depth < depth:
            inner = [c for c in branch.children if c.size > 0]
            inner_total = sum(c.size for c in inner) or 1
            inner_angle = branch.start_angle
            for child in inner:
                child_span = span * (child.size / inner_total)
                child.x = branch.x + math.cos(inner_angle) * ring * 0.85
                child.y = branch.y + math.sin(inner_angle) * ring * 0.85
                child.start_angle = inner_angle
                child.end_angle = inner_angle + child_span
                child.radius = ring * 0.85
                result.append(child)
                inner_angle += child_span

        angle += span

    return result


# --------------------------------------------------------------------- age map

#: Age buckets, newest first. ``max_days`` of ``None`` means "everything else".
AGE_BUCKETS: tuple[tuple[str, int | None], ...] = (
    ("Last 7 days", 7),
    ("Last 30 days", 30),
    ("Last 3 months", 90),
    ("Last 6 months", 180),
    ("Last year", 365),
    ("Last 2 years", 730),
    ("Older", None),
)


@dataclass(slots=True)
class AgeBucket:
    """One bucket of the age map."""

    label: str
    size: int
    files: int
    max_days: int | None

    def to_dict(self) -> dict[str, object]:
        return {
            "label": self.label,
            "size": self.size,
            "files": self.files,
            "max_days": self.max_days,
        }


def age_view(files: list[tuple[int, float]], *, now: float | None = None) -> list[AgeBucket]:
    """Bucket ``(size, mtime)`` pairs into the age map.

    Files with an unknown modification time land in the oldest bucket, which is
    the honest place for them: they are the ones most likely to be stale.
    """
    reference = now if now is not None else time.time()
    buckets = [AgeBucket(label, 0, 0, max_days) for label, max_days in AGE_BUCKETS]

    for size, mtime in files:
        age_days = (reference - mtime) / 86400
        target = buckets[-1]
        for bucket in buckets:
            if bucket.max_days is None:
                continue
            if age_days <= bucket.max_days:
                target = bucket
                break
        target.size += size
        target.files += 1

    return buckets
