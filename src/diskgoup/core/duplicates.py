"""Duplicate file detection.

DiskBOX does not treat equal names or equal sizes as evidence of duplication.
It runs a pipeline and only publishes a group after the files have matched byte
for byte:

1. **Size filtering** — candidates are grouped by size; different sizes are
   never compared.
2. **Prefix sampling** — the head of each candidate is sampled.
3. **Bounded middle/tail sampling** — bounded samples from the middle and the
   end eliminate further candidates.
4. **Full SHA-256** — survivors are hashed in full.
5. **Exact byte comparison** — a group is published only after the files also
   match byte for byte.

Sampling is a performance shortcut only; it never establishes equality on its
own. Reads are streamed, so large files stay eligible — the retained comparison
buffer is not a maximum searchable file size.

Zero-byte files are excluded, and hard links pointing at the same underlying
file are excluded.

Four things make the search usable on a real disk rather than only on a folder
of test files:

* The **size comes from the scan index**. The search never asks the disk how
  big a file is — asking it once per file, twice over, is what made the search
  crawl on a volume with a million files.
* A file that **fits in one read** is hashed straight away. The samples would
  only repeat what the hash already says, so the head, the middle and the
  tail of a small file come out of the same read that hashes it.
* The **digest is remembered**. Hashing a file means reading all of it, so the
  digests are kept in the index and reused while the file still has the size
  and the modification time it had when it was hashed. The second search of a
  scan does not read the files again.
* The **work runs on several workers at a time**. Every stage of the pipeline
  reads and hashes files, and the work of one file is mostly bookkeeping in
  Python — which is what the GIL holds on to. A stage of many files is
  therefore handed to a pool of processes, and a stage of a few files to a
  pool of threads, which start far more quickly.
"""

from __future__ import annotations

import contextlib
import hashlib
import os
import sqlite3
from collections.abc import Callable, Iterable, Sequence
from concurrent.futures.process import BrokenProcessPool
from dataclasses import dataclass, field
from pathlib import Path

from diskgoup.core.parallel import Pool
from diskgoup.core.store import ScanIndex

#: Bytes read for the prefix sample.
PREFIX_SAMPLE = 64 * 1024
#: Bytes read for the middle sample.
MIDDLE_SAMPLE = 64 * 1024
#: Bytes read for the tail sample.
TAIL_SAMPLE = 64 * 1024
#: Chunk size for streaming reads.
CHUNK = 1024 * 1024

#: How many files are read between two progress messages.
PROGRESS_EVERY = 250

#: What a worker is given: the path of a file and the size it has.
Payload = tuple[str, int]


@dataclass(slots=True)
class Candidate:
    """A file the search looks at.

    The size and the modification time come from the scan index — the disk
    already told us, and asking it again is what made the search slow.
    """

    path: Path
    size: int
    mtime: float = 0.0
    #: The row of the scan index, when the candidate came from one.
    entry_id: int = 0


@dataclass(slots=True)
class HashCache:
    """The digest of a file, remembered between searches.

    A digest is only reused while the file still has the size and the
    modification time it had when it was hashed — a file that changed since
    then is hashed again.
    """

    known: dict[str, tuple[int, float, int, str]] = field(default_factory=dict)

    def get(self, path: str, size: int, mtime: float) -> str | None:
        found = self.known.get(path)
        if found is None:
            return None
        cached_size, cached_mtime, _, digest = found
        if cached_size != size or cached_mtime != mtime:
            return None
        return digest

    def put(self, path: str, size: int, mtime: float, entry_id: int, digest: str) -> None:
        self.known[path] = (size, mtime, entry_id, digest)

    def records(self) -> list[tuple[int, int, float, str]]:
        """``(entry_id, size, mtime, digest)`` of every remembered digest."""
        return [
            (entry_id, size, mtime, digest) for size, mtime, entry_id, digest in self.known.values()
        ]


