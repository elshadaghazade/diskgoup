"""Removing a scan from the index.

A scan is a walk of a tree, and everything the app shows is derived from it.
Removing a scan therefore has to take the whole derivation with it — the
entries, the skipped paths, the hashes — and leave the other scans alone.

The CLI does this with ``diskgoup scans remove <id>``; the GUI asks for the
same thing over the ``scans.remove`` RPC method.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from diskgoup.commands.serve import INTERNAL_ERROR, Server
from diskgoup.core.scanner import Scanner, ScanOptions
from diskgoup.core.store import ScanIndex


@pytest.fixture
def tree(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """A small tree to scan."""
    root = tmp_path_factory.mktemp("delete")
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
    return Scanner(index, ScanOptions(root=root)).run().meta.scan_id


def test_deleting_a_scan_removes_its_entries(index: ScanIndex, tree: Path) -> None:
    scan_id = scan(index, tree)
    assert index.count_entries(scan_id) == 4

    index.delete_scan(scan_id)

    assert index.count_entries(scan_id) == 0
    assert index.scan_meta(scan_id) is None


def test_deleting_a_scan_leaves_the_others_alone(index: ScanIndex, tree: Path) -> None:
    first = scan(index, tree)
    second = scan(index, tree)

    index.delete_scan(first)

    remaining = index.scans()
    assert [meta.scan_id for meta in remaining] == [second]


def test_the_rpc_removes_a_scan(
    tmp_path: Path, tree: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db = tmp_path / "index.db"
    monkeypatch.setenv("DISKGOUP_INDEX", str(db))
    with ScanIndex(db) as index:
        scan_id = scan(index, tree)

    response = Server().handle({"id": 1, "method": "scans.remove", "params": {"scan_id": scan_id}})

    assert response is not None
    assert "error" not in response
    assert response["result"]["removed"]["scan_id"] == scan_id

    with ScanIndex(db) as index:
        assert index.scans() == []


def test_the_rpc_rejects_an_unknown_scan(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DISKGOUP_INDEX", str(tmp_path / "index.db"))

    response = Server().handle({"id": 1, "method": "scans.remove", "params": {"scan_id": 99}})

    assert response is not None
    assert response["error"]["code"] == INTERNAL_ERROR
    assert "no scan with id 99" in response["error"]["message"]


def test_the_rpc_needs_a_scan_id(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DISKGOUP_INDEX", str(tmp_path / "index.db"))

    response = Server().handle({"id": 1, "method": "scans.remove", "params": {}})

    assert response is not None
    assert "error" in response
