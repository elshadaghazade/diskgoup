"""Cross-platform volume discovery.

DiskBOX is Windows-only and lists drive letters. We reproduce that behaviour on
macOS and Linux by enumerating mounted volumes, and normalise everything into a
single :class:`Volume` record.
"""

from __future__ import annotations

import os
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path

from diskgoup.core.models import Kind


@dataclass(slots=True, frozen=True)
class Volume:
    """A mounted volume or drive."""

    device: str
    mountpoint: Path
    fstype: str
    total: int
    used: int
    free: int
    removable: bool = False

    @property
    def label(self) -> str:
        """A short human name for the volume."""
        if sys.platform.startswith("win"):
            return self.mountpoint.name or self.device
        return self.mountpoint.name or self.device

    @property
    def used_percent(self) -> float:
        if not self.total:
            return 0.0
        return (self.used / self.total) * 100

    def to_dict(self) -> dict[str, object]:
        return {
            "device": self.device,
            "mountpoint": str(self.mountpoint),
            "label": self.label,
            "fstype": self.fstype,
            "total": self.total,
            "used": self.used,
            "free": self.free,
            "used_percent": round(self.used_percent, 1),
            "removable": self.removable,
        }


def _usage(mountpoint: Path) -> tuple[int, int, int]:
    try:
        usage = shutil.disk_usage(mountpoint)
    except OSError:
        return (0, 0, 0)
    return (usage.total, usage.used, usage.free)


def _windows_volumes() -> list[Volume]:
    import string

    volumes: list[Volume] = []
    for letter in string.ascii_uppercase:
        root = Path(f"{letter}:\\")
        if not root.exists():
            continue
        total, used, free = _usage(root)
        volumes.append(
            Volume(
                device=f"{letter}:",
                mountpoint=root,
                fstype="ntfs",
                total=total,
                used=used,
                free=free,
            )
        )
    return volumes


def _posix_volumes() -> list[Volume]:
    candidates: list[Volume] = []
    seen: set[str] = set()

    def add(volume: Volume) -> None:
        key = str(volume.mountpoint)
        if key in seen:
            return
        seen.add(key)
        candidates.append(volume)

    try:
        import psutil

        for part in psutil.disk_partitions(all=False):
            mountpoint = Path(part.mountpoint)
            # Skip pseudo-filesystems that have no meaningful size.
            if part.fstype in {"proc", "sysfs", "devtmpfs", "devfs", "squashfs", "autofs"}:
                continue
            if not mountpoint.exists():
                continue
            total, used, free = _usage(mountpoint)
            add(
                Volume(
                    device=part.device,
                    mountpoint=mountpoint,
                    fstype=part.fstype,
                    total=total,
                    used=used,
                    free=free,
                    removable="removable" in getattr(part, "opts", ""),
                )
            )
    except Exception:
        pass

    if not candidates:
        total, used, free = _usage(Path("/"))
        add(
            Volume(
                device="/dev/root",
                mountpoint=Path("/"),
                fstype="",
                total=total,
                used=used,
                free=free,
            )
        )

    # macOS and Linux expose extra user mounts under /Volumes and /media.
    for base in (Path("/Volumes"), Path("/media")):
        if not base.is_dir():
            continue
        for child in sorted(base.iterdir()):
            if not child.is_dir() or str(child) in seen:
                continue
            total, used, free = _usage(child)
            if total == 0:
                continue
            add(
                Volume(
                    device=str(child),
                    mountpoint=child,
                    fstype="",
                    total=total,
                    used=used,
                    free=free,
                    removable=True,
                )
            )

    if sys.platform == "darwin":
        candidates = _collapse_macos(candidates)
    return _dedupe_by_device(candidates)


