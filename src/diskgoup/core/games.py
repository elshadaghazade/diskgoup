"""Game library discovery.

DiskBOX discovers Steam and Epic libraries from their local manifests, then
measures the storage each game occupies. Our implementation reads the same
manifests:

* **Steam** — ``steamapps/libraryfolder.vdf`` lists the library roots; each
  library holds ``steamapps/common/<Game>`` plus an ``appmanifest_<appid>.acf``
  per installed title.
* **Epic** — each installed title is a directory under the Epic Games
  launcher root.

Within an installation, standard directory names are classified into the
categories DiskBOX reports:

| Category | Typical names | Protected |
|---|---|---|
| Game files | the installation root | ✅ |
| DLC | ``DLC``, ``dlc`` | ✅ |
| Mods | ``Mods``, ``modding`` | — |
| Saved games | ``Saved Games``, ``Saves``, ``Savegames`` | ✅ |
| Screenshots | ``Screenshots`` | — |

External save locations and mod-manager directories cannot be inferred, so they
must be associated explicitly — the same limitation the original has.

Measured game size is **not** reclaimable space: removing a game entry only
changes our inventory, it does not delete anything.
"""

from __future__ import annotations

import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

#: The categories DiskBOX reports for a game.
CATEGORY_GAME_FILES = "Game files"
CATEGORY_DLC = "DLC"
CATEGORY_MODS = "Mods"
CATEGORY_SAVES = "Saved games"
CATEGORY_SCREENSHOTS = "Screenshots"

#: Categories whose contents are protected from cleanup.
PROTECTED_CATEGORIES = frozenset({CATEGORY_GAME_FILES, CATEGORY_DLC, CATEGORY_SAVES})

_CATEGORY_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (CATEGORY_DLC, re.compile(r"^(dlc|dlc[_ -]?.*|expansions?)$", re.IGNORECASE)),
    (CATEGORY_MODS, re.compile(r"^(mods?|modding)$", re.IGNORECASE)),
    (
        CATEGORY_SAVES,
        re.compile(r"^(saved? ?games?|saves?|savegames?)$", re.IGNORECASE),
    ),
    (CATEGORY_SCREENSHOTS, re.compile(r"^(screenshots?)$", re.IGNORECASE)),
)


def category_for(name: str) -> str | None:
    """The category a directory name inside a game install belongs to."""
    for category, pattern in _CATEGORY_PATTERNS:
        if pattern.match(name.strip()):
            return category
    return None


@dataclass(slots=True)
class GameEntry:
    """One category of one game."""

    category: str
    size: int = 0
    files: int = 0
    protected: bool = False

    def to_dict(self) -> dict[str, object]:
        return {
            "category": self.category,
            "size": self.size,
            "files": self.files,
            "protected": self.protected,
        }


@dataclass(slots=True)
class Game:
    """One installed game."""

    name: str
    platform: str
    path: Path
    size: int = 0
    files: int = 0
    app_id: str | None = None
    categories: dict[str, GameEntry] = field(default_factory=dict)

    @property
    def protected(self) -> bool:
        """True when the measured size is not reclaimable space."""
        return self.size > 0

    def to_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "platform": self.platform,
            "path": str(self.path),
            "size": self.size,
            "files": self.files,
            "app_id": self.app_id,
            "protected": self.protected,
            "categories": [entry.to_dict() for entry in self.categories.values()],
        }


@dataclass(slots=True)
class Library:
    """A discovered game library."""

    platform: str
    root: Path
    games: list[Game] = field(default_factory=list)

    @property
    def size(self) -> int:
        return sum(game.size for game in self.games)

    def to_dict(self) -> dict[str, object]:
        return {
            "platform": self.platform,
            "root": str(self.root),
            "size": self.size,
            "games": [game.to_dict() for game in self.games],
        }


# --------------------------------------------------------------------- Steam


def _program_files() -> list[Path]:
    """The Windows ``Program Files`` roots, when running on Windows."""
    if not sys.platform.startswith("win"):
        return []
    from diskgoup.core import _windows

    return _windows.program_files()


def steam_roots() -> list[Path]:
    """The candidate Steam installation roots for this platform."""
    home = Path.home()
    if sys.platform.startswith("win"):
        candidates = [root / "Steam" for root in _program_files()]
        candidates.append(Path(os.environ.get("LOCALAPPDATA", "")) / "Steam")
    elif sys.platform == "darwin":
        candidates = [home / "Library" / "Application Support" / "Steam"]
    else:
        candidates = [
            home / ".steam" / "steam",
            home / ".local" / "share" / "Steam",
            home / ".var" / "app" / "com.valvesoftware.Steam" / ".local" / "share" / "Steam",
        ]
    return [candidate for candidate in candidates if candidate.is_dir()]


def parse_vdf_paths(text: str) -> list[Path]:
    """Extract library paths from a ``libraryfolders.vdf`` file.

    The file is Valve's KeyValues format; we only need the ``"path"`` values,
    so a targeted scan is enough and avoids pulling in a VDF parser.
    """
    paths: list[Path] = []
    for match in re.finditer(r'"path"\s*"([^"]+)"', text):
        raw = match.group(1).replace("\\\\", "\\")
        paths.append(Path(raw))
    return paths


