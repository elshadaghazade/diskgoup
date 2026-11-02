"""Shared test setup.

Every test runs against a throw-away configuration file. The real one lives
in the user's config directory, and a test that removes the configuration —
the factory reset does — must never touch it.
"""

from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def temporary_config(
    tmp_path_factory: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch
) -> Path:
    """Point the configuration file at a temporary one for every test."""
    path = tmp_path_factory.mktemp("config") / "config.json"
    monkeypatch.setenv("DISKGOUP_CONFIG", str(path))
    return path
