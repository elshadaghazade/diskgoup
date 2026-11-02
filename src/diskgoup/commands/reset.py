"""``diskgoup reset`` — put the app back to the state it had before the first scan.

The index is a cache of the disk: everything in it can be rebuilt by
scanning again. It is also the one piece of state that can break in a way
the user cannot fix from the interface — a corrupted database makes every
command fail with *"database disk image is malformed"*, and a database held
by a stuck scan makes the app wait forever.

The reset removes the index — the database and the SQLite files beside it —
and writes a new, empty one. No file on the disk is touched.
"""

from __future__ import annotations

import typer

from diskgoup.commands.common import console, emit, fail, is_json
from diskgoup.core.reset import ResetError, reset_app


def reset_command(
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip the confirmation prompt."),
) -> None:
    """Delete the scan index and start over with an empty one."""
    if not yes and not is_json():
        console.print("[bold yellow]This deletes the scan index.[/bold yellow]")
        console.print("  every scan, its entries, its snapshots and the staged list go with it")
        console.print("[dim]No file on your disk is deleted — the next scan reads it again.[/dim]")
        if not typer.confirm("Continue?"):
            console.print("[yellow]Cancelled.[/yellow]")
            raise typer.Exit(1)

    try:
        result = reset_app()
    except ResetError as exc:
        fail(str(exc))

    if is_json():
        emit({"reset": True, **result.to_dict()})
        return

    console.print("[bold green]✔[/bold green] the index was reset — every scan is gone")
    console.print(f"  [dim]{result.index_path}[/dim]")


def register(app: typer.Typer) -> None:
    """Register the reset command on the root application."""
    app.command("reset")(reset_command)
