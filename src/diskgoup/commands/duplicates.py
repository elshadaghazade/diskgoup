"""Duplicate file command."""

from __future__ import annotations

from pathlib import Path

import typer
from rich.table import Table

from diskgoup.commands.common import console, emit, ensure_scan, is_json, open_index
from diskgoup.core.duplicates import find_duplicates
from diskgoup.util.humanize import human_bytes, human_count


def duplicates_command(
    path: str,
    min_size: int = typer.Option(
        1, "--min-size", help="Ignore files smaller than this many bytes."
    ),
    max_size: int | None = typer.Option(
        None, "--max-size", help="Ignore files larger than this many bytes."
    ),
    kind: str | None = typer.Option(None, "--kind", help="Only consider files of this kind."),
    limit: int = typer.Option(0, help="Show at most this many groups (0 = all)."),
    scan_id: int | None = typer.Option(None, help="Use a specific scan id."),
    rescan: bool = typer.Option(False, help="Rescan before searching."),
) -> None:
    """Find files with identical content.

    Content is verified with SHA-256 **and** an exact byte comparison; equal
    names or sizes alone are never treated as proof.
    """
    with open_index() as index:
        meta = ensure_scan(index, path, scan_id=scan_id, rescan=rescan)

        candidates: list[Path] = []
        for row in index.iter_entries(meta.scan_id):
            if row["is_dir"]:
                continue
            size = int(row["size"])
            if size < min_size:
                continue
            if max_size is not None and size > max_size:
                continue
            if kind and row["kind"] != kind:
                continue
            candidates.append(Path(row["path"]))

        def on_progress(message: str) -> None:
            if not is_json():
                console.print(f"[dim]{message}[/dim]")

        report = find_duplicates(candidates, progress=on_progress)
        groups = report.groups[:limit] if limit else report.groups

        if is_json():
            emit(
                {
                    "scan": meta.to_dict(),
                    "group_count": len(report.groups),
                    "total_reclaimable": report.total_reclaimable,
                    "candidates": report.candidates,
                    "groups": [group.to_dict() for group in groups],
                    "skipped": [{"path": str(p), "reason": r} for p, r in report.skipped],
                }
            )
            return

        console.print(
            f"[bold]{human_count(len(report.groups))} duplicate groups[/bold] · "
            f"[green]{human_bytes(report.total_reclaimable)} reclaimable[/green] · "
            f"[dim]{human_count(report.candidates)} candidates[/dim]"
        )

        table = Table(header_style="bold")
        table.add_column("Copies", justify="right")
        table.add_column("Size", justify="right")
        table.add_column("Reclaimable", justify="right")
        table.add_column("Paths", overflow="fold")
        for group in groups:
            table.add_row(
                str(group.copies),
                human_bytes(group.size),
                human_bytes(group.reclaimable),
                "\n".join(str(p) for p in group.paths),
            )
        console.print(table)


def register(app: typer.Typer) -> None:
    """Register the duplicates command on the root application."""
    app.command("duplicates")(duplicates_command)
