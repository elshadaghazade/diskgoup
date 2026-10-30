"""Snapshot commands: save, list, remove and compare size snapshots."""

from __future__ import annotations

import typer
from rich.table import Table

from diskgoup.commands.common import console, emit, ensure_scan, fail, is_json, open_index
from diskgoup.core.snapshots import compare, growth_rank, list_snapshots, remove, save
from diskgoup.util.humanize import human_bytes, percent

snapshots_app = typer.Typer(
    help="Record size snapshots and compare them over time.", no_args_is_help=True
)


@snapshots_app.command("save")
def save_command(
    label: str | None = typer.Option(None, "--label", help="A name for the snapshot."),
    scan_id: int | None = typer.Option(None, help="Use a specific scan id."),
) -> None:
    """Record a snapshot of the current scan."""
    with open_index() as index:
        meta = ensure_scan(index, None, scan_id=scan_id)
        snapshot = save(index, meta.scan_id, label)
        if is_json():
            emit(snapshot.to_dict())
            return
        console.print(f"[green]✔[/green] snapshot saved: {snapshot.label}")


@snapshots_app.command("list")
def list_command(scan_id: int | None = typer.Option(None, help="Use a specific scan id.")) -> None:
    """List the snapshots taken for a scan."""
    with open_index() as index:
        meta = ensure_scan(index, None, scan_id=scan_id)
        snapshots = list_snapshots(index, meta.scan_id)

        if is_json():
            emit({"snapshots": [s.to_dict() for s in snapshots]})
            return

        if not snapshots:
            console.print("[dim]No snapshots yet.[/dim]")
            return

        table = Table(title="Snapshots", header_style="bold")
        table.add_column("ID", justify="right")
        table.add_column("Label")
        table.add_column("Total", justify="right")
        table.add_column("Taken")
        for snapshot in snapshots:
            from datetime import datetime

            table.add_row(
                str(snapshot.id),
                snapshot.label,
                human_bytes(snapshot.total_size),
                datetime.fromtimestamp(snapshot.created_at).strftime("%Y-%m-%d %H:%M"),
            )
        console.print(table)


@snapshots_app.command("remove")
def remove_command(snapshot_id: int = typer.Argument(..., help="Snapshot id.")) -> None:
    """Remove a snapshot."""
    with open_index() as index:
        if not remove(index, snapshot_id):
            fail(f"no snapshot with id {snapshot_id}")
        if is_json():
            emit({"removed": snapshot_id})
            return
        console.print(f"[green]✔[/green] removed snapshot {snapshot_id}")


@snapshots_app.command("compare")
def compare_command(
    scan_id: int | None = typer.Option(None, help="Use a specific scan id."),
    min_age_days: float = typer.Option(
        7.0, "--min-age-days", help="How old the baseline snapshot must be."
    ),
) -> None:
    """Compare the current scan against the baseline snapshot."""
    with open_index() as index:
        meta = ensure_scan(index, None, scan_id=scan_id)
        comparison = compare(index, meta.scan_id, min_age_days=min_age_days)

        if is_json():
            emit(comparison.to_dict())
            return

        if not comparison.has_history:
            console.print(
                "[yellow]No comparable history.[/yellow] Growth requires a file-type "
                "report for the same drive at least "
                f"{min_age_days:g} days earlier. Current usage is shown below."
            )
        else:
            growth = comparison.total_growth
            console.print(
                f"[bold]7-day change:[/bold] "
                f"[{'up' if growth > 0 else 'down'}]{human_bytes(abs(growth))}[/]"
                f" ({percent(abs(growth), comparison.total_baseline or 1)})"
            )

        table = Table(header_style="bold")
        table.add_column("Type")
        table.add_column("Current", justify="right")
        table.add_column("Growth", justify="right")
        table.add_column("Usage share", justify="right")
        for change in growth_rank(comparison.changes):
            if comparison.has_history:
                marker = "[up]+[/up]" if change.growth > 0 else "[down]−[/down]"
                growth_text = f"{marker} {human_bytes(abs(change.growth))}"
            else:
                growth_text = "—"
            table.add_row(
                str(change.kind),
                human_bytes(change.current),
                growth_text,
                percent(change.current, comparison.total_current),
            )
        console.print(table)


def register(app: typer.Typer) -> None:
    """Register the snapshot commands on the root application."""
    app.add_typer(snapshots_app, name="snapshots")
