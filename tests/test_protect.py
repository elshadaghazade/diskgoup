from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

from diskgoup.core.models import Kind
from diskgoup.core.protect import (
    PROTECTED_GAME,
    PROTECTED_SYSTEM,
    critical_rules,
    entry_is_protected,
    guard_for,
    is_critical,
    is_protected,
    is_system_path,
    protection_reason,
)


def test_system_roots_are_protected() -> None:
    assert is_system_path("/System/Library/CoreServices")
    assert is_system_path("/Library/Preferences")
    assert is_system_path("/Applications")


def test_user_paths_are_not_protected() -> None:
    assert not is_system_path("/Users/someone/Downloads")
    assert not is_system_path("/home/someone/Downloads")
    assert not is_system_path("/Volumes/Data/Users/someone")


def test_macos_user_temp_is_cleanable() -> None:
    # /private/var holds both OS state and the per-user temporary directory.
    # Only the OS-owned parts are protected — a disk analyser that refuses to
    # touch the user's own temp files is not much use.
    assert is_system_path("/private/var/db")
    assert is_system_path("/private/var/log")
    assert not is_system_path("/private/var/folders/ab/xyz/T")


def test_game_content_is_protected(tmp_path: Path) -> None:
    assert is_protected(tmp_path, Kind.GAME)


def test_ordinary_content_is_not_protected(tmp_path: Path) -> None:
    target = tmp_path / "notes.txt"
    target.write_text("hello")

    assert not is_protected(target, Kind.DOCUMENT)


def test_inherited_protection_covers_the_subtree(tmp_path: Path) -> None:
    child = tmp_path / "nested" / "file.bin"

    assert is_protected(child, Kind.DOCUMENT, inherited=True)


def test_windows_system_paths_are_protected() -> None:
    from diskgoup.core.protect import _SYSTEM_ROOTS

    windows = _SYSTEM_ROOTS["win32"]
    assert any(root.lower().startswith("c:\\windows") for root in windows)
    assert any("program files" in root.lower() for root in windows)


def test_linux_system_paths_are_protected() -> None:
    from diskgoup.core.protect import _SYSTEM_ROOTS

    linux = _SYSTEM_ROOTS["linux"]
    assert "/usr" in linux
    assert "/etc" in linux
    assert "/home" not in linux


def test_platform_roots_match_this_platform() -> None:
    from diskgoup.core.protect import system_roots

    roots = system_roots()
    if sys.platform == "darwin":
        assert "/System" in roots
    elif sys.platform.startswith("win"):
        assert all(root.startswith("C:\\") for root in roots)
    else:
        assert "/usr" in roots


def _fake_stat() -> os.stat_result:
    """A stat result for a plain, unprotected file."""
    return os.stat_result((0o100644, 1, 1, 1, 0, 0, 10, 0.0, 0.0, 0.0))


#: (parent directory, child path, child name) triples covering the cases the
#: fast path has to get right: a directory that *is* a system root, a child of
#: one, a system directory name and ordinary content.
_FAST_PATH_CASES = (
    ("/", "/Library", "Library"),
    ("/", "/Applications", "Applications"),
    ("/", "/System", "System"),
    ("/System", "/System/Library", "Library"),
    ("/private", "/private/var", "var"),
    ("/private/var", "/private/var/db", "db"),
    ("/Users/someone", "/Users/someone/Downloads", "Downloads"),
    ("/Users/someone/Downloads", "/Users/someone/Downloads/movie.mp4", "movie.mp4"),
    ("/Users/someone", "/Users/someone/System", "System"),
    ("/Users/someone", "/Users/someone/system32", "system32"),
    ("/Users/someone", "/Users/someone/notes.txt", "notes.txt"),
    # The macOS data volume — the folder the scan usually starts at.
    ("/System/Volumes/Data", "/System/Volumes/Data/Users", "Users"),
    ("/System/Volumes/Data", "/System/Volumes/Data/Applications", "Applications"),
    ("/System/Volumes/Data", "/System/Volumes/Data/Library", "Library"),
)


