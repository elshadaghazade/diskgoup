"""Refreshing one folder of a scan, and cleaning up after a removal.

A scan is a snapshot. When a folder changes, the snapshot is corrected
*locally*: the folder is walked again, only its rows are replaced, and the
totals of the folders above it are corrected by the difference. A cleanup
takes the rows of what was removed away, so the index keeps telling the
truth about the disk.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from diskgoup.commands.serve import Server
from diskgoup.core import cleanup
from diskgoup.core.cleanup import commit, stage
from diskgoup.core.scanner import Scanner, ScanOptions, is_stale, refresh_subtree
from diskgoup.core.store import ScanIndex


def _remove(path: Path) -> None:
    """Stand-in for the recycle bin: the path is simply gone."""
    if path.is_dir():
        shutil.rmtree(path)
    else:
        path.unlink()


@pytest.fixture
def tree(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """A small tree with a nested folder."""
    root = tmp_path_factory.mktemp("refresh")
    (root / "Documents" / "deep").mkdir(parents=True)
    (root / "Pictures").mkdir()
    (root / "Documents" / "notes.txt").write_bytes(b"x" * 100)
    (root / "Documents" / "deep" / "deeper.txt").write_bytes(b"x" * 200)
    (root / "Pictures" / "photo.jpg").write_bytes(b"x" * 300)
    return root


@pytest.fixture
def index(tmp_path_factory: pytest.TempPathFactory) -> ScanIndex:
    store = ScanIndex(tmp_path_factory.mktemp("idx") / "index.db")
    yield store
    store.close()


def scan(index: ScanIndex, root: Path) -> int:
    return Scanner(index, ScanOptions(root=root)).run().meta.scan_id


def content(index: ScanIndex, scan_id: int) -> list[tuple[object, ...]]:
    """Everything the index holds about a scan, in a comparable order."""
    rows = index.connection.execute(
        """
        SELECT path, name, is_dir, size, on_disk, kind, protected, depth, file_count, dir_count
          FROM entries WHERE scan_id = ? ORDER BY path
        """,
        (scan_id,),
    ).fetchall()
    return [tuple(row) for row in rows]


def test_a_refresh_picks_up_what_changed(index: ScanIndex, tree: Path) -> None:
    """The folder is walked again, so what was added is in the index."""
    scan_id = scan(index, tree)
    documents = tree / "Documents"
    (documents / "new.txt").write_bytes(b"x" * 50)

    result = refresh_subtree(index, scan_id, documents)

    assert result.files == 3  # notes.txt, deeper.txt and new.txt
    names = {
        str(row["name"])
        for row in index.connection.execute(
            "SELECT name FROM entries WHERE scan_id = ? AND parent_id = "
            "(SELECT id FROM entries WHERE scan_id = ? AND path = ?)",
            (scan_id, scan_id, str(documents)),
        )
    }
    assert "new.txt" in names


def test_a_refresh_leaves_the_rest_of_the_scan_alone(index: ScanIndex, tree: Path) -> None:
    """Only the folder's own rows are replaced."""
    scan_id = scan(index, tree)
    pictures = index.entry_by_path(scan_id, tree / "Pictures")
    assert pictures is not None
    before = index.connection.execute(
        "SELECT id FROM entries WHERE scan_id = ? AND parent_id = ?",
        (scan_id, int(pictures["id"])),
    ).fetchall()

    (tree / "Documents" / "new.txt").write_bytes(b"x" * 50)
    refresh_subtree(index, scan_id, tree / "Documents")

    after = index.connection.execute(
        "SELECT id FROM entries WHERE scan_id = ? AND parent_id = ?",
        (scan_id, int(pictures["id"])),
    ).fetchall()
    assert [row["id"] for row in after] == [row["id"] for row in before]


def test_a_refresh_gives_the_same_index_as_a_full_rescan(
    index: ScanIndex, tree: Path, tmp_path_factory: pytest.TempPathFactory
) -> None:
    """The result of a refresh has to be what a rescan would have found."""
    scan_id = scan(index, tree)

    (tree / "Documents" / "new.txt").write_bytes(b"x" * 50)
    (tree / "Documents" / "deep" / "even-deeper.txt").write_bytes(b"x" * 25)
    (tree / "Pictures" / "photo.jpg").unlink()
    (tree / "Music").mkdir()
    (tree / "Music" / "song.mp3").write_bytes(b"x" * 75)

    refresh_subtree(index, scan_id, tree)

    # The same tree, scanned from scratch in a second index.
    other = ScanIndex(tmp_path_factory.mktemp("other") / "index.db")
    try:
        fresh = scan(other, tree)
        assert content(index, scan_id) == content(other, fresh)

        meta = index.scan_meta(scan_id)
        fresh_meta = other.scan_meta(fresh)
        assert meta is not None and fresh_meta is not None
        assert meta.total_size == fresh_meta.total_size
        assert meta.total_on_disk == fresh_meta.total_on_disk
        assert meta.file_count == fresh_meta.file_count
        assert meta.dir_count == fresh_meta.dir_count
    finally:
        other.close()


