---
title: Installation
description: Install the DiskGOup CLI with uv, build a standalone binary with PyInstaller, or install the desktop app.
---

DiskGOup ships as a Python CLI, as a standalone compiled binary, and as an
Electron desktop app that bundles the binary. Pick the one that fits how you
want to use it.

:::tip
Do not want to build anything? [Downloads →](/getting-started/downloads/) has
a ready-made binary and installer for macOS, Linux and Windows, built by the
project's CI.
:::

## Requirements

| Component | Needs |
|---|---|
| CLI (from source) | Python **3.12+**, [`uv`](https://docs.astral.sh/uv/) |
| Standalone binary | nothing — the binary is self-contained |
| Desktop app | the compiled binary (the app refuses to start without it) |

The repository ships a `.python-version` file, so `uv sync` picks the right
interpreter for you.

## Install the CLI from source

```bash
git clone https://github.com/elshadaghazade/diskgoup.git
cd diskgoup
uv sync
```

`uv sync` creates `.venv/`, installs the project in editable mode and pulls in
the development toolchain (`pytest`, `ruff`, `mypy`, `pyinstaller`).

Check that it works:

```bash
uv run diskgoup --version
uv run diskgoup --help
```

The console script is registered as `diskgoup`, so `uv run diskgoup …` works
from anywhere in the project.

### Without `uv`

The project is a standard PEP 621 package, so `pip` works too:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
diskgoup --help
```

## Build a standalone binary

`uv run pyinstaller diskgoup.spec` produces a single self-contained executable:

```bash
uv run pyinstaller diskgoup.spec
```

| Platform | Output |
|---|---|
| macOS / Linux | `dist/diskgoup` |
| Windows | `dist/diskgoup.exe` |

The build bundles the Jinja2 report templates and `send2trash`'s data files,
and excludes the usual test-and-REPL baggage. `diskgoup.spec` also lists the
modules PyInstaller would otherwise miss, because they are imported lazily.

:::caution
The binary must be able to spawn itself. `cli.py` calls
`multiprocessing.freeze_support()` before anything else, which is what lets the
duplicate search run its worker processes from a frozen build.
:::

## Install the desktop app

The desktop app is a front-end for the CLI. It **needs** the compiled binary —
if it is missing, the app shows an error and quits rather than opening an empty
window.

```bash
npm --prefix ui install
npm --prefix electron install
```

Then, from the repository root:

```bash
uv run pyinstaller diskgoup.spec     # → dist/diskgoup
npm --prefix electron run dev
```

`npm --prefix electron run dev` builds the CLI copy, compiles the Electron
main process and starts the app against the Vite dev server.

### Where the app looks for the binary

In order:

1. **Packaged** — `<app>/Contents/Resources/diskgoup` (electron-builder copies
   it there via `extraResources`).
2. **Development** — `electron/resources/diskgoup` (built by
   `npm run build:cli`).
3. **Fallback** — `<repo>/dist/diskgoup` (the raw PyInstaller output).

### Release builds

```bash
npm --prefix electron run dist:mac        # DMG, arm64 + x64
npm --prefix electron run dist:win        # NSIS installer, x64
npm --prefix electron run dist:linux      # AppImage
```

See [Building and releasing](/development/building/) for the full pipeline.

## Next

[Quick start →](/getting-started/quick-start/) — your first scan.
