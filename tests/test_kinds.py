from pathlib import Path

from diskgoup.core.kinds import classify_dir, classify_extension, classify_file, is_cache_dir
from diskgoup.core.models import Kind


def test_classify_extension_by_suffix() -> None:
    assert classify_extension("movie.mp4") is Kind.VIDEO
    assert classify_extension("archive.zip") is Kind.ARCHIVE
    assert classify_extension("notes.txt") is Kind.DOCUMENT
    assert classify_extension("app.exe") is Kind.APPLICATION
    assert classify_extension("unknown.xyz") is Kind.OTHER
    assert classify_extension("noextension") is Kind.OTHER


def test_cache_directory_names() -> None:
    assert is_cache_dir("Cache")
    assert is_cache_dir("cache")
    assert is_cache_dir("AppCache")
    assert is_cache_dir("browser_cache")
    assert is_cache_dir("Logs")
    assert not is_cache_dir("Casino")
    assert not is_cache_dir("Cascade")


def test_classify_dir_prefers_cache_then_game_then_app() -> None:
    assert classify_dir("Cache") is Kind.CACHE
    assert classify_dir("Steam") is Kind.GAME
    assert classify_dir("Applications") is Kind.APPLICATION
    assert classify_dir("Documents") is Kind.OTHER


def test_forced_kind_propagates_to_subtree() -> None:
    assert classify_dir("anything", forced=Kind.CACHE) is Kind.CACHE
    assert classify_file("blob.bin", parent_kind=Kind.CACHE) is Kind.CACHE
    assert classify_file("movie.mp4", parent_kind=Kind.CACHE) is Kind.CACHE


def test_game_parent_marks_files_as_game() -> None:
    assert classify_file("data.pak", parent_kind=Kind.GAME) is Kind.GAME


def test_path_suffix_is_case_insensitive() -> None:
    assert classify_extension("MOVIE.MP4") is Kind.VIDEO


def test_multipart_archive_names() -> None:
    assert classify_extension("game.part1.rar") is Kind.ARCHIVE
    assert classify_extension("game.rar") is Kind.ARCHIVE


def test_path_types_are_accepted() -> None:
    assert classify_extension(Path("movie.mp4").name) is Kind.VIDEO
