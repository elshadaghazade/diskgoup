"""Filesystem scanner.

The scanner walks a tree once and writes every entry into the SQLite index. It is:

* **streaming** — file rows are written in batches, so memory stays flat on huge
  volumes;
* **partial-safe** — an unreadable entry is recorded as *skipped* and the scan
  continues, exactly as DiskBOX reports skipped-entry notices;
* **cancelable** — a progress callback can request a stop;
* **pausable** — a :class:`ScanControl` can hold the walk between two entries.
"""

from __future__ import annotations

import fnmatch
import os
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from diskgoup.core.kinds import classify_dir, classify_file
from diskgoup.core.models import Kind, ScanMeta
from diskgoup.core.protect import is_protected
from diskgoup.core.store import ScanIndex

#: Attribute bit meaning "hidden" on Windows.
_WIN_HIDDEN = 0x2

#: Kinds that a directory propagates to its whole subtree.
_INHERITED_KINDS = frozenset({Kind.CACHE, Kind.GAME, Kind.APPLICATION})


@dataclass(slots=True)
class ScanOptions:
    """Knobs for a scan run."""

    root: Path
    follow_symlinks: bool = False
    include_hidden: bool = True
    exclude: tuple[str, ...] = ()
    max_depth: int | None = None
    batch_size: int = 2000


@dataclass(slots=True)
class ScanProgress:
    """A progress snapshot handed to the progress callback."""

    files: int = 0
    folders: int = 0
    bytes_seen: int = 0
    current: Path | None = None
    started_at: float = field(default_factory=time.time)

    @property
    def elapsed(self) -> float:
        return max(0.0, time.time() - self.started_at)

    def to_dict(self) -> dict[str, object]:
        return {
            "files": self.files,
            "folders": self.folders,
            "bytes": self.bytes_seen,
            "current": str(self.current) if self.current else None,
            "elapsed": self.elapsed,
        }


@dataclass(slots=True)
class ScanResult:
    """Outcome of a scan run."""

    meta: ScanMeta
    skipped: list[tuple[Path, str]] = field(default_factory=list)
    canceled: bool = False

    def to_dict(self) -> dict[str, object]:
        return {
            **self.meta.to_dict(),
            "canceled": self.canceled,
            "skipped_entries": [{"path": str(p), "reason": r} for p, r in self.skipped],
        }


class ScanCanceledError(Exception):
    """Raised internally when a progress callback asks to stop the scan."""


class ScanControl:
    """A pause / cancel handle for a running scan.

    The walk is an explicit loop over an explicit stack, so it can be held
    between two entries without unwinding anything. The GUI holds one of
    these while a scan runs and can stop it at any time.
    """

    def __init__(self) -> None:
        self._resumed = threading.Event()
        self._resumed.set()
        self._canceled = threading.Event()

    @property
    def paused(self) -> bool:
        """True while the scan is holding still."""
        return not self._resumed.is_set()

    @property
    def canceled(self) -> bool:
        """True once the scan has been asked to stop."""
        return self._canceled.is_set()

    def pause(self) -> None:
        """Hold the scan at its next checkpoint."""
        self._resumed.clear()

    def resume(self) -> None:
        """Let a paused scan continue."""
        self._resumed.set()

    def cancel(self) -> None:
        """Stop the scan at its next checkpoint."""
        self._canceled.set()
        # Wake a paused scan so it can notice the cancel.
        self._resumed.set()

    def checkpoint(self) -> None:
        """Wait while paused; raise :class:`ScanCanceledError` if canceled."""
        self._resumed.wait()
        if self._canceled.is_set():
            raise ScanCanceledError


ProgressCallback = Callable[[ScanProgress], None]


