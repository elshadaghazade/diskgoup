"""Explore commands: the folder tree, size ranking and the file-type report.

These three views are the backbone of DiskBOX's "one scan, different perspectives"
promise — every view below reads from the same scan result.
"""

from __future__ import annotations

import typer
from rich.table import Table
from rich.tree import Tree

from diskgoup.commands.common import console, emit, ensure_scan, is_json, open_index
from diskgoup.core.models import KIND_ORDER, Kind, Node
from diskgoup.util.humanize import human_bytes, human_count, percent

#: Phosphor-ish palette used for the file-type dots and the table accents.
_KIND_STYLE: dict[Kind, str] = {
    Kind.GAME: "magenta",
    Kind.VIDEO: "red",
    Kind.ARCHIVE: "yellow",
    Kind.DOCUMENT: "cyan",
    Kind.CACHE: "green",
    Kind.APPLICATION: "blue",
    Kind.AUDIO: "bright_magenta",
    Kind.IMAGE: "bright_cyan",
    Kind.CODE: "bright_black",
    Kind.SYSTEM: "bright_black",
    Kind.OTHER: "white",
}


def _label(node: Node) -> str:
    badge = " [red]protected[/red]" if node.protected else ""
    return f"{node.name} [dim]{human_bytes(node.size)}[/dim]{badge}"


def _build_rich_tree(node: Node, branch: Tree, depth: int, max_depth: int) -> None:
    for child in node.children:
        if not child.is_dir:
            continue
        child_branch = branch.add(_label(child))
        if depth < max_depth:
            _build_rich_tree(child, child_branch, depth + 1, max_depth)


def tree_command(
    path: str,
    depth: int = 2,
    scan_id: int | None = None,
    rescan: bool = False,
) -> None:
    """Show the folder tree of a scan."""
    with open_index() as index:
        meta = ensure_scan(index, path, scan_id=scan_id, rescan=rescan)
        root = index.build_tree(meta.scan_id)
        if root is None:
            emit({"scan": meta.to_dict(), "tree": None})
            return

        if is_json():
            emit(
                {
                    "scan": meta.to_dict(),
                    "tree": root.to_dict(),
                }
            )
            return

        tree = Tree(
            f"[bold]{root.name}[/bold] [dim]{human_bytes(root.size)} · "
            f"{human_count(root.file_count)} files[/dim]"
        )
        _build_rich_tree(root, tree, 1, depth)
        console.print(tree)


def sizes_command(
    path: str,
    limit: int = 25,
    folders: bool = True,
    files: bool = True,
    scan_id: int | None = None,
    rescan: bool = False,
) -> None:
    """Rank the largest folders and files in a scan."""
    with open_index() as index:
        meta = ensure_scan(index, path, scan_id=scan_id, rescan=rescan)
        rows = index.largest_entries(meta.scan_id, limit=limit, folders=folders, files=files)

        if is_json():
            emit(
                {
                    "scan": meta.to_dict(),
                    "entries": [
                        {
                            "name": row["name"],
                            "path": row["path"],
                            "is_dir": bool(row["is_dir"]),
                            "size": int(row["size"]),
                            "on_disk": int(row["on_disk"]),
                            "kind": row["kind"],
                            "protected": bool(row["protected"]),
                            "share": (
                                (int(row["size"]) / meta.total_size) if meta.total_size else 0.0
                            ),
                        }
                        for row in rows
                    ],
                }
            )
            return

        table = Table(title=f"Largest items in {meta.root}", header_style="bold")
        table.add_column("#", justify="right", style="dim")
        table.add_column("Name")
        table.add_column("Path", style="dim", overflow="fold")
        table.add_column("Kind")
        table.add_column("Size", justify="right")
        table.add_column("Share", justify="right")
        for position, row in enumerate(rows, start=1):
            kind = Kind(row["kind"])
            style = _KIND_STYLE.get(kind, "white")
            table.add_row(
                str(position),
                row["name"],
                row["path"],
                f"[{style}]{kind}[/{style}]",
                human_bytes(int(row["size"])),
                percent(int(row["size"]), meta.total_size),
            )
        console.print(table)


def types_command(
    path: str,
    scan_id: int | None = None,
    rescan: bool = False,
) -> None:
    """Show the file-type breakdown of a scan."""
    with open_index() as index:
        meta = ensure_scan(index, path, scan_id=scan_id, rescan=rescan)
        totals = index.kind_breakdown(meta.scan_id)

        ordered = [
            (kind, *totals.get(str(kind), (0, 0)))
            for kind in KIND_ORDER
            if totals.get(str(kind), (0, 0))[0] or totals.get(str(kind), (0, 0))[1]
        ]
        total = sum(size for _, size, _ in ordered)

        if is_json():
            emit(
                {
                    "scan": meta.to_dict(),
                    "types": [
                        {
                            "kind": str(kind),
                            "size": size,
                            "files": count,
                            "share": (size / total) if total else 0.0,
                        }
                        for kind, size, count in ordered
                    ],
                }
            )
            return

        table = Table(title=f"File types in {meta.root}", header_style="bold")
        table.add_column("Type")
        table.add_column("Files", justify="right")
        table.add_column("Size", justify="right")
        table.add_column("Share", justify="right")
        table.add_column("Bar")
        for kind, size, count in ordered:
            style = _KIND_STYLE.get(kind, "white")
            bar_width = int((size / total) * 30) if total else 0
            table.add_row(
                f"[{style}]●[/] {kind}",
                human_count(count),
                human_bytes(size),
                percent(size, total),
                f"[{style}]{'█' * bar_width}[/{style}]",
            )
        table.add_row("[bold]Total[/bold]", "", human_bytes(total), "100.0%", "")
        console.print(table)


def register(app: typer.Typer) -> None:
    """Register the explore commands on the root application."""
    app.command("tree")(tree_command)
    app.command("sizes")(sizes_command)
    app.command("types")(types_command)
