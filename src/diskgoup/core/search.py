"""Advanced search.

Reproduces DiskBOX's advanced-search semantics exactly:

* every condition applies **together** (logical AND);
* the **end date and the size limits are inclusive**;
* results are reviewed **page by page** (200 rows per page by default).

The query runs against the SQLite index, so searching a scanned volume does not
touch the disk again.
"""

from __future__ import annotations

import sqlite3
import time
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path

#: DiskBOX pages its results 200 rows at a time.
DEFAULT_PER_PAGE = 200


class SearchError(Exception):
    """Raised when a query is not valid."""


@dataclass(slots=True)
class SearchQuery:
    """A set of search conditions."""

    name: str | None = None
    path: str | None = None
    extensions: tuple[str, ...] = ()
    entry_type: str = "any"  # any | file | folder
    kinds: tuple[str, ...] = ()
    from_date: date | None = None
    to_date: date | None = None
    min_size: int | None = None
    max_size: int | None = None
    min_age_days: float | None = None
    max_age_days: float | None = None
    protected_only: bool = False

    def validate(self) -> None:
        """Raise :class:`SearchError` if the query cannot be satisfied."""
        if self.entry_type not in {"any", "file", "folder"}:
            raise SearchError(f"unknown entry type: {self.entry_type}")
        if self.from_date and self.to_date and self.from_date > self.to_date:
            raise SearchError("Enter a valid date range (YYYY-MM-DD).")
        if (
            self.min_size is not None
            and self.max_size is not None
            and self.min_size > self.max_size
        ):
            raise SearchError("Enter a valid size range; minimum cannot exceed maximum.")
        if self.min_size is not None and self.min_size < 0:
            raise SearchError("Size limits cannot be negative.")
        if (
            self.min_age_days is not None
            and self.max_age_days is not None
            and self.min_age_days > self.max_age_days
        ):
            raise SearchError("Enter a valid age range; minimum cannot exceed maximum.")

    def to_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "path": self.path,
            "extensions": list(self.extensions),
            "entry_type": self.entry_type,
            "kinds": list(self.kinds),
            "from_date": self.from_date.isoformat() if self.from_date else None,
            "to_date": self.to_date.isoformat() if self.to_date else None,
            "min_size": self.min_size,
            "max_size": self.max_size,
            "min_age_days": self.min_age_days,
            "max_age_days": self.max_age_days,
            "protected_only": self.protected_only,
        }


