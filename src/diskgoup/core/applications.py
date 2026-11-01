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

The applications of the operating system itself are never removed. They live
in the folders the system owns — on macOS some of them are linked into
``/Applications`` — and they are reported with the reason, so the user sees
why they are off limits instead of a silent no-op.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

#: Why an application may not be removed.
SYSTEM_APP = "This application belongs to the operating system and cannot be removed."
SYSTEM_PACKAGE = "This application was installed by the system package manager — remove it there."

#: The folders that hold the applications of the operating system itself.
_SYSTEM_APP_ROOTS: dict[str, tuple[str, ...]] = {
    "macos": ("/system",),
    "windows": ("c:/windows",),
    "linux": (
        "/usr/share/applications",
        "/usr/local/share/applications",
        "/var/lib/flatpak",
    ),
}


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
    #: The application belongs to the operating system and cannot be removed.
    protected: bool = False
    #: Why it cannot be removed.
    reason: str | None = None

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
            "protected": self.protected,
            "reason": self.reason,
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
                    uninstall_command=f'Move "{bundle}" to the Trash',
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


def _normalized(path: Path | str) -> str:
    """The comparison form of a path: slashes, no trailing slash, lower case."""
    normalized = str(path).replace("\\", "/").rstrip("/").lower()
    if not normalized.startswith("/"):
        normalized = "/" + normalized
    return normalized


def _under(path: Path | str, root: str) -> bool:
    """True when ``path`` is ``root`` or lies inside it."""
    normalized = _normalized(path)
    base = _normalized(root)
    return normalized == base or normalized.startswith(base + "/")


def _under_any(path: Path | str, roots: tuple[str, ...]) -> bool:
    """True when ``path`` lies inside one of ``roots``."""
    return any(_under(path, root) for root in roots)


def _resolved(path: Path) -> str:
    """The path a bundle really lives at, following links."""
    try:
        return str(path.resolve())
    except OSError:
        return str(path)


def _platform_key(platform: str | None = None) -> str:
    """The key of a platform in :data:`_SYSTEM_APP_ROOTS`."""
    key = platform or sys.platform
    if key.startswith("win"):
        return "windows"
    if key == "darwin":
        return "macos"
    return "linux"


def system_reason(application: Application, *, platform: str | None = None) -> str | None:
    """Why the application belongs to the system — ``None`` when it does not.

    The applications of the operating system live in the folders the system
    owns. On macOS a link into the sealed system volume is followed first:
    ``/Applications/Safari.app`` is a link into ``/System``, and removing the
    link would take the system application with it.
    """
    path = application.path
    if path is None:
        return None
    key = application.source if application.source in _SYSTEM_APP_ROOTS else _platform_key(platform)
    roots = _SYSTEM_APP_ROOTS[key]
    if key == "linux":
        return SYSTEM_PACKAGE if _under_any(path, roots) else None
    if key == "macos":
        return SYSTEM_APP if _under_any(_resolved(path), roots) else None
    return SYSTEM_APP if _under_any(path, roots) else None


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

    for application in inventory.applications:
        reason = system_reason(application)
        application.protected = reason is not None
        application.reason = reason

    inventory.applications.sort(key=lambda app: -app.size)
    return inventory


def uninstall(
    application: Application,
    *,
    dry_run: bool = False,
    permanent: bool = False,
) -> tuple[bool, str]:
    """Uninstall an application using the platform's own mechanism.

    Returns ``(ok, message)``. The inventory is expected to be re-read
    afterwards — DiskBOX does the same after a real uninstall. An application
    of the operating system is refused: it is not the user's to remove.
    """
    if application.protected:
        return False, application.reason or SYSTEM_APP

    if application.source == "macos" and application.path is not None:
        if dry_run:
            return True, f"Would move {application.path} to the Trash."
        if permanent:
            try:
                _remove(application.path)
            except OSError as exc:
                return False, str(exc)
            return True, f"{application.name} deleted for good."
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

    if application.source == "linux" and application.path is not None:
        # A desktop entry is not the program — the ``Exec`` line of one is
        # the command that *starts* it. Removing the entry of an application
        # the user installed is what "uninstalling" it means here.
        if dry_run:
            return True, f"Would remove {application.path}."
        try:
            application.path.unlink()
        except OSError as exc:
            return False, str(exc)
        return True, f"{application.name} was removed from the application menu."

    if application.path is not None and application.path.exists():
        if dry_run:
            return True, f"Would remove {application.path}."
        try:
            _remove(application.path)
        except OSError as exc:
            return False, str(exc)
        return True, f"{application.name} removed."

    return False, "No uninstall mechanism is known for this application."


def _remove(path: Path) -> None:
    """Delete a file, a folder or a link."""
    if path.is_symlink() or not path.is_dir():
        path.unlink()
    else:
        shutil.rmtree(path)
