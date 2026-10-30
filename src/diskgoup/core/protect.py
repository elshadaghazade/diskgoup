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

The scanner asks about *every* entry of a walk, so this module also carries a
fast path (:func:`entry_is_protected`) that reuses what the parent directory
already established instead of deriving the same facts again for every child.
"""

from __future__ import annotations

import os
import stat
import sys
from dataclasses import dataclass
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


def _platform() -> str:
    """The key of the running platform in :data:`_SYSTEM_ROOTS`."""
    if sys.platform.startswith("win"):
        return "win32"
    if sys.platform == "darwin":
        return "darwin"
    return "linux"


def system_roots() -> tuple[str, ...]:
    """Return the protected system roots for the current platform."""
    return _SYSTEM_ROOTS[_platform()]


def _norm(path: Path | str) -> str:
    return str(path).replace("\\", "/").rstrip("/").lower()


#: The system roots of this platform, normalised once instead of per lookup.
_NORMALIZED_ROOTS: tuple[str, ...] = tuple(_norm(root) for root in system_roots())

#: For every system-root basename, the paths of the directory that holds it.
#: A directory becomes a system root exactly when its own name is the basename
#: and its parent is one of these paths — "/Library" under "/", for example.
_ROOT_PARENTS: dict[str, frozenset[str]] = {}
for _root in _NORMALIZED_ROOTS:
    _cut = _root.rfind("/")
    _base = _root[_cut + 1 :]
    _parent = _root[:_cut] if _cut >= 0 else ""
    _ROOT_PARENTS[_base] = _ROOT_PARENTS.get(_base, frozenset()) | {_parent}


def is_system_path(path: Path | str) -> bool:
    """True when ``path`` lives under a protected system root."""
    normalized = _norm(path)
    for root in _NORMALIZED_ROOTS:
        if normalized == root or normalized.startswith(root + "/"):
            return True
    return False


def has_system_name(path: Path | str) -> bool:
    """True when any component of ``path`` is a well-known OS directory name."""
    parts = _norm(path).split("/")
    return any(part in _SYSTEM_DIR_NAMES for part in parts)


def _attributes_protect(info: os.stat_result) -> bool:
    """True when a stat result carries system or read-only attributes."""
    # Windows: FILE_ATTRIBUTE_SYSTEM (0x4) / FILE_ATTRIBUTE_READONLY (0x1).
    attrs = getattr(info, "st_file_attributes", 0)
    if attrs & 0x4:
        return True

    # Unix: the immutable/append-only flags and the hidden flag on macOS.
    # The attribute is absent off macOS and can be unset on a stat result
    # that was not filled in by the operating system.
    flags = getattr(info, "st_flags", 0) or 0
    if flags & (stat.UF_IMMUTABLE | stat.UF_APPEND):
        return True
    if sys.platform == "darwin" and flags & stat.UF_HIDDEN:
        return True

    return False


def has_protected_attributes(path: Path) -> bool:
    """True when the OS marks the entry itself as system or read-only."""
    try:
        info = os.lstat(path)
    except OSError:
        return False
    return _attributes_protect(info)


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


@dataclass(frozen=True, slots=True)
class DirGuard:
    """What a directory has already established for the entries below it.

    A system root, a system directory name or an attribute flag can only be
    introduced by an entry itself, never by one of its children — so a
    directory decides once and its children only add their own name and flags.
    """

    protected: bool = False
    under_root: bool = False
    norm_path: str = ""


def guard_for(path: Path | str, *, protected: bool = False) -> DirGuard:
    """The guard for a directory that is about to be scanned."""
    normalized = _norm(path)
    under_root = any(
        normalized == root or normalized.startswith(root + "/") for root in _NORMALIZED_ROOTS
    )
    return DirGuard(protected=protected, under_root=under_root, norm_path=normalized)


def entry_is_protected(path: str, name: str, info: os.stat_result, guard: DirGuard) -> bool:
    """True when an entry may not be staged for deletion.

    This is the hot-path twin of :func:`is_protected`: it takes the stat
    result the caller already holds and the guard of the parent directory,
    and reaches the same verdict without touching the filesystem again.
    """
    if guard.protected:
        return True
    lowered = name.lower()
    if lowered in _SYSTEM_DIR_NAMES:
        return True
    if not guard.under_root:
        parents = _ROOT_PARENTS.get(lowered)
        if parents is not None and guard.norm_path in parents:
            # The entry is a system root in its own right, e.g. "/Library".
            return True
    return _attributes_protect(info)
