"""The RPC loop must not stall behind a slow request.

A scan of a whole volume records millions of entries. Reading the kind
breakdown out of one, building its treemap or deleting it takes seconds — and
the requests are served one after another, so a slow one would hold up every
other one behind it. The folder browser would wait for the sidebar's numbers
before it could show a folder.
"""

from __future__ import annotations

from diskgoup.commands.serve import BACKGROUND_METHODS


def test_the_slow_methods_run_off_the_read_loop() -> None:
    """A scan, the big reads and the delete are served by a worker."""
    assert {
        "scan.run",
        "explore.types",
        "explore.age",
        "view.layout",
        "scans.remove",
    } <= BACKGROUND_METHODS


def test_the_quick_and_the_ordered_methods_stay_inline() -> None:
    """Browsing a folder answers at once, and the cleanup keeps its order."""
    assert "explore.children" not in BACKGROUND_METHODS
    assert "cleanup.stage" not in BACKGROUND_METHODS
    assert "cleanup.validate" not in BACKGROUND_METHODS
    assert "cleanup.commit" not in BACKGROUND_METHODS
