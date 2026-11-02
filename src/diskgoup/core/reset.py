"""Factory reset — put DiskGOup back to the state it had before the first scan.

The index is a cache of what the disk held when it was walked: everything in
it can be rebuilt by scanning again. It is also the one piece of state that
can break in a way the user cannot fix from the interface. A corrupted
SQLite file makes every command fail with *"database disk image is
malformed"*, and a database held by a stuck scan makes the app wait forever.

So the reset does not touch the disk the user cares about. It removes the
index — the database file and the SQLite side files beside it — and writes a
new, empty one with the current schema. No file on the disk is scanned,
moved or deleted; the next scan reads them again.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from diskgoup.core.store import ScanIndex
from diskgoup.paths import config_path, default_index_path, env_index_path

#: The files SQLite keeps beside the database.
#:
#: The write-ahead log and the shared-memory file hold the state of the last
#: session; the rollback journal is what a database uses before it is put in
#: WAL mode. They belong to the database and go with it — leaving one behind
#: would let the new index read the old one's data.
SIDECARS = ("-wal", "-shm", "-journal")


class ResetError(RuntimeError):
    """The reset could not be carried out."""


@dataclass(frozen=True, slots=True)
class ResetResult:
    """What a reset did."""

    #: The index that was replaced.
    index_path: Path
    #: The files that were removed, by name.
    removed: tuple[str, ...] = ()
    #: Whether the configuration file was removed as well.
    config_removed: bool = False

    def to_dict(self) -> dict[str, object]:
        return {
            "index_path": str(self.index_path),
            "removed": list(self.removed),
            "config_removed": self.config_removed,
        }


def target_index_path() -> Path:
    """The index the app uses — the override when one is set."""
    return env_index_path() or default_index_path()


def reset(path: Path | None = None, *, config: Path | None = None) -> ResetResult:
    """Replace the index with a new, empty one.

    The old database is removed *before* anything tries to open it: a
    corrupted file cannot be opened, and the reset has to work on exactly
    that file. The new index is created with the current schema, so the app
    can use it straight away.

    ``path`` is the index to replace and ``config`` the configuration file to
    remove. ``None`` leaves the configuration alone.
    """
    index_path = path or target_index_path()
    removed: list[str] = []

    for suffix in ("", *SIDECARS):
        candidate = Path(f"{index_path}{suffix}")
        if not candidate.exists():
            continue
        try:
            candidate.unlink()
        except PermissionError as exc:
            raise ResetError(
                f"{candidate.name} is in use by another process — close it and try again"
            ) from exc
        except OSError as exc:
            raise ResetError(f"could not remove {candidate}: {exc}") from exc
        removed.append(candidate.name)

    # The new index carries the current schema, so a reset also repairs an
    # index written by an older version of the app.
    index = ScanIndex(index_path)
    index.close()

    config_removed = False
    if config is not None and config.exists():
        try:
            config.unlink()
        except OSError as exc:
            raise ResetError(f"could not remove {config}: {exc}") from exc
        config_removed = True

    return ResetResult(
        index_path=index_path,
        removed=tuple(removed),
        config_removed=config_removed,
    )


def reset_app() -> ResetResult:
    """Reset everything the app keeps: the index and the configuration."""
    return reset(config=config_path())
