from __future__ import annotations

from pathlib import Path

from diskgoup.core.duplicates import find_duplicates


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
