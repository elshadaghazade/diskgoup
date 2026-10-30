"""Read-only archive browsing.

DiskBOX lets you look inside an archive **without extracting it**: nothing is
written to disk and nothing is executed. This module reproduces that behaviour.

Rules taken from the original:

* the browser is read-only — a sample archive is never extracted or run;
* text previews are limited to **64 KiB**;
* HTML is shown as plain text too;
* binary or encrypted content cannot be previewed as text;
* the **uncompressed** and **compressed** sizes are both reported;
* invalid entry names are skipped and the listing is marked partial.
"""

from __future__ import annotations

import zipfile
from dataclasses import dataclass, field
from pathlib import Path

#: Maximum number of bytes shown in a text preview.
PREVIEW_LIMIT = 64 * 1024


@dataclass(slots=True)
class ArchiveEntry:
    """One member of an archive."""

    name: str
    is_dir: bool
    size: int
    compressed: int
    encrypted: bool = False

    @property
    def ratio(self) -> float:
        """Compressed size as a fraction of the uncompressed size."""
        if not self.size:
            return 0.0
        return self.compressed / self.size

    def to_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "is_dir": self.is_dir,
            "size": self.size,
            "compressed": self.compressed,
            "ratio": round(self.ratio, 4),
            "encrypted": self.encrypted,
        }


@dataclass(slots=True)
class ArchiveListing:
    """The contents of an archive."""

    path: Path
    entries: list[ArchiveEntry] = field(default_factory=list)
    partial: bool = False
    error: str | None = None

    @property
    def uncompressed(self) -> int:
        return sum(entry.size for entry in self.entries)

    @property
    def compressed(self) -> int:
        return sum(entry.compressed for entry in self.entries)

    @property
    def item_count(self) -> int:
        return len(self.entries)

    def to_dict(self) -> dict[str, object]:
        return {
            "path": str(self.path),
            "items": self.item_count,
            "uncompressed": self.uncompressed,
            "compressed": self.compressed,
            "partial": self.partial,
            "error": self.error,
            "entries": [entry.to_dict() for entry in self.entries],
        }


@dataclass(slots=True)
class Preview:
    """The result of previewing a file inside an archive."""

    text: str | None = None
    truncated: bool = False
    binary: bool = False
    encrypted: bool = False
    empty: bool = False
    reason: str | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "text": self.text,
            "truncated": self.truncated,
            "binary": self.binary,
            "encrypted": self.encrypted,
            "empty": self.empty,
            "reason": self.reason,
        }


def is_supported(path: Path) -> bool:
    """True when the file is an archive this module can browse."""
    return path.suffix.lower() == ".zip"


def list_archive(path: Path, *, prefix: str = "") -> ArchiveListing:
    """List the members of a ZIP archive.

    ``prefix`` restricts the listing to a folder inside the archive.
    """
    listing = ArchiveListing(path=path)
    if not path.exists():
        listing.error = "Archive not found."
        return listing

    try:
        with zipfile.ZipFile(path) as archive:
            for info in archive.infolist():
                name = info.filename
                if prefix and not name.startswith(prefix):
                    continue
                if info.flag_bits & 0x1:
                    listing.partial = True
                listing.entries.append(
                    ArchiveEntry(
                        name=name,
                        is_dir=info.is_dir(),
                        size=info.file_size,
                        compressed=info.compress_size,
                        encrypted=bool(info.flag_bits & 0x1),
                    )
                )
    except zipfile.BadZipFile:
        listing.error = "Not a valid ZIP archive."
    except OSError as exc:
        listing.error = str(exc)

    return listing


def preview(path: Path, member: str) -> Preview:
    """Preview a text file inside an archive without extracting it."""
    try:
        with zipfile.ZipFile(path) as archive:
            try:
                info = archive.getinfo(member)
            except KeyError:
                return Preview(reason="Entry not found in archive.")

            if info.flag_bits & 0x1:
                return Preview(
                    encrypted=True,
                    reason="Binary or encrypted content cannot be previewed as text.",
                )

            with archive.open(info) as handle:
                data = handle.read(PREVIEW_LIMIT + 1)
    except zipfile.BadZipFile:
        return Preview(reason="Not a valid ZIP archive.")
    except OSError as exc:
        return Preview(reason=str(exc))

    if not data:
        return Preview(empty=True, text="")

    truncated = len(data) > PREVIEW_LIMIT
    if truncated:
        data = data[:PREVIEW_LIMIT]

    if _looks_binary(data):
        return Preview(
            binary=True,
            reason="Binary or encrypted content cannot be previewed as text.",
        )

    return Preview(text=data.decode("utf-8", errors="replace"), truncated=truncated)


def _looks_binary(data: bytes) -> bool:
    """Heuristic: a NUL byte in the first block means binary content."""
    return b"\x00" in data[:4096]


def folders_of(listing: ArchiveListing) -> list[str]:
    """The distinct folder prefixes inside an archive, sorted."""
    folders: set[str] = set()
    for entry in listing.entries:
        parts = entry.name.split("/")[:-1]
        for index in range(len(parts)):
            folders.add("/".join(parts[: index + 1]))
    return sorted(folders)


def parent_of(prefix: str) -> str:
    """The parent folder of a prefix inside an archive."""
    if not prefix:
        return ""
    parts = prefix.rstrip("/").split("/")[:-1]
    return "/".join(parts)