@dataclass(slots=True)
class DuplicateGroup:
    """A set of files with identical content."""

    sha256: str
    size: int
    paths: list[Path] = field(default_factory=list)
    keep: Path | None = None

    @property
    def copies(self) -> int:
        return len(self.paths)

    @property
    def reclaimable(self) -> int:
        """Bytes that could be freed by keeping one copy."""
        if len(self.paths) < 2:
            return 0
        return self.size * (len(self.paths) - 1)

    def to_dict(self) -> dict[str, object]:
        return {
            "sha256": self.sha256,
            "size": self.size,
            "copies": self.copies,
            "reclaimable": self.reclaimable,
            "keep": str(self.keep) if self.keep else None,
            "paths": [str(path) for path in self.paths],
        }


@dataclass(slots=True)
class DuplicateReport:
    """The outcome of a duplicate scan."""

    groups: list[DuplicateGroup] = field(default_factory=list)
    candidates: int = 0
    skipped: list[tuple[Path, str]] = field(default_factory=list)

    @property
    def total_reclaimable(self) -> int:
        return sum(group.reclaimable for group in self.groups)

    def to_dict(self) -> dict[str, object]:
        return {
            "groups": [group.to_dict() for group in self.groups],
            "group_count": len(self.groups),
            "candidates": self.candidates,
            "total_reclaimable": self.total_reclaimable,
            "skipped": [{"path": str(p), "reason": r} for p, r in self.skipped],
        }


class _Ticker:
    """Reports progress every few files, so a long search is not silent."""

    def __init__(self, callback: Callable[[str], None] | None, every: int = PROGRESS_EVERY) -> None:
        self._callback = callback
        self._every = every
        self._last = 0

    def say(self, message: str) -> None:
        if self._callback:
            self._callback(message)

    def step(self, done: int, total: int, message: str) -> None:
        if not self._callback:
            return
        if done - self._last >= self._every:
            self._last = done
            self._callback(message)


def _inode(path: Path) -> tuple[int, int] | None:
    """``(st_dev, st_ino)`` for a path, or ``None`` when unavailable."""
    try:
        info = os.stat(path)
    except OSError:
        return None
    inode = getattr(info, "st_ino", 0)
    if not inode:
        return None
    return (info.st_dev, inode)


def _drop_hard_links(candidates: Sequence[Candidate]) -> list[Candidate]:
    """Remove candidates that are hard links to another one in the same set.

    A hard link is not a second copy — it is the same file with a second
    name — so it must never be reported as a duplicate.
    """
    seen: set[tuple[int, int]] = set()
    result: list[Candidate] = []
    for candidate in candidates:
        identity = _inode(candidate.path)
        if identity is not None:
            if identity in seen:
                continue
            seen.add(identity)
        result.append(candidate)
    return result


def _sample(path: str, offset: int, length: int) -> bytes:
    """Read ``length`` bytes at ``offset``; fewer bytes at the end of a file."""
    try:
        with open(path, "rb") as handle:
            handle.seek(offset)
            return handle.read(length)
    except OSError:
        return b""


def _prefix_digest(payload: Payload) -> str:
    """Digest of the head of a file."""
    path, _size = payload
    return hashlib.sha256(_sample(path, 0, PREFIX_SAMPLE)).hexdigest()


