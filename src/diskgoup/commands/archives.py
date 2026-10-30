"""Archive commands: find ZIP files and browse them read-only."""

from __future__ import annotations

from pathlib import Path

import typer
from rich.table import Table

from diskgoup.commands.common import console, emit, ensure_scan, fail, is_json, open_index
from diskgoup.core.archives import list_archive, parent_of, preview
from diskgoup.util.humanize import human_bytes, human_count

archives_app = typer.Typer(help="Browse archives without extracting them.", no_args_is_help=True)


@archives_app.command("list")
def list_command(
    path: str,
    scan_id: int | None = typer.Option(None, help="Use a specific scan id."),
    rescan: bool = typer.Option(False, help="Rescan before listing."),
) -> None:
    """Find the ZIP archives in a scan."""
    with open_index() as index:
        meta = ensure_scan(index, path, scan_id=scan_id, rescan=rescan)
        rows = [
            row
            for row in index.iter_entries(meta.scan_id)
            if not row["is_dir"] and str(row["name"]).lower().endswith(".zip")
        ]
        rows.sort(key=lambda row: -int(row["size"]))

        if is_json():
            emit(
                {
                    "scan": meta.to_dict(),
                    "archives": [
                        {
                            "path": row["path"],
                            "name": row["name"],
                            "size": int(row["size"]),
                        }
                        for row in rows
                    ],
                }
            )
            return

        if not rows:
            console.print("[dim]No ZIP archives found in this scan.[/dim]")
            return

        table = Table(title=f"Archives in {meta.root}", header_style="bold")
        table.add_column("Name")
        table.add_column("Path", style="dim", overflow="fold")
        table.add_column("Size", justify="right")
        for row in rows:
            table.add_row(row["name"], row["path"], human_bytes(int(row["size"])))
        console.print(table)


@archives_app.command("show")
def show_command(
    archive: Path = typer.Argument(..., help="The ZIP file to browse."),
    prefix: str = typer.Option("", "--prefix", help="Browse inside a folder of the archive."),
) -> None:
    """List the contents of a ZIP archive without extracting it."""
    if not archive.exists():
        fail(f"archive not found: {archive}")

    listing = list_archive(archive, prefix=prefix)

    if is_json():
        emit(listing.to_dict())
        return

    if listing.error:
        fail(listing.error)

    console.print(
        f"[bold]{archive.name}[/bold] · {human_count(listing.item_count)} items · "
        f"[green]{human_bytes(listing.uncompressed)}[/green] uncompressed · "
        f"[dim]{human_bytes(listing.compressed)} compressed[/dim]"
    )
    if listing.partial:
        console.print("[yellow]invalid names skipped; listing is partial.[/yellow]")

    table = Table(header_style="bold")
    table.add_column("Path", overflow="fold")
    table.add_column("Uncompressed", justify="right")
    table.add_column("Compressed", justify="right")
    table.add_column("Ratio", justify="right")
    for entry in listing.entries:
        table.add_row(
            entry.name if entry.name.endswith("/") else entry.name + ("/" if entry.is_dir else ""),
            human_bytes(entry.size),
            human_bytes(entry.compressed),
            f"{entry.ratio * 100:.0f}%",
        )
    console.print(table)

    if prefix:
        parent = parent_of(prefix)
        console.print(f"[dim]Parent archive folder: {parent or '/'}[/dim]")


@archives_app.command("preview")
def preview_command(
    archive: Path = typer.Argument(..., help="The ZIP file to read from."),
    member: str = typer.Argument(..., help="The entry to preview."),
) -> None:
    """Preview a text file inside an archive (first 64 KiB, never extracted)."""
    if not archive.exists():
        fail(f"archive not found: {archive}")

    result = preview(archive, member)

    if is_json():
        emit(result.to_dict())
        return

    if result.encrypted or result.binary:
        console.print(f"[yellow]{result.reason}[/yellow]")
        return
    if result.empty:
        console.print("[dim](Empty file)[/dim]")
        return
    if result.reason:
        fail(result.reason)

    console.print(result.text or "")
    if result.truncated:
        console.print("[dim]Partial preview: showing the first 64 KiB.[/dim]")


def register(app: typer.Typer) -> None:
    """Register the archive commands on the root application."""
    app.add_typer(archives_app, name="archives")
