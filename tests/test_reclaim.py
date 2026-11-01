from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from diskgoup.commands.serve import Server
from diskgoup.core.reclaim import reclaimable
from diskgoup.core.scanner import Scanner, ScanOptions
from diskgoup.core.store import ScanIndex


@pytest.fixture
def scanned(tmp_path_factory: pytest.TempPathFactory) -> tuple[ScanIndex, int, Path]:
    """A tree with the kinds a cleaner cares about — and one it must not touch."""
    root = tmp_path_factory.mktemp("reclaim")
    (root / "Cache").mkdir()
    (root / "Cache" / "inner").mkdir()
    (root / "Cache" / "inner" / "blob.bin").write_bytes(b"x" * 100)
    (root / "logs").mkdir()
    (root / "logs" / "app.log").write_bytes(b"y" * 50)
    (root / "Documents").mkdir()
    (root / "Documents" / "notes.txt").write_text("hello")

    index = ScanIndex(tmp_path_factory.mktemp("idx") / "index.db")
    scan_id = Scanner(index, ScanOptions(root=root)).run().meta.scan_id
    return index, scan_id, root


def test_the_junk_of_a_scan_is_the_top_most_cache_folders(
    scanned: tuple[ScanIndex, int, Path],
) -> None:
    """The folders below a cache folder are counted with it, not on their own."""
    index, scan_id, _ = scanned

    candidates = reclaimable(index, scan_id)

    assert sorted(candidate.name for candidate in candidates) == ["Cache", "logs"]


def test_a_candidate_carries_what_the_user_needs_to_know(
    scanned: tuple[ScanIndex, int, Path],
) -> None:
    index, scan_id, root = scanned

    cache = next(
        candidate for candidate in reclaimable(index, scan_id) if candidate.name == "Cache"
    )

    assert cache.path == root / "Cache"
    assert cache.size == 100
    assert cache.files == 1
    assert cache.cleanable
    assert not cache.protected
    assert not cache.critical


def test_ordinary_folders_are_not_offered(scanned: tuple[ScanIndex, int, Path]) -> None:
    """A user's own documents are not junk — the cleaner does not touch them."""
    index, scan_id, _ = scanned

    paths = [str(candidate.path) for candidate in reclaimable(index, scan_id)]

    assert not any(path.endswith("Documents") for path in paths)


def test_nothing_is_offered_when_the_scan_holds_no_junk(
    tmp_path_factory: pytest.TempPathFactory,
) -> None:
    root = tmp_path_factory.mktemp("clean")
    (root / "notes.txt").write_text("hello")

    index = ScanIndex(tmp_path_factory.mktemp("idx") / "index.db")
    scan_id = Scanner(index, ScanOptions(root=root)).run().meta.scan_id

    assert reclaimable(index, scan_id) == []


def test_the_scope_is_served_in_the_shape_the_browser_draws(
    scanned: tuple[ScanIndex, int, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    """The scope is a folder listing — the browser needs no second widget."""
    index, scan_id, root = scanned
    monkeypatch.setenv("DISKGOUP_INDEX", str(index.db_path))

    response = Server().handle(
        {
            "id": 1,
            "method": "explore.reclaimable",
            "params": {"path": str(root), "scan_id": scan_id},
        }
    )

    assert response is not None
    assert "error" not in response, response
    result = response["result"]
    assert isinstance(result, dict)
    entries: list[dict[str, Any]] = result["entries"]

    assert result["path"] == str(root)
    assert result["parent"] is None
    assert result["crumbs"] == [{"name": "Safe to clean", "path": str(root)}]
    assert sorted(entry["name"] for entry in entries) == ["Cache", "logs"]
    for entry in entries:
        assert entry["is_dir"] is True
        assert entry["reason"] is None
        assert entry["protected"] is False
        assert entry["critical"] is False


def test_the_scope_does_not_scan_the_disk_again(
    scanned: tuple[ScanIndex, int, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    """The answer comes out of the index — no second scan, no walk."""
    index, scan_id, root = scanned
    monkeypatch.setenv("DISKGOUP_INDEX", str(index.db_path))

    for _ in range(3):
        Server().handle(
            {
                "id": 1,
                "method": "explore.reclaimable",
                "params": {"path": str(root), "scan_id": scan_id},
            }
        )

    with ScanIndex(index.db_path) as reopened:
        assert len(reopened.scans()) == 1
