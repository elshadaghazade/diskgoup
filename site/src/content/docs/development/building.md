---
title: Building and releasing
description: How to set up the development environment, run the tests, and build the binary.
---

## Requirements

| Tool | Version |
|---|---|
| Python | 3.12 or newer |
| [uv](https://docs.astral.sh/uv/) | latest |
| Node.js | 20 or newer — only for the desktop app |
| npm | 10 or newer — only for the desktop app |

## Setting up

```bash
git clone https://github.com/elshadaghazade/diskgoup
cd diskgoup
uv sync
```

`uv sync` creates the virtual environment and installs the runtime
dependencies plus the development group:

| Group | Packages |
|---|---|
| Runtime | `typer` `rich` `psutil` `platformdirs` `send2trash` `watchdog` `jinja2` |
| Development | `pytest` `pytest-cov` `ruff` `mypy` `pyinstaller` and the type stubs |

Then check it works:

```bash
uv run diskgoup --version
```

### Without uv

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

`pip install -e .` installs the package in editable mode and puts the
`diskgoup` command on your path.

## Running the tests

```bash
uv run pytest
```

The suite is configured in `pyproject.toml`:

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "-q --strict-markers"
markers = ["slow: long-running tests"]
```

`--strict-markers` means an unknown marker is an error rather than a
warning — a typo in `@pytest.mark.slow` fails instead of silently running
the test unmarked.

With coverage:

```bash
uv run pytest --cov=diskgoup --cov-report=term-missing
```

The slow tests are marked and can be skipped:

```bash
uv run pytest -m "not slow"
```

## Linting and type checking

```bash
uv run ruff check .
uv run ruff format .
uv run mypy
```

The configuration is strict:

| Tool | Setting |
|---|---|
| `ruff` | line length 100, target `py312`, rules `E F W I N UP B C4 SIM RUF ANN` |
| `mypy` | `strict = true` over the `diskgoup` package |

`ruff`'s bugbear integration knows about Typer:

```toml
[tool.ruff.lint.flake8-bugbear]
extend-immutable-calls = ["typer.Argument", "typer.Option"]
```

Without it, B008 would flag every `typer.Option(...)` default as a
"function call in a default argument" — which is exactly what Typer's
decorators are.

## Building the binary

```bash
uv run pyinstaller diskgoup.spec
```

The result is a single self-contained executable:

| Platform | Path |
|---|---|
| macOS, Linux | `dist/diskgoup` |
| Windows | `dist/diskgoup.exe` |

The spec bundles the Jinja2 templates and the `send2trash` data files, and
lists the modules PyInstaller cannot see by itself as `hiddenimports`:

```python
datas = [
    (str(SRC / "diskgoup" / "templates"), "diskgoup/templates"),
    *collect_data_files("send2trash"),
]
```

Excluded, to keep the binary small:

```python
excludes = ["tkinter", "unittest", "pydoc_data", "test", "pytest", "IPython", "notebook"]
```

:::caution
The frozen binary has one requirement that the source does not:
`multiprocessing.freeze_support()` has to be called **before** the Typer app
starts, or the worker processes of a frozen build re-run the whole program
instead of doing their job. `cli.py` already does this — but if you ever
change the entry point, keep the call.
:::

## Building the desktop app

The Electron app is built separately from the Python one.

```bash
# 1. the UI
npm --prefix ui install
npm --prefix ui run build

# 2. the Electron shell
npm --prefix electron install
npm --prefix electron run build
```

`electron/scripts/build-cli.mjs` builds the Python binary and puts it in
`electron/resources/`, where the development resolver looks for it.

### Packaging

```bash
npm --prefix electron run dist:mac          # arm64 + x64
npm --prefix electron run dist:mac:arm64
npm --prefix electron run dist:mac:x64
npm --prefix electron run dist:win          # x64
npm --prefix electron run dist:linux        # AppImage
```

The output lands in `electron/release/`.

| Platform | Format |
|---|---|
| macOS | `.dmg` |
| Windows | NSIS installer |
| Linux | `AppImage` |

The macOS build is configured with `identity: "-"`, `hardenedRuntime: false`
and `gatekeeperAssess: false` — it is not signed or notarized, so Gatekeeper
will complain on another machine. Sign it before shipping to anyone else.

## Releasing

A release is a **git tag**. Pushing `v0.2.0` starts two workflows that build
everything and attach it to the
[GitHub release](https://github.com/elshadaghazade/diskgoup/releases) of that
tag:

| Workflow | What it builds |
|---|---|
| [`release-cli.yml`](https://github.com/elshadaghazade/diskgoup/blob/main/.github/workflows/release-cli.yml) | The CLI binary for macOS (arm64 + x64), Linux (x64 + arm64) and Windows (x64) |
| [`release-desktop.yml`](https://github.com/elshadaghazade/diskgoup/blob/main/.github/workflows/release-desktop.yml) | The desktop app: a `.dmg` for macOS, an `.exe` for Windows, an `.AppImage` for Linux |

The steps, in short:

1. The tag gives the version — `scripts/set-version.py` writes it into the
   Python package and both `package.json` files, so the artifact and the tag
   always agree.
2. The CLI is built with `uv run pyinstaller diskgoup.spec` and smoke-tested
   with `diskgoup --version`.
3. The desktop app is packaged with `electron-builder`, with the CLI binary
   bundled into it.
4. The files are uploaded to the release under fixed names — the
   documentation links to them with `releases/latest/download/<name>`, so
   those links never break.
5. `site/scripts/update-downloads.py` updates the version on the
   [downloads page](/getting-started/downloads/) and opens a pull request
   with the change.

So a release is:

```bash
# 1. the version, everywhere
python3 scripts/set-version.py 0.2.0

# 2. the commit
git commit -am "release: 0.2.0"

# 3. the tag — this is what triggers the build
git tag -a v0.2.0 -m "DiskGOup 0.2.0"
git push origin main --follow-tags
```

Then wait for the two workflows, and merge the pull request that updates the
downloads page.

:::caution
The macOS and Windows installers are **unsigned**. Gatekeeper and SmartScreen
will warn on a machine that has never seen them.
:::

## The repository layout

```
diskgoup/
├── src/diskgoup/          the Python package
│   ├── cli.py             the Typer app
│   ├── commands/          one module per CLI area
│   ├── core/              the engine
│   ├── templates/         the Jinja2 report templates
│   └── util/              formatting helpers
├── electron/              the Electron main process
│   ├── src/               main.ts, backend.ts, preload.ts
│   └── scripts/           build-cli.mjs, build-assets.mjs
├── ui/                    the React renderer
│   ├── src/components/    one per tab
│   └── src/lib/           the API client and the shared types
├── tests/                 the Python test suite
├── diskgoup.spec          the PyInstaller spec
├── pyproject.toml         the Python project
└── docs/                  the project's own notes
```

The Python package lives under `src/`, so the import path is
`diskgoup.*` — the same as it is on PyPI.

## Before you commit

```bash
uv run ruff check .
uv run mypy
uv run pytest
npm --prefix ui run typecheck
```

The UI has its own type check, separate from the build:

```bash
npm --prefix ui run typecheck
```

## See also

- [Contributing](/development/contributing/) — the workflow.
- [The desktop app](/development/desktop/) — how the two halves fit together.