def test_a_refresh_corrects_the_totals_of_the_ancestors(index: ScanIndex, tree: Path) -> None:
    """The folders above the refreshed one hold the new totals."""
    scan_id = scan(index, tree)
    root = index.root_entry(scan_id)
    assert root is not None
    assert int(root["size"]) == 600
    assert int(root["file_count"]) == 3

    (tree / "Documents" / "new.txt").write_bytes(b"x" * 500)
    refresh_subtree(index, scan_id, tree / "Documents")

    root = index.root_entry(scan_id)
    assert root is not None
    assert int(root["size"]) == 1100
    assert int(root["file_count"]) == 4

    meta = index.scan_meta(scan_id)
    assert meta is not None
    assert meta.total_size == 1100
    assert meta.file_count == 4


def test_a_refresh_of_a_folder_removes_what_it_no_longer_holds(
    index: ScanIndex, tree: Path
) -> None:
    """A file that was deleted outside the app leaves the index."""
    scan_id = scan(index, tree)
    (tree / "Documents" / "notes.txt").unlink()

    refresh_subtree(index, scan_id, tree / "Documents")

    paths = {
        str(row["path"])
        for row in index.connection.execute(
            "SELECT path FROM entries WHERE scan_id = ?", (scan_id,)
        )
    }
    assert str(tree / "Documents" / "notes.txt") not in paths


def test_a_changed_folder_is_stale(index: ScanIndex, tree: Path) -> None:
    """The modification time of the folder is what says so."""
    scan_id = scan(index, tree)
    documents = tree / "Documents"

    assert is_stale(index, scan_id, documents) is False

    (documents / "new.txt").write_bytes(b"x" * 10)

    assert is_stale(index, scan_id, documents) is True

    refresh_subtree(index, scan_id, documents)

    assert is_stale(index, scan_id, documents) is False


def test_a_removed_folder_is_stale(index: ScanIndex, tree: Path) -> None:
    """A folder that is gone is stale — the index still lists it."""
    scan_id = scan(index, tree)
    pictures = tree / "Pictures"
    (pictures / "photo.jpg").unlink()
    pictures.rmdir()

    assert is_stale(index, scan_id, pictures) is True


def test_a_cleanup_takes_the_rows_out_of_the_index(index: ScanIndex, tree: Path) -> None:
    """What was cleaned is gone from the index — and from the totals."""
    scan_id = scan(index, tree)
    notes = tree / "Documents" / "notes.txt"

    staged, refused = stage(index, scan_id, [notes])
    assert len(staged) == 1
    assert refused == []

    result = commit(index, scan_id, permanent=True)

    assert [str(path) for path in result.moved] == [str(notes)]
    paths = {
        str(row["path"])
        for row in index.connection.execute(
            "SELECT path FROM entries WHERE scan_id = ?", (scan_id,)
        )
    }
    assert str(notes) not in paths

    root = index.root_entry(scan_id)
    assert root is not None
    assert int(root["size"]) == 500  # 600 minus the 100 bytes of notes.txt
    assert int(root["file_count"]) == 2

    meta = index.scan_meta(scan_id)
    assert meta is not None
    assert meta.total_size == 500
    assert meta.file_count == 2


