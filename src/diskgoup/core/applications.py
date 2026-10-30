"""Application inventory and uninstall.

DiskBOX lists the applications on the machine together with the space they
occupy, and uninstalls them by running the **registered uninstaller** — after
which the inventory is checked again.

The discovery is platform-native:

* **macOS** — ``.app`` bundles in ``/Applications`` and ``~/Applications``.
* **Windows** — the ``Uninstall`` registry keys.
* **Linux** — the ``.desktop`` entries in the XDG application directories.

Uninstalling is deliberately conservative: the platform's own uninstaller is
run where one exists, and the inventory is re-measured afterwards. Shared data
is never cleaned up — that is the uninstaller's business, not ours.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(slots=True)
class Application:
    """One installed application."""

    name: str
    path: Path | None
    size: int = 0
    version: str | None = None
    publisher: str | None = None
    uninstall_command: str | None = None
    source: str = "unknown"

    @property
    def id(self) -> str:
        """A stable identifier used to address the application."""
        return str(self.path) if self.path else self.name

    def to_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "name": self.name,
            "path": str(self.path) if self.path else None,
            "size": self.size,
            "version": self.version,
            "publisher": self.publisher,
            "uninstall_command": self.uninstall_command,
            "source": self.source,
        }


@dataclass(slots=True)
class Inventory:
    """The applications found on this machine."""

    applications: list[Application] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def total_size(self) -> int:
        return sum(app.size for app in self.applications)

    def to_dict(self) -> dict[str, object]:
        return {
            "applications": [app.to_dict() for app in self.applications],
            "total_size": self.total_size,
            "errors": self.errors,
        }


def directory_size(path: Path) -> int:
    """Total size of a directory tree, following no symlinks."""
    total = 0
    for root, _dirnames, filenames in os.walk(path, onerror=lambda _e: None):
        root_path = Path(root)
        for filename in filenames:
            file_path = root_path / filename
            try:
                info = file_path.lstat()
            except OSError:
                continue
            blocks = getattr(info, "st_blocks", 0)
            total += blocks * 512 if blocks else info.st_size
    return total


# ------------------------------------------------------------------- macOS


def _macos_applications() -> list[Application]:
    apps: list[Application] = []
    for base in (Path("/Applications"), Path.home() / "Applications"):
        if not base.is_dir():
            continue
        for bundle in sorted(base.glob("*.app")):
            if not bundle.is_dir():
                continue
            version = _macos_version(bundle)
            apps.append(
                Application(
                    name=bundle.stem,
                    path=bundle,
                    size=directory_size(bundle),
                    version=version,
                    source="macos",
                    uninstall_command=f'rm -rf "{bundle}"',
                )
            )
    return apps


def _macos_version(bundle: Path) -> str | None:
    """Read the version from an app bundle's ``Info.plist``."""
    plist = bundle / "Contents" / "Info.plist"
    if not plist.is_file():
        return None
    try:
        import plistlib

        with plist.open("rb") as handle:
            data = plistlib.load(handle)
        version = data.get("CFBundleShortVersionString") or data.get("CFBundleVersion")
        return str(version) if version else None
    except Exception:
        return None


# ----------------------------------------------------------------- Windows


def _windows_applications() -> list[Application]:
    """Read the Windows uninstall registry."""
    from diskgoup.core import _windows

    apps: list[Application] = []
    for entry in _windows.uninstall_entries():
        location = entry.get("install_location")
        path = Path(location) if location else None
        apps.append(
            Application(
                name=str(entry["name"]),
                path=path,
                size=directory_size(path) if path and path.is_dir() else 0,
                version=entry.get("version"),
                publisher=entry.get("publisher"),
                uninstall_command=entry.get("uninstall_string"),
                source="windows",
            )
        )
    return apps


# ------------------------------------------------------------------- Linux


def _linux_applications() -> list[Application]:
    apps: list[Application] = []
    seen: set[str] = set()

    directories = [
        Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share")),
        Path("/usr/share"),
        Path("/usr/local/share"),
        Path("/var/lib/flatpak/exports/share"),
    ]

    for base in directories:
        desktop_dir = base / "applications"
        if not desktop_dir.is_dir():
            continue
        for entry in sorted(desktop_dir.glob("*.desktop")):
            try:
                data = _parse_desktop(entry)
            except OSError:
                continue
            name = data.get("Name")
            if not name or name in seen:
                continue
            seen.add(name)
            exec_line = data.get("Exec", "")
            apps.append(
                Application(
                    name=name,
                    path=entry,
                    size=entry.stat().st_size,
                    version=data.get("Version"),
                    publisher=data.get("Comment") or None,
                    uninstall_command=exec_line or None,
                    source="linux",
                )
            )
    return apps


def _parse_desktop(entry: Path) -> dict[str, str]:
    """Parse a ``.desktop`` entry into a flat key/value mapping."""
    values: dict[str, str] = {}
    in_entry = False
    for line in entry.read_text(encoding="utf-8", errors="replace").splitlines():
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            in_entry = stripped == "[Desktop Entry]"
            continue
        if not in_entry or "=" not in stripped or stripped.startswith("#"):
            continue
        key, _, value = stripped.partition("=")
        values[key.strip()] = value.strip()
    return values


# ------------------------------------------------------------------ public


def discover() -> Inventory:
    """Build the application inventory for this machine."""
    inventory = Inventory()
    try:
        if sys.platform.startswith("win"):
            inventory.applications = _windows_applications()
        elif sys.platform == "darwin":
            inventory.applications = _macos_applications()
        else:
            inventory.applications = _linux_applications()
    except Exception as exc:
        inventory.errors.append(str(exc))

    inventory.applications.sort(key=lambda app: -app.size)
    return inventory


def uninstall(application: Application, *, dry_run: bool = False) -> tuple[bool, str]:
    """Uninstall an application using the platform's own mechanism.

    Returns ``(ok, message)``. The inventory is expected to be re-read
    afterwards — DiskBOX does the same after a real uninstall.
    """
    if application.source == "macos" and application.path is not None:
        if dry_run:
            return True, f"Would move {application.path} to the Trash."
        try:
            from send2trash import send2trash

            send2trash(str(application.path))
        except Exception as exc:
            return False, str(exc)
        return True, f"{application.name} moved to the Trash."

    if application.source == "windows" and application.uninstall_command:
        if dry_run:
            return True, f"Would run: {application.uninstall_command}"
        command = application.uninstall_command
        try:
            subprocess.run(
                command,
                shell=True,
                check=False,
                capture_output=True,
                timeout=300,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            return False, str(exc)
        return True, f"Uninstaller for {application.name} finished."

    if application.source == "linux" and application.uninstall_command:
        if dry_run:
            return True, f"Would run: {application.uninstall_command}"
        try:
            subprocess.run(
                application.uninstall_command,
                shell=True,
                check=False,
                capture_output=True,
                timeout=300,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            return False, str(exc)
        return True, f"Uninstaller for {application.name} finished."

    if application.path is not None and application.path.exists():
        if dry_run:
            return True, f"Would remove {application.path}."
        try:
            if application.path.is_dir():
                shutil.rmtree(application.path)
            else:
                application.path.unlink()
        except OSError as exc:
            return False, str(exc)
        return True, f"{application.name} removed."

    return False, "No uninstall mechanism is known for this application."
