"""Application commands: the inventory and the uninstall flow."""

from __future__ import annotations

import typer
from rich.table import Table

from diskgoup.commands.common import console, emit, fail, is_json
from diskgoup.core.applications import discover, uninstall
from diskgoup.util.humanize import human_bytes, human_count

applications_app = typer.Typer(
    help="List installed applications and their footprint.", no_args_is_help=True
)


@applications_app.command("list")
def list_command(
    limit: int = typer.Option(0, "--limit", help="Show at most this many applications."),
) -> None:
    """List the installed applications."""
    inventory = discover()

    if is_json():
        emit(inventory.to_dict())
        return

    if not inventory.applications:
        console.print("[dim]No applications were found on this machine.[/dim]")
        return

    console.print(
        f"[bold]{human_count(len(inventory.applications))} applications[/bold] · "
        f"{human_bytes(inventory.total_size)}"
    )
    table = Table(header_style="bold")
    table.add_column("Name")
    table.add_column("Version")
    table.add_column("Size", justify="right")
    table.add_column("Path", style="dim", overflow="fold")
    applications = inventory.applications[:limit] if limit else inventory.applications
    for application in applications:
        table.add_row(
            application.name,
            application.version or "—",
            human_bytes(application.size),
            str(application.path) if application.path else "—",
        )
    console.print(table)


@applications_app.command("uninstall")
def uninstall_command(
    name: str = typer.Argument(..., help="Name of the application to uninstall."),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip the confirmation prompt."),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show what would run without doing it."),
) -> None:
    """Uninstall an application using the platform's own uninstaller."""
    inventory = discover()
    matches = [app for app in inventory.applications if app.name == name]
    if not matches:
        matches = [app for app in inventory.applications if name.lower() in app.name.lower()]
    if not matches:
        fail(f"no application named {name!r}")

    application = matches[0]
    if not yes and not is_json() and not dry_run:
        console.print(f"About to uninstall [bold]{application.name}[/bold]")
        if application.uninstall_command:
            console.print(f"  {application.uninstall_command}")
        if not typer.confirm("Continue?"):
            console.print("[yellow]Cancelled.[/yellow]")
            raise typer.Exit(1)

    ok, message = uninstall(application, dry_run=dry_run)

    if is_json():
        emit({"application": application.to_dict(), "ok": ok, "message": message})
        return

    if ok:
        console.print(f"[green]✔[/green] {message}")
        console.print("[dim]Inventory rechecked; shared data was not cleaned.[/dim]")
    else:
        fail(message)


def register(app: typer.Typer) -> None:
    """Register the application commands on the root application."""
    app.add_typer(applications_app, name="apps")
