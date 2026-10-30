"""SQLite-backed scan index.

Every scan is persisted, so the Explorer views, the advanced search, the duplicate
finder, the snapshots and the reports all read from the *same* result set instead of
re-walking the filesystem. This is what makes DiskBOX's "one scan, different
perspectives" promise real.
"""

from __future__ import annotations

import sqlite3
import time
from collections.abc import Iterable, Iterator
from pathlib import Path
from typing import Any, cast

from diskgoup.core.models import Kind, Node, ScanMeta
from diskgoup.paths import default_index_path, env_index_path

_SCHEMA = """
PRAGMA journal_mode = WAL;

CREATE TABLE IF NOT EXISTS scans (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    root         TEXT    NOT NULL,
    started_at   REAL    NOT NULL,
    finished_at  REAL,
    total_size   INTEGER NOT NULL DEFAULT 0,
    total_on_disk INTEGER NOT NULL DEFAULT 0,
    file_count   INTEGER NOT NULL DEFAULT 0,
    dir_count    INTEGER NOT NULL DEFAULT 0,
    skipped      INTEGER NOT NULL DEFAULT 0,
    complete     INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS entries (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    scan_id    INTEGER NOT NULL REFERENCES scans(id) ON DELETE CASCADE,
    parent_id  INTEGER,
    path       TEXT    NOT NULL,
    name       TEXT    NOT NULL,
    is_dir     INTEGER NOT NULL,
    size       INTEGER NOT NULL DEFAULT 0,
    on_disk    INTEGER NOT NULL DEFAULT 0,
    mtime      REAL    NOT NULL DEFAULT 0,
    kind       TEXT    NOT NULL DEFAULT 'other',
    protected  INTEGER NOT NULL DEFAULT 0,
    depth      INTEGER NOT NULL DEFAULT 0,
    file_count INTEGER NOT NULL DEFAULT 0,
    dir_count  INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_entries_scan_parent ON entries(scan_id, parent_id);
CREATE INDEX IF NOT EXISTS idx_entries_scan_size   ON entries(scan_id, size);
CREATE INDEX IF NOT EXISTS idx_entries_scan_kind   ON entries(scan_id, kind);
CREATE INDEX IF NOT EXISTS idx_entries_scan_name   ON entries(scan_id, name);
CREATE INDEX IF NOT EXISTS idx_entries_scan_path   ON entries(scan_id, path);
CREATE INDEX IF NOT EXISTS idx_entries_scan_depth  ON entries(scan_id, depth);

CREATE TABLE IF NOT EXISTS skipped (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    scan_id  INTEGER NOT NULL REFERENCES scans(id) ON DELETE CASCADE,
    path     TEXT    NOT NULL,
    reason   TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS hashes (
    scan_id  INTEGER NOT NULL REFERENCES scans(id) ON DELETE CASCADE,
    entry_id INTEGER NOT NULL REFERENCES entries(id) ON DELETE CASCADE,
    size     INTEGER NOT NULL,
    sha256   TEXT    NOT NULL,
    PRIMARY KEY (scan_id, entry_id)
);

CREATE INDEX IF NOT EXISTS idx_hashes_scan_digest ON hashes(scan_id, sha256);

CREATE TABLE IF NOT EXISTS snapshots (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    scan_id       INTEGER NOT NULL REFERENCES scans(id) ON DELETE CASCADE,
    label         TEXT    NOT NULL,
    created_at    REAL    NOT NULL,
    total_size    INTEGER NOT NULL,
    total_on_disk INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS snapshot_kinds (
    snapshot_id INTEGER NOT NULL REFERENCES snapshots(id) ON DELETE CASCADE,
    kind        TEXT    NOT NULL,
    size        INTEGER NOT NULL,
    PRIMARY KEY (snapshot_id, kind)
);

CREATE TABLE IF NOT EXISTS staged (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    scan_id  INTEGER NOT NULL REFERENCES scans(id) ON DELETE CASCADE,
    path     TEXT    NOT NULL,
    size     INTEGER NOT NULL DEFAULT 0,
    kind     TEXT    NOT NULL DEFAULT 'other',
    added_at REAL    NOT NULL,
    status   TEXT    NOT NULL DEFAULT 'staged'
);

CREATE INDEX IF NOT EXISTS idx_staged_scan ON staged(scan_id, status);
"""

