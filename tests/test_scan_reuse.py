"""Reusing a stored scan instead of walking the tree again.

The persistent index exists so one scan can power every view. These tests
pin down the behaviour that makes that possible: a command asked for a path
that has already been scanned reads the stored scan rather than re-walking
the disk.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from diskgoup.commands.common import ensure_scan
from diskgoup.core.scanner import Scanner, ScanOptions
from diskgoup.core.store import ScanIndex


@pytest.fixture
def tree(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """A small tree to scan."""
    root = tmp_path_factory.mktemp("reuse")
    (root / "Documents").mkdir()
    (root / "Documents" / "notes.txt").write_bytes(b"x" * 100)
    (root / "movie.mp4").write_bytes(b"x" * 100)
    return root


@pytest.fixture
def index(tmp_path_factory: pytest.TempPathFactory) -> ScanIndex:
    """An index that lives outside the scanned tree."""
    store = ScanIndex(tmp_path_factory.mktemp("idx") / "index.db")
    yield store
    store.close()


def scan(index: ScanIndex, root: Path) -> int:
    scanner = Scanner(index, ScanOptions(root=root))
    return scanner.run().meta.scan_id


def test_scan_for_root_finds_the_latest_scan(index: ScanIndex, tree: Path) -> None:
    first = scan(index, tree)
    second = scan(index, tree)

    found = index.scan_for_root(tree)
    assert found is not None
    assert found.scan_id == second
    assert first != second


def test_scan_for_root_ignores_other_roots(index: ScanIndex, tree: Path) -> None:
    scan(index, tree)
    assert index.scan_for_root(tree / "Documents") is None


def test_ensure_scan_reuses_a_stored_scan(index: ScanIndex, tree: Path) -> None:
    stored = scan(index, tree)

    reused = ensure_scan(index, tree, show_progress=False)

    assert reused.scan_id == stored
    # Reusing means reusing — the index still holds exactly one scan.
    assert len(index.scans()) == 1


def test_ensure_scan_rescans_on_request(index: ScanIndex, tree: Path) -> None:
    stored = scan(index, tree)

    fresh = ensure_scan(index, tree, rescan=True, show_progress=False)

    assert fresh.scan_id != stored
    assert len(index.scans()) == 2


def test_ensure_scan_by_id_ignores_the_path(index: ScanIndex, tree: Path) -> None:
    stored = scan(index, tree)

    chosen = ensure_scan(index, tree, scan_id=stored, show_progress=False)

    assert chosen.scan_id == stored


def test_ensure_scan_scans_a_root_that_was_never_scanned(index: ScanIndex, tree: Path) -> None:
    meta = ensure_scan(index, tree, show_progress=False)

    assert meta.complete is True
    assert meta.file_count == 2


def test_scan_for_root_skips_an_incomplete_scan(index: ScanIndex, tree: Path) -> None:
    # A scan that was interrupted is recorded but never finished.
    index.begin_scan(tree)

    assert index.scan_for_root(tree) is None
    assert index.scan_for_root(tree, complete_only=False) is not None


def test_delete_scan_removes_it_from_the_index(index: ScanIndex, tree: Path) -> None:
    scan_id = scan(index, tree)

    index.delete_scan(scan_id)

    assert index.scans() == []
    assert index.scan_meta(scan_id) is None
    assert index.scan_for_root(tree) is None
