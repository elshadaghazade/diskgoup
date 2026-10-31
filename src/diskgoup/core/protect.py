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

A second, narrower tier covers the containers that would break the machine if
they were removed as a whole — the volume root, the users container, a user's
home directory. Those are refused *as an item* while their contents stay
cleanable (see :func:`critical_rules`).

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

#: Why an item was refused — these are the sentences the user reads.
PROTECTED_GAME = "Protected game or application data cannot be staged."
PROTECTED_SYSTEM = "System folders cannot be cleaned."
PROTECTED_ATTRIBUTES = "The operating system marks this item as system or read-only."
PROTECTED_CRITICAL = "This folder is required by the system or your account and cannot be cleaned."

#: On macOS the writable data volume is mounted inside the sealed system
#: volume, at ``/System/Volumes/Data``. Its contents mirror ``/`` — ``/Users``,
#: ``/Applications``, ``/Library`` and ``/private`` are firmlinks into it — so a
#: path that names the data volume *is* the path it mirrors and the rules have
#: to be applied to that one.
_MACOS_DATA_VOLUME = "/system/volumes/data"


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
    """The comparison form of a path: slashes, no trailing slash, lower case.

    On macOS the data volume is folded onto the root it mirrors, so
    ``/System/Volumes/Data/Users/me`` is judged as ``/Users/me`` and the volume
    itself as the root ``/``.
    """
    normalized = str(path).replace("\\", "/").rstrip("/").lower()
    if normalized == _MACOS_DATA_VOLUME:
        return ""
    if normalized.startswith(_MACOS_DATA_VOLUME + "/"):
        return normalized[len(_MACOS_DATA_VOLUME) :]
    return normalized


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


def _is_system_normalized(normalized: str) -> bool:
    """True when a normalised path lives under a protected system root."""
    for root in _NORMALIZED_ROOTS:
        if normalized == root or normalized.startswith(root + "/"):
            return True
    return False


def is_system_path(path: Path | str) -> bool:
    """True when ``path`` lives under a protected system root."""
    return _is_system_normalized(_norm(path))


def _has_system_name_normalized(normalized: str) -> bool:
    """True when a normalised path carries a well-known OS directory name."""
    return any(part in _SYSTEM_DIR_NAMES for part in normalized.split("/"))


def has_system_name(path: Path | str) -> bool:
    """True when any component of ``path`` is a well-known OS directory name."""
    return _has_system_name_normalized(_norm(path))


def _attributes_protect(info: os.stat_result | None) -> bool:
    """True when a stat result carries system or read-only attributes."""
    if info is None:
        return False

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


def entry_stat(path: Path | str) -> os.stat_result | None:
    """The stat of an entry, or ``None`` when it cannot be read."""
    try:
        return os.lstat(path)
    except OSError:
        return None


def has_protected_attributes(path: Path | str) -> bool:
    """True when the OS marks the entry itself as system or read-only."""
    return _attributes_protect(entry_stat(path))


def is_protected_kind(kind: Kind | None) -> bool:
    """True when a kind is never reclaimable — game data and saved games."""
    return kind in _PROTECTED_KINDS


def protection_reason(
    path: Path | str,
    kind: Kind | None = None,
    *,
    parent_kind: Kind | None = None,
) -> str | None:
    """Why ``path`` may not be cleaned — ``None`` when it may be.

    This is the one place that decides. The scanner's fast path
    (:func:`entry_is_protected`) reaches the same verdict for the entries of a
    walk; the cleanup gate and the folder listing use this function because it
    also explains itself.

    ``parent_kind`` is the kind of the directory that holds the path, so a file
    inside a game folder is game data too.
    """
    if is_protected_kind(kind) or is_protected_kind(parent_kind):
        return PROTECTED_GAME
    normalized = _norm(path)
    if _is_system_normalized(normalized) or _has_system_name_normalized(normalized):
        return PROTECTED_SYSTEM
    if _attributes_protect(entry_stat(path)):
        return PROTECTED_ATTRIBUTES
    return None


def is_protected(path: Path, kind: Kind | None = None, *, inherited: bool = False) -> bool:
    """Decide whether an entry may be staged for deletion.

    ``inherited`` is set for children of a protected directory, which keeps the
    protection consistent for a whole protected subtree.
    """
    if inherited:
        return True
    return protection_reason(path, kind) is not None


@dataclass(frozen=True, slots=True)
class CriticalRules:
    """The containers that may never be staged as a whole.

    Their *contents* stay cleanable — only the container itself is refused.
    """

    roots: frozenset[str] = frozenset()
    containers: frozenset[str] = frozenset()


def critical_rules(platform: str | None = None, home: Path | str | None = None) -> CriticalRules:
    """The critical containers of a platform.

    ``platform`` and ``home`` default to the running system. They exist so the
    rules of macOS, Windows and Linux can be built — and tested — anywhere.

    The users container and the home directory are derived from the home path,
    which is the same shape on all three platforms: the parent of the home is
    the container that holds the accounts (``/Users``, ``C:\\Users``, ``/home``)
    and every direct child of it is an account's own home.
    """
    key = platform or _platform()
    home_path = Path(home) if home is not None else Path.home()
    home_normalized = _norm(home_path)
    container = home_normalized.rsplit("/", 1)[0] if "/" in home_normalized else ""

    roots = {"", home_normalized}
    containers: set[str] = set()
    if container:
        roots.add(container)
        containers.add(container)
    if key == "darwin":
        roots |= {"/private", f"{home_normalized}/library"}
    elif key == "linux":
        roots |= {"/root", f"{home_normalized}/.config", f"{home_normalized}/.local"}
    elif key == "win32":
        roots |= {home_normalized.split("/")[0], f"{home_normalized}/appdata"}

    return CriticalRules(roots=frozenset(roots), containers=frozenset(containers))


#: The critical containers of the running system.
_CRITICAL_RULES = critical_rules()


def is_critical(path: Path | str, rules: CriticalRules | None = None) -> bool:
    """True when ``path`` is a container that must never be staged as a whole.

    Removing the volume root, the users container or a user's home directory
    breaks the machine or the account; removing what is *inside* them does not.
    That is why this is an exact-path rule and not a subtree rule.
    """
    active = rules if rules is not None else _CRITICAL_RULES
    normalized = _norm(path)
    if normalized in active.roots:
        return True
    # The root of another drive — "d:" on Windows.
    if len(normalized) == 2 and normalized[1] == ":" and normalized[0].isalpha():
        return True
    parent = normalized.rsplit("/", 1)[0] if "/" in normalized else ""
    return parent in active.containers


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


def entry_is_protected(
    path: str,
    name: str,
    info: os.stat_result | None,
    guard: DirGuard,
) -> bool:
    """True when an entry may not be staged for deletion.

    This is the hot-path twin of :func:`protection_reason`: it takes the stat
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
