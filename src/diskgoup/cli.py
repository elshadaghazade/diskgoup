"""DiskGOup command-line interface.

The CLI is the product: it must be able to do everything the desktop GUI does.
The Electron app is a thin front-end that drives these commands as a child
process, which is why every command also speaks JSON (``--json``).
"""

from __future__ import annotations

import typer

from diskgoup import __version__
from diskgoup.commands import (
    applications,
    archives,
    cleanup,
    duplicates,
    explore,
    games,
    monitor,
    reports,
    search,
    serve,
    snapshots,
    system,
    views,
)
from diskgoup.commands.common import set_json_output

app = typer.Typer(
    name="diskgoup",
    help="Cross-platform disk space analyzer and duplicate file finder.",
    no_args_is_help=True,
    add_completion=True,
    context_settings={"help_option_names": ["-h", "--help"]},
)


def _show_version(value: bool) -> None:
    """Print the version and exit.

    This runs as an *eager* option callback, before Click resolves the
    subcommand — a group callback would never run for ``diskgoup --version``,
    because Click reports a missing command first.
    """
    if value:
        typer.echo(f"diskgoup {__version__}")
        raise typer.Exit()


@app.callback()
def root(
    json_output: bool = typer.Option(
        False,
        "--json",
        help="Emit machine-readable JSON instead of formatted output.",
    ),
    version: bool = typer.Option(
        False,
        "--version",
        callback=_show_version,
        is_eager=True,
        help="Show the version and exit.",
    ),
) -> None:
    """DiskGOup — see where your disk space went."""
    set_json_output(json_output)


system.register(app)
explore.register(app)
views.register(app)
search.register(app)
duplicates.register(app)
cleanup.register(app)
archives.register(app)
snapshots.register(app)
reports.register(app)
games.register(app)
applications.register(app)
monitor.register(app)
serve.register(app)


def run() -> None:
    """Console-script entry point."""
    app()


if __name__ == "__main__":  # pragma: no cover
    run()
