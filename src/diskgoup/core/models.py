"""Core data model shared by the scanner, the index and every command."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path


class Kind(StrEnum):
    """File kinds used for the file-type breakdown and the type report."""

    GAME = "game"
    VIDEO = "video"
    AUDIO = "audio"
    IMAGE = "image"
    ARCHIVE = "archive"
    DOCUMENT = "document"
    CODE = "code"
    CACHE = "cache"
    APPLICATION = "application"
    SYSTEM = "system"
    OTHER = "other"


#: Presentation order for the file-type breakdown (matches DiskBOX's sidebar).
KIND_ORDER: tuple[Kind, ...] = (
    Kind.GAME,
    Kind.VIDEO,
    Kind.ARCHIVE,
    Kind.DOCUMENT,
    Kind.CACHE,
    Kind.APPLICATION,
    Kind.AUDIO,
    Kind.IMAGE,
    Kind.CODE,
    Kind.SYSTEM,
    Kind.OTHER,
)


@dataclass(slots=True, frozen=True)
class Entry:
    """A single indexed file or directory.

    ``size`` is the *logical* size (sum of file byte lengths) and ``on_disk`` is the
    *allocated* size — the two differ for sparse and compressed files, which is why
    DiskBOX reports both.
    """

    path: Path
    name: str
    is_dir: bool
    size: int
    on_disk: int
    mtime: float
    kind: Kind
    protected: bool = False
    depth: int = 0
    parent: int | None = None
    id: int | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "path": str(self.path),
            "name": self.name,
            "is_dir": self.is_dir,
            "size": self.size,
            "on_disk": self.on_disk,
            "mtime": self.mtime,
            "kind": str(self.kind),
            "protected": self.protected,
            "depth": self.depth,
        }


@dataclass(slots=True)
class Node:
    """An aggregated node in the folder tree.

    Aggregates are cumulative: a directory's ``size`` includes every descendant,
    so a parent total must never be added to its children's totals.
    """

    path: Path
    name: str
    is_dir: bool
    size: int = 0
    on_disk: int = 0
    file_count: int = 0
    dir_count: int = 0
    kind: Kind = Kind.OTHER
    mtime: float = 0.0
    protected: bool = False
    depth: int = 0
    children: list[Node] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        return {
            "path": str(self.path),
            "name": self.name,
            "is_dir": self.is_dir,
            "size": self.size,
            "on_disk": self.on_disk,
            "files": self.file_count,
            "folders": self.dir_count,
            "kind": str(self.kind),
            "mtime": self.mtime,
            "protected": self.protected,
            "depth": self.depth,
            "children": [child.to_dict() for child in self.children],
        }


@dataclass(slots=True)
class ScanMeta:
    """Summary of one completed scan."""

    scan_id: int
    root: Path
    started_at: float
    finished_at: float
    total_size: int
    total_on_disk: int
    file_count: int
    dir_count: int
    skipped: int
    complete: bool = True

    @property
    def duration(self) -> float:
        return max(0.0, self.finished_at - self.started_at)

    def to_dict(self) -> dict[str, object]:
        return {
            "scan_id": self.scan_id,
            "root": str(self.root),
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "duration": self.duration,
            "total_size": self.total_size,
            "total_on_disk": self.total_on_disk,
            "files": self.file_count,
            "folders": self.dir_count,
            "skipped": self.skipped,
            "complete": self.complete,
        }


@dataclass(slots=True)
class SkippedEntry:
    """An entry that could not be read, with the reason it was skipped."""

    path: Path
    reason: str

    def to_dict(self) -> dict[str, object]:
        return {"path": str(self.path), "reason": self.reason}
