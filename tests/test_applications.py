"""The application inventory — and what may be removed from it.

The applications of the operating system are off limits. On macOS some of
them are linked into ``/Applications`` — Safari is — and a user who cannot
tell them apart would lose the system by accident.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from diskgoup.core import applications
from diskgoup.core.applications import (
    SYSTEM_APP,
    SYSTEM_PACKAGE,
    Application,
    Inventory,
    system_reason,
    uninstall,
)


def test_an_installed_app_is_not_a_system_app() -> None:
    app = Application(name="Firefox", path=Path("/Applications/Firefox.app"), source="macos")

    assert system_reason(app) is None


def test_a_link_into_the_system_is_protected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The system applications are linked into ``/Applications``.

    The link is followed before the place is judged — otherwise Safari looks
    like an ordinary application and would be removed with it.
    """
    system = tmp_path / "system" / "Applications"
    system.mkdir(parents=True)
    (system / "Safari.app").mkdir()
    folder = tmp_path / "Applications"
    folder.mkdir()
    (folder / "Safari.app").symlink_to(system / "Safari.app")

    monkeypatch.setitem(
        applications._SYSTEM_APP_ROOTS, "macos", (str((tmp_path / "system").resolve()),)
    )

    app = Application(name="Safari", path=folder / "Safari.app", source="macos")

    assert system_reason(app) == SYSTEM_APP


def test_a_package_of_the_system_is_protected() -> None:
    app = Application(
        name="GIMP",
        path=Path("/usr/share/applications/gimp.desktop"),
        source="linux",
    )

    assert system_reason(app) == SYSTEM_PACKAGE


def test_a_desktop_entry_of_the_user_can_be_removed() -> None:
    app = Application(
        name="My app",
        path=Path("/home/me/.local/share/applications/my.desktop"),
        source="linux",
    )

    assert system_reason(app) is None


def test_an_app_inside_windows_is_protected() -> None:
    app = Application(
        name="Windows Update",
        path=Path(r"C:\Windows\SystemApps\Something"),
        source="windows",
    )

    assert system_reason(app) == SYSTEM_APP


def test_a_system_application_is_not_removed(tmp_path: Path) -> None:
    bundle = tmp_path / "Safari.app"
    bundle.mkdir()
    app = Application(
        name="Safari",
        path=bundle,
        source="macos",
        protected=True,
        reason=SYSTEM_APP,
    )

    ok, message = uninstall(app)

    assert ok is False
    assert message == SYSTEM_APP
    assert bundle.exists(), "a system application was removed"


def test_removing_an_application_removes_its_folder(tmp_path: Path) -> None:
    bundle = tmp_path / "Some.app"
    (bundle / "Contents").mkdir(parents=True)

    ok, message = uninstall(Application(name="Some", path=bundle, source="other"))

    assert ok is True
    assert not bundle.exists()
    assert "Some" in message


def test_removing_an_app_for_good_deletes_its_bundle(tmp_path: Path) -> None:
    """The permanent way deletes the bundle instead of moving it to the Trash."""
    bundle = tmp_path / "Some.app"
    (bundle / "Contents").mkdir(parents=True)

    ok, _message = uninstall(Application(name="Some", path=bundle, source="macos"), permanent=True)

    assert ok is True
    assert not bundle.exists()


def test_the_gui_cannot_remove_a_system_application() -> None:
    """The request of the GUI is answered from the inventory it listed."""
    from diskgoup.commands.serve import Server

    server = Server()
    server._apps = Inventory(
        applications=[
            Application(
                name="Safari",
                path=Path("/System/Applications/Safari.app"),
                source="macos",
                protected=True,
                reason=SYSTEM_APP,
            )
        ]
    )

    response = server.handle(
        {
            "id": 1,
            "method": "apps.uninstall",
            "params": {"id": "/System/Applications/Safari.app"},
        }
    )

    assert response is not None
    result = response["result"]
    assert result["ok"] is False
    assert result["message"] == SYSTEM_APP