#: The schema version stored in the index. Bump it when ``_SCHEMA`` changes.
_SCHEMA_VERSION = 2

#: What each version adds to an index that already has the tables. Applied in
#: order when an existing index is opened, so an index written by an older
#: version gains the new indexes instead of being marked as up to date.
_MIGRATIONS: dict[int, tuple[str, ...]] = {
    2: ("CREATE INDEX IF NOT EXISTS idx_entries_scan_depth ON entries(scan_id, depth)",),
}

#: The tables the schema is made of. Their presence says "this index has the
#: schema" — a read, so opening an index never takes the write lock.
_SCHEMA_TABLES = (
    "scans",
    "entries",
    "skipped",
    "hashes",
    "snapshots",
    "snapshot_kinds",
    "staged",
)

#: How many times to retry creating the schema when the index is locked.
_SCHEMA_ATTEMPTS = 5


class ScanIndex:
    """Handle on the on-disk scan index."""

    def __init__(self, db_path: Path | None = None) -> None:
        self.db_path = (
            Path(db_path) if db_path is not None else (env_index_path() or default_index_path())
        )
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self.db_path)
        self._conn.row_factory = sqlite3.Row
        # Per-connection settings. These are reads, so opening an index never
        # takes the write lock — a running scan and the app can share one.
        self._conn.execute("PRAGMA synchronous = NORMAL")
        self._conn.execute("PRAGMA foreign_keys = ON")
        self._create_schema()

    def _create_schema(self) -> None:
        """Make sure the index has the schema.

        Everything here is a read except the creation itself, so opening an
        existing index never takes the write lock — a running scan and the app
        can share one index. Only a brand new index needs the lock, and
        nothing else is using it yet.
        """
        version = int(self._conn.execute("PRAGMA user_version").fetchone()[0])
        if version >= _SCHEMA_VERSION:
            return

        if self._has_schema():
            # The schema is there; only the marker is missing. Writing it is
            # a nicety, so it must never fail the open.
            try:
                for target in range(version + 1, _SCHEMA_VERSION + 1):
                    for statement in _MIGRATIONS.get(target, ()):
                        self._conn.execute(statement)
                self._conn.execute(f"PRAGMA user_version = {_SCHEMA_VERSION}")
                self._conn.commit()
            except sqlite3.OperationalError:
                pass
            return

        self._conn.execute("PRAGMA busy_timeout = 300")
        try:
            for attempt in range(_SCHEMA_ATTEMPTS):
                if self._has_schema():
                    return
                try:
                    self._conn.executescript(_SCHEMA)
                    self._conn.execute(f"PRAGMA user_version = {_SCHEMA_VERSION}")
                    self._conn.commit()
                    return
                except sqlite3.OperationalError:
                    if attempt == _SCHEMA_ATTEMPTS - 1:
                        raise
                    time.sleep(0.1)
        finally:
            self._conn.execute("PRAGMA busy_timeout = 5000")

    def _has_schema(self) -> bool:
        """True when every table of the schema is present.

        A read: it works while another process holds the write lock.
        """
        placeholders = ",".join("?" * len(_SCHEMA_TABLES))
        row = self._conn.execute(
            f"SELECT count(*) FROM sqlite_master WHERE type = 'table' AND name IN ({placeholders})",
            _SCHEMA_TABLES,
        ).fetchone()
        return int(row[0]) == len(_SCHEMA_TABLES)

    @property
    def connection(self) -> sqlite3.Connection:
        """The underlying SQLite connection."""
        return self._conn

    # ---------------------------------------------------------------- lifecycle

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> ScanIndex:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    # ------------------------------------------------------------------- scans

    def begin_scan(self, root: Path) -> int:
        """Open a new scan for ``root`` and return its id."""
        cursor = self._conn.execute(
            "INSERT INTO scans (root, started_at) VALUES (?, ?)",
            (str(root), time.time()),
        )
        self._conn.commit()
        return int(cursor.lastrowid or 0)

    def add_entries(self, scan_id: int, rows: Iterable[tuple[Any, ...]]) -> None:
        """Bulk-insert index rows.

        Each row is ``(parent_id, path, name, is_dir, size, on_disk, mtime, kind,
        protected, depth, file_count)``.
        """
        self._conn.executemany(
            """
            INSERT INTO entries
                (scan_id, parent_id, path, name, is_dir, size, on_disk, mtime, kind,
                 protected, depth, file_count)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ((scan_id, *row) for row in rows),
        )

    def add_entry(self, scan_id: int, row: tuple[Any, ...]) -> int:
        """Insert one index row and return its id.

        The id comes from the insert itself. Asking for it with a second
        query would be wrong the moment more than one writer exists.
        """
        cursor = self._conn.execute(
            """
            INSERT INTO entries
                (scan_id, parent_id, path, name, is_dir, size, on_disk, mtime, kind,
                 protected, depth, file_count)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (scan_id, *row),
        )
        return int(cursor.lastrowid or 0)

    def set_totals(
        self, entry_id: int, size: int, on_disk: int, file_count: int, dir_count: int
    ) -> None:
        """Write the rolled-up totals of one directory."""
        self._conn.execute(
            """
            UPDATE entries
               SET size = ?, on_disk = ?, file_count = ?, dir_count = ?
             WHERE id = ?
            """,
            (size, on_disk, file_count, dir_count, entry_id),
        )

    def add_skipped(self, scan_id: int, path: Path, reason: str) -> None:
        self._conn.execute(
            "INSERT INTO skipped (scan_id, path, reason) VALUES (?, ?, ?)",
            (scan_id, str(path), reason),
        )

    def commit(self) -> None:
        """Commit what has been written so far.

        A scan writes its entries in batches but commits only at the very end,
        which holds the write lock for the whole walk — long enough to lock
        out every other process. Committing each batch keeps the lock short.
        """
        self._conn.commit()

    def finish_scan(self, scan_id: int, meta: ScanMeta) -> None:
        """Write the scan totals and mark the scan complete."""
        self._conn.execute(
            """
            UPDATE scans
               SET finished_at = ?, total_size = ?, total_on_disk = ?, file_count = ?,
                   dir_count = ?, skipped = ?, complete = ?
             WHERE id = ?
            """,
            (
                meta.finished_at,
                meta.total_size,
                meta.total_on_disk,
                meta.file_count,
                meta.dir_count,
                meta.skipped,
                int(meta.complete),
                scan_id,
            ),
        )
        self._conn.commit()

    def latest_scan_id(self) -> int | None:
        row = self._conn.execute("SELECT id FROM scans ORDER BY id DESC LIMIT 1").fetchone()
        return int(row["id"]) if row else None

    def scan_meta(self, scan_id: int) -> ScanMeta | None:
        row = self._conn.execute("SELECT * FROM scans WHERE id = ?", (scan_id,)).fetchone()
        if row is None:
            return None
        return ScanMeta(
            scan_id=int(row["id"]),
            root=Path(row["root"]),
            started_at=float(row["started_at"]),
            finished_at=float(row["finished_at"] or 0.0),
            total_size=int(row["total_size"]),
            total_on_disk=int(row["total_on_disk"]),
            file_count=int(row["file_count"]),
            dir_count=int(row["dir_count"]),
            skipped=int(row["skipped"]),
            complete=bool(row["complete"]),
        )

    def scans(self) -> list[ScanMeta]:
        rows = self._conn.execute("SELECT id FROM scans ORDER BY id DESC").fetchall()
        return [meta for meta in (self.scan_meta(int(r["id"])) for r in rows) if meta]

    def scan_for_root(self, root: Path | str, *, complete_only: bool = True) -> ScanMeta | None:
        """The most recent scan of ``root``.

        This is what lets a command reuse an existing scan instead of walking
        the same tree again. Incomplete scans are skipped by default — a
        partial scan is missing whatever the walk did not reach.
        """
        sql = "SELECT id FROM scans WHERE root = ?"
        if complete_only:
            sql += " AND complete = 1"
        sql += " ORDER BY id DESC LIMIT 1"
        row = self._conn.execute(sql, (str(root),)).fetchone()
        return self.scan_meta(int(row["id"])) if row else None

    def delete_scan(self, scan_id: int) -> None:
        self._conn.execute("DELETE FROM scans WHERE id = ?", (scan_id,))
        self._conn.commit()

    # ----------------------------------------------------------------- entries

    def root_entry(self, scan_id: int) -> sqlite3.Row | None:
        row = self._conn.execute(
            "SELECT * FROM entries WHERE scan_id = ? AND parent_id IS NULL LIMIT 1",
            (scan_id,),
        ).fetchone()
        return cast(sqlite3.Row | None, row)

    def children(self, scan_id: int, parent_id: int | None) -> list[sqlite3.Row]:
        if parent_id is None:
            return self._conn.execute(
                "SELECT * FROM entries WHERE scan_id = ? AND parent_id IS NULL",
                (scan_id,),
            ).fetchall()
        return self._conn.execute(
            "SELECT * FROM entries WHERE scan_id = ? AND parent_id = ? ORDER BY name",
            (scan_id, parent_id),
        ).fetchall()

    def entry_by_path(self, scan_id: int, path: Path) -> sqlite3.Row | None:
        row = self._conn.execute(
            "SELECT * FROM entries WHERE scan_id = ? AND path = ?",
            (scan_id, str(path)),
        ).fetchone()
        return cast(sqlite3.Row | None, row)

    def iter_entries(self, scan_id: int) -> Iterator[sqlite3.Row]:
        yield from self._conn.execute(
            "SELECT * FROM entries WHERE scan_id = ? ORDER BY id",
            (scan_id,),
        )

    def count_entries(self, scan_id: int) -> int:
        row = self._conn.execute(
            "SELECT COUNT(*) AS n FROM entries WHERE scan_id = ?", (scan_id,)
        ).fetchone()
        return int(row["n"])

    def root_totals(self, scan_id: int) -> dict[str, int]:
        """Cumulative totals of the scan root.

        ``files`` is the transitive file count; ``subfolders`` counts only the
        root's immediate subdirectories (the total number of directories is
        tracked by the scanner itself).
        """
        row = self._conn.execute(
            """
            SELECT size, on_disk, file_count, dir_count
              FROM entries
             WHERE scan_id = ? AND parent_id IS NULL
             LIMIT 1
            """,
            (scan_id,),
        ).fetchone()
        if row is None:
            return {"size": 0, "on_disk": 0, "files": 0, "subfolders": 0}
        return {
            "size": int(row["size"]),
            "on_disk": int(row["on_disk"]),
            "files": int(row["file_count"]),
            "subfolders": int(row["dir_count"]),
        }

    def skipped_entries(self, scan_id: int) -> list[sqlite3.Row]:
        return self._conn.execute(
            "SELECT path, reason FROM skipped WHERE scan_id = ? ORDER BY path",
            (scan_id,),
        ).fetchall()

    # -------------------------------------------------------------------- tree

    def aggregate_scan(self, scan_id: int) -> None:
        """Roll file sizes up into cumulative directory totals.

        A scan that ran to the end already has the totals: the scanner writes
        them while it walks. This is the fallback for a scan that was stopped
        early — the directories are put back to zero and the file rows are
        rolled up again, so a partial scan still reports what it did see.

        Processing is done one depth level at a time, so memory stays
        proportional to the widest level rather than to the size of the tree.
        """
        self._conn.execute(
            """
            UPDATE entries
               SET size = 0, on_disk = 0, file_count = 0, dir_count = 0
             WHERE scan_id = ? AND is_dir = 1
            """,
            (scan_id,),
        )

        row = self._conn.execute(
            "SELECT MAX(depth) AS d FROM entries WHERE scan_id = ?", (scan_id,)
        ).fetchone()
        max_depth = int(row["d"] or 0)

        acc_size: dict[int, int] = {}
        acc_ondisk: dict[int, int] = {}
        acc_files: dict[int, int] = {}
        acc_dirs: dict[int, int] = {}

        for depth in range(max_depth, -1, -1):
            rows = self._conn.execute(
                """
                SELECT id, parent_id, is_dir, size, on_disk
                  FROM entries
                 WHERE scan_id = ? AND depth = ?
                """,
                (scan_id, depth),
            ).fetchall()

            updates: list[tuple[int, int, int, int, int]] = []
            for entry in rows:
                entry_id = int(entry["id"])
                is_dir = bool(entry["is_dir"])
                total_size = int(entry["size"]) + acc_size.get(entry_id, 0)
                total_ondisk = int(entry["on_disk"]) + acc_ondisk.get(entry_id, 0)
                total_files = (0 if is_dir else 1) + acc_files.get(entry_id, 0)
                total_dirs = acc_dirs.get(entry_id, 0)
                if is_dir:
                    # Files carry their own totals already; only directories
                    # are rolled up.
                    updates.append((total_size, total_ondisk, total_files, total_dirs, entry_id))

                parent_id = entry["parent_id"]
                if parent_id is not None:
                    parent = int(parent_id)
                    acc_size[parent] = acc_size.get(parent, 0) + total_size
                    acc_ondisk[parent] = acc_ondisk.get(parent, 0) + total_ondisk
                    acc_files[parent] = acc_files.get(parent, 0) + total_files
                    if is_dir:
                        acc_dirs[parent] = acc_dirs.get(parent, 0) + 1

            if updates:
                self._conn.executemany(
                    """
                    UPDATE entries
                       SET size = ?, on_disk = ?, file_count = ?, dir_count = ?
                     WHERE id = ?
                    """,
                    updates,
                )
        self._conn.commit()

    def build_tree(self, scan_id: int) -> Node | None:
        """Materialise the folder tree for a scan.

        Directory totals are already cumulative because :meth:`aggregate_scan`
        rolled them up, so a parent's total includes every descendant and must
        never be added to the totals of the children it already contains.
        """
        root_row = self.root_entry(scan_id)
        if root_row is None:
            return None

        nodes: dict[int, Node] = {}
        parents: dict[int, int | None] = {}
        for row in self._conn.execute(
            "SELECT * FROM entries WHERE scan_id = ? ORDER BY id",
            (scan_id,),
        ):
            entry_id = int(row["id"])
            nodes[entry_id] = Node(
                path=Path(row["path"]),
                name=row["name"],
                is_dir=bool(row["is_dir"]),
                size=int(row["size"]),
                on_disk=int(row["on_disk"]),
                file_count=int(row["file_count"]),
                dir_count=int(row["dir_count"]),
                kind=Kind(row["kind"]),
                mtime=float(row["mtime"]),
                protected=bool(row["protected"]),
                depth=int(row["depth"]),
            )
            parents[entry_id] = int(row["parent_id"]) if row["parent_id"] is not None else None

        for entry_id, parent_id in parents.items():
            if parent_id is None:
                continue
            parent = nodes.get(parent_id)
            if parent is not None:
                parent.children.append(nodes[entry_id])

        for node in nodes.values():
            node.children.sort(key=lambda n: (-n.size, n.name.lower()))

        return nodes[int(root_row["id"])]

    def largest_entries(
        self,
        scan_id: int,
        *,
        limit: int = 25,
        folders: bool = True,
        files: bool = True,
    ) -> list[sqlite3.Row]:
        """The largest folders and files of a scan, biggest first."""
        clauses: list[str] = []
        params: list[object] = [scan_id]
        if folders and files:
            pass
        elif folders:
            clauses.append("is_dir = 1")
        elif files:
            clauses.append("is_dir = 0")
        else:
            return []

        where = f" AND {' OR '.join(clauses)}" if clauses else ""
        params.append(limit)
        return self._conn.execute(
            f"""
            SELECT name, path, is_dir, size, on_disk, kind, protected
              FROM entries
             WHERE scan_id = ?{where}
             ORDER BY size DESC, name ASC
             LIMIT ?
            """,
            params,
        ).fetchall()

    # ------------------------------------------------------------------ helpers

    def kind_totals(self, scan_id: int) -> dict[str, int]:
        """Total size per file kind for a scan."""
        rows = self._conn.execute(
            """
            SELECT kind, SUM(size) AS total
              FROM entries
             WHERE scan_id = ? AND is_dir = 0
             GROUP BY kind
             ORDER BY total DESC
            """,
            (scan_id,),
        ).fetchall()
        return {row["kind"]: int(row["total"] or 0) for row in rows}

    def files_with_mtime(self, scan_id: int) -> list[tuple[int, float]]:
        """``(size, mtime)`` for every file in a scan."""
        return [
            (int(row["size"]), float(row["mtime"]))
            for row in self._conn.execute(
                "SELECT size, mtime FROM entries WHERE scan_id = ? AND is_dir = 0",
                (scan_id,),
            )
        ]

    def kind_counts(self, scan_id: int) -> dict[str, int]:
        """File count per file kind for a scan."""
        rows = self._conn.execute(
            """
            SELECT kind, COUNT(*) AS total
              FROM entries
             WHERE scan_id = ? AND is_dir = 0
             GROUP BY kind
            """,
            (scan_id,),
        ).fetchall()
        return {row["kind"]: int(row["total"]) for row in rows}
