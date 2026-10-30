"""Protected-path rules.

DiskBOX never offers system or protected application paths for cleanup. The same
rule is reproduced here: a *protected* entry can be scanned and reported, but it can
never be staged for deletion.

Protection is decided by three independent signals:

1. **System roots** — per-platform directories that hold the OS and its core
   applications (``/System``, ``C:\\Windows``, ``/usr`` …).
2. **Platform attributes** — Windows ``FILE_ATTRIBUTE_SYSTEM`` /
   ``FILE_ATTRIBUTE_READONLY``, and the macOS ``UF_HIDDEN`` flag.
3. **Semantic role** — game files, DLC and saved games are protected because they
   are not reclaimable space.
"""

from __future__ import annotations

import os
import stat
import sys
from pathlib import Path

from diskgoup.core.models import Kind

#: Absolute prefixes that are always protected, per platform.
_SYSTEM_ROOTS: dict[str, tuple[str, ...]] = {
    "darwin": (
        "/System",
        "/Library",
        "/Applications",
        "/private/etc",
        "/private/var/db",
        "/private/var/log",
        "/private/var/vm",
        "/private/var/root",
        "/cores",
        "/dev",
        "/Volumes/Preboot",
        "/Volumes/Recovery",
        "/Volumes/VM",
        "/Volumes/Update",
    ),
    "win32": (
        r"C:\Windows",
        r"C:\Program Files",
        r"C:\Program Files (x86)",
        r"C:\ProgramData",
        r"C:\System Volume Information",
        r"C:\Recovery",
        r"C:\$Recycle.Bin",
        r"C:\System Volume Information",
    ),
    "linux": (
        "/bin",
        "/sbin",
        "/usr",
        "/etc",
        "/boot",
        "/lib",
        "/lib32",
        "/lib64",
        "/opt",
        "/proc",
        "/sys",
        "/dev",
        "/run",
        "/snap",
        "/var/lib",
        "/var/cache",
    ),
}

#: Directory names that hold operating-system state and must never be cleaned.
_SYSTEM_DIR_NAMES = frozenset(
    {
        "windows",
        "system volume information",
        "$recycle.bin",
        "system32",
        "syswow64",
        "winsxs",
        "recovery",
        "preboot",
        "vm",
        "update",
    }
)

#: Kinds whose contents are never reclaimable.
_PROTECTED_KINDS = frozenset({Kind.GAME})


def system_roots() -> tuple[str, ...]:
    """Return the protected system roots for the current platform."""
    if sys.platform.startswith("win"):
        return _SYSTEM_ROOTS["win32"]
    if sys.platform == "darwin":
        return _SYSTEM_ROOTS["darwin"]
    return _SYSTEM_ROOTS["linux"]


def _norm(path: Path | str) -> str:
    return str(path).replace("\\", "/").rstrip("/").lower()


def is_system_path(path: Path | str) -> bool:
    """True when ``path`` lives under a protected system root."""
    normalized = _norm(path)
    for root in system_roots():
        root_norm = _norm(root)
        if normalized == root_norm or normalized.startswith(root_norm + "/"):
            return True
    return False


def has_system_name(path: Path | str) -> bool:
    """True when any component of ``path`` is a well-known OS directory name."""
    parts = _norm(path).split("/")
    return any(part in _SYSTEM_DIR_NAMES for part in parts)


def has_protected_attributes(path: Path) -> bool:
    """True when the OS marks the entry itself as system or read-only."""
    try:
        info = os.lstat(path)
    except OSError:
        return False

    # Windows: FILE_ATTRIBUTE_SYSTEM (0x4) / FILE_ATTRIBUTE_READONLY (0x1).
    attrs = getattr(info, "st_file_attributes", 0)
    if attrs & 0x4:
        return True

    # Unix: the immutable/append-only flags and the hidden flag on macOS.
    if getattr(info, "st_flags", 0) & (stat.UF_IMMUTABLE | stat.UF_APPEND):
        return True
    if sys.platform == "darwin" and getattr(info, "st_flags", 0) & stat.UF_HIDDEN:
        return True

    return False


def is_protected(path: Path, kind: Kind | None = None, *, inherited: bool = False) -> bool:
    """Decide whether an entry may be staged for deletion.

    ``inherited`` is set for children of a protected directory, which keeps the
    protection consistent for a whole protected subtree.
    """
    if inherited:
        return True
    if kind in _PROTECTED_KINDS:
        return True
    if is_system_path(path) or has_system_name(path):
        return True
    return has_protected_attributes(path)