def test_a_cleanup_of_a_folder_takes_its_subtree_with_it(
    index: ScanIndex, tree: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A cleaned folder and everything below it leave the index."""
    scan_id = scan(index, tree)
    documents = tree / "Documents"

    # The recycle bin is not part of the test — the folder is simply gone.
    monkeypatch.setattr(cleanup, "_to_trash", _remove)

    stage(index, scan_id, [documents])
    result = commit(index, scan_id)

    assert [str(path) for path in result.moved] == [str(documents)]
    paths = {
        str(row["path"])
        for row in index.connection.execute(
            "SELECT path FROM entries WHERE scan_id = ?", (scan_id,)
        )
    }
    assert str(documents) not in paths
    assert str(documents / "deep" / "deeper.txt") not in paths

    root = index.root_entry(scan_id)
    assert root is not None
    assert int(root["size"]) == 300  # only the picture is left
    assert int(root["file_count"]) == 1
    assert int(root["dir_count"]) == 1  # Pictures is left

    meta = index.scan_meta(scan_id)
    assert meta is not None
    assert meta.total_size == 300
    assert meta.file_count == 1
    assert meta.dir_count == 1


def test_a_cleanup_leaves_the_folder_it_held_not_stale(index: ScanIndex, tree: Path) -> None:
    """The folder that held the item changed — the index knows its new time."""
    scan_id = scan(index, tree)
    notes = tree / "Documents" / "notes.txt"

    stage(index, scan_id, [notes])
    commit(index, scan_id, permanent=True)

    assert is_stale(index, scan_id, tree / "Documents") is False


@pytest.fixture
def server_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """The index the server reads — it opens the one the environment names."""
    db = tmp_path / "index.db"
    monkeypatch.setenv("DISKGOUP_INDEX", str(db))
    return db


def call(method: str, params: dict[str, object]) -> dict[str, object]:
    """Ask the server something."""
    response = Server().handle({"id": 1, "method": method, "params": params})
    assert response is not None
    assert "error" not in response, response
    result = response["result"]
    assert isinstance(result, dict)
    return result


def test_opening_a_changed_folder_refreshes_it(tree: Path, server_db: Path) -> None:
    """The listing is what is on the disk, not what the scan found."""
    with ScanIndex(server_db) as index:
        scan_id = scan(index, tree)
        root = index.scan_meta(scan_id)
        assert root is not None
        base = root.root
    (tree / "Documents" / "new.txt").write_bytes(b"x" * 50)

    result = call("explore.children", {"path": str(base / "Documents"), "scan_id": scan_id})

    assert "new.txt" in [entry["name"] for entry in result["entries"]]
    assert result["stale"] is False


def test_the_answer_carries_the_corrected_totals(tree: Path, server_db: Path) -> None:
    """The listing reports the totals the index holds now."""
    with ScanIndex(server_db) as index:
        scan_id = scan(index, tree)
        root = index.scan_meta(scan_id)
        assert root is not None
        base = root.root
    (tree / "Documents" / "new.txt").write_bytes(b"x" * 500)

    result = call("explore.children", {"path": str(base / "Documents"), "scan_id": scan_id})

    assert result["scan"]["total_size"] == 1100
    assert result["scan"]["files"] == 4


def test_a_folder_too_big_to_refresh_is_reported_as_stale(
    tree: Path, server_db: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A folder that would take too long to walk is left to the user."""
    import diskgoup.core.scanner as scanner_module

    monkeypatch.setattr(scanner_module, "AUTO_REFRESH_LIMIT", 0)

    with ScanIndex(server_db) as index:
        scan_id = scan(index, tree)
        root = index.scan_meta(scan_id)
        assert root is not None
        base = root.root
    (tree / "Documents" / "new.txt").write_bytes(b"x" * 50)

    result = call("explore.children", {"path": str(base / "Documents"), "scan_id": scan_id})

    assert result["stale"] is True
    assert "new.txt" not in [entry["name"] for entry in result["entries"]]


def test_the_server_can_refresh_a_folder(tree: Path, server_db: Path) -> None:
    """``scan.refresh`` walks one folder and corrects the index."""
    with ScanIndex(server_db) as index:
        scan_id = scan(index, tree)
        root = index.scan_meta(scan_id)
        assert root is not None
        base = root.root
    (tree / "Pictures" / "new.jpg").write_bytes(b"x" * 40)

    result = call("scan.refresh", {"path": str(base / "Pictures"), "scan_id": scan_id})

    assert result["changed"] is True
    assert result["files"] == 2
    assert result["scan"]["total_size"] == 640  # 600 plus the 40 bytes of new.jpg


def test_cleaning_the_scan_root_empties_the_index(
    index: ScanIndex, tree: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The root of a scan can be cleaned too — the scan then holds nothing."""
    scan_id = scan(index, tree)
    root = index.scan_meta(scan_id)
    assert root is not None

    monkeypatch.setattr(cleanup, "_to_trash", _remove)

    stage(index, scan_id, [root.root])
    result = commit(index, scan_id)

    assert [str(path) for path in result.moved] == [str(root.root)]
    assert index.count_entries(scan_id) == 0

    meta = index.scan_meta(scan_id)
    assert meta is not None
    assert meta.total_size == 0
    assert meta.file_count == 0
    assert meta.dir_count == 0
