from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

from diskgoup.core.models import Kind
from diskgoup.core.protect import (
    entry_is_protected,
    guard_for,
    is_protected,
    is_system_path,
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
