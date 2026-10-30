"""Filesystem scanner.

The scanner walks a tree once and writes every entry into the SQLite index. It is:

* **streaming** — file rows are written in batches, so memory stays flat on huge
  volumes;
* **partial-safe** — an unreadable entry is recorded as *skipped* and the scan
  continues, exactly as DiskBOX reports skipped-entry notices;
* **cancelable** — a progress callback can request a stop;
* **pausable** — a :class:`ScanControl` can hold the walk between two entries;
* **single-pass** — the totals of a directory are accumulated while its subtree
  is walked, so the index is never read back to be rolled up afterwards.
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
from diskgoup.core.protect import DirGuard, entry_is_protected, guard_for, is_protected
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
    #: Collect a timing breakdown of the run.
    profile: bool = False


@dataclass(slots=True)
class ScanProgress:
    """A progress snapshot handed to the progress callback."""

    files: int = 0
    folders: int = 0
    bytes_seen: int = 0
    current: str | None = None
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
    #: Where the time went, when the run was profiled.
    timings: dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> dict[str, object]:
        data: dict[str, object] = {
            **self.meta.to_dict(),
            "canceled": self.canceled,
            "skipped_entries": [{"path": str(p), "reason": r} for p, r in self.skipped],
        }
        if self.timings:
            data["timings"] = self.timings
        return data


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


@dataclass(slots=True)
class _Profiler:
    """Collects a timing breakdown of a scan run."""

    enabled: bool = False
    spans: dict[str, float] = field(default_factory=dict)

    def add(self, name: str, seconds: float) -> None:
        self.spans[name] = self.spans.get(name, 0.0) + seconds

    def to_dict(self) -> dict[str, float]:
        return {name: round(value, 4) for name, value in sorted(self.spans.items())}


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

        profiler = _Profiler(enabled=self.options.profile)
        profiling = profiler.enabled

        options = self.options
        follow_symlinks = options.follow_symlinks
        include_hidden = options.include_hidden
        exclude = options.exclude
        max_depth = options.max_depth
        batch_size = options.batch_size

        walk_started = time.perf_counter()
        try:
            root_kind = classify_dir(root.name)
            root_protected = is_protected(root, root_kind)
            root_state = _DirState()
            root_id = self._insert_dir(
                scan_id, None, root, root.name, root_kind, root_protected, 0, _mtime(root)
            )
            root_state.entry_id = root_id
            stack: list[_PendingDir] = [
                _PendingDir(
                    path=root,
                    entry_id=root_id,
                    depth=0,
                    forced=root_kind if root_kind in _INHERITED_KINDS else None,
                    guard=guard_for(root, protected=root_protected),
                    state=root_state,
                )
            ]

            while stack:
                current = stack.pop()
                cstate = current.state
                cguard = current.guard
                cforced = current.forced
                cdepth = current.depth
                cpath = current.path
                try:
                    with os.scandir(cpath) as iterator:
                        for entry in iterator:
                            if control is not None:
                                control.checkpoint()

                            if progress is not None:
                                # The path is kept as a string: building a Path
                                # for every entry was a measurable part of the
                                # cost of a scan.
                                state.current = entry.path
                                progress(state.snapshot())

                            name = entry.name
                            if not include_hidden and _is_hidden(entry):
                                continue
                            if exclude and self._excluded(name, entry.path):
                                continue

                            try:
                                is_symlink = entry.is_symlink()
                                is_dir = entry.is_dir(follow_symlinks=follow_symlinks)
                            except OSError as exc:
                                skipped.append((Path(entry.path), str(exc)))
                                self.index.add_skipped(scan_id, Path(entry.path), str(exc))
                                continue

                            if is_symlink and not follow_symlinks:
                                # Record the link itself; never traverse it.
                                is_dir = False

                            try:
                                st = entry.stat(follow_symlinks=False)
                            except OSError as exc:
                                skipped.append((Path(entry.path), str(exc)))
                                self.index.add_skipped(scan_id, Path(entry.path), str(exc))
                                continue

                            if profiling:
                                mark = time.perf_counter()
                            protected = entry_is_protected(entry.path, name, st, cguard)
                            if profiling:
                                profiler.add("protect", time.perf_counter() - mark)

                            if is_dir:
                                if profiling:
                                    mark = time.perf_counter()
                                kind = classify_dir(name, forced=cforced)
                                if profiling:
                                    profiler.add("classify", time.perf_counter() - mark)
                                child_path = Path(entry.path)
                                child_state = _DirState(parent=cstate)
                                child_id = self._insert_dir(
                                    scan_id,
                                    cstate.entry_id,
                                    child_path,
                                    name,
                                    kind,
                                    protected,
                                    cdepth + 1,
                                    float(st.st_mtime),
                                )
                                child_state.entry_id = child_id
                                cstate.child_dirs += 1
                                if max_depth is None or cdepth + 1 < max_depth:
                                    state.folders += 1
                                    stack.append(
                                        _PendingDir(
                                            path=child_path,
                                            entry_id=child_id,
                                            depth=cdepth + 1,
                                            forced=kind if kind in _INHERITED_KINDS else None,
                                            guard=guard_for(entry.path, protected=protected),
                                            state=child_state,
                                        )
                                    )
                                else:
                                    # The row exists, but the subtree below it is
                                    # not walked.
                                    self._finish_dir(child_state, profiler)
                                continue

                            if profiling:
                                mark = time.perf_counter()
                            kind = classify_file(name, parent_kind=cforced)
                            if profiling:
                                profiler.add("classify", time.perf_counter() - mark)
                            size = int(st.st_size)
                            on_disk = _allocated_size(st)
                            state.files += 1
                            state.bytes_seen += size
                            state.on_disk_seen += on_disk
                            cstate.own_size += size
                            cstate.own_on_disk += on_disk
                            cstate.own_files += 1
                            pending.append(
                                (
                                    cstate.entry_id,
                                    entry.path,
                                    name,
                                    0,
                                    size,
                                    on_disk,
                                    float(st.st_mtime),
                                    str(kind),
                                    int(protected),
                                    cdepth + 1,
                                    1,
                                )
                            )
                            if len(pending) >= batch_size:
                                if profiling:
                                    mark = time.perf_counter()
                                self.index.add_entries(scan_id, pending)
                                pending.clear()
                                if profiling:
                                    profiler.add("insert", time.perf_counter() - mark)
                                # Commit each batch: a scan that holds the
                                # write lock for its whole duration locks out
                                # every other process.
                                self.index.commit()
                except PermissionError as exc:
                    skipped.append((cpath, str(exc)))
                    self.index.add_skipped(scan_id, cpath, str(exc))
                except OSError as exc:
                    skipped.append((cpath, str(exc)))
                    self.index.add_skipped(scan_id, cpath, str(exc))

                # The directory has been walked; it is finished once every
                # child directory is.
                cstate.scanned = True
                if cstate.finished_children == cstate.child_dirs:
                    self._finish_dir(cstate, profiler)

        except ScanCanceledError:
            canceled = True
        finally:
            if pending:
                self.index.add_entries(scan_id, pending)
                pending.clear()
                self.index.commit()

        if profiling:
            profiler.add("walk", time.perf_counter() - walk_started)

        finished = time.time()

        if canceled:
            # The walk stopped early, so the directories that were never
            # finished carry no totals. Roll the files up once more to give
            # the partial scan the best numbers it can.
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

        timings = profiler.to_dict()
        if timings:
            timings["total"] = round(finished - started, 4)
        return ScanResult(meta=meta, skipped=skipped, canceled=canceled, timings=timings)

    # ----------------------------------------------------------------- private

    def _insert_dir(
        self,
        scan_id: int,
        parent_id: int | None,
        path: Path,
        name: str,
        kind: Kind,
        protected: bool,
        depth: int,
        mtime: float,
    ) -> int:
        """Insert a directory row and return its index id."""
        return self.index.add_entry(
            scan_id,
            (
                parent_id,
                str(path),
                name,
                1,
                0,
                0,
                mtime,
                str(kind),
                int(protected),
                depth,
                0,
            ),
        )

    def _finish_dir(self, dstate: _DirState, profiler: _Profiler) -> None:
        """Write the totals of a directory whose subtree is complete.

        The totals travel up the tree: a finished directory adds what it holds
        to its parent, and the parent is finished too once its last child is.
        """
        profiling = profiler.enabled
        while True:
            size = dstate.own_size + dstate.sub_size
            on_disk = dstate.own_on_disk + dstate.sub_on_disk
            files = dstate.own_files + dstate.sub_files
            if profiling:
                mark = time.perf_counter()
            self.index.set_totals(dstate.entry_id, size, on_disk, files, dstate.child_dirs)
            if profiling:
                profiler.add("rollup", time.perf_counter() - mark)

            parent = dstate.parent
            if parent is None:
                return
            parent.sub_size += size
            parent.sub_on_disk += on_disk
            parent.sub_files += files
            parent.finished_children += 1
            if not (parent.scanned and parent.finished_children == parent.child_dirs):
                return
            dstate = parent

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
    guard: DirGuard
    state: _DirState


@dataclass(slots=True)
class _DirState:
    """The totals of one directory while its subtree is walked."""

    entry_id: int = 0
    parent: _DirState | None = None
    #: What the files directly in this directory add up to.
    own_size: int = 0
    own_on_disk: int = 0
    own_files: int = 0
    #: What the finished child directories brought in.
    sub_size: int = 0
    sub_on_disk: int = 0
    sub_files: int = 0
    #: How many child directories were found, and how many of them are done.
    child_dirs: int = 0
    finished_children: int = 0
    #: True once the directory itself has been walked.
    scanned: bool = False


@dataclass(slots=True)
class _RunState:
    """Mutable counters for a scan run."""

    started: float
    files: int = 0
    folders: int = 0
    bytes_seen: int = 0
    on_disk_seen: int = 0
    current: str | None = None

    def snapshot(self) -> ScanProgress:
        return ScanProgress(
            files=self.files,
            folders=self.folders,
            bytes_seen=self.bytes_seen,
            current=self.current,
            started_at=self.started,
        )


def _mtime(path: Path) -> float:
    """The modification time of a path, or zero when it cannot be read."""
    try:
        return float(path.stat().st_mtime)
    except OSError:
        return 0.0


def _is_hidden(entry: os.DirEntry[str]) -> bool:
    """True when an entry is hidden by platform convention."""
    if entry.name.startswith("."):
        return True
    if not hasattr(os.stat_result, "st_file_attributes"):
        # Only Windows marks entries as hidden with an attribute; everywhere
        # else the name is the only convention.
        return False
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