def _middle_tail_digest(payload: Payload) -> str:
    """Digest of bounded samples from the middle and the tail of a file.

    Both samples come out of one open file — the middle and the tail of a
    file are two seeks, not two opens.
    """
    path, size = payload
    middle_offset = max(0, (size // 2) - (MIDDLE_SAMPLE // 2))
    tail_offset = max(0, size - TAIL_SAMPLE)
    digest = hashlib.sha256()
    try:
        with open(path, "rb") as handle:
            handle.seek(middle_offset)
            digest.update(handle.read(MIDDLE_SAMPLE))
            handle.seek(tail_offset)
            digest.update(handle.read(TAIL_SAMPLE))
    except OSError:
        pass
    return digest.hexdigest()


def _full_digest(payload: Payload) -> str | None:
    """SHA-256 of the whole file, streamed."""
    path, _size = payload
    digest = hashlib.sha256()
    try:
        with open(path, "rb") as handle:
            while chunk := handle.read(CHUNK):
                digest.update(chunk)
    except OSError:
        return None
    return digest.hexdigest()


def _identical(left: str, right: str) -> bool:
    """True when two files have byte-for-byte identical content."""
    try:
        if os.stat(left).st_size != os.stat(right).st_size:
            return False
        with open(left, "rb") as first, open(right, "rb") as second:
            while True:
                a = first.read(CHUNK)
                b = second.read(CHUNK)
                if a != b:
                    return False
                if not a:
                    return True
    except OSError:
        return False


def _same_bytes(pair: tuple[str, str]) -> bool:
    """True when the two files of a pair have identical content."""
    return _identical(pair[0], pair[1])


def _group_by(
    candidates: Iterable[Candidate], key: Callable[[Candidate], object]
) -> list[list[Candidate]]:
    buckets: dict[object, list[Candidate]] = {}
    for candidate in candidates:
        buckets.setdefault(key(candidate), []).append(candidate)
    return [group for group in buckets.values() if len(group) > 1]


def _shared(candidates: Sequence[Candidate], key: Callable[[Candidate], object]) -> list[Candidate]:
    """The candidates whose key is shared with another candidate.

    A candidate with a key of its own cannot be a duplicate of anything, so
    the pipeline never reads it again.
    """
    buckets: dict[object, list[Candidate]] = {}
    for candidate in candidates:
        buckets.setdefault(key(candidate), []).append(candidate)
    return [candidate for bucket in buckets.values() if len(bucket) > 1 for candidate in bucket]


def _candidates(items: Iterable[Path | Candidate], report: DuplicateReport) -> list[Candidate]:
    """Turn what the caller gave us into candidates whose size is known."""
    result: list[Candidate] = []
    for item in items:
        if isinstance(item, Candidate):
            candidate = item
        else:
            try:
                info = os.stat(item)
            except OSError as exc:
                report.skipped.append((item, str(exc)))
                continue
            candidate = Candidate(path=item, size=info.st_size, mtime=info.st_mtime)
        if candidate.size == 0:
            # An empty file is not worth a place in a duplicate group.
            continue
        result.append(candidate)
    return result


def _ordered(candidates: Sequence[Candidate]) -> list[Candidate]:
    """Put the copy to keep first.

    The oldest copy is kept: it is the one that was there first, and the
    content is the same either way, so the age is the only thing that tells
    the copies apart.
    """
    oldest = sorted(candidates, key=lambda item: (item.mtime, str(item.path)))
    keeper = oldest[0]
    return [keeper, *sorted(oldest[1:], key=lambda item: str(item.path))]


def _fresh(candidate: Candidate) -> tuple[int, float]:
    """The size and the modification time the file has now.

    The file may have changed since the scan; the digest is taken from what
    it holds now, so the group reports the size it really has.
    """
    try:
        info = os.stat(candidate.path)
    except OSError:
        return candidate.size, candidate.mtime
    return info.st_size, info.st_mtime


def _hashed(
    candidates: Sequence[Candidate],
    digests: dict[str, str],
    cache: HashCache | None,
    pool: Pool,
) -> list[Candidate]:
    """The candidates whose whole file was hashed, with their digests kept.

    The size and the modification time are asked for here, in one place, so
    that the digest cache can be checked without a worker having to know
    about it — and so that a worker only has to read and hash.
    """
    payloads: list[Payload] = []
    pending: dict[str, Candidate] = {}
    alive: list[Candidate] = []
    for candidate in candidates:
        size, mtime = _fresh(candidate)
        if size == 0:
            # The file is empty now — it cannot be a copy of anything.
            continue
        candidate.size = size
        candidate.mtime = mtime
        path = str(candidate.path)
        known = cache.get(path, size, mtime) if cache is not None else None
        if known is not None:
            digests[path] = known
            alive.append(candidate)
            continue
        payloads.append((path, size))
        pending[path] = candidate

    digests_found = pool.run(_full_digest, payloads)
    for (path, size), digest in zip(payloads, digests_found, strict=True):
        if digest is None:
            continue
        candidate = pending[path]
        digests[path] = digest
        if cache is not None:
            cache.put(path, size, candidate.mtime, candidate.entry_id, digest)
        alive.append(candidate)
    return alive


def find_duplicates(
    candidates: Iterable[Path | Candidate],
    *,
    progress: Callable[[str], None] | None = None,
    cache: HashCache | None = None,
    workers: int | None = None,
    processes: bool | None = None,
) -> DuplicateReport:
    """Find groups of byte-identical files among ``candidates``.

    Every stage of the pipeline hands its files to a pool of workers, so
    that a stage reads and hashes several files at a time instead of one
    after the other. A stage of many files runs on processes, a stage of a
    few on threads — see :mod:`diskgoup.core.parallel`.
    """
    report = DuplicateReport()
    ticker = _Ticker(progress)

    # Stage 0 — drop zero-byte files. The size is known, so the disk is not
    # asked about the files that cannot be in a group.
    items = _candidates(candidates, report)
    report.candidates = len(items)
    if not items:
        return report

    # Stage 1 — size filtering.
    size_groups = _group_by(items, lambda item: item.size)
    ticker.say(f"{len(size_groups)} size groups")
    if not size_groups:
        return report

    # The pool decides the backend per stage: a stage of many files runs on
    # processes, a stage of a few on threads.
    pool = Pool(workers, processes=processes)
    try:
        try:
            _search(items, report, ticker, cache, pool)
        except BrokenProcessPool:
            # The workers did not start — a machine that does not allow a
            # process of its own is not a reason to fail the search.
            report.groups.clear()
            pool.close()
            pool = Pool(workers, processes=False)
            _search(items, report, ticker, cache, pool)
    finally:
        pool.close()

    report.groups.sort(key=lambda group: (-group.reclaimable, str(group.paths[0])))
    ticker.say(f"{len(report.groups)} duplicate groups")
    return report


def _search(
    items: Sequence[Candidate],
    report: DuplicateReport,
    ticker: _Ticker,
    cache: HashCache | None,
    pool: Pool,
) -> None:
    """Run the pipeline over the candidates and fill the report with groups."""
    digests: dict[str, str] = {}
    total = len(items)

    # A file that fits in the prefix sample is hashed straight away: the
    # samples would only repeat what the hash already says, and one read of
    # the file is enough for all of it.
    small = [candidate for candidate in items if candidate.size <= PREFIX_SAMPLE]
    large = [candidate for candidate in items if candidate.size > PREFIX_SAMPLE]

    alive = _hashed(small, digests, cache, pool)
    ticker.step(len(small), total, f"hashed {len(small)} of {total} files")

    # Stage 2 — prefix sampling.
    payloads = [(str(candidate.path), candidate.size) for candidate in large]
    heads = {
        path: digest
        for (path, _size), digest in zip(payloads, pool.run(_prefix_digest, payloads), strict=True)
    }
    large = _shared(large, lambda candidate: (candidate.size, heads[str(candidate.path)]))
    ticker.step(len(small) + len(large), total, f"sampled {len(large)} of {total} files")

    # Stage 3 — bounded middle/tail sampling.
    payloads = [(str(candidate.path), candidate.size) for candidate in large]
    middles = {
        path: digest
        for (path, _size), digest in zip(
            payloads, pool.run(_middle_tail_digest, payloads), strict=True
        )
    }
    large = _shared(
        large,
        lambda candidate: (
            candidate.size,
            heads[str(candidate.path)],
            middles[str(candidate.path)],
        ),
    )
    ticker.step(len(small) + len(large), total, f"sampled {len(large)} of {total} files")

    # Stage 4 — full SHA-256.
    alive += _hashed(large, digests, cache, pool)
    ticker.step(total, total, f"hashed {total} of {total} files")

    digest_groups = _group_by(alive, lambda candidate: digests[str(candidate.path)])
    ticker.say(f"{len(digest_groups)} groups after SHA-256")
    if not digest_groups:
        return

    # Stage 5 — exact byte comparison.
    members: list[list[Candidate]] = []
    pairs: list[tuple[str, str]] = []
    for group in digest_groups:
        kept = _drop_hard_links(_ordered(group))
        if len(kept) < 2:
            continue
        members.append(kept)
        pairs.append((str(kept[0].path), str(kept[1].path)))

    verdicts = pool.run(_same_bytes, pairs)
    for kept, same in zip(members, verdicts, strict=True):
        if same:
            report.groups.append(_group_of(kept, digests))
            continue
        # The digests match but the bytes do not: a collision. The group is
        # split by comparing the bytes of every member.
        for cluster in _identical_clusters(kept):
            report.groups.append(_group_of(cluster, digests))


def _group_of(members: Sequence[Candidate], digests: dict[str, str]) -> DuplicateGroup:
    """Build the group of identical files."""
    digest = digests.get(str(members[0].path), "")
    return DuplicateGroup(
        sha256=digest,
        size=members[0].size,
        paths=[member.path for member in members],
        keep=members[0].path,
    )


def _identical_clusters(group: Sequence[Candidate]) -> list[list[Candidate]]:
    """Split a group into byte-identical clusters.

    Two files can share a SHA-256 and still differ in the astronomically
    unlikely event of a collision, so the final stage compares the bytes. A
    cluster needs at least two members to be a duplicate group.
    """
    clusters: list[list[Candidate]] = [[group[0]]]
    for candidate in group[1:]:
        for cluster in clusters:
            if _identical(str(cluster[0].path), str(candidate.path)):
                cluster.append(candidate)
                break
        else:
            clusters.append([candidate])
    return [cluster for cluster in clusters if len(cluster) > 1]


def search_scan(
    index: ScanIndex,
    scan_id: int,
    *,
    progress: Callable[[str], None] | None = None,
    min_size: int = 0,
    max_size: int | None = None,
    kind: str | None = None,
    workers: int | None = None,
    processes: bool | None = None,
) -> DuplicateReport:
    """Find the duplicate groups of a scan.

    The sizes come from the index — the disk is not asked about every file —
    and the digests that were computed before are reused, so a repeated search
    does not read the files again.
    """
    # The index drops the files whose size no other file has: they cannot be
    # a duplicate of anything, so the search never even looks at them.
    items = [
        Candidate(path=Path(path), size=size, mtime=mtime, entry_id=entry_id)
        for entry_id, path, size, mtime, _kind in index.duplicate_candidates(
            scan_id, min_size=min_size, max_size=max_size, kind=kind
        )
    ]

    cache = HashCache()
    for path, size, mtime, entry_id, digest in index.cached_hashes(scan_id):
        cache.known[path] = (size, mtime, entry_id, digest)

    report = find_duplicates(
        items, progress=progress, cache=cache, workers=workers, processes=processes
    )
    # The number of candidates is every file the filters let through, not
    # only the ones that share their size with another file.
    report.candidates = index.count_files(scan_id, min_size=min_size, max_size=max_size, kind=kind)
    _remember(index, scan_id, cache)
    return report


def _remember(index: ScanIndex, scan_id: int, cache: HashCache) -> None:
    """Write the digests back to the index.

    They are an optimisation, not a part of the result: a scan that holds the
    write lock must not fail the search over it.
    """
    with contextlib.suppress(sqlite3.OperationalError):
        index.save_hashes(scan_id, cache.records())