@dataclass(slots=True)
class SearchResult:
    """A page of search results."""

    query: SearchQuery
    rows: list[sqlite3.Row] = field(default_factory=list)
    total: int = 0
    page: int = 1
    per_page: int = DEFAULT_PER_PAGE

    @property
    def pages(self) -> int:
        if not self.per_page:
            return 1
        return max(1, -(-self.total // self.per_page))

    @property
    def matching_files_only(self) -> int:
        """How many of the matches are files (DiskBOX reports both numbers)."""
        return sum(1 for row in self.rows if not row["is_dir"])

    def to_dict(self) -> dict[str, object]:
        return {
            "query": self.query.to_dict(),
            "total": self.total,
            "page": self.page,
            "per_page": self.per_page,
            "pages": self.pages,
            "matches": [
                {
                    "path": row["path"],
                    "name": row["name"],
                    "is_dir": bool(row["is_dir"]),
                    "size": int(row["size"]),
                    "on_disk": int(row["on_disk"]),
                    "mtime": float(row["mtime"]),
                    "kind": row["kind"],
                    "protected": bool(row["protected"]),
                }
                for row in self.rows
            ],
        }


def parse_date(value: str) -> date:
    """Parse a ``YYYY-MM-DD`` date, raising :class:`SearchError` on bad input."""
    try:
        return datetime.strptime(value.strip(), "%Y-%m-%d").date()
    except ValueError as exc:
        raise SearchError("Enter a valid date range (YYYY-MM-DD).") from exc


def parse_size(value: str) -> int:
    """Parse a size such as ``10MB`` or ``1024`` into bytes."""
    text = value.strip().lower().replace(" ", "")
    units = {
        "b": 1,
        "kb": 1024,
        "kib": 1024,
        "mb": 1024**2,
        "mib": 1024**2,
        "gb": 1024**3,
        "gib": 1024**3,
        "tb": 1024**4,
        "tib": 1024**4,
    }
    for suffix, factor in sorted(units.items(), key=lambda item: -len(item[0])):
        if text.endswith(suffix):
            number = text[: -len(suffix)]
            try:
                return int(float(number) * factor)
            except ValueError as exc:
                raise SearchError(f"Invalid size: {value}") from exc
    try:
        return int(float(text))
    except ValueError as exc:
        raise SearchError(f"Invalid size: {value}") from exc


def _normalise_extensions(extensions: tuple[str, ...]) -> tuple[str, ...]:
    cleaned = []
    for extension in extensions:
        for part in extension.split(","):
            part = part.strip().lower()
            if not part:
                continue
            cleaned.append(part if part.startswith(".") else f".{part}")
    return tuple(cleaned)


def _where(query: SearchQuery, now: float) -> tuple[str, list[object]]:
    """Build the SQL ``WHERE`` clause for a query."""
    clauses: list[str] = []
    params: list[object] = []

    if query.name:
        clauses.append("LOWER(name) LIKE ? ESCAPE '\\'")
        params.append(f"%{_escape_like(query.name.lower())}%")
    if query.path:
        clauses.append("LOWER(path) LIKE ? ESCAPE '\\'")
        params.append(f"%{_escape_like(query.path.lower())}%")

    extensions = _normalise_extensions(query.extensions)
    if extensions:
        placeholders = ", ".join("?" for _ in extensions)
        clauses.append(f"LOWER(name) LIKE {placeholders}")
        for extension in extensions:
            params.append(f"%{extension}")

    if query.entry_type == "file":
        clauses.append("is_dir = 0")
    elif query.entry_type == "folder":
        clauses.append("is_dir = 1")

    if query.kinds:
        placeholders = ", ".join("?" for _ in query.kinds)
        clauses.append(f"kind IN ({placeholders})")
        params.extend(query.kinds)

    if query.from_date:
        # Inclusive: the whole start day counts.
        start = datetime.combine(query.from_date, datetime.min.time()).timestamp()
        clauses.append("mtime >= ?")
        params.append(start)
    if query.to_date:
        # Inclusive: the whole end day counts.
        end = datetime.combine(query.to_date, datetime.max.time()).timestamp()
        clauses.append("mtime <= ?")
        params.append(end)

    if query.min_size is not None:
        clauses.append("size >= ?")
        params.append(query.min_size)
    if query.max_size is not None:
        clauses.append("size <= ?")
        params.append(query.max_size)

    if query.min_age_days is not None:
        clauses.append("mtime <= ?")
        params.append(now - query.min_age_days * 86400)
    if query.max_age_days is not None:
        clauses.append("mtime >= ?")
        params.append(now - query.max_age_days * 86400)

    if query.protected_only:
        clauses.append("protected = 1")

    return (" AND ".join(clauses) if clauses else "1=1"), params


def _escape_like(text: str) -> str:
    return text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def search(
    index_sql: sqlite3.Connection,
    scan_id: int,
    query: SearchQuery,
    *,
    page: int = 1,
    per_page: int = DEFAULT_PER_PAGE,
    now: float | None = None,
) -> SearchResult:
    """Run a query against a scan and return one page of results."""
    query.validate()
    reference = now if now is not None else time.time()
    where, params = _where(query, reference)

    total_row = index_sql.execute(
        f"SELECT COUNT(*) AS n FROM entries WHERE scan_id = ? AND ({where})",
        [scan_id, *params],
    ).fetchone()
    total = int(total_row["n"]) if total_row else 0

    page = max(1, page)
    per_page = max(1, per_page)
    offset = (page - 1) * per_page

    rows = index_sql.execute(
        f"""
        SELECT * FROM entries
         WHERE scan_id = ? AND ({where})
         ORDER BY size DESC, path ASC
         LIMIT ? OFFSET ?
        """,
        [scan_id, *params, per_page, offset],
    ).fetchall()

    return SearchResult(
        query=query,
        rows=list(rows),
        total=total,
        page=page,
        per_page=per_page,
    )


def path_matches(path: str, pattern: str) -> bool:
    """True when a path contains ``pattern`` (case-insensitive substring)."""
    return pattern.lower() in str(Path(path)).lower()
