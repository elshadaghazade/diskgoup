"""Factory reset — starting the app over from scratch.

The index is a cache of the disk: everything in it can be rebuilt by scanning
again. The reset therefore throws it away and writes an empty one in its
place, which is the way out of a corrupted database or one that is stuck.

The important part is the order: the old file is removed *before* anything
opens it, because a corrupted file cannot be opened at all.
"""

from __future__ import annotations

import threading
import time
from pathlib import Path

import pytest

from diskgoup.commands.serve import Server
from diskgoup.core.reset import ResetError, reset, reset_app
from diskgoup.core.scanner import Scanner, ScanOptions
from diskgoup.core.store import ScanIndex


@pytest.fixture
def tree(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """A small tree to scan."""
    root = tmp_path_factory.mktemp("reset")
    (root / "Documents").mkdir()
    (root / "Documents" / "notes.txt").write_bytes(b"x" * 100)
    (root / "movie.mp4").write_bytes(b"x" * 100)
    return root


def scan(index: ScanIndex, root: Path) -> int:
    return Scanner(index, ScanOptions(root=root)).run().meta.scan_id


def test_the_reset_empties_the_index(tmp_path: Path, tree: Path) -> None:
    db = tmp_path / "index.db"
    with ScanIndex(db) as index:
        scan_id = scan(index, tree)
        assert index.count_entries(scan_id) == 4

    result = reset(db)

    assert result.index_path == db
    with ScanIndex(db) as index:
        assert index.scans() == []
        assert index.count_entries(scan_id) == 0


def test_the_reset_leaves_a_usable_index(tmp_path: Path, tree: Path) -> None:
    """The new index carries the current schema — the app can use it at once."""
    db = tmp_path / "index.db"
    with ScanIndex(db) as index:
        scan(index, tree)

    reset(db)

    with ScanIndex(db) as index:
        scan_id = scan(index, tree)
        assert index.count_entries(scan_id) == 4


def test_the_reset_removes_the_sqlite_side_files(tmp_path: Path) -> None:
    """The write-ahead log belongs to the old database — it goes with it.

    A session that ended badly leaves the files behind; SQLite removes them
    when the last connection closes cleanly, so they only survive a crash.
    """
    db = tmp_path / "index.db"
    with ScanIndex(db) as index:
        index.begin_scan(tmp_path)

    sidecars = [Path(f"{db}{suffix}") for suffix in ("-wal", "-shm", "-journal")]
    for sidecar in sidecars:
        sidecar.write_bytes(b"left over")

    result = reset(db)

    assert not any(sidecar.exists() for sidecar in sidecars)
    assert "index.db" in result.removed


def test_the_reset_repairs_a_corrupted_index(tmp_path: Path) -> None:
    """The point of the reset: a file that cannot be opened is replaced."""
    db = tmp_path / "index.db"
    db.write_bytes(b"this is not a database at all")

    result = reset(db)

    assert result.index_path == db
    with ScanIndex(db) as index:
        assert index.scans() == []


def test_the_reset_can_be_repeated(tmp_path: Path) -> None:
    """Running it twice is harmless — the second one replaces the first."""
    db = tmp_path / "index.db"
    reset(db)
    reset(db)

    with ScanIndex(db) as index:
        assert index.scans() == []


def test_the_reset_removes_the_configuration(tmp_path: Path) -> None:
    db = tmp_path / "index.db"
    config = tmp_path / "config.json"
    config.write_text("{}")

    result = reset(db, config=config)

    assert result.config_removed is True
    assert not config.exists()


def test_the_reset_leaves_the_configuration_alone_when_asked(tmp_path: Path) -> None:
    db = tmp_path / "index.db"
    config = tmp_path / "config.json"
    config.write_text("{}")

    result = reset(db)

    assert result.config_removed is False
    assert config.exists()


def test_the_reset_reports_a_file_it_cannot_remove(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db = tmp_path / "index.db"
    db.write_bytes(b"data")

    def refuse(self: Path, missing_ok: bool = False) -> None:
        raise PermissionError(13, "Permission denied")

    monkeypatch.setattr(Path, "unlink", refuse)
    with pytest.raises(ResetError, match="in use by another process"):
        reset(db)


def test_the_reset_uses_the_index_the_app_uses(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db = tmp_path / "index.db"
    monkeypatch.setenv("DISKGOUP_INDEX", str(db))
    monkeypatch.setenv("DISKGOUP_CONFIG", str(tmp_path / "config.json"))

    result = reset_app()

    assert result.index_path == db
    assert db.exists()


def test_the_rpc_resets_the_app(
    tmp_path: Path, tree: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db = tmp_path / "index.db"
    monkeypatch.setenv("DISKGOUP_INDEX", str(db))
    with ScanIndex(db) as index:
        scan(index, tree)

    response = Server().handle({"id": 1, "method": "app.reset", "params": {}})

    assert response is not None
    assert "error" not in response
    assert response["result"]["reset"] is True
    assert response["result"]["index_path"] == str(db)

    with ScanIndex(db) as index:
        assert index.scans() == []


def test_the_rpc_stops_a_running_scan_first(
    tmp_path: Path, tree: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A scan holds the index open — the reset has to let it go first."""
    db = tmp_path / "index.db"
    monkeypatch.setenv("DISKGOUP_INDEX", str(db))
    server = Server()

    thread = threading.Thread(
        target=server.handle,
        args=({"id": 1, "method": "scan.run", "params": {"path": str(tree)}},),
        daemon=True,
    )
    thread.start()
    deadline = time.monotonic() + 5
    while not server._scan_is_running() and time.monotonic() < deadline:
        time.sleep(0.01)
    assert server._scan_is_running(), "the scan never started"

    response = server.handle({"id": 2, "method": "app.reset", "params": {}})

    thread.join(timeout=10)
    assert not thread.is_alive(), "the scan should have been stopped"
    assert response is not None
    assert "error" not in response
    assert response["result"]["reset"] is True

    with ScanIndex(db) as index:
        assert index.scans() == []
