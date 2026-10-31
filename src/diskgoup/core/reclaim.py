"""The junk of a scan — the space that can be reclaimed.

A disk cleaner is only useful when it finds the space by itself. The index
already knows the kind of every folder: a folder named ``cache``, ``logs`` or
a temporary one, together with its whole subtree, is the cache group. The
**top-most** folders of that group are what a user can reclaim — the ones
below them are counted with their parent, exactly as DiskBOX counts the
cache/log group once.

Nothing here decides anything. Every candidate still goes through the cleanup
gate (:func:`diskgoup.core.cleanup.refusal_reason`), so a candidate that the
system protects is never offered as cleanable.

Downloads, documents and the trash are deliberately absent: they are the
user's own data, not something the system regenerates.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path

from diskgoup.core.cleanup import refusal_reason
from diskgoup.core.models import Kind
from diskgoup.core.protect import is_critical
from diskgoup.core.store import ScanIndex

#: The kinds that hold what the operating system regenerates.
RECLAIMABLE_KINDS: tuple[Kind, ...] = (Kind.CACHE,)

#: How many candidates the answer carries at most.
DEFAULT_LIMIT = 1000


@dataclass(slots=True)
class Candidate:
    """One folder that can be reclaimed — or that cannot, and why."""

    path: Path
    name: str
    size: int
    on_disk: int
    files: int
    folders: int
    mtime: float
    #: The kind the index gave the folder — the group it was found in.
    kind: Kind = Kind.CACHE
    #: Why it may not be cleaned — ``None`` when it may.
    reason: str | None = None
    #: The container rule refused it (the volume root, a home directory).
    critical: bool = False

    @property
    def cleanable(self) -> bool:
        """True when the cleanup gate would let this folder through."""
        return self.reason is None

    @property
    def protected(self) -> bool:
        """True when a rule refuses the whole subtree below it."""
        return self.reason is not None and not self.critical

    def to_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "path": str(self.path),
            "size": self.size,
            "on_disk": self.on_disk,
            "files": self.files,
            "folders": self.folders,
            "mtime": self.mtime,
            "kind": str(self.kind),
            "reason": self.reason,
            "protected": self.protected,
            "critical": self.critical,
            "cleanable": self.cleanable,
        }


def reclaimable(
    index: ScanIndex,
    scan_id: int,
    *,
    limit: int = DEFAULT_LIMIT,
) -> list[Candidate]:
    """The junk of a scan — the top-most cache folders, biggest first.

    The answer comes out of the index: no folder is walked again.
    """
    candidates: list[Candidate] = []
    for row in _top_most(index, scan_id, limit):
        path = Path(str(row["path"]))
        reason = refusal_reason(index, scan_id, path)
        candidates.append(
            Candidate(
                path=path,
                name=str(row["name"]),
                size=int(row["size"]),
                on_disk=int(row["on_disk"]),
                files=int(row["file_count"]),
                folders=int(row["dir_count"]),
                mtime=float(row["mtime"]),
                kind=Kind(str(row["kind"])),
                reason=reason,
                critical=is_critical(path),
            )
        )
    return candidates


def _top_most(index: ScanIndex, scan_id: int, limit: int) -> list[sqlite3.Row]:
    """The top-most folders of the reclaimable kinds.

    A cache folder inside another cache folder is part of its parent, so it
    is not a candidate of its own — the space is counted once.
    """
    placeholders = ", ".join("?" for _ in RECLAIMABLE_KINDS)
    kinds = [kind.value for kind in RECLAIMABLE_KINDS]
    rows = index.connection.execute(
        f"SELECT e.path, e.name, e.size, e.on_disk, e.file_count, e.dir_count, e.mtime, e.kind "
        f"FROM entries e "
        f"LEFT JOIN entries p ON p.id = e.parent_id AND p.scan_id = e.scan_id "
        f"WHERE e.scan_id = ? AND e.is_dir = 1 AND e.kind IN ({placeholders}) "
        f"AND (p.id IS NULL OR p.kind NOT IN ({placeholders})) "
        f"ORDER BY e.size DESC LIMIT ?",
        [scan_id, *kinds, *kinds, limit],
    ).fetchall()
    return list(rows)