def _macos_container(device: str) -> str | None:
    """The APFS container a device belongs to.

    macOS device names look like ``/dev/disk3s5``; the ``disk3`` prefix is the
    container, and ``disk3s5`` is one volume inside it.
    """
    name = Path(device).name
    if not name.startswith("disk"):
        return None
    digits = ""
    for char in name[4:]:
        if char.isdigit():
            digits += char
        else:
            break
    return f"disk{digits}" if digits else None


#: Auxiliary APFS volumes that are not interesting to a disk analyser.
_MACOS_AUXILIARY = frozenset(
    {"preboot", "vm", "update", "recovery", "xarts", "iscpreboot", "hardware", "cores"}
)


def _collapse_macos(volumes: list[Volume]) -> list[Volume]:
    """Reduce macOS's APFS view to one row per container.

    A modern macOS install mounts the same container many times — the sealed
    system volume at ``/``, the writable data volume at ``/System/Volumes/Data``,
    plus auxiliary volumes. To the user that is one disk, so only the data
    volume is reported.
    """
    by_container: dict[str, Volume] = {}
    others: list[Volume] = []

    for volume in volumes:
        mount = str(volume.mountpoint)
        if mount.startswith("/System/Volumes/"):
            leaf = mount.rstrip("/").rsplit("/", 1)[-1].lower()
            if leaf in _MACOS_AUXILIARY:
                continue

        container = _macos_container(volume.device)
        if container is None:
            others.append(volume)
            continue

        current = by_container.get(container)
        if current is None:
            by_container[container] = volume
            continue

        # Prefer the writable data volume; it is where the user's files live.
        def score(candidate: Volume) -> tuple[int, int]:
            is_data = str(candidate.mountpoint).rstrip("/").endswith("Volumes/Data")
            return (int(is_data), candidate.total)

        if score(volume) > score(current):
            by_container[container] = volume

    return list(by_container.values()) + others


def _dedupe_by_device(volumes: list[Volume]) -> list[Volume]:
    """Collapse volumes that resolve to the same device.

    macOS exposes an APFS container through several firmlinks (``/``,
    ``/Volumes/Macintosh HD``). They are one disk to the user, so only one path
    is kept.
    """
    by_device: dict[int, Volume] = {}
    anonymous: list[Volume] = []

    for volume in volumes:
        try:
            device_id = os.stat(volume.mountpoint).st_dev
        except OSError:
            anonymous.append(volume)
            continue
        current = by_device.get(device_id)
        if current is None:
            by_device[device_id] = volume
            continue
        # Prefer the shorter path: "/" beats "/System/Volumes/Data".
        if len(str(volume.mountpoint)) < len(str(current.mountpoint)):
            by_device[device_id] = volume

    return list(by_device.values()) + anonymous


def volumes() -> list[Volume]:
    """List the mounted volumes of the current machine."""
    if sys.platform.startswith("win"):
        found = _windows_volumes()
    else:
        found = _posix_volumes()
    return sorted(found, key=lambda v: str(v.mountpoint))


def home_volume() -> Volume | None:
    """The volume that contains the user's home directory."""
    home = Path.home()
    for volume in volumes():
        try:
            home.relative_to(volume.mountpoint)
        except ValueError:
            continue
        return volume
    return volumes()[0] if volumes() else None


def default_scan_root() -> Path:
    """The path a scan starts from when the user does not name one."""
    if sys.platform.startswith("win"):
        return Path.home()
    return Path.home()


def classify_volume(path: Path) -> Kind:
    """Classify a path for the file-kind breakdown."""
    name = path.name.lower()
    if "cache" in name or "tmp" in name:
        return Kind.CACHE
    return Kind.OTHER


def is_hidden(path: Path) -> bool:
    """True when a path lives inside a hidden directory."""
    return any(part.startswith(".") for part in path.parts)


def same_volume(a: Path, b: Path) -> bool:
    """True when both paths live on the same mounted volume."""
    try:
        return os.stat(a).st_dev == os.stat(b).st_dev
    except OSError:
        return a.anchor == b.anchor
