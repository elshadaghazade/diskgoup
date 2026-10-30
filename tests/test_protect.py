from __future__ import annotations

import sys
from pathlib import Path

from diskgoup.core.models import Kind
from diskgoup.core.protect import is_protected, is_system_path


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
