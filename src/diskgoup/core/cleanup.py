"""Staged cleanup.

Nothing is ever deleted straight away. The flow mirrors DiskBOX exactly:

1. **Stage** — the user adds items to a review list.
2. **Review** — the staged list is inspected.
3. **Validate** — each item is checked to still exist and still be eligible.
4. **Confirm** — the user approves.
5. **Revalidate** — the items are checked once more, immediately before the move.
6. **Recycle bin** — the items are moved to the platform's trash.

Protected paths (system directories, protected application data, game files and
saves) can never be staged, and neither can the containers that would break the
machine — the volume root, the users container, a user's home directory — as
long as only the container itself is refused and not what is inside it.
Cancelling leaves every file exactly where it was.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path

from diskgoup.core.models import Kind
from diskgoup.core.protect import PROTECTED_CRITICAL, is_critical, protection_reason
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


def _kind_of(value: str) -> Kind | None:
    """The kind a stored name stands for, or ``None`` when it is unknown."""
    try:
        return Kind(value)
    except ValueError:
        return None


def _parent_kind(index: ScanIndex, scan_id: int, path: Path) -> Kind | None:
    """The kind of the directory that holds a path.

    A file inside a game folder is game data as well — DiskBOX protects the
    whole subtree, not just the folder itself.
    """
    parent = path.parent
    if parent == path:
        return None
    row = index.entry_by_path(scan_id, parent)
    if row is None:
        return None
    return _kind_of(str(row["kind"]))


def refusal_reason(index: ScanIndex, scan_id: int, path: Path) -> str | None:
    """Why a path may not be cleaned — ``None`` when it may be.

    Two rules are at work: the *protected* rules (system paths, platform
    attributes, game data) refuse a whole subtree, and the *critical* rules
    refuse a container as an item — the volume root, the users container, a
    user's home — while leaving what is inside it cleanable.
    """
    row = index.entry_by_path(scan_id, path)
    kind = _kind_of(str(row["kind"])) if row is not None else None
    # The critical rule is the more specific one, so it explains first.
    if is_critical(path):
        return PROTECTED_CRITICAL
    return protection_reason(path, kind, parent_kind=_parent_kind(index, scan_id, path))


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
    and critical paths are refused with an explanation rather than silently
    ignored.
    """
    staged: list[StagedItem] = []
    refused: list[ValidationIssue] = []
    now = time.time()

    for path in paths:
        reason = refusal_reason(index, scan_id, path)
        if reason is not None:
            refused.append(ValidationIssue(path, reason))
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
        reason = refusal_reason(index, scan_id, item.path)
        if reason is not None:
            issues.append(ValidationIssue(item.path, reason))
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
        _forget(index, scan_id, item.path)

    index.connection.commit()
    return result


def _forget(index: ScanIndex, scan_id: int, path: Path) -> None:
    """Take a removed path out of the index.

    The rows of the item — and of everything below it — are deleted and the
    totals of the folders that held it are corrected, so the index keeps
    telling the truth about the disk. Without this the scan would still
    list what was just cleaned, and the totals would keep counting it.
    """
    row = index.entry_by_path(scan_id, path)
    if row is None:
        # The path was not part of the scan — nothing to forget.
        return

    parent_id = row["parent_id"]
    index.remove_entry(scan_id, int(row["id"]))

    if parent_id is not None:
        # The folder that held the item changed — its modification time is
        # now the one the scan would record, so it is not stale any more.
        index.update_entry_mtime(int(parent_id), _folder_mtime(path.parent))
    index.commit()


def _folder_mtime(path: Path) -> float:
    """The modification time of a folder, or zero when it cannot be read."""
    try:
        return float(path.stat().st_mtime)
    except OSError:
        return 0.0


def _to_trash(path: Path) -> None:
    """Send a path to the platform's recycle bin."""
    try:
        from send2trash import send2trash
    except ImportError as exc:  # pragma: no cover - dependency is declared
        raise CleanupError("send2trash is unavailable — refusing to delete permanently.") from exc
    send2trash(str(path))
