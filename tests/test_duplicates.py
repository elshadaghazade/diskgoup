from __future__ import annotations

import os
from pathlib import Path

import pytest

from diskgoup.core.cleanup import stage
from diskgoup.core.duplicates import find_duplicates, search_scan
from diskgoup.core.scanner import Scanner, ScanOptions
from diskgoup.core.store import ScanIndex


def _write(path: Path, data: bytes) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return path


def test_identical_files_are_grouped(tmp_path: Path) -> None:
    payload = b"the quick brown fox" * 100
    first = _write(tmp_path / "a" / "one.bin", payload)
    second = _write(tmp_path / "b" / "two.bin", payload)
    other = _write(tmp_path / "c" / "three.bin", b"different content entirely")

    report = find_duplicates([first, second, other])

    assert len(report.groups) == 1
    group = report.groups[0]
    assert group.copies == 2
    assert group.size == len(payload)
    assert group.reclaimable == len(payload)
    assert set(group.paths) == {first, second}


def test_equal_size_but_different_content_is_not_a_duplicate(tmp_path: Path) -> None:
    first = _write(tmp_path / "a.bin", b"a" * 4096)
    second = _write(tmp_path / "b.bin", b"b" * 4096)

    report = find_duplicates([first, second])

    assert report.groups == []


def test_zero_byte_files_are_excluded(tmp_path: Path) -> None:
    first = _write(tmp_path / "a.bin", b"")
    second = _write(tmp_path / "b.bin", b"")

    report = find_duplicates([first, second])

    assert report.groups == []
    assert report.candidates == 0


def test_three_copies_reclaim_two(tmp_path: Path) -> None:
    payload = b"x" * 2048
    paths = [_write(tmp_path / f"copy{index}.bin", payload) for index in range(3)]

    report = find_duplicates(paths)

    assert len(report.groups) == 1
    assert report.groups[0].copies == 3
    assert report.groups[0].reclaimable == 2048 * 2


def test_hard_links_are_excluded(tmp_path: Path) -> None:
    import os

    original = _write(tmp_path / "original.bin", b"y" * 1024)
    link = tmp_path / "link.bin"
    try:
        os.link(original, link)
    except (OSError, NotImplementedError):  # pragma: no cover - platform dependent
        return

    report = find_duplicates([original, link])

    assert report.groups == []


def test_large_files_with_the_same_prefix_are_still_distinguished(tmp_path: Path) -> None:
    # Same head, different tail: the pipeline must not stop at the prefix sample.
    head = b"A" * (200 * 1024)
    first = _write(tmp_path / "one.bin", head + b"tail-one")
    second = _write(tmp_path / "two.bin", head + b"tail-two")

    report = find_duplicates([first, second])

    assert report.groups == []


# ─────────────────────────────────────────────────────── the search of a scan ───


def _scanned(tmp_path_factory: pytest.TempPathFactory, root: Path) -> tuple[ScanIndex, int]:
    """A scan of ``root`` in an index of its own."""
    index = ScanIndex(tmp_path_factory.mktemp("idx") / "index.db")
    scan_id = Scanner(index, ScanOptions(root=root)).run().meta.scan_id
    return index, scan_id


def test_the_search_finds_the_groups_of_a_scan(
    tmp_path_factory: pytest.TempPathFactory,
) -> None:
    root = tmp_path_factory.mktemp("tree")
    payload = b"the same bytes" * 500
    _write(root / "one.bin", payload)
    _write(root / "two.bin", payload)
    _write(root / "other.bin", b"something else entirely")

    index, scan_id = _scanned(tmp_path_factory, root)
    with index:
        report = search_scan(index, scan_id)

    assert len(report.groups) == 1
    assert report.groups[0].copies == 2
    assert report.total_reclaimable == len(payload)


def test_the_oldest_copy_is_the_one_that_is_kept(tmp_path: Path) -> None:
    """The content is the same, so the age is what tells the copies apart."""
    payload = b"x" * 4096
    older = _write(tmp_path / "older.bin", payload)
    newer = _write(tmp_path / "newer.bin", payload)
    os.utime(older, (1_000_000, 1_000_000))
    os.utime(newer, (2_000_000, 2_000_000))

    report = find_duplicates([older, newer])

    assert report.groups[0].keep == older
    assert report.groups[0].paths[0] == older


def test_a_file_that_changed_is_hashed_again(
    tmp_path_factory: pytest.TempPathFactory,
) -> None:
    """The remembered digest must not survive a change of the file."""
    root = tmp_path_factory.mktemp("tree")
    payload = b"a" * 4096
    first = _write(root / "one.bin", payload)
    _write(root / "two.bin", payload)

    index, scan_id = _scanned(tmp_path_factory, root)
    with index:
        report = search_scan(index, scan_id)
        assert len(report.groups) == 1

        # The file keeps its size but not its content.
        first.write_bytes(b"b" * 4096)

        report = search_scan(index, scan_id)

    assert report.groups == []


def test_the_digest_is_remembered_between_searches(
    tmp_path_factory: pytest.TempPathFactory,
) -> None:
    root = tmp_path_factory.mktemp("tree")
    payload = b"remembered" * 100
    _write(root / "one.bin", payload)
    _write(root / "two.bin", payload)

    index, scan_id = _scanned(tmp_path_factory, root)
    with index:
        search_scan(index, scan_id)
        remembered = index.cached_hashes(scan_id)

        assert len(remembered) == 2
        assert all(digest for _, _, _, _, digest in remembered)

        # The second search finds the same groups — the digests are reused.
        report = search_scan(index, scan_id)

    assert len(report.groups) == 1


def test_a_protected_copy_is_not_cleanable(
    tmp_path_factory: pytest.TempPathFactory,
) -> None:
    """The copy of a game is never up for removal."""
    root = tmp_path_factory.mktemp("tree")
    payload = b"game data" * 100
    game = _write(root / "Steam" / "save.dat", payload)
    _write(root / "Downloads" / "save.dat", payload)

    index, scan_id = _scanned(tmp_path_factory, root)
    with index:
        report = search_scan(index, scan_id)
        assert len(report.groups) == 1

        added, refused = stage(index, scan_id, list(report.groups[0].paths))

    assert [item.path for item in added] == [root / "Downloads" / "save.dat"]
    assert [issue.path for issue in refused] == [game]
    assert "game" in refused[0].reason.lower()


def test_the_search_survives_a_file_that_is_gone(
    tmp_path_factory: pytest.TempPathFactory,
) -> None:
    root = tmp_path_factory.mktemp("tree")
    payload = b"b" * 4096
    _write(root / "one.bin", payload)
    _write(root / "two.bin", payload)

    index, scan_id = _scanned(tmp_path_factory, root)
    with index:
        (root / "two.bin").unlink()

        report = search_scan(index, scan_id)

    assert report.groups == []
