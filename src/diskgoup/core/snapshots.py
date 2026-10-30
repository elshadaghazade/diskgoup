"""Size snapshots and the seven-day comparison.

A snapshot records the size of every file kind at a point in time. Comparing
the current scan against a snapshot taken at least seven days earlier gives the
"why is the disk full?" answer: which category grew, and by how much.

The comparison rules follow DiskBOX:

* growth is measured against the **previous category size**;
* usage share is measured against **total scanned bytes**;
* files inside cache/log folders count **only** in that group, so they are
  never counted twice.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path

from diskgoup.core.models import KIND_ORDER, Kind
from diskgoup.core.store import ScanIndex


@dataclass(slots=True)
class Snapshot:
    """A recorded size snapshot."""

    id: int
    scan_id: int
    label: str
    created_at: float
    total_size: int
    total_on_disk: int
    kinds: dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "scan_id": self.scan_id,
            "label": self.label,
            "created_at": self.created_at,
            "total_size": self.total_size,
            "total_on_disk": self.total_on_disk,
            "kinds": dict(self.kinds),
        }


@dataclass(slots=True)
class KindChange:
    """How one file kind changed between two points in time."""

    kind: Kind
    current: int
    baseline: int | None
    share: float

    @property
    def growth(self) -> int:
        """Bytes added since the baseline; negative when the kind shrank."""
        if self.baseline is None:
            return 0
        return self.current - self.baseline

    @property
    def growth_percent(self) -> float:
        if not self.baseline:
            return 0.0
        return (self.growth / self.baseline) * 100

    def to_dict(self) -> dict[str, object]:
        return {
            "kind": str(self.kind),
            "current": self.current,
            "baseline": self.baseline,
            "growth": self.growth,
            "growth_percent": round(self.growth_percent, 2),
            "share": round(self.share, 6),
        }


@dataclass(slots=True)
class Comparison:
    """A current scan measured against a baseline snapshot."""

    current: dict[str, int]
    baseline: Snapshot | None
    changes: list[KindChange] = field(default_factory=list)
    total_current: int = 0
    total_baseline: int | None = None

    @property
    def has_history(self) -> bool:
        return self.baseline is not None

    @property
    def total_growth(self) -> int:
        if self.total_baseline is None:
            return 0
        return self.total_current - self.total_baseline

    def to_dict(self) -> dict[str, object]:
        return {
            "has_history": self.has_history,
            "baseline": self.baseline.to_dict() if self.baseline else None,
            "total_current": self.total_current,
            "total_baseline": self.total_baseline,
            "total_growth": self.total_growth,
            "changes": [change.to_dict() for change in self.changes],
        }


def save(index: ScanIndex, scan_id: int, label: str | None = None) -> Snapshot:
    """Record a snapshot of the current scan."""
    meta = index.scan_meta(scan_id)
    if meta is None:
        raise ValueError(f"no scan with id {scan_id}")

    totals = index.kind_totals(scan_id)
    name = label or f"Snapshot {int(time.time())}"
    cursor = index.connection.execute(
        "INSERT INTO snapshots (scan_id, label, created_at, total_size, total_on_disk) "
        "VALUES (?, ?, ?, ?, ?)",
        (scan_id, name, time.time(), meta.total_size, meta.total_on_disk),
    )
    snapshot_id = int(cursor.lastrowid or 0)

    index.connection.executemany(
        "INSERT INTO snapshot_kinds (snapshot_id, kind, size) VALUES (?, ?, ?)",
        [(snapshot_id, kind, size) for kind, size in totals.items()],
    )
    index.connection.commit()

    return Snapshot(
        id=snapshot_id,
        scan_id=scan_id,
        label=name,
        created_at=time.time(),
        total_size=meta.total_size,
        total_on_disk=meta.total_on_disk,
        kinds=totals,
    )


def list_snapshots(index: ScanIndex, scan_id: int) -> list[Snapshot]:
    """Every snapshot taken for a scan, newest first."""
    rows = index.connection.execute(
        "SELECT * FROM snapshots WHERE scan_id = ? ORDER BY created_at DESC",
        (scan_id,),
    ).fetchall()

    snapshots: list[Snapshot] = []
    for row in rows:
        kinds = {
            kind_row["kind"]: int(kind_row["size"])
            for kind_row in index.connection.execute(
                "SELECT kind, size FROM snapshot_kinds WHERE snapshot_id = ?",
                (int(row["id"]),),
            )
        }
        snapshots.append(
            Snapshot(
                id=int(row["id"]),
                scan_id=int(row["scan_id"]),
                label=row["label"],
                created_at=float(row["created_at"]),
                total_size=int(row["total_size"]),
                total_on_disk=int(row["total_on_disk"]),
                kinds=kinds,
            )
        )
    return snapshots


def remove(index: ScanIndex, snapshot_id: int) -> bool:
    """Delete a snapshot."""
    cursor = index.connection.execute("DELETE FROM snapshots WHERE id = ?", (snapshot_id,))
    index.connection.commit()
    return cursor.rowcount > 0


def baseline(index: ScanIndex, scan_id: int, *, min_age_days: float = 7.0) -> Snapshot | None:
    """The newest snapshot that is at least ``min_age_days`` old.

    DiskBOX requires a report for the same drive at least seven days earlier
    before it will show growth; without one it shows current usage only.
    """
    cutoff = time.time() - min_age_days * 86400
    for snapshot in list_snapshots(index, scan_id):
        if snapshot.created_at <= cutoff:
            return snapshot
    return None


def compare(index: ScanIndex, scan_id: int, *, min_age_days: float = 7.0) -> Comparison:
    """Compare the current scan against the baseline snapshot."""
    current = index.kind_totals(scan_id)
    total = sum(current.values())
    base = baseline(index, scan_id, min_age_days=min_age_days)

    changes: list[KindChange] = []
    for kind in KIND_ORDER:
        size = current.get(str(kind), 0)
        base_size = base.kinds.get(str(kind)) if base else None
        changes.append(
            KindChange(
                kind=kind,
                current=size,
                baseline=base_size,
                share=(size / total) if total else 0.0,
            )
        )

    return Comparison(
        current=current,
        baseline=base,
        changes=changes,
        total_current=total,
        total_baseline=base.total_size if base else None,
    )


def growth_rank(changes: list[KindChange], *, limit: int = 0) -> list[KindChange]:
    """The kinds that grew the most, biggest growth first."""
    ranked = sorted(changes, key=lambda change: -change.growth)
    return ranked[:limit] if limit else ranked


def snapshot_path(label: str) -> Path:
    """A safe filename for a snapshot label."""
    safe = "".join(char if char.isalnum() or char in "-_" else "-" for char in label)
    return Path(f"{safe.strip('-') or 'snapshot'}.json")
