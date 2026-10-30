"""Spatial view commands: treemap, sunburst, flame, bubbles, mind map and age map.

Every view reads the same scan result and produces the same three output modes:

* ``table`` — a human-readable summary (default).
* ``json`` — the computed geometry, for the Electron GUI to draw.
* ``svg``  — a standalone SVG file.
"""

from __future__ import annotations

from pathlib import Path

import typer
from rich.table import Table

from diskgoup.commands.common import console, emit, ensure_scan, fail, is_json, open_index
from diskgoup.core.render import (
    color_for,
    render_bubbles,
    render_flame,
    render_mindmap,
    render_sunburst,
    render_treemap,
)
from diskgoup.core.views import (
    DEFAULT_DEPTH,
    DEFAULT_HEIGHT,
    DEFAULT_WIDTH,
    LayoutNode,
    age_view,
    bubbles_view,
    build_layout,
    flame_view,
    mindmap_view,
    sunburst_view,
    treemap_view,
)
from diskgoup.util.humanize import human_bytes, percent


def _summary_table(title: str, nodes: list[LayoutNode], total: int) -> Table:
    table = Table(title=title, header_style="bold")
    table.add_column("Name")
    table.add_column("Path", style="dim", overflow="fold")
    table.add_column("Size", justify="right")
    table.add_column("Share", justify="right")
    for node in nodes[:40]:
        table.add_row(
            node.name,
            node.path,
            human_bytes(node.size),
            percent(node.size, total),
        )
    return table


def _geometry(nodes: list[LayoutNode], view: str) -> dict[str, object]:
    """Serialise a layout for the GUI."""
    items = []
    for node in nodes:
        entry: dict[str, object] = {
            "path": node.path,
            "name": node.name,
            "size": node.size,
            "kind": node.kind,
            "depth": node.depth,
            "color": color_for(node),
        }
        if node.rect is not None:
            entry["rect"] = node.rect.to_dict()
        if view == "sunburst":
            entry["start_angle"] = round(node.start_angle, 6)
            entry["end_angle"] = round(node.end_angle, 6)
            entry["radius"] = round(node.radius, 4)
        if view in {"flame", "bubbles", "mindmap"}:
            entry["x"] = round(node.x, 4)
            entry["y"] = round(node.y, 4)
            entry["radius"] = round(node.radius, 4)
        items.append(entry)
    return {"view": view, "items": items}


def _emit_or_write(svg: str, output: Path | None) -> None:
    if output is None:
        console.print(svg, markup=False, highlight=False)
        return
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(svg, encoding="utf-8")
    console.print(f"[green]✔[/green] wrote {output}")


def _view_command(
    view: str,
    path: str,
    width: float,
    height: float,
    depth: int,
    output: Path | None,
    scan_id: int | None,
    rescan: bool,
) -> None:
    with open_index() as index:
        meta = ensure_scan(index, path, scan_id=scan_id, rescan=rescan)
        root = index.build_tree(meta.scan_id)
        if root is None:
            fail("the scan produced no results")
            return
        layout = build_layout(root, max_depth=depth)

        if view == "treemap":
            nodes = treemap_view(layout, width=width, height=height, depth=depth)
            svg = render_treemap(nodes, width=width, height=height, title=str(root.name))
        elif view == "sunburst":
            nodes = sunburst_view(layout, depth=depth)
            svg = render_sunburst(nodes, width=width, height=height, title=str(root.name))
        elif view == "flame":
            nodes = flame_view(layout, depth=depth)
            svg = render_flame(nodes, width=width, height=height, title=str(root.name))
        elif view == "bubbles":
            nodes = bubbles_view(layout, width=width, height=height, depth=depth)
            svg = render_bubbles(nodes, width=width, height=height, title=str(root.name))
        else:
            nodes = mindmap_view(layout, width=width, height=height, depth=depth)
            svg = render_mindmap(nodes, width=width, height=height, title=str(root.name))

        if is_json():
            emit({"scan": meta.to_dict(), **_geometry(nodes, view)})
            return
        if output is not None:
            _emit_or_write(svg, output)
            return
        console.print(_summary_table(f"{view.title()} — {root.name}", nodes, meta.total_size))


def treemap_command(
    path: str,
    width: float = typer.Option(DEFAULT_WIDTH, help="Canvas width in pixels."),
    height: float = typer.Option(DEFAULT_HEIGHT, help="Canvas height in pixels."),
    depth: int = typer.Option(DEFAULT_DEPTH, help="How many levels to expand."),
    output: Path | None = typer.Option(None, "--output", "-o", help="Write an SVG file."),
    scan_id: int | None = typer.Option(None, help="Use a specific scan id."),
    rescan: bool = typer.Option(False, help="Rescan before drawing."),
) -> None:
    """Draw a treemap of a scan."""
    _view_command("treemap", path, width, height, depth, output, scan_id, rescan)


