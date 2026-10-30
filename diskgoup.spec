# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller build spec for the DiskGOup CLI.

Produces a single self-contained executable at ``dist/diskgoup`` (``dist/diskgoup.exe``
on Windows). The Electron app bundles this binary as a resource and spawns it as
a child process — see ``electron/scripts/build-cli.mjs``.

Build with::

    uv run pyinstaller diskgoup.spec
"""

from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files

ROOT = Path(SPECPATH)
SRC = ROOT / "src"

# Jinja2 report templates ship alongside the code.
datas = [
    (str(SRC / "diskgoup" / "templates"), "diskgoup/templates"),
    *collect_data_files("send2trash"),
]

hiddenimports = [
    "diskgoup.cli",
    "diskgoup.core.scanner",
    "diskgoup.core.store",
    "diskgoup.core.archives",
    "diskgoup.core.cleanup",
    "diskgoup.core.duplicates",
    "diskgoup.core.games",
    "diskgoup.core.applications",
    "diskgoup.core.monitor",
    "diskgoup.core.reports",
    "diskgoup.core.snapshots",
    "diskgoup.core.render",
    "diskgoup.core.treemap",
    "diskgoup.core.views",
    "diskgoup.commands.explore",
    "diskgoup.commands.views",
    "diskgoup.commands.search",
    "diskgoup.commands.archives",
    "diskgoup.commands.duplicates",
    "diskgoup.commands.games",
    "diskgoup.commands.applications",
    "diskgoup.commands.monitor",
    "diskgoup.commands.snapshots",
    "diskgoup.commands.reports",
    "diskgoup.commands.cleanup",
    "diskgoup.commands.serve",
    "typer",
    "rich",
    "watchdog.observers",
    "watchdog.observers.polling",
    "send2trash",
    "psutil",
    "platformdirs",
    "jinja2",
]

excludes = [
    "tkinter",
    "unittest",
    "pydoc_data",
    "test",
    "pytest",
    "IPython",
    "notebook",
]

a = Analysis(
    [str(SRC / "diskgoup" / "__main__.py")],
    pathex=[str(SRC)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    noarchive=False,
    optimize=1,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="diskgoup",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
