"""Advanced search command."""

from __future__ import annotations

import typer
from rich.table import Table

from diskgoup.commands.common import console, emit, ensure_scan, fail, is_json, open_index
from diskgoup.core.models import Kind
from diskgoup.core.search import (
    DEFAULT_PER_PAGE,
    SearchError,
    SearchQuery,
    parse_date,
    parse_size,
    search,
)
from diskgoup.util.humanize import human_bytes, human_count


def search_command(
    path: str,
    name: str | None = typer.Option(None, "--name", help="Match against the file name."),
    path_filter: str | None = typer.Option(None, "--in-path", help="Match against the full path."),
    ext: list[str] = typer.Option(
        None, "--ext", help="Extensions to include, e.g. --ext mp4 --ext zip."
    ),
    entry_type: str = typer.Option("any", "--type", help="any | file | folder."),
    kind: list[str] = typer.Option(None, "--kind", help="Limit to a file kind."),
    from_date: str | None = typer.Option(None, "--from", help="Start date, YYYY-MM-DD."),
    to_date: str | None = typer.Option(None, "--to", help="End date, YYYY-MM-DD."),
    min_size: str | None = typer.Option(None, "--min-size", help="e.g. 100MB."),
    max_size: str | None = typer.Option(None, "--max-size", help="e.g. 2GB."),
    min_age: float | None = typer.Option(
        None, "--min-age", help="Only files older than this many days."
    ),
    max_age: float | None = typer.Option(
        None, "--max-age", help="Only files newer than this many days."
    ),
    protected_only: bool = typer.Option(False, "--protected", help="Only protected paths."),
    page: int = typer.Option(1, help="Page number (1-based)."),
    limit: int = typer.Option(DEFAULT_PER_PAGE, help="Rows per page."),
    scan_id: int | None = typer.Option(None, help="Use a specific scan id."),
    rescan: bool = typer.Option(False, help="Rescan before searching."),
) -> None:
    """Search a scan by name, path, extension, type, date and size.

    Every condition applies together, and the end date and the size limits are
    inclusive.
    """
    try:
        query = SearchQuery(
            name=name,
            path=path_filter,
            extensions=tuple(ext or ()),
            entry_type=entry_type,
            kinds=tuple(kind or ()),
            from_date=parse_date(from_date) if from_date else None,
            to_date=parse_date(to_date) if to_date else None,
            min_size=parse_size(min_size) if min_size else None,
            max_size=parse_size(max_size) if max_size else None,
            min_age_days=min_age,
            max_age_days=max_age,
            protected_only=protected_only,
        )
        query.validate()
    except SearchError as exc:
        fail(str(exc))

    with open_index() as index:
        meta = ensure_scan(index, path, scan_id=scan_id, rescan=rescan)
        result = search(
            index.connection,
            meta.scan_id,
            query,
            page=page,
            per_page=limit,
        )

        if is_json():
            emit({"scan": meta.to_dict(), **result.to_dict()})
            return

        table = Table(
            title=f"{human_count(result.total)} matches in {meta.root}",
            header_style="bold",
        )
        table.add_column("Name")
        table.add_column("Path", style="dim", overflow="fold")
        table.add_column("Type")
        table.add_column("Size", justify="right")
        table.add_column("Modified", justify="right")
        for row in result.rows:
            table.add_row(
                row["name"],
                row["path"],
                "folder" if row["is_dir"] else str(Kind(row["kind"])),
                human_bytes(int(row["size"])),
                _timestamp(row["mtime"]),
            )
        console.print(table)
        console.print(
            f"[dim]page {result.page} of {result.pages} · "
            f"{result.per_page} rows per page · "
            f"{result.matching_files_only} matching files only[/dim]"
        )


def _timestamp(value: float) -> str:
    from datetime import datetime

    return datetime.fromtimestamp(value).strftime("%Y-%m-%d %H:%M")


def register(app: typer.Typer) -> None:
    """Register the search command on the root application."""
    app.command("search")(search_command)
