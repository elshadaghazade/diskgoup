"""Windows-only helpers, isolated so the type checker can skip them.

``winreg`` exists only on Windows, so this module cannot be type-checked on a
POSIX development machine. It is imported lazily by
:mod:`diskgoup.core.applications`.
"""

# mypy: ignore-errors

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

if sys.platform != "win32":  # pragma: no cover - Windows only
    raise ImportError("Windows-only module")


def _value(key: Any, name: str) -> Any:
    import winreg

    try:
        return winreg.QueryValueEx(key, name)[0]
    except OSError:
        return None


def uninstall_entries() -> list[dict[str, Any]]:
    """Every application registered in the Windows uninstall registry."""
    import winreg

    roots: list[tuple[Any, str]] = [
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
        (
            winreg.HKEY_LOCAL_MACHINE,
            r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall",
        ),
        (
            winreg.HKEY_CURRENT_USER,
            r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall",
        ),
    ]

    entries: list[dict[str, Any]] = []
    seen: set[str] = set()

    for hive, key_path in roots:
        try:
            key = winreg.OpenKey(hive, key_path)
        except OSError:
            continue
        with key:
            count = winreg.QueryInfoKey(key)[0]
            for index in range(count):
                try:
                    subkey_name = winreg.EnumKey(key, index)
                    with winreg.OpenKey(key, subkey_name) as subkey:
                        values = {
                            field: _value(subkey, field)
                            for field in (
                                "DisplayName",
                                "InstallLocation",
                                "DisplayVersion",
                                "Publisher",
                                "UninstallString",
                            )
                        }
                except OSError:
                    continue

                name = str(values.get("DisplayName") or "").strip()
                if not name or name in seen:
                    continue
                seen.add(name)

                location = values.get("InstallLocation")
                entries.append(
                    {
                        "name": name,
                        "install_location": str(location) if location else None,
                        "version": str(values.get("DisplayVersion") or "") or None,
                        "publisher": str(values.get("Publisher") or "") or None,
                        "uninstall_string": str(values.get("UninstallString") or "") or None,
                    }
                )

    return entries


def program_files() -> list[Path]:
    """The ``Program Files`` roots that may hold installed applications."""
    import os

    roots: list[Path] = []
    for variable in ("ProgramFiles(x86)", "ProgramFiles", "ProgramW6432"):
        value = os.environ.get(variable)
        if value:
            roots.append(Path(value))
    return roots