@pytest.mark.parametrize(("parent", "child", "name"), _FAST_PATH_CASES)
def test_the_fast_path_agrees_with_the_full_check(parent: str, child: str, name: str) -> None:
    """The hot path must reach the same verdict as the full check."""
    guard = guard_for(parent, protected=is_protected(Path(parent)))
    fast = entry_is_protected(child, name, _fake_stat(), guard)
    slow = is_protected(Path(parent)) or is_protected(Path(child))
    assert fast == slow, (parent, child)


def test_a_protected_parent_protects_its_children() -> None:
    guard = guard_for("/System", protected=True)
    assert entry_is_protected("/System/Library/thing", "thing", _fake_stat(), guard)


def test_the_guard_knows_a_system_root() -> None:
    assert guard_for("/System").under_root
    assert guard_for("/System/Library").under_root
    assert not guard_for("/Users/someone").under_root


def test_the_macos_data_volume_is_judged_as_the_place_it_mirrors() -> None:
    """The writable data volume sits inside /System but holds the user's files.

    A scan of it stores paths like ``/System/Volumes/Data/Users/<me>/…``; if
    those were judged by the ``/System`` prefix, every item of such a scan
    would be refused as protected and nothing could ever be cleaned.
    """
    assert not is_system_path("/System/Volumes/Data/Users/someone/Downloads")
    assert not is_protected(Path("/System/Volumes/Data/Users/someone/Downloads/old.zip"))
    assert not is_protected(Path("/System/Volumes/Data/Users/someone/Downloads"))

    # What it mirrors keeps its own rules.
    assert is_system_path("/System/Volumes/Data/Applications")
    assert is_system_path("/System/Volumes/Data/Library")
    assert is_system_path("/System/Volumes/Data/private/etc")
    assert is_protected(Path("/System/Volumes/Data/Applications"))

    # The volume itself is the root of the writable disk.
    assert is_critical("/System/Volumes/Data")


def test_the_critical_containers_of_macos() -> None:
    rules = critical_rules("darwin", "/Users/someone")

    assert is_critical("/", rules)
    assert is_critical("/Users", rules)
    assert is_critical("/Users/someone", rules)
    assert is_critical("/Users/other", rules)
    assert is_critical("/private", rules)
    assert is_critical("/Users/someone/Library", rules)

    # What is inside them stays cleanable.
    assert not is_critical("/Users/someone/Downloads", rules)
    assert not is_critical("/Users/someone/Downloads/old.zip", rules)
    assert not is_critical("/Applications", rules)


def test_the_critical_containers_of_windows() -> None:
    rules = critical_rules("win32", r"C:\Users\someone")

    assert is_critical(r"C:\Users", rules)
    assert is_critical(r"C:\Users\someone", rules)
    assert is_critical(r"C:\Users\other", rules)
    assert is_critical(r"C:\Users\someone\AppData", rules)
    assert is_critical("C:\\", rules)
    # The root of any other drive.
    assert is_critical("d:", rules)

    assert not is_critical(r"C:\Users\someone\Downloads", rules)
    assert not is_critical(r"C:\Program Files\Thing", rules)


def test_the_critical_containers_of_linux() -> None:
    rules = critical_rules("linux", "/home/someone")

    assert is_critical("/", rules)
    assert is_critical("/home", rules)
    assert is_critical("/home/someone", rules)
    assert is_critical("/home/other", rules)
    assert is_critical("/root", rules)
    assert is_critical("/home/someone/.config", rules)
    assert is_critical("/home/someone/.local", rules)

    assert not is_critical("/home/someone/Downloads", rules)
    assert not is_critical("/home/someone/Downloads/old.zip", rules)
    assert not is_critical("/var/tmp", rules)


def test_the_reason_says_why_an_item_is_refused(tmp_path: Path) -> None:
    target = tmp_path / "notes.txt"
    target.write_text("hello")

    assert protection_reason(target) is None
    assert protection_reason(target, Kind.DOCUMENT) is None
    assert protection_reason(target, Kind.GAME) == PROTECTED_GAME
    assert protection_reason(Path("/System/Library")) == PROTECTED_SYSTEM
    # A file inside a game folder is game data as well.
    assert protection_reason(target, parent_kind=Kind.GAME) == PROTECTED_GAME
