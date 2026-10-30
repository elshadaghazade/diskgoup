"""JSON emission helpers.

Every command can answer with machine-readable JSON so the Electron GUI (and shell
scripts) can consume the CLI without scraping human-formatted output.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, TextIO


def dumps(payload: Any, *, indent: int | None = 2) -> str:
    """Serialize ``payload`` deterministically."""
    return json.dumps(payload, indent=indent, ensure_ascii=False, default=_fallback)


def _fallback(value: Any) -> Any:
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, (set, frozenset)):
        return sorted(value)
    if isinstance(value, bytes):
        return value.decode("utf-8", "replace")
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


def write_json(payload: Any, path: Path, *, indent: int | None = 2) -> Path:
    """Write ``payload`` to ``path`` as UTF-8 JSON."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(dumps(payload, indent=indent) + "\n", encoding="utf-8")
    return path


def emit_json(payload: Any, *, stream: TextIO | None = None, indent: int | None = 2) -> None:
    """Print ``payload`` as JSON to stdout (or ``stream``)."""
    out = stream if stream is not None else sys.stdout
    out.write(dumps(payload, indent=indent) + "\n")
    out.flush()
