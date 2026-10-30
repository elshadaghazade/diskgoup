"""Well-known application paths, resolved per platform."""

from __future__ import annotations

import os
from pathlib import Path

from platformdirs import user_cache_dir, user_config_dir, user_data_dir


def data_dir() -> Path:
    """Directory holding application state (config, databases, snapshots)."""
    path = Path(user_data_dir("diskgoup"))
    path.mkdir(parents=True, exist_ok=True)
    return path


def cache_dir() -> Path:
    """Directory holding regenerable data (the scan index)."""
    path = Path(user_cache_dir("diskgoup"))
    path.mkdir(parents=True, exist_ok=True)
    return path


def config_dir() -> Path:
    """Directory holding user-editable configuration."""
    path = Path(user_config_dir("diskgoup"))
    path.mkdir(parents=True, exist_ok=True)
    return path


def default_index_path() -> Path:
    """Default location of the SQLite scan index."""
    return cache_dir() / "index.db"


def config_path() -> Path:
    """Location of the JSON configuration file."""
    return config_dir() / "config.json"


def env_index_path() -> Path | None:
    """Index path override via ``DISKGOUP_INDEX`` (used by tests and the GUI)."""
    override = os.environ.get("DISKGOUP_INDEX")
    return Path(override).expanduser() if override else None