class Scanner:
    """Walk a filesystem tree into a :class:`~diskgoup.core.store.ScanIndex`."""

    def __init__(self, index: ScanIndex, options: ScanOptions) -> None:
        self.index = index
        self.options = options

    # ------------------------------------------------------------------ public

    def run(
        self,
        progress: ProgressCallback | None = None,
        *,
        control: ScanControl | None = None,
    ) -> ScanResult:
        """Scan the configured root and return the result.

        ``control`` lets the caller pause or cancel the walk while it runs.
        """
        root = self.options.root.expanduser()
        try:
            root = root.resolve(strict=True)
        except OSError as exc:
            raise FileNotFoundError(f"cannot scan {root}: {exc}") from exc
        if not root.is_dir():
            raise NotADirectoryError(f"{root} is not a directory")

        scan_id = self.index.begin_scan(root)
        started = time.time()
        state = _RunState(started=started)

        pending: list[tuple[object, ...]] = []
        skipped: list[tuple[Path, str]] = []
        canceled = False

        try:
            root_kind = classify_dir(root.name)
            root_protected = is_protected(root, root_kind)
            root_id = self._insert_dir(
                scan_id, None, root, root_kind, root_protected, 0, started, state
            )
            stack: list[_PendingDir] = [
                _PendingDir(
                    path=root,
                    entry_id=root_id,
                    depth=0,
                    forced=root_kind if root_kind in _INHERITED_KINDS else None,
                    protected=root_protected,
                )
            ]

            while stack:
                current = stack.pop()
                try:
                    with os.scandir(current.path) as iterator:
                        for entry in iterator:
                            if control is not None:
                                control.checkpoint()
                            if progress is not None:
                                state.current = Path(entry.path)
                                progress(state.snapshot())

                            if not self.options.include_hidden and _is_hidden(entry):
                                continue
                            if self._excluded(entry.name, entry.path):
                                continue

                            try:
                                is_symlink = entry.is_symlink()
                                is_dir = entry.is_dir(follow_symlinks=self.options.follow_symlinks)
                            except OSError as exc:
                                skipped.append((Path(entry.path), str(exc)))
                                self.index.add_skipped(scan_id, Path(entry.path), str(exc))
                                continue

                            if is_symlink and not self.options.follow_symlinks:
                                # Record the link itself; never traverse it.
                                is_dir = False

                            try:
                                st = entry.stat(follow_symlinks=False)
                            except OSError as exc:
                                skipped.append((Path(entry.path), str(exc)))
                                self.index.add_skipped(scan_id, Path(entry.path), str(exc))
                                continue

                            child_path = Path(entry.path)
                            protected = current.protected or is_protected(child_path)

                            if is_dir:
                                kind = classify_dir(entry.name, forced=current.forced)
                                child_id = self._insert_dir(
                                    scan_id,
                                    current.entry_id,
                                    child_path,
                                    kind,
                                    protected,
                                    current.depth + 1,
                                    started,
                                    state,
                                )
                                if (
                                    self.options.max_depth is None
                                    or current.depth + 1 < self.options.max_depth
                                ):
                                    state.folders += 1
                                    stack.append(
                                        _PendingDir(
                                            path=child_path,
                                            entry_id=child_id,
                                            depth=current.depth + 1,
                                            forced=kind if kind in _INHERITED_KINDS else None,
                                            protected=protected,
                                        )
                                    )
                                continue

                            kind = classify_file(entry.name, parent_kind=current.forced)
                            size = int(st.st_size)
                            on_disk = _allocated_size(st)
                            state.files += 1
                            state.bytes_seen += size
                            state.on_disk_seen += on_disk
                            pending.append(
                                (
                                    current.entry_id,
                                    str(child_path),
                                    entry.name,
                                    0,
                                    size,
                                    on_disk,
                                    float(st.st_mtime),
                                    str(kind),
                                    int(protected),
                                    current.depth + 1,
                                )
                            )
                            if len(pending) >= self.options.batch_size:
                                self.index.add_entries(scan_id, pending)
                                pending.clear()
                                # Commit each batch: a scan that holds the
                                # write lock for its whole duration locks out
                                # every other process.
                                self.index.commit()
                except PermissionError as exc:
                    skipped.append((current.path, str(exc)))
                    self.index.add_skipped(scan_id, current.path, str(exc))
                except OSError as exc:
                    skipped.append((current.path, str(exc)))
                    self.index.add_skipped(scan_id, current.path, str(exc))

        except ScanCanceledError:
            canceled = True
        finally:
            if pending:
                self.index.add_entries(scan_id, pending)
                pending.clear()

        finished = time.time()

        # Roll file sizes up into cumulative directory totals so every view can
        # read them straight from SQL.
        self.index.aggregate_scan(scan_id)
        totals = self.index.root_totals(scan_id)

        meta = ScanMeta(
            scan_id=scan_id,
            root=root,
            started_at=started,
            finished_at=finished,
            total_size=totals["size"] or state.bytes_seen,
            total_on_disk=totals["on_disk"] or state.on_disk_seen,
            file_count=state.files,
            dir_count=state.folders,
            skipped=len(skipped),
            complete=not canceled,
        )
        self.index.finish_scan(scan_id, meta)
        return ScanResult(meta=meta, skipped=skipped, canceled=canceled)

    # ----------------------------------------------------------------- private

    def _insert_dir(
        self,
        scan_id: int,
        parent_id: int | None,
        path: Path,
        kind: Kind,
        protected: bool,
        depth: int,
        started: float,
        state: _RunState,
    ) -> int:
        """Insert a directory row and return its index id."""
        try:
            st = path.stat()
            mtime = float(st.st_mtime)
        except OSError:
            mtime = 0.0
        self.index.add_entries(
            scan_id,
            [
                (
                    parent_id,
                    str(path),
                    path.name,
                    1,
                    0,
                    0,
                    mtime,
                    str(kind),
                    int(protected),
                    depth,
                )
            ],
        )
        row = self.index.last_entry_id(scan_id)
        return row

    def _excluded(self, name: str, path: str) -> bool:
        for pattern in self.options.exclude:
            if fnmatch.fnmatch(name, pattern) or fnmatch.fnmatch(path, pattern):
                return True
        return False


@dataclass(slots=True)
class _PendingDir:
    """A directory queued for traversal."""

    path: Path
    entry_id: int
    depth: int
    forced: Kind | None
    protected: bool


@dataclass(slots=True)
class _RunState:
    """Mutable counters for a scan run."""

    started: float
    files: int = 0
    folders: int = 0
    bytes_seen: int = 0
    on_disk_seen: int = 0
    current: Path | None = None

    def snapshot(self) -> ScanProgress:
        return ScanProgress(
            files=self.files,
            folders=self.folders,
            bytes_seen=self.bytes_seen,
            current=self.current,
            started_at=self.started,
        )


def _is_hidden(entry: os.DirEntry[str]) -> bool:
    """True when an entry is hidden by platform convention."""
    if entry.name.startswith("."):
        return True
    try:
        attrs = getattr(entry.stat(follow_symlinks=False), "st_file_attributes", 0)
    except (OSError, AttributeError):
        return False
    return bool(attrs & _WIN_HIDDEN)


def _allocated_size(st: os.stat_result) -> int:
    """Bytes actually occupied on the volume.

    POSIX reports ``st_blocks`` in 512-byte units; Windows has no equivalent, so
    the logical size is used there.
    """
    blocks = getattr(st, "st_blocks", 0)
    if blocks:
        return int(blocks) * 512
    return int(st.st_size)
