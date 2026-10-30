"""Pausing and stopping a running scan.

A scan of a whole volume takes a while, so the GUI has to be able to hold it
and to stop it. These tests pin down the behaviour of the handle that makes
that possible.
"""

from __future__ import annotations

import threading
import time
from pathlib import Path

import pytest

from diskgoup.commands.serve import Server
from diskgoup.core.scanner import ScanControl, Scanner, ScanOptions
from diskgoup.core.store import ScanIndex


@pytest.fixture
def tree(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """A small tree to scan."""
    root = tmp_path_factory.mktemp("pause")
    (root / "docs").mkdir()
    for i in range(20):
        (root / "docs" / f"file{i}.txt").write_bytes(b"x" * 100)
    return root


@pytest.fixture
def db_path(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Where the index lives — outside the scanned tree."""
    return tmp_path_factory.mktemp("idx") / "index.db"


def test_a_paused_scan_waits_for_the_resume(db_path: Path, tree: Path) -> None:
    control = ScanControl()
    seen: list[int] = []

    def on_progress(progress: object) -> None:
        # Pause once — otherwise the scan would stop itself again on the very
        # next entry.
        if not seen:
            seen.append(1)
            control.pause()

    def work() -> None:
        with ScanIndex(db_path) as index:
            Scanner(index, ScanOptions(root=tree)).run(on_progress, control=control)

    thread = threading.Thread(target=work, daemon=True)
    thread.start()
    try:
        deadline = time.monotonic() + 5
        while not seen and time.monotonic() < deadline:
            time.sleep(0.01)
        assert seen, "the scan never started"

        # The scan is holding at its next checkpoint.
        time.sleep(0.2)
        assert thread.is_alive(), "a paused scan should not finish on its own"
    finally:
        control.resume()

    thread.join(timeout=10)
    assert not thread.is_alive()


def test_a_resumed_scan_still_records_everything(db_path: Path, tree: Path) -> None:
    control = ScanControl()
    paused = False

    def on_progress(progress: object) -> None:
        nonlocal paused
        if not paused:
            paused = True
            control.pause()

    def work() -> None:
        with ScanIndex(db_path) as index:
            Scanner(index, ScanOptions(root=tree)).run(on_progress, control=control)

    thread = threading.Thread(target=work, daemon=True)
    thread.start()
    time.sleep(0.2)
    control.resume()
    thread.join(timeout=10)

    with ScanIndex(db_path) as index:
        scans = index.scans()
    assert len(scans) == 1
    assert scans[0].complete is True
    assert scans[0].file_count == 20


def test_a_cancelled_scan_is_marked_incomplete(db_path: Path, tree: Path) -> None:
    control = ScanControl()

    def on_progress(progress: object) -> None:
        control.cancel()

    with ScanIndex(db_path) as index:
        result = Scanner(index, ScanOptions(root=tree)).run(on_progress, control=control)

    assert result.canceled is True
    with ScanIndex(db_path) as index:
        meta = index.scan_meta(result.meta.scan_id)
    assert meta is not None
    assert meta.complete is False


def test_cancelling_wakes_a_paused_scan(db_path: Path, tree: Path) -> None:
    control = ScanControl()
    paused = False

    def on_progress(progress: object) -> None:
        nonlocal paused
        if not paused:
            paused = True
            control.pause()

    def work() -> None:
        with ScanIndex(db_path) as index:
            Scanner(index, ScanOptions(root=tree)).run(on_progress, control=control)

    thread = threading.Thread(target=work, daemon=True)
    thread.start()
    time.sleep(0.2)
    assert thread.is_alive()

    control.cancel()
    thread.join(timeout=10)
    assert not thread.is_alive(), "a cancelled scan should stop"


def test_a_running_scan_does_not_lock_out_other_writers(db_path: Path, tree: Path) -> None:
    """A scan commits every batch, so it never holds the write lock for long.

    A scan that held SQLite's write lock for its whole duration would make
    every other process — the app, the CLI, a second scan — fail with
    "database is locked".
    """
    control = ScanControl()
    seen = 0

    def on_progress(progress: object) -> None:
        # Pause after the first batch has been committed: the scan then holds
        # no lock at all, so the write below must succeed.
        nonlocal seen
        seen += 1
        if seen == 6:
            control.pause()

    # Create the index up front, so both connections find the schema in place.
    with ScanIndex(db_path):
        pass

    def work() -> None:
        with ScanIndex(db_path) as index:
            scanner = Scanner(index, ScanOptions(root=tree, batch_size=5))
            scanner.run(on_progress, control=control)

    thread = threading.Thread(target=work, daemon=True)
    thread.start()
    try:
        deadline = time.monotonic() + 10
        while not control.paused and time.monotonic() < deadline:
            time.sleep(0.01)
        assert control.paused, "the scan never paused"

        # The scan is holding at its checkpoint with nothing committed and no
        # lock held — another writer must be able to write.
        with ScanIndex(db_path) as other:
            other.begin_scan(tree)
    finally:
        control.resume()
    thread.join(timeout=10)


def test_the_server_reports_when_there_is_no_scan_to_pause() -> None:
    server = Server()

    response = server.handle({"id": 1, "method": "scan.pause", "params": {}})

    assert response is not None
    assert "error" in response
    assert "no scan is running" in str(response["error"])


def test_the_server_runs_scans_off_the_read_loop(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    server = Server()
    picked_up: list[dict[str, object]] = []
    monkeypatch.setattr(server, "_run_background", picked_up.append)

    assert server.dispatch_background({"id": 1, "method": "scan.run", "params": {}})
    assert not server.dispatch_background({"id": 2, "method": "scans.list", "params": {}})

    deadline = time.monotonic() + 5
    while not picked_up and time.monotonic() < deadline:
        time.sleep(0.01)
    assert picked_up, "the scan should have been handed to a worker"
