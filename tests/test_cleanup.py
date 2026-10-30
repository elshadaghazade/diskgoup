from __future__ import annotations

from pathlib import Path

import pytest

from diskgoup.commands.serve import Server
from diskgoup.core.cleanup import clear, commit, stage, staged_items, unstage, validate
from diskgoup.core.scanner import Scanner, ScanOptions
from diskgoup.core.store import ScanIndex


@pytest.fixture
def scanned(tmp_path_factory: pytest.TempPathFactory) -> tuple[ScanIndex, int, Path]:
    """A scanned tree with two disposable files."""
    root = tmp_path_factory.mktemp("cleanup")
    (root / "junk.bin").write_bytes(b"x" * 1024)
    (root / "keep.bin").write_bytes(b"y" * 512)

    index = ScanIndex(tmp_path_factory.mktemp("idx") / "index.db")
    scanner = Scanner(index, ScanOptions(root=root))
    scan_id = scanner.run().meta.scan_id
    return index, scan_id, root


def test_staging_adds_to_the_review_list(scanned: tuple[ScanIndex, int, Path]) -> None:
    index, scan_id, root = scanned
    added, refused = stage(index, scan_id, [root / "junk.bin"])

    assert len(added) == 1
    assert refused == []
    assert [item.path for item in staged_items(index, scan_id)] == [root / "junk.bin"]


def test_staging_twice_does_not_duplicate(scanned: tuple[ScanIndex, int, Path]) -> None:
    index, scan_id, root = scanned
    stage(index, scan_id, [root / "junk.bin"])
    added, _ = stage(index, scan_id, [root / "junk.bin"])

    assert added == []
    assert len(staged_items(index, scan_id)) == 1


def test_unstage_removes_the_item(scanned: tuple[ScanIndex, int, Path]) -> None:
    index, scan_id, root = scanned
    stage(index, scan_id, [root / "junk.bin"])

    removed = unstage(index, scan_id, [root / "junk.bin"])

    assert removed == 1
    assert staged_items(index, scan_id) == []


def test_clear_empties_the_review_list(scanned: tuple[ScanIndex, int, Path]) -> None:
    index, scan_id, root = scanned
    stage(index, scan_id, [root / "junk.bin", root / "keep.bin"])

    clear(index, scan_id)

    assert staged_items(index, scan_id) == []


def test_protected_paths_cannot_be_staged(
    scanned: tuple[ScanIndex, int, Path],
) -> None:
    import sys

    index, scan_id, _ = scanned
    if sys.platform == "darwin":
        protected = Path("/System/Library")
    elif sys.platform.startswith("win"):
        protected = Path(r"C:\Windows\System32")
    else:
        protected = Path("/usr/lib")

    added, refused = stage(index, scan_id, [protected])

    assert added == []
    assert len(refused) == 1
    assert "Protected" in refused[0].reason


def test_validation_detects_a_vanished_file(scanned: tuple[ScanIndex, int, Path]) -> None:
    index, scan_id, root = scanned
    target = root / "junk.bin"
    stage(index, scan_id, [target])
    target.unlink()

    valid, issues = validate(index, scan_id)

    assert valid == []
    assert len(issues) == 1
    assert "no longer exists" in issues[0].reason


def test_commit_moves_the_file_out_of_the_way(
    scanned: tuple[ScanIndex, int, Path],
) -> None:
    index, scan_id, root = scanned
    target = root / "junk.bin"
    stage(index, scan_id, [target])

    result = commit(index, scan_id, permanent=True)

    assert result.moved == [target]
    assert not target.exists()
    assert result.freed == 1024


def test_commit_reports_a_failure_without_raising(
    scanned: tuple[ScanIndex, int, Path],
) -> None:
    index, scan_id, root = scanned
    target = root / "junk.bin"
    stage(index, scan_id, [target])
    target.unlink()

    result = commit(index, scan_id, permanent=True)

    assert result.moved == []
    assert result.issues


def test_the_rpc_stages_and_takes_items_back(
    tmp_path: Path, scanned: tuple[ScanIndex, int, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    """The desktop app stages a selection, then can undo it."""
    _, _, root = scanned
    db = tmp_path / "index.db"
    monkeypatch.setenv("DISKGOUP_INDEX", str(db))
    with ScanIndex(db) as index:
        scan_id = Scanner(index, ScanOptions(root=root)).run().meta.scan_id

    response = Server().handle(
        {
            "id": 1,
            "method": "cleanup.stage",
            "params": {"scan_id": scan_id, "paths": [str(root / "junk.bin")]},
        }
    )

    assert response is not None
    assert "error" not in response, response
    assert [item["path"] for item in response["result"]["staged"]] == [str(root / "junk.bin")]

    response = Server().handle(
        {
            "id": 2,
            "method": "cleanup.unstage",
            "params": {"scan_id": scan_id, "paths": [str(root / "junk.bin")]},
        }
    )

    assert response is not None
    assert response["result"]["removed"] == 1

    response = Server().handle({"id": 3, "method": "cleanup.list", "params": {"scan_id": scan_id}})

    assert response is not None
    assert response["result"]["items"] == []
