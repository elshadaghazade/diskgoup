"""Browsing inside a scan.

The desktop app opens a folder by asking the CLI for its children. The answer
comes from the index, so browsing a folder never walks the disk again — and the
breadcrumb the app shows is the chain of ancestors the CLI reports.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from diskgoup.commands.serve import INTERNAL_ERROR, Server
from diskgoup.core.scanner import Scanner, ScanOptions
from diskgoup.core.store import ScanIndex


@pytest.fixture
def tree(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """A small tree with a nested folder, an empty folder and a file."""
    root = tmp_path_factory.mktemp("browse")
    (root / "Documents").mkdir()
    (root / "Documents" / "notes.txt").write_bytes(b"x" * 100)
    (root / "Documents" / "deep").mkdir()
    (root / "Documents" / "deep" / "deeper.txt").write_bytes(b"x" * 200)
    (root / "Empty").mkdir()
    (root / "movie.mp4").write_bytes(b"x" * 300)
    return root


@pytest.fixture
def scanned(tmp_path: Path, tree: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[int, str, Path]:
    """A scanned tree: the scan id, the resolved root and the index file."""
    db = tmp_path / "index.db"
    monkeypatch.setenv("DISKGOUP_INDEX", str(db))
    with ScanIndex(db) as index:
        scan_id = Scanner(index, ScanOptions(root=tree)).run().meta.scan_id
        root = str(index.scan_meta(scan_id).root)  # type: ignore[union-attr]
    return scan_id, root, db


def browse(scan_id: int, path: str) -> dict[str, Any]:
    """Ask the server for the children of a folder."""
    response = Server().handle(
        {"id": 1, "method": "explore.children", "params": {"path": path, "scan_id": scan_id}}
    )
    assert response is not None
    assert "error" not in response, response
    result = response["result"]
    assert isinstance(result, dict)
    return result


def test_the_children_of_the_root_are_listed(scanned: tuple[int, str, Path]) -> None:
    scan_id, root, _ = scanned

    result = browse(scan_id, root)

    # Folders first, each group by size.
    assert [entry["name"] for entry in result["entries"]] == [
        "Documents",
        "Empty",
        "movie.mp4",
    ]
    assert result["path"] == root


def test_an_entry_carries_its_size_and_counts(scanned: tuple[int, str, Path]) -> None:
    scan_id, root, _ = scanned

    result = browse(scan_id, root)
    documents = next(entry for entry in result["entries"] if entry["name"] == "Documents")
    movie = next(entry for entry in result["entries"] if entry["name"] == "movie.mp4")

    assert documents["is_dir"] is True
    assert documents["size"] == 300  # the whole subtree
    assert documents["files"] == 2  # notes.txt and deeper.txt
    assert documents["folders"] == 1  # the immediate subfolder "deep"
    assert movie["is_dir"] is False
    assert movie["size"] == 300
    assert movie["files"] == 1


def test_the_parent_and_the_crumbs_are_reported(scanned: tuple[int, str, Path]) -> None:
    scan_id, root, _ = scanned
    documents = str(Path(root) / "Documents")

    result = browse(scan_id, documents)

    assert result["parent"] == root
    assert result["crumbs"] == [
        {"name": Path(root).name, "path": root},
        {"name": "Documents", "path": documents},
    ]


def test_the_root_has_no_parent(scanned: tuple[int, str, Path]) -> None:
    scan_id, root, _ = scanned

    result = browse(scan_id, root)

    assert result["parent"] is None
    assert len(result["crumbs"]) == 1


def test_a_folder_outside_the_scan_is_rejected(scanned: tuple[int, str, Path]) -> None:
    scan_id, _, _ = scanned

    response = Server().handle(
        {
            "id": 1,
            "method": "explore.children",
            "params": {"path": "/definitely/not/in/the/scan", "scan_id": scan_id},
        }
    )

    assert response is not None
    assert response["error"]["code"] == INTERNAL_ERROR
    assert "not in scan" in response["error"]["message"]


def test_browsing_does_not_scan_the_disk_again(scanned: tuple[int, str, Path]) -> None:
    scan_id, root, db = scanned

    for _ in range(3):
        browse(scan_id, root)
    browse(scan_id, str(Path(root) / "Documents"))

    with ScanIndex(db) as index:
        assert len(index.scans()) == 1
