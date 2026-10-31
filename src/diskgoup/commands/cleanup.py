"""Cleanup commands: the staged review list and its safe commit.

The flow is deliberately explicit — stage, review, validate, confirm, revalidate,
recycle bin — because a disk analyser that deletes without asking is worse than
useless.
"""

from __future__ import annotations

from pathlib import Path

import typer
from rich.table import Table

from diskgoup.commands.common import console, emit, ensure_scan, fail, is_json, open_index
from diskgoup.core.cleanup import (
    clear,
    commit,
    stage,
    staged_items,
    unstage,
    validate,
)
from diskgoup.util.humanize import human_bytes, human_count

cleanup_app = typer.Typer(help="Stage, review and safely remove files.", no_args_is_help=True)


@cleanup_app.command("stage")
def stage_command(
    paths: list[str] = typer.Argument(..., help="Paths to add to the review list."),
    scan_id: int | None = typer.Option(None, help="Use a specific scan id."),
) -> None:
    """Add files or folders to the review list."""
    with open_index() as index:
        meta = ensure_scan(index, None, scan_id=scan_id)
        resolved = [Path(p).expanduser().resolve() for p in paths]
        added, refused = stage(index, meta.scan_id, resolved)

        if is_json():
            emit(
                {
                    "scan": meta.to_dict(),
                    "staged": [item.to_dict() for item in added],
                    "refused": [issue.to_dict() for issue in refused],
                }
            )
            return

        console.print(f"[green]✔[/green] staged {human_count(len(added))} item(s)")
        for issue in refused:
            console.print(f"[yellow]refused[/yellow] {issue.path}: {issue.reason}")
        console.print("[dim]Nothing has been removed. Review the list, then commit.[/dim]")


@cleanup_app.command("list")
def list_command(scan_id: int | None = typer.Option(None, help="Use a specific scan id.")) -> None:
    """Show the review list."""
    with open_index() as index:
        meta = ensure_scan(index, None, scan_id=scan_id)
        items = staged_items(index, meta.scan_id)
        total = sum(item.size for item in items)

        if is_json():
            emit(
                {
                    "scan": meta.to_dict(),
                    "items": [item.to_dict() for item in items],
                    "total": total,
                }
            )
            return

        if not items:
            console.print("[dim]The review list is empty.[/dim]")
            return

        table = Table(title="Review list", header_style="bold")
        table.add_column("Path", overflow="fold")
        table.add_column("Kind")
        table.add_column("Size", justify="right")
        for item in items:
            table.add_row(str(item.path), item.kind, human_bytes(item.size))
        table.add_row("[bold]Total[/bold]", "", human_bytes(total))
        console.print(table)


@cleanup_app.command("remove")
def remove_command(
    paths: list[str] = typer.Argument(..., help="Paths to remove from the review list."),
    scan_id: int | None = typer.Option(None, help="Use a specific scan id."),
) -> None:
    """Remove items from the review list."""
    with open_index() as index:
        meta = ensure_scan(index, None, scan_id=scan_id)
        removed = unstage(index, meta.scan_id, [Path(p).expanduser() for p in paths])
        if is_json():
            emit({"removed": removed})
            return
        console.print(f"[green]✔[/green] removed {removed} item(s) from the review list")


@cleanup_app.command("clear")
def clear_command(scan_id: int | None = typer.Option(None, help="Use a specific scan id.")) -> None:
    """Empty the review list."""
    with open_index() as index:
        meta = ensure_scan(index, None, scan_id=scan_id)
        removed = clear(index, meta.scan_id)
        if is_json():
            emit({"cleared": removed})
            return
        console.print(f"[green]✔[/green] cleared {removed} item(s)")


@cleanup_app.command("validate")
def validate_command(
    scan_id: int | None = typer.Option(None, help="Use a specific scan id."),
) -> None:
    """Check that every staged item is still safe to remove."""
    with open_index() as index:
        meta = ensure_scan(index, None, scan_id=scan_id)
        valid, issues = validate(index, meta.scan_id)

        if is_json():
            emit(
                {
                    "scan": meta.to_dict(),
                    "valid": [item.to_dict() for item in valid],
                    "issues": [issue.to_dict() for issue in issues],
                }
            )
            return

        console.print(f"[green]{human_count(len(valid))} item(s) ready[/green]")
        for issue in issues:
            console.print(f"[yellow]issue[/yellow] {issue.path}: {issue.reason}")


@cleanup_app.command("commit")
def commit_command(
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip the confirmation prompt."),
    permanent: bool = typer.Option(
        False, "--permanent", help="Delete permanently instead of using the recycle bin."
    ),
    scan_id: int | None = typer.Option(None, help="Use a specific scan id."),
) -> None:
    """Move the reviewed items to the recycle bin."""
    with open_index() as index:
        meta = ensure_scan(index, None, scan_id=scan_id)
        items = staged_items(index, meta.scan_id)
        if not items:
            fail("The review list is empty.")

        total = sum(item.size for item in items)
        if not yes and not is_json():
            console.print(f"[bold]{human_count(len(items))} item(s)[/bold] · {human_bytes(total)}")
            for item in items[:20]:
                console.print(f"  {item.path}")
            if len(items) > 20:
                console.print(f"  [dim]… and {len(items) - 20} more[/dim]")
            if not typer.confirm("Approve this cleanup?"):
                console.print("[yellow]Cancelled. Nothing was removed.[/yellow]")
                raise typer.Exit(1)

        result = commit(index, meta.scan_id, permanent=permanent)

        if is_json():
            emit({"scan": meta.to_dict(), **result.to_dict()})
            return

        if permanent:
            console.print(
                f"[green]✔[/green] deleted {human_count(len(result.moved))} item(s) for good · "
                f"{human_bytes(result.freed)} freed"
            )
        else:
            console.print(
                f"[green]✔[/green] moved {human_count(len(result.moved))} item(s) to the "
                "recycle bin — the space comes back when the trash is emptied"
            )
        for path, reason in result.failed:
            console.print(f"[red]failed[/red] {path}: {reason}")
        for issue in result.issues:
            console.print(f"[yellow]skipped[/yellow] {issue.path}: {issue.reason}")


def register(app: typer.Typer) -> None:
    """Register the cleanup commands on the root application."""
    app.add_typer(cleanup_app, name="cleanup")
