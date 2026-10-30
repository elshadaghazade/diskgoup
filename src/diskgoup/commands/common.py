"""Shared helpers for the CLI commands."""

from __future__ import annotations

from pathlib import Path
from typing import NoReturn

import typer
from rich.console import Console

from diskgoup.core.models import ScanMeta
from diskgoup.core.scanner import Scanner, ScanOptions, ScanProgress, ScanResult
from diskgoup.core.store import ScanIndex
from diskgoup.util.humanize import human_bytes
from diskgoup.util.jsonio import emit_json

console = Console()
err_console = Console(stderr=True)

#: Set by the root callback so every command can honour ``--json``.
JSON_OUTPUT = False


def set_json_output(value: bool) -> None:
    """Remember whether the user asked for machine-readable output."""
    global JSON_OUTPUT
    JSON_OUTPUT = value


def is_json() -> bool:
    """True when ``--json`` was requested."""
    return JSON_OUTPUT


def emit(payload: object) -> None:
    """Print a JSON payload when running in JSON mode."""
    if JSON_OUTPUT:
        emit_json(payload)


def fail(message: str, *, code: int = 1) -> NoReturn:
    """Report an error and exit."""
    err_console.print(f"[bold red]error:[/bold red] {message}")
    raise typer.Exit(code)


def open_index() -> ScanIndex:
    """Open the scan index."""
    return ScanIndex()


def resolve_root(path: str | Path) -> Path:
    """Resolve a user-supplied path, failing with a clear message."""
    candidate = Path(path).expanduser()
    if not candidate.exists():
        fail(f"path does not exist: {candidate}")
    return candidate.resolve()


def latest_scan(index: ScanIndex) -> ScanMeta | None:
    """The most recent scan in the index."""
    scan_id = index.latest_scan_id()
    return index.scan_meta(scan_id) if scan_id is not None else None


def ensure_scan(
    index: ScanIndex,
    path: str | Path | None,
    *,
    scan_id: int | None = None,
    rescan: bool = False,
    show_progress: bool = True,
    **scan_kwargs: object,
) -> ScanMeta:
    """Return a scan to read from, scanning ``path`` first when necessary.

    This is what lets ``diskgoup tree ~/Downloads`` work without a separate
    ``scan`` step: if the index has no scan covering the path, one is created.

    An existing *complete* scan of the same root is reused rather than walking
    the tree again — that is the whole point of the persistent index. Pass
    ``rescan=True`` to force a fresh walk.
    """
    if scan_id is not None:
        meta = index.scan_meta(scan_id)
        if meta is None:
            fail(f"no scan with id {scan_id}")
        return meta

    root = resolve_root(path) if path is not None else None

    if not rescan and root is not None:
        existing = index.scan_for_root(root)
        if existing is not None:
            return existing

    if root is None:
        meta = latest_scan(index)
        if meta is None:
            fail("no scan available — run `diskgoup scan <path>` first")
        return meta

    return run_scan(index, root, show_progress=show_progress, **scan_kwargs)


def run_scan(
    index: ScanIndex,
    root: Path,
    *,
    show_progress: bool = True,
    **scan_kwargs: object,
) -> ScanMeta:
    """Scan ``root`` and persist the result, reporting progress to the terminal."""
    options = ScanOptions(root=root, **scan_kwargs)  # type: ignore[arg-type]
    scanner = Scanner(index, options)

    def on_progress(progress: ScanProgress) -> None:
        if show_progress and not is_json():
            console.print(
                f"[dim]scanned {progress.files:,} files · {human_bytes(progress.bytes_seen)}[/dim]",
                end="\r",
            )

    result: ScanResult = scanner.run(on_progress if show_progress and not is_json() else None)
    if show_progress and not is_json():
        console.print()
    return result.meta