def steam_libraries() -> list[Path]:
    """Every Steam library root on this machine."""
    libraries: list[Path] = []
    for root in steam_roots():
        libraries.append(root)
        vdf = root / "steamapps" / "libraryfolder.vdf"
        if vdf.is_file():
            try:
                libraries.extend(parse_vdf_paths(vdf.read_text(encoding="utf-8", errors="replace")))
            except OSError:
                continue

    unique: list[Path] = []
    seen: set[str] = set()
    for library in libraries:
        key = str(library)
        if key in seen:
            continue
        seen.add(key)
        unique.append(library)
    return unique


def steam_games() -> list[Game]:
    """Every Steam game found in the local manifests."""
    games: list[Game] = []
    seen: set[str] = set()

    for library in steam_libraries():
        steamapps = library / "steamapps"
        common = steamapps / "common"
        manifests = steamapps

        # The manifests carry the real install directory and the display name.
        manifest_dirs: dict[str, tuple[str, str | None]] = {}
        for manifest in sorted(manifests.glob("appmanifest_*.acf")):
            app_id = manifest.stem.replace("appmanifest_", "")
            try:
                text = manifest.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            name = _vdf_value(text, "name") or f"App {app_id}"
            install_dir = _vdf_value(text, "installdir")
            manifest_dirs[name] = (install_dir or name, app_id)

        candidates = set(manifest_dirs)
        if common.is_dir():
            candidates.update(child.name for child in common.iterdir() if child.is_dir())

        for name in sorted(candidates):
            install, manifest_app_id = manifest_dirs.get(name, (name, None))
            path = common / str(install)
            if not path.is_dir():
                continue
            key = str(path)
            if key in seen:
                continue
            seen.add(key)
            games.append(_measure_game(name, "Steam", path, manifest_app_id))

    return games


def _vdf_value(text: str, key: str) -> str | None:
    """Read a top-level string value out of a VDF file."""
    match = re.search(rf'"{re.escape(key)}"\s*"([^"]*)"', text)
    return match.group(1) if match else None


# ---------------------------------------------------------------------- Epic


def epic_roots() -> list[Path]:
    """The candidate Epic Games launcher roots for this platform."""
    home = Path.home()
    if sys.platform.startswith("win"):
        candidates = [root / "Epic Games" for root in _program_files()]
    elif sys.platform == "darwin":
        candidates = [home / "Library" / "Application Support" / "Epic"]
    else:
        candidates = [home / ".local" / "share" / "Epic"]
    return [candidate for candidate in candidates if candidate.is_dir()]


def epic_games() -> list[Game]:
    """Every Epic Games title found locally."""
    games: list[Game] = []
    seen: set[str] = set()

    for root in epic_roots():
        if not root.is_dir():
            continue
        for child in sorted(root.iterdir()):
            if not child.is_dir() or child.name.startswith("EpicGamesLauncher"):
                continue
            key = str(child)
            if key in seen:
                continue
            seen.add(key)
            games.append(_measure_game(child.name, "Epic Games", child, None))

    return games


# ------------------------------------------------------------------ measuring


def _measure_game(name: str, platform: str, path: Path, app_id: str | None) -> Game:
    """Measure a game installation and classify its categories."""
    game = Game(name=name, platform=platform, path=path, app_id=app_id)

    base = GameEntry(category=CATEGORY_GAME_FILES, protected=True)
    game.categories[CATEGORY_GAME_FILES] = base

    for root, dirnames, filenames in os.walk(path, onerror=lambda _e: None):
        root_path = Path(root)
        # Only the top level of the install decides the category; everything
        # below it belongs to that category.
        if root_path == path:
            for child in sorted(dirnames):
                category = category_for(child)
                if category is None:
                    continue
                entry = game.categories.get(category)
                if entry is None:
                    entry = GameEntry(category=category, protected=category in PROTECTED_CATEGORIES)
                    game.categories[category] = entry
        for filename in filenames:
            file_path = root_path / filename
            try:
                size = file_path.stat().st_size
            except OSError:
                continue
            game.files += 1
            game.size += size
            base.size += size
            base.files += 1

    # A category's size is the sum of its own files; the base category holds
    # everything that is not in a named sub-category.
    named = sum(entry.size for entry in game.categories.values() if entry is not base)
    base.size = max(0, game.size - named)
    other_files = sum(entry.files for entry in game.categories.values() if entry is not base)
    base.files = max(0, game.files - other_files)

    return game


def discover() -> list[Library]:
    """Discover every Steam and Epic library on this machine."""
    libraries: list[Library] = []

    steam = Library(platform="Steam", root=steam_roots()[0] if steam_roots() else Path("."))
    steam.games = steam_games()
    if steam.games:
        libraries.append(steam)

    epic = Library(platform="Epic Games", root=epic_roots()[0] if epic_roots() else Path("."))
    epic.games = epic_games()
    if epic.games:
        libraries.append(epic)

    return libraries


def aggregate_other(games: list[Game], *, limit: int) -> list[tuple[str, int]]:
    """Group games by size for a chart, folding the tail into "Other"."""
    ordered = sorted(games, key=lambda game: -game.size)
    if limit <= 0 or len(ordered) <= limit:
        return [(game.name, game.size) for game in ordered]

    head = [(game.name, game.size) for game in ordered[:limit]]
    tail = sum(game.size for game in ordered[limit:])
    head.append(("Other", tail))
    return head
