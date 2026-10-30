from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from diskgoup.core.models import Kind
from diskgoup.core.scanner import ScanControl, Scanner, ScanOptions
from diskgoup.core.store import ScanIndex


@pytest.fixture
def tree(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """A small fixture tree with known sizes.

    All files are 1000 bytes so the expected totals are easy to reason about.
    """
    root = tmp_path_factory.mktemp("tree")
    (root / "Downloads" / "Cache").mkdir(parents=True)
    (root / "Documents" / "Work").mkdir(parents=True)
    (root / "Videos").mkdir()

    (root / "Downloads" / "movie.mp4").write_bytes(b"x" * 1000)
    (root / "Downloads" / "Linux.iso").write_bytes(b"x" * 1000)
    (root / "Downloads" / "Cache" / "pkg.bin").write_bytes(b"x" * 1000)
    (root / "Documents" / "Work" / "design.zip").write_bytes(b"x" * 1000)
    (root / "Videos" / "render.mp4").write_bytes(b"x" * 1000)
    return root


@pytest.fixture
def index(tmp_path_factory: pytest.TempPathFactory) -> ScanIndex:
    """An index that lives outside the scanned tree."""
    store = ScanIndex(tmp_path_factory.mktemp("idx") / "index.db")
    yield store
    store.close()


def scan(index: ScanIndex, root: Path, **kwargs: object) -> int:
    scanner = Scanner(index, ScanOptions(root=root, **kwargs))  # type: ignore[arg-type]
    return scanner.run().meta.scan_id


def test_scan_counts_files_and_folders(index: ScanIndex, tree: Path) -> None:
    scan_id = scan(index, tree)
    meta = index.scan_meta(scan_id)
    assert meta is not None
    assert meta.file_count == 5
    # Downloads, Downloads/Cache, Documents, Documents/Work, Videos + the root.
    assert meta.dir_count == 5
    assert meta.complete is True


def test_directory_totals_are_cumulative(index: ScanIndex, tree: Path) -> None:
    scan_id = scan(index, tree)
    root = index.build_tree(scan_id)
    assert root is not None
    assert root.size == 5000

    by_name = {child.name: child for child in root.children}
    assert by_name["Downloads"].size == 3000
    assert by_name["Videos"].size == 1000
    assert by_name["Documents"].size == 1000

    cache = by_name["Downloads"].children[0]
    assert cache.name == "Cache"
    assert cache.size == 1000


def test_root_totals_match_the_aggregate(index: ScanIndex, tree: Path) -> None:
    scan_id = scan(index, tree)
    totals = index.root_totals(scan_id)
    assert totals["size"] == 5000
    assert totals["files"] == 5


def test_cache_subtree_is_classified_as_cache(index: ScanIndex, tree: Path) -> None:
    scan_id = scan(index, tree)
    rows = {row["path"]: row for row in index.iter_entries(scan_id)}
    cache_file = next(row for path, row in rows.items() if path.endswith("pkg.bin"))
    assert cache_file["kind"] == str(Kind.CACHE)

    movie = next(row for path, row in rows.items() if path.endswith("movie.mp4"))
    assert movie["kind"] == str(Kind.VIDEO)


def test_largest_entries_are_ordered_by_size(index: ScanIndex, tree: Path) -> None:
    scan_id = scan(index, tree)
    rows = index.largest_entries(scan_id, limit=5)
    sizes = [int(row["size"]) for row in rows]
    assert sizes == sorted(sizes, reverse=True)
    assert rows[0]["name"] == tree.name


def test_max_depth_limits_traversal(index: ScanIndex, tree: Path) -> None:
    scan_id = scan(index, tree, max_depth=1)
    meta = index.scan_meta(scan_id)
    assert meta is not None
    # Only the root's immediate children are reachable at depth 1.
    assert meta.file_count == 0


def test_exclude_patterns_are_skipped(index: ScanIndex, tree: Path) -> None:
    scan_id = scan(index, tree, exclude=("*.mp4",))
    meta = index.scan_meta(scan_id)
    assert meta is not None
    assert meta.file_count == 3


def test_missing_root_raises(index: ScanIndex, tmp_path: Path) -> None:
    scanner = Scanner(index, ScanOptions(root=tmp_path / "nope"))
    with pytest.raises(FileNotFoundError):
        scanner.run()


def test_file_root_raises(index: ScanIndex, tree: Path) -> None:
    scanner = Scanner(index, ScanOptions(root=tree / "Videos" / "render.mp4"))
    with pytest.raises(NotADirectoryError):
        scanner.run()


def test_directory_counts_are_cumulative(index: ScanIndex, tree: Path) -> None:
    """Every directory knows its own subtree: the files below it and the
    number of directories directly inside it."""
    scan_id = scan(index, tree)
    rows = {row["path"]: row for row in index.iter_entries(scan_id)}

    def row_for(suffix: str) -> sqlite3.Row:
        return next(row for path, row in rows.items() if path.endswith(suffix))

    root = row_for(tree.name)
    assert root["size"] == 5000
    assert root["file_count"] == 5
    assert root["dir_count"] == 3  # Downloads, Documents, Videos

    downloads = row_for("Downloads")
    assert downloads["size"] == 3000
    assert downloads["file_count"] == 3
    assert downloads["dir_count"] == 1  # Downloads/Cache

    cache = row_for("Cache")
    assert cache["size"] == 1000
    assert cache["file_count"] == 1
    assert cache["dir_count"] == 0

    work = row_for("Work")
    assert work["size"] == 1000
    assert work["file_count"] == 1
    assert work["dir_count"] == 0

    movie = row_for("movie.mp4")
    assert movie["file_count"] == 1
    assert movie["dir_count"] == 0
    assert movie["size"] == 1000


def test_a_stopped_scan_still_reports_what_it_saw(index: ScanIndex, tree: Path) -> None:
    """A scan that was stopped early keeps the totals of the part it walked."""
    control = ScanControl()
    seen = 0

    def on_progress(_progress: object) -> None:
        nonlocal seen
        seen += 1
        # The fixture holds five directories and five files, so stopping after
        # eight entries always leaves at least one file behind.
        if seen >= 8:
            control.cancel()

    result = Scanner(index, ScanOptions(root=tree)).run(on_progress, control=control)

    assert result.canceled is True
    assert result.meta.complete is False
    totals = index.root_totals(result.meta.scan_id)
    assert 0 < totals["size"] <= 5000
    assert 0 < totals["files"] <= 5


def test_a_profiled_scan_reports_where_the_time_went(index: ScanIndex, tree: Path) -> None:
    scanner = Scanner(index, ScanOptions(root=tree, profile=True))
    result = scanner.run()

    assert result.timings
    assert "walk" in result.timings
    assert "total" in result.timings
    assert result.timings["total"] >= result.timings["walk"]
