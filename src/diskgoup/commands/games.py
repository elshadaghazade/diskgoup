"""Games commands: library discovery, per-game storage and the platform filter."""

from __future__ import annotations

import typer
from rich.table import Table

from diskgoup.commands.common import console, emit, is_json
from diskgoup.core.games import aggregate_other, discover
from diskgoup.util.humanize import human_bytes, human_count

games_app = typer.Typer(help="Discover and measure installed games.", no_args_is_help=True)


@games_app.command("list")
def list_command(
    platform: str | None = typer.Option(
        None, "--platform", help="Filter by platform, e.g. Steam or Epic Games."
    ),
    limit: int = typer.Option(
        0, "--limit", help="Limit the chart to this many games (the rest become 'Other')."
    ),
) -> None:
    """List the discovered game libraries and the space each game uses."""
    libraries = discover()

    if platform:
        wanted = platform.lower()
        libraries = [library for library in libraries if wanted in library.platform.lower()]

    games = [game for library in libraries for game in library.games]

    if is_json():
        emit(
            {
                "libraries": [library.to_dict() for library in libraries],
                "total_size": sum(game.size for game in games),
                "game_count": len(games),
            }
        )
        return

    if not libraries:
        console.print("[dim]No Steam or Epic libraries were found on this machine.[/dim]")
        return

    for library in libraries:
        console.print(
            f"[bold]{library.platform}[/bold] · {human_count(len(library.games))} games · "
            f"{human_bytes(library.size)}"
        )
        table = Table(header_style="bold")
        table.add_column("Game")
        table.add_column("Size", justify="right")
        table.add_column("Categories", overflow="fold")
        for game in library.games:
            categories = ", ".join(
                f"{entry.category} {human_bytes(entry.size)}"
                for entry in game.categories.values()
                if entry.size > 0
            )
            table.add_row(game.name, human_bytes(game.size), categories)
        console.print(table)

    if limit:
        console.print("[bold]Chart data[/bold] (the remainder is aggregated as 'Other'):")
        for name, size in aggregate_other(games, limit=limit):
            console.print(f"  {name}: {human_bytes(size)}")

    console.print(
        "[dim]Measured game size is not reclaimable space. Saves and game files "
        "are protected.[/dim]"
    )


def register(app: typer.Typer) -> None:
    """Register the games commands on the root application."""
    app.add_typer(games_app, name="games")
