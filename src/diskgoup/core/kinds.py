"""File-kind classification.

Two levels are used, mirroring DiskBOX:

* **Kind** — the coarse bucket shown in the sidebar (Game files, Videos, Archives,
  Documents, Cache, Application files).
* **Type group** — the finer bucket used by the file-type report (Video, ISO / disk
  images, Archives, Cache / logs, Game files, Documents, Applications).

Classification follows DiskBOX's rules: a directory named ``cache`` or ``logs`` forces
its whole subtree into the cache group, otherwise the file extension decides.
"""

from __future__ import annotations

import re
from pathlib import PurePath

from diskgoup.core.models import Kind

#: Extensions that map onto a :class:`Kind`.
_EXTENSIONS: dict[str, Kind] = {
    # video
    ".mp4": Kind.VIDEO,
    ".mov": Kind.VIDEO,
    ".mkv": Kind.VIDEO,
    ".avi": Kind.VIDEO,
    ".webm": Kind.VIDEO,
    ".wmv": Kind.VIDEO,
    ".flv": Kind.VIDEO,
    ".m4v": Kind.VIDEO,
    ".mpg": Kind.VIDEO,
    ".mpeg": Kind.VIDEO,
    # audio
    ".mp3": Kind.AUDIO,
    ".flac": Kind.AUDIO,
    ".wav": Kind.AUDIO,
    ".aac": Kind.AUDIO,
    ".ogg": Kind.AUDIO,
    ".m4a": Kind.AUDIO,
    ".alac": Kind.AUDIO,
    # image
    ".png": Kind.IMAGE,
    ".jpg": Kind.IMAGE,
    ".jpeg": Kind.IMAGE,
    ".gif": Kind.IMAGE,
    ".webp": Kind.IMAGE,
    ".svg": Kind.IMAGE,
    ".bmp": Kind.IMAGE,
    ".tiff": Kind.IMAGE,
    ".heic": Kind.IMAGE,
    ".raw": Kind.IMAGE,
    ".psd": Kind.IMAGE,
    # archive / disk images
    ".zip": Kind.ARCHIVE,
    ".7z": Kind.ARCHIVE,
    ".rar": Kind.ARCHIVE,
    ".tar": Kind.ARCHIVE,
    ".gz": Kind.ARCHIVE,
    ".bz2": Kind.ARCHIVE,
    ".xz": Kind.ARCHIVE,
    ".zst": Kind.ARCHIVE,
    ".iso": Kind.ARCHIVE,
    ".dmg": Kind.ARCHIVE,
    ".img": Kind.ARCHIVE,
    ".vhd": Kind.ARCHIVE,
    ".vhdx": Kind.ARCHIVE,
    # documents
    ".pdf": Kind.DOCUMENT,
    ".doc": Kind.DOCUMENT,
    ".docx": Kind.DOCUMENT,
    ".odt": Kind.DOCUMENT,
    ".rtf": Kind.DOCUMENT,
    ".txt": Kind.DOCUMENT,
    ".md": Kind.DOCUMENT,
    ".rst": Kind.DOCUMENT,
    ".csv": Kind.DOCUMENT,
    ".xls": Kind.DOCUMENT,
    ".xlsx": Kind.DOCUMENT,
    ".ods": Kind.DOCUMENT,
    ".ppt": Kind.DOCUMENT,
    ".pptx": Kind.DOCUMENT,
    ".key": Kind.DOCUMENT,
    ".numbers": Kind.DOCUMENT,
    ".pages": Kind.DOCUMENT,
    ".epub": Kind.DOCUMENT,
    ".mobi": Kind.DOCUMENT,
    # code / data
    ".py": Kind.CODE,
    ".js": Kind.CODE,
    ".ts": Kind.CODE,
    ".tsx": Kind.CODE,
    ".jsx": Kind.CODE,
    ".go": Kind.CODE,
    ".rs": Kind.CODE,
    ".java": Kind.CODE,
    ".c": Kind.CODE,
    ".cpp": Kind.CODE,
    ".h": Kind.CODE,
    ".cs": Kind.CODE,
    ".rb": Kind.CODE,
    ".php": Kind.CODE,
    ".swift": Kind.CODE,
    ".kt": Kind.CODE,
    ".sh": Kind.CODE,
    ".json": Kind.CODE,
    ".yaml": Kind.CODE,
    ".yml": Kind.CODE,
    ".toml": Kind.CODE,
    ".xml": Kind.CODE,
    ".html": Kind.CODE,
    ".css": Kind.CODE,
    ".sql": Kind.CODE,
    ".db": Kind.CODE,
    ".sqlite": Kind.CODE,
    ".exe": Kind.APPLICATION,
    ".msi": Kind.APPLICATION,
    ".so": Kind.APPLICATION,
    ".dylib": Kind.APPLICATION,
    ".app": Kind.APPLICATION,
    ".deb": Kind.APPLICATION,
    ".rpm": Kind.APPLICATION,
    ".pkg": Kind.APPLICATION,
    ".appimage": Kind.APPLICATION,
    # system
    ".dll": Kind.SYSTEM,
    ".sys": Kind.SYSTEM,
    ".drv": Kind.SYSTEM,
    ".efi": Kind.SYSTEM,
}

