"""Duplicate file detection.

DiskBOX does not treat equal names or equal sizes as evidence of duplication.
It runs a five-stage pipeline and only publishes a group after the files have
matched byte for byte:

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
"""

from __future__ import annotations

import hashlib
import os
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass, field
from pathlib import Path

#: Bytes read for the prefix sample.
PREFIX_SAMPLE = 64 * 1024
#: Bytes read for the middle sample.
MIDDLE_SAMPLE = 64 * 1024
#: Bytes read for the tail sample.
TAIL_SAMPLE = 64 * 1024
#: Chunk size for streaming reads.
CHUNK = 1024 * 1024


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


def _drop_hard_links(paths: Sequence[Path]) -> list[Path]:
    """Remove paths that are hard links to another path in the same set."""
    seen: set[tuple[int, int]] = set()
    result: list[Path] = []
    for path in paths:
        identity = _inode(path)
        if identity is not None:
            if identity in seen:
                continue
            seen.add(identity)
        result.append(path)
    return result


def _sample(path: Path, offset: int, length: int) -> bytes:
    """Read ``length`` bytes at ``offset``; fewer bytes at the end of a file."""
    try:
        with path.open("rb") as handle:
            handle.seek(offset)
            return handle.read(length)
    except OSError:
        return b""


def _prefix_digest(path: Path) -> str:
    return hashlib.sha256(_sample(path, 0, PREFIX_SAMPLE)).hexdigest()


def _middle_tail_digest(path: Path, size: int) -> str:
    """Digest of bounded samples from the middle and the tail of a file."""
    middle_offset = max(0, (size // 2) - (MIDDLE_SAMPLE // 2))
    tail_offset = max(0, size - TAIL_SAMPLE)
    digest = hashlib.sha256()
    digest.update(_sample(path, middle_offset, MIDDLE_SAMPLE))
    digest.update(_sample(path, tail_offset, TAIL_SAMPLE))
    return digest.hexdigest()


def _full_digest(path: Path) -> str | None:
    """SHA-256 of the whole file, streamed."""
    digest = hashlib.sha256()
    try:
        with path.open("rb") as handle:
            while chunk := handle.read(CHUNK):
                digest.update(chunk)
    except OSError:
        return None
    return digest.hexdigest()


def _identical(left: Path, right: Path) -> bool:
    """True when two files have byte-for-byte identical content."""
    try:
        if left.stat().st_size != right.stat().st_size:
            return False
        with left.open("rb") as first, right.open("rb") as second:
            while True:
                a = first.read(CHUNK)
                b = second.read(CHUNK)
                if a != b:
                    return False
                if not a:
                    return True
    except OSError:
        return False


def _group_by(paths: Iterable[Path], key: Callable[[Path], object]) -> list[list[Path]]:
    buckets: dict[object, list[Path]] = {}
    for path in paths:
        buckets.setdefault(key(path), []).append(path)
    return [group for group in buckets.values() if len(group) > 1]


def find_duplicates(
    paths: Iterable[Path],
    *,
    progress: Callable[[str], None] | None = None,
) -> DuplicateReport:
    """Find groups of byte-identical files among ``paths``."""
    report = DuplicateReport()

    # Stage 0 — drop zero-byte files and hard links to the same file.
    candidates: list[Path] = []
    for path in paths:
        try:
            size = path.stat().st_size
        except OSError as exc:
            report.skipped.append((path, str(exc)))
            continue
        if size == 0:
            continue
        candidates.append(path)

    candidates = _drop_hard_links(candidates)
    report.candidates = len(candidates)
    if not candidates:
        return report

    # Stage 1 — size filtering.
    def size_of(path: Path) -> int:
        try:
            return path.stat().st_size
        except OSError:
            return -1

    size_groups = _group_by(candidates, size_of)
    if progress:
        progress(f"{len(size_groups)} size groups")
    if not size_groups:
        return report

    # Stage 2 — prefix sampling.
    prefix_groups: list[list[Path]] = []
    for group in size_groups:
        prefix_groups.extend(_group_by(group, _prefix_digest))
    if progress:
        progress(f"{len(prefix_groups)} groups after prefix sampling")
    if not prefix_groups:
        return report

    # Stage 3 — bounded middle/tail sampling.
    middle_groups: list[list[Path]] = []
    for group in prefix_groups:
        size = size_of(group[0])

        def sample_digest(path: Path, file_size: int = size) -> str:
            return _middle_tail_digest(path, file_size)

        middle_groups.extend(_group_by(group, sample_digest))
    if progress:
        progress(f"{len(middle_groups)} groups after middle/tail sampling")
    if not middle_groups:
        return report

    # Stage 4 — full SHA-256.
    digest_groups: list[list[Path]] = []
    for group in middle_groups:
        digest_groups.extend(_group_by(group, lambda path: _full_digest(path) or ""))
    if progress:
        progress(f"{len(digest_groups)} groups after SHA-256")
    if not digest_groups:
        return report

    # Stage 5 — exact byte comparison.
    for group in digest_groups:
        for cluster in _identical_clusters(group):
            digest = _full_digest(cluster[0]) or ""
            size = size_of(cluster[0])
            members = sorted(cluster, key=lambda path: str(path))
            report.groups.append(
                DuplicateGroup(
                    sha256=digest,
                    size=size,
                    paths=members,
                    keep=members[0],
                )
            )

    report.groups.sort(key=lambda group: (-group.reclaimable, str(group.paths[0])))
    if progress:
        progress(f"{len(report.groups)} duplicate groups")
    return report


def _identical_clusters(group: Sequence[Path]) -> list[list[Path]]:
    """Split a group into byte-identical clusters.

    Two files can share a SHA-256 and still differ in the astronomically
    unlikely event of a collision, so the final stage compares the bytes. A
    cluster needs at least two members to be a duplicate group.
    """
    clusters: list[list[Path]] = [[group[0]]]
    for candidate in group[1:]:
        for cluster in clusters:
            if _identical(cluster[0], candidate):
                cluster.append(candidate)
                break
        else:
            clusters.append([candidate])
    return [cluster for cluster in clusters if len(cluster) > 1]