def sunburst_command(
    path: str,
    width: float = typer.Option(DEFAULT_WIDTH, help="Canvas width in pixels."),
    height: float = typer.Option(DEFAULT_HEIGHT, help="Canvas height in pixels."),
    depth: int = typer.Option(DEFAULT_DEPTH, help="How many levels to expand."),
    output: Path | None = typer.Option(None, "--output", "-o", help="Write an SVG file."),
    scan_id: int | None = typer.Option(None, help="Use a specific scan id."),
    rescan: bool = typer.Option(False, help="Rescan before drawing."),
) -> None:
    """Draw a sunburst chart of a scan."""
    _view_command("sunburst", path, width, height, depth, output, scan_id, rescan)


def flame_command(
    path: str,
    width: float = typer.Option(DEFAULT_WIDTH, help="Canvas width in pixels."),
    height: float = typer.Option(DEFAULT_HEIGHT, help="Canvas height in pixels."),
    depth: int = typer.Option(DEFAULT_DEPTH, help="How many levels to expand."),
    output: Path | None = typer.Option(None, "--output", "-o", help="Write an SVG file."),
    scan_id: int | None = typer.Option(None, help="Use a specific scan id."),
    rescan: bool = typer.Option(False, help="Rescan before drawing."),
) -> None:
    """Draw a flame graph of a scan."""
    _view_command("flame", path, width, height, depth, output, scan_id, rescan)


def bubbles_command(
    path: str,
    width: float = typer.Option(DEFAULT_WIDTH, help="Canvas width in pixels."),
    height: float = typer.Option(DEFAULT_HEIGHT, help="Canvas height in pixels."),
    depth: int = typer.Option(DEFAULT_DEPTH, help="How many levels to expand."),
    output: Path | None = typer.Option(None, "--output", "-o", help="Write an SVG file."),
    scan_id: int | None = typer.Option(None, help="Use a specific scan id."),
    rescan: bool = typer.Option(False, help="Rescan before drawing."),
) -> None:
    """Draw a bubble packing of a scan."""
    _view_command("bubbles", path, width, height, depth, output, scan_id, rescan)


def mindmap_command(
    path: str,
    width: float = typer.Option(DEFAULT_WIDTH, help="Canvas width in pixels."),
    height: float = typer.Option(DEFAULT_HEIGHT, help="Canvas height in pixels."),
    depth: int = typer.Option(DEFAULT_DEPTH, help="How many levels to expand."),
    output: Path | None = typer.Option(None, "--output", "-o", help="Write an SVG file."),
    scan_id: int | None = typer.Option(None, help="Use a specific scan id."),
    rescan: bool = typer.Option(False, help="Rescan before drawing."),
) -> None:
    """Draw a mind map of a scan."""
    _view_command("mindmap", path, width, height, depth, output, scan_id, rescan)


def age_command(
    path: str,
    scan_id: int | None = typer.Option(None, help="Use a specific scan id."),
    rescan: bool = typer.Option(False, help="Rescan before drawing."),
) -> None:
    """Show how the scan's files are distributed by modification age."""
    with open_index() as index:
        meta = ensure_scan(index, path, scan_id=scan_id, rescan=rescan)
        files = index.files_with_mtime(meta.scan_id)
        buckets = age_view(files)

        if is_json():
            emit(
                {
                    "scan": meta.to_dict(),
                    "buckets": [bucket.to_dict() for bucket in buckets],
                }
            )
            return

        total = sum(bucket.size for bucket in buckets)
        table = Table(title=f"File age in {meta.root}", header_style="bold")
        table.add_column("Age")
        table.add_column("Files", justify="right")
        table.add_column("Size", justify="right")
        table.add_column("Share", justify="right")
        table.add_column("Bar")
        for bucket in buckets:
            width = int((bucket.size / total) * 30) if total else 0
            table.add_row(
                bucket.label,
                f"{bucket.files:,}",
                human_bytes(bucket.size),
                percent(bucket.size, total),
                f"[#f5a623]{'█' * width}[/]",
            )
        console.print(table)


def register(app: typer.Typer) -> None:
    """Register the view commands on the root application."""
    app.command("treemap")(treemap_command)
    app.command("sunburst")(sunburst_command)
    app.command("flame")(flame_command)
    app.command("bubbles")(bubbles_command)
    app.command("mindmap")(mindmap_command)
    app.command("age")(age_command)
