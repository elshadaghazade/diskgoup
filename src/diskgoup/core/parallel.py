"""Running many small jobs at the same time.

The duplicate search reads thousands of files and hashes them, and the work
of one file is mostly bookkeeping in Python — open the file, read it, feed
the hash, remember the result. That bookkeeping is what the GIL holds on to,
so **threads** only get as far as the reads and the hashing, which are the
parts that let go of it.

A pool of **processes** does not wait for the GIL at all, and a search of
many small files is exactly the case where that matters. The processes have
a price: every worker of a frozen build has to unpack the whole binary again
before it can work, so they are worth their price on a search of thousands of
files and not worth it on a search of a handful.

The jobs handed to a pool must therefore be self-contained — they take what
they need and return a value — and picklable, so that a process can carry
them over the pipe.
"""

from __future__ import annotations

import os
from collections.abc import Callable, Sequence
from concurrent.futures import Executor, Future, ProcessPoolExecutor, ThreadPoolExecutor

#: How many threads a search runs on.
THREAD_WORKERS = 4

#: How many processes a search runs on.
PROCESS_WORKERS = 8

#: The environment variable that sets the number of workers.
WORKERS_ENV = "DISKGOUP_WORKERS"

#: The environment variable that chooses the backend: ``1`` for processes,
#: ``0`` for threads, unset for the automatic choice.
BACKEND_ENV = "DISKGOUP_PROCESSES"

#: How many jobs are handed to the pool at once.
CHUNK = 256

#: A search of at least this many files is worth a pool of processes.
PROCESSES_FROM = 2000


def use_processes(candidates: int, forced: bool | None = None) -> bool:
    """True when a stage of this many files should run in processes.

    Starting the workers costs a moment — every one of a frozen build unpacks
    the whole binary again — so a stage of a handful of files is faster on
    threads. A stage of thousands of files is not: the work of one file is
    mostly bookkeeping in Python, and that is what the GIL holds on to.
    """
    if forced is not None:
        return forced
    raw = os.environ.get(BACKEND_ENV, "").strip()
    if raw in ("0", "1"):
        return raw == "1"
    return candidates >= PROCESSES_FROM


def worker_count(requested: int | None = None, *, processes: bool = False) -> int:
    """How many workers a parallel run should use.

    An explicit request wins, then the environment, then the default — and
    the default depends on the backend, because a process does not wait for
    the others the way a thread does.
    """
    if requested is not None and requested > 0:
        return requested
    raw = os.environ.get(WORKERS_ENV, "").strip()
    if raw.isdigit() and int(raw) > 0:
        return int(raw)
    return PROCESS_WORKERS if processes else THREAD_WORKERS


def _run_chunk[T, R](chunk: Sequence[T], func: Callable[[T], R]) -> list[R]:
    """Run ``func`` over one chunk of items, in order.

    The function is passed along rather than captured, so that a process can
    pickle the job.
    """
    return [func(item) for item in chunk]


class Pool:
    """Runs jobs at the same time and hands back their results in order.

    One pool serves the whole search: the workers are started once and used
    by every stage of the pipeline.

    A stage with many files runs on **processes** — the work of a file is
    mostly bookkeeping in Python, and that is what the GIL holds on to. A
    stage with few files runs on **threads**, which start at once: starting
    the processes costs a moment, and a stage of a few files does not earn
    that back.
    """

    def __init__(self, workers: int | None = None, *, processes: bool | None = None) -> None:
        self._requested = workers
        self._forced = processes
        self._threads: ThreadPoolExecutor | None = None
        self._processes: ProcessPoolExecutor | None = None

    def _threads_pool(self) -> Executor:
        if self._threads is None:
            count = worker_count(self._requested, processes=False)
            self._threads = ThreadPoolExecutor(max_workers=count)
        return self._threads

    def _processes_pool(self) -> Executor:
        if self._processes is None:
            count = worker_count(self._requested, processes=True)
            self._processes = ProcessPoolExecutor(max_workers=count)
        return self._processes

    def _executor(self, jobs: int) -> Executor:
        """The pool that suits a stage of ``jobs`` files."""
        if use_processes(jobs, self._forced):
            return self._processes_pool()
        return self._threads_pool()

    def run[T, R](self, func: Callable[[T], R], items: Sequence[T]) -> list[R]:
        """Run ``func`` over ``items``, a few at a time, and return the results.

        The results keep the order of the items. The items are handed to the
        pool in chunks, so that a search of a million files queues a few
        thousand jobs instead of a million — the bookkeeping of the pool is
        then cheaper than the work it is there to do.
        """
        if not items:
            return []
        if len(items) == 1 or worker_count(self._requested) == 1:
            return [func(item) for item in items]
        chunks = [items[start : start + CHUNK] for start in range(0, len(items), CHUNK)]
        executor = self._executor(len(items))
        futures: list[Future[list[R]]] = [
            executor.submit(_run_chunk, chunk, func) for chunk in chunks
        ]
        results: list[R] = []
        for future in futures:
            results.extend(future.result())
        return results

    def close(self) -> None:
        """Stop the workers."""
        for executor in (self._threads, self._processes):
            if executor is not None:
                executor.shutdown(wait=True)
        self._threads = None
        self._processes = None