#: Directory names whose whole subtree is treated as cache/log content.
#:
#: ``cache`` matches anywhere in the name ("Cache", "AppCache", "cached_content"),
#: while ``log``/``logs`` must be a whole token ("Logs", "app_logs") — matching
#: "log" anywhere would wrongly catch names such as "Dialog" or "Catalogue".
_CACHE_RE = re.compile(r"cache", re.IGNORECASE)
_LOG_RE = re.compile(r"(^|[ ._-])logs?([ ._-]|$)", re.IGNORECASE)
_TEMP_RE = re.compile(r"(^|[ ._-])(temp|tmp)([ ._-]|$)", re.IGNORECASE)

#: ``.ts`` is treated as TypeScript rather than MPEG transport stream: a developer
#: machine holds thousands of small ``.ts`` sources, while broadcast captures in
#: that format are rare.
#: Directory names that indicate game content.
_GAME_DIR_RE = re.compile(
    r"(^|[ ._-])(games?|steam|epic|gog|origin|uplay|battle\.net)([ ._-]|$)", re.IGNORECASE
)

#: Directory names that indicate application content.
_APP_DIR_RE = re.compile(
    r"(^|[ ._-])(apps?|applications?|programs?|software|bin)([ ._-]|$)", re.IGNORECASE
)


def classify_extension(name: str) -> Kind:
    """Return the :class:`Kind` implied by a file name's extension."""
    suffix = PurePath(name).suffix.lower()
    if not suffix:
        return Kind.OTHER
    return _EXTENSIONS.get(suffix, Kind.OTHER)


def is_cache_dir(name: str) -> bool:
    """True when a directory name marks its subtree as cache/log content."""
    return bool(_CACHE_RE.search(name) or _LOG_RE.search(name) or _TEMP_RE.search(name))


def is_game_dir(name: str) -> bool:
    """True when a directory name suggests game content."""
    return bool(_GAME_DIR_RE.search(name))


def is_app_dir(name: str) -> bool:
    """True when a directory name suggests application content."""
    return bool(_APP_DIR_RE.search(name))


def classify_dir(name: str, *, forced: Kind | None = None) -> Kind:
    """Classify a directory by name.

    ``forced`` propagates a parent's classification down the subtree, which is how
    DiskBOX keeps an entire cache folder inside the cache group.
    """
    if forced is not None:
        return forced
    if is_cache_dir(name):
        return Kind.CACHE
    if is_game_dir(name):
        return Kind.GAME
    if is_app_dir(name):
        return Kind.APPLICATION
    return Kind.OTHER


def classify_file(name: str, *, parent_kind: Kind | None = None) -> Kind:
    """Classify a file, honouring an inherited parent classification."""
    if parent_kind is Kind.CACHE:
        return Kind.CACHE
    if parent_kind is Kind.GAME:
        return Kind.GAME
    if parent_kind is Kind.APPLICATION:
        return Kind.APPLICATION
    return classify_extension(name)
