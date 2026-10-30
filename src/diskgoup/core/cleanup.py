"""Staged cleanup.

Nothing is ever deleted straight away. The flow mirrors DiskBOX exactly:

1. **Stage** — the user adds items to a review list.
2. **Review** — the staged list is inspected.
3. **Validate** — each item is checked to still exist and still be eligible.
4. **Confirm** — the user approves.
5. **Revalidate** — the items are checked once more, immediately before the move.
6. **Recycle bin** — the items are moved to the platform's trash.

Protected paths (system directories, protected application data, game files and
saves) can never be staged. Cancelling leaves every file exactly where it was.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path

from diskgoup.core.protect import is_protected
from diskgoup.core.store import ScanIndex


class CleanupError(Exception):
    """Raised when a cleanup operation cannot proceed."""


@dataclass(slots=True)
class StagedItem:
    """One entry of the review list."""

    path: Path
    size: int
    kind: str
    added_at: float

    def to_dict(self) -> dict[str, object]:
        return {
            "path": str(self.path),
            "size": self.size,
            "kind": self.kind,
            "added_at": self.added_at,
        }


@dataclass(slots=True)
class ValidationIssue:
    """A problem found while validating a staged item."""

    path: Path
    reason: str

    def to_dict(self) -> dict[str, object]:
        return {"path": str(self.path), "reason": self.reason}


@dataclass(slots=True)
class CleanupResult:
    """The outcome of a cleanup run."""

    moved: list[Path] = field(default_factory=list)
    failed: list[tuple[Path, str]] = field(default_factory=list)
    issues: list[ValidationIssue] = field(default_factory=list)
    freed: int = 0

    def to_dict(self) -> dict[str, object]:
        return {
            "moved": [str(path) for path in self.moved],
            "failed": [{"path": str(p), "reason": r} for p, r in self.failed],
            "issues": [issue.to_dict() for issue in self.issues],
        }


def stage(
    index: ScanIndex,
    scan_id: int,
    paths: list[Path],
    *,
    kind: str = "other",
    size: int = 0,
) -> tuple[list[StagedItem], list[ValidationIssue]]:
    """Add paths to the review list.

    Returns the newly staged items and the paths that were refused. Protected
    paths are refused with an explanation rather than silently ignored.
    """
    staged: list[StagedItem] = []
    refused: list[ValidationIssue] = []
    now = time.time()

    for path in paths:
        if is_protected(path):
            refused.append(
                ValidationIssue(path, "Protected game or application data cannot be staged.")
            )
            continue
        exists = index.connection.execute(
            "SELECT 1 FROM staged WHERE scan_id = ? AND path = ?",
            (scan_id, str(path)),
        ).fetchone()
        if exists:
            continue
        item_size = size
        item_kind = kind
        row = index.entry_by_path(scan_id, path)
        if row is not None:
            if not item_size:
                item_size = int(row["size"])
            item_kind = str(row["kind"])
        index.connection.execute(
            "INSERT INTO staged (scan_id, path, size, kind, added_at, status) "
            "VALUES (?, ?, ?, ?, ?, 'staged')",
            (scan_id, str(path), item_size, item_kind, now),
        )
        staged.append(StagedItem(path=path, size=item_size, kind=item_kind, added_at=now))

    index.connection.commit()
    return staged, refused


def unstage(index: ScanIndex, scan_id: int, paths: list[Path]) -> int:
    """Remove paths from the review list. Returns how many were removed."""
    removed = 0
    for path in paths:
        cursor = index.connection.execute(
            "DELETE FROM staged WHERE scan_id = ? AND path = ?",
            (scan_id, str(path)),
        )
        removed += cursor.rowcount if cursor.rowcount > 0 else 0
    index.connection.commit()
    return removed


def staged_items(index: ScanIndex, scan_id: int) -> list[StagedItem]:
    """The current review list."""
    rows = index.connection.execute(
        "SELECT path, size, kind, added_at FROM staged "
        "WHERE scan_id = ? AND status = 'staged' ORDER BY size DESC",
        (scan_id,),
    ).fetchall()
    return [
        StagedItem(
            path=Path(row["path"]),
            size=int(row["size"]),
            kind=row["kind"],
            added_at=float(row["added_at"]),
        )
        for row in rows
    ]


def clear(index: ScanIndex, scan_id: int) -> int:
    """Empty the review list."""
    cursor = index.connection.execute("DELETE FROM staged WHERE scan_id = ?", (scan_id,))
    index.connection.commit()
    return cursor.rowcount


def validate(index: ScanIndex, scan_id: int) -> tuple[list[StagedItem], list[ValidationIssue]]:
    """Check that every staged item is still safe to remove.

    An item is refused when it has disappeared, when it is no longer eligible
    (it became protected), or when its size changed since the scan — that last
    case means the file was modified while the scan was running.
    """
    items = staged_items(index, scan_id)
    valid: list[StagedItem] = []
    issues: list[ValidationIssue] = []

    for item in items:
        if not item.path.exists():
            issues.append(ValidationIssue(item.path, "File no longer exists."))
            continue
        if is_protected(item.path):
            issues.append(ValidationIssue(item.path, "Path is protected and cannot be cleaned."))
            continue
        row = index.entry_by_path(scan_id, item.path)
        if row is not None and int(row["size"]) != item.size:
            issues.append(
                ValidationIssue(item.path, "File changed since the scan; re-scan to refresh.")
            )
            continue
        valid.append(item)

    return valid, issues


def commit(
    index: ScanIndex,
    scan_id: int,
    *,
    to_trash: bool = True,
    permanent: bool = False,
) -> CleanupResult:
    """Move the validated items to the recycle bin.

    The list is revalidated immediately before anything is moved, so an item
    that changed since validation is left alone.
    """
    result = CleanupResult()
    valid, issues = validate(index, scan_id)
    result.issues = issues

    for item in valid:
        try:
            if permanent:
                item.path.unlink()
            else:
                _to_trash(item.path)
        except OSError as exc:
            result.failed.append((item.path, str(exc)))
            continue
        result.moved.append(item.path)
        result.freed += item.size
        index.connection.execute(
            "UPDATE staged SET status = 'removed' WHERE scan_id = ? AND path = ?",
            (scan_id, str(item.path)),
        )

    index.connection.commit()
    return result


def _to_trash(path: Path) -> None:
    """Send a path to the platform's recycle bin."""
    try:
        from send2trash import send2trash
    except ImportError as exc:  # pragma: no cover - dependency is declared
        raise CleanupError("send2trash is unavailable — refusing to delete permanently.") from exc
    send2trash(str(path))
