from __future__ import annotations

import os
from concurrent.futures.process import BrokenProcessPool
from pathlib import Path

import pytest

from diskgoup.core import parallel
from diskgoup.core.duplicates import find_duplicates
from diskgoup.core.parallel import BACKEND_ENV, WORKERS_ENV, Pool, use_processes, worker_count


def _write(path: Path, data: bytes) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return path


def _pid_of(_index: int) -> int:
    """The pid of the worker that ran the job.

    It lives at the top level because a process has to be able to pickle the
    job it is given — the same rule the real workers follow.
    """
    return os.getpid()


def test_the_pool_keeps_the_order_of_the_items() -> None:
    pool = Pool(4)
    try:
        assert pool.run(lambda item: item * 2, list(range(50))) == [item * 2 for item in range(50)]
    finally:
        pool.close()


def test_the_pool_runs_the_work_in_several_workers() -> None:
    """A stage of many files runs on processes, so the work really leaves
    the process that started it — the workers report their own pid."""
    pool = Pool(4)
    try:
        results = pool.run(_pid_of, list(range(parallel.PROCESSES_FROM + 48)))
    finally:
        pool.close()

    pids = set(results)
    assert len(pids) > 1, f"the work stayed in one process: {pids}"


def test_one_worker_does_the_work_in_the_calling_process() -> None:
    pool = Pool(1)
    try:
        results = pool.run(_pid_of, list(range(4)))
    finally:
        pool.close()

    assert results == [os.getpid()] * 4


def test_the_backend_is_chosen_by_the_size_of_the_stage(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(BACKEND_ENV, raising=False)
    assert use_processes(10) is False
    assert use_processes(parallel.PROCESSES_FROM) is True

    monkeypatch.setenv(BACKEND_ENV, "1")
    assert use_processes(10) is True
    monkeypatch.setenv(BACKEND_ENV, "0")
    assert use_processes(10_000) is False


def test_the_worker_count_follows_the_request_and_the_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv(WORKERS_ENV, raising=False)
    assert worker_count() == parallel.THREAD_WORKERS
    assert worker_count(processes=True) == parallel.PROCESS_WORKERS
    assert worker_count(3) == 3

    monkeypatch.setenv(WORKERS_ENV, "5")
    assert worker_count() == 5
    assert worker_count(2) == 2


def test_the_search_falls_back_to_threads_when_the_workers_do_not_start(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A machine that does not allow a process of its own is not a reason to
    fail the search."""

    class RefusesToStart:
        def __init__(self, *args: object, **kwargs: object) -> None:
            pass

        def submit(self, *args: object, **kwargs: object) -> None:
            raise BrokenProcessPool("no processes here")

        def shutdown(self, wait: bool = True) -> None:
            pass

    payload = b"the quick brown fox" * 100
    first = _write(tmp_path / "a" / "one.bin", payload)
    second = _write(tmp_path / "b" / "two.bin", payload)

    monkeypatch.setattr(parallel, "ProcessPoolExecutor", RefusesToStart)
    monkeypatch.setenv(BACKEND_ENV, "1")

    report = find_duplicates([first, second])

    assert len(report.groups) == 1
    assert set(report.groups[0].paths) == {first, second}
