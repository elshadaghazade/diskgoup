"""System-level commands: drives, scanning and scan history."""

from __future__ import annotations

from pathlib import Path

import typer
from rich.table import Table

from diskgoup.commands.common import console, emit, fail, is_json, open_index
from diskgoup.core.partitions import volumes
from diskgoup.core.scanner import Scanner, ScanOptions, ScanProgress
from diskgoup.util.humanize import human_bytes, human_duration


def drives_command() -> None:
    """List the mounted volumes of this machine."""
    found = volumes()
    if is_json():
        emit({"volumes": [v.to_dict() for v in found]})
        return

    table = Table(title="Volumes", header_style="bold", show_lines=False)
    table.add_column("Mount")
    table.add_column("Device")
    table.add_column("Type", style="dim")
    table.add_column("Total", justify="right")
    table.add_column("Used", justify="right")
    table.add_column("Free", justify="right")
    table.add_column("Usage", justify="right")
    for volume in found:
        table.add_row(
            str(volume.mountpoint),
            volume.device,
            volume.fstype or "—",
            human_bytes(volume.total),
            human_bytes(volume.used),
            human_bytes(volume.free),
            f"{volume.used_percent:.0f}%",
        )
    console.print(table)


def scan_command(
    path: str,
    follow_symlinks: bool = False,
    include_hidden: bool = True,
    exclude: list[str] | None = None,
    max_depth: int | None = None,
    profile: bool = False,
) -> None:
    """Scan a drive or folder and store the result in the index."""
    root = Path(path).expanduser()
    if not root.exists():
        fail(f"path does not exist: {root}")
    root = root.resolve()

    with open_index() as index:
        options = ScanOptions(
            root=root,
            follow_symlinks=follow_symlinks,
            include_hidden=include_hidden,
            exclude=tuple(exclude or ()),
            max_depth=max_depth,
            profile=profile,
        )
        scanner = Scanner(index, options)

        last_update = 0.0

        def on_progress(progress: ScanProgress) -> None:
            # Throttle: rewriting the line on every entry floods a log and
            # slows the scan down on large volumes.
            nonlocal last_update
            now = progress.elapsed
            if now - last_update < 0.1 and progress.files:
                return
            last_update = now
            console.print(
                f"[dim]{progress.files:,} files · "
                f"{human_bytes(progress.bytes_seen)} · "
                f"{now:.1f}s[/dim]",
                end="\r",
            )

        result = scanner.run(None if is_json() else on_progress)
        if not is_json():
            console.print()

        if is_json():
            emit(result.to_dict())
            return

        meta = result.meta
        console.print(f"[bold green]✔[/bold green] scanned [bold]{meta.root}[/bold]")
        console.print(
            f"  {meta.file_count:,} files · {meta.dir_count:,} folders · "
            f"{human_bytes(meta.total_size)} logical · "
            f"{human_bytes(meta.total_on_disk)} on disk · "
            f"{human_duration(meta.duration)}"
        )
        if meta.skipped:
            console.print(f"  [yellow]{meta.skipped:,} entries skipped[/yellow]")
        console.print(f"  [dim]scan id {meta.scan_id}[/dim]")
        if result.timings:
            console.print(
                "  [dim]timings:[/dim] "
                + " · ".join(f"{name} {seconds:.2f}s" for name, seconds in result.timings.items())
            )


scans_app = typer.Typer(
    help="List and prune the scans stored in the index.",
    invoke_without_command=True,
    no_args_is_help=False,
)


@scans_app.callback()
def scans_callback(ctx: typer.Context) -> None:
    """List the scans stored in the index."""
    if ctx.invoked_subcommand is not None:
        return

    with open_index() as index:
        entries = index.scans()
        if is_json():
            emit({"scans": [meta.to_dict() for meta in entries]})
            return

        if not entries:
            console.print("[dim]no scans yet — run `diskgoup scan <path>`[/dim]")
            return

        table = Table(title="Scans", header_style="bold")
        table.add_column("ID", justify="right")
        table.add_column("Root")
        table.add_column("Files", justify="right")
        table.add_column("Size", justify="right")
        table.add_column("Duration", justify="right")
        table.add_column("State")
        for meta in entries:
            state = "complete" if meta.complete else "partial"
            table.add_row(
                str(meta.scan_id),
                str(meta.root),
                f"{meta.file_count:,}",
                human_bytes(meta.total_size),
                human_duration(meta.duration),
                state,
            )
        console.print(table)


@scans_app.command("remove")
def scans_remove_command(
    scan_id: int = typer.Argument(..., help="The id of the scan to remove."),
) -> None:
    """Remove a scan and everything recorded for it from the index."""
    with open_index() as index:
        meta = index.scan_meta(scan_id)
        if meta is None:
            fail(f"no scan with id {scan_id}")

        index.delete_scan(scan_id)

        if is_json():
            emit({"removed": meta.to_dict()})
            return

        console.print(f"[bold green]✔[/bold green] removed scan [bold]{scan_id}[/bold]")
        console.print(f"  [dim]{meta.root}[/dim]")


def register(app: typer.Typer) -> None:
    """Register the system commands on the root application."""
    app.command("drives")(drives_command)
    app.command("scan")(scan_command)
    app.add_typer(scans_app, name="scans")
