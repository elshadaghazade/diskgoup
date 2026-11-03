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
npm --prefix electron run dist:linux        # AppImage + tar.gz
```

The output lands in `electron/release/`.

| Platform | Format | What it is |
|---|---|---|
| macOS | `.dmg` | the installer — drag the app into Applications |
| macOS | `.zip` | portable — unzip and run `DiskGOup.app` from anywhere |
| Windows | NSIS installer `.exe` | the installer |
| Windows | portable `.exe` | portable — it unpacks itself and runs, no installation |
| Linux | `AppImage` | one file, needs the executable bit |
| Linux | `tar.gz` | portable — the unpacked folder, works without FUSE |

Both kinds are built by the same `electron-builder` run: the target list of
each platform in `electron/package.json` names them, and one `dist:*` command
produces all of them. The artifact names carry `${ext}`, because one name
pattern covers every target of a platform.

The macOS build signs the bundle with an **ad-hoc** identity (`identity: "-"`)
and the hardened runtime, with the entitlements in `electron/build/`. That
seals the app — so it is not a damaged file — but it proves nothing about who
built it, so Gatekeeper still asks on another machine. The packaging fails if
the signature does not verify, so a broken seal can never be shipped.

To sign it properly, add these repository secrets; the release workflow picks
them up on its own:

| Secret | What it is |
|---|---|
| `MACOS_CERTIFICATE` | the `Developer ID Application` certificate (`.p12`), base64-encoded |
| `MACOS_CERTIFICATE_PASSWORD` | that certificate's password |
| `APPLE_ID` | the Apple ID that owns the team |
| `APPLE_APP_SPECIFIC_PASSWORD` | an app-specific password for that Apple ID |
| `APPLE_TEAM_ID` | the 10-character team ID |

With them in place the app is signed with the Developer ID and notarized
before the `.dmg` is built, and macOS opens it without asking anything.

## Releasing

**Merging into `main` is the release.** There is no command to run and no tag
to push — the workflow does it.

| Workflow | When it runs | What it does |
|---|---|---|
| [`ci.yml`](https://github.com/elshadaghazade/diskgoup/blob/main/.github/workflows/ci.yml) | on every pull request and on `main` | the CLI's tests and types, the desktop app's types, the documentation build |
| [`release.yml`](https://github.com/elshadaghazade/diskgoup/blob/main/.github/workflows/release.yml) | on every merge into `main` | works out the version, writes it into the project, tags it and starts the two builds below |
| [`release-cli.yml`](https://github.com/elshadaghazade/diskgoup/blob/main/.github/workflows/release-cli.yml) | started by `release.yml` | the CLI binary for macOS (arm64 + x64), Linux (x64 + arm64) and Windows (x64) |
| [`release-desktop.yml`](https://github.com/elshadaghazade/diskgoup/blob/main/.github/workflows/release-desktop.yml) | started by `release.yml` | the desktop app: a `.dmg` and a portable `.zip` for macOS, an installer `.exe` and a portable `.exe` for Windows, an `.AppImage` and a portable `.tar.gz` for Linux |

The steps, in short:

1. **The version.** The first release publishes the version in
   `pyproject.toml`. After that the bump follows what was merged: a `feat:`
   commit means a minor release, a breaking change a major one, anything else a
   patch. `scripts/next-version.py` is where that rule lives.
2. **The tag is the version** — `scripts/set-version.py` writes it into the
   Python package and both `package.json` files, so the artifact and the tag
   always agree. The version is committed to `main` and tagged `v0.2.0`.
3. **The builds.** The CLI is built with `uv run pyinstaller diskgoup.spec` and
   smoke-tested with `diskgoup --version`; the desktop app is packaged with
   `electron-builder`, with the CLI binary bundled into it.
4. **The files** are uploaded to the release under fixed names — the
   documentation links to them with `releases/latest/download/<name>`, so
   those links never break.
5. **The documentation** follows in the same commit:
   `site/scripts/update-downloads.py` updates the version on the
   [downloads page](/getting-started/downloads/), so a release and the
   documentation never drift apart. Nothing is left to merge by hand.

Two ways to cut a release by hand, if you want one:

```bash
# a version of your own choosing — Actions → Cut a release → Run workflow
gh workflow run release.yml -f version=0.3.0

# or a tag, which builds exactly the same thing
git tag -a v0.3.0 -m "DiskGOup 0.3.0"
git push origin v0.3.0
```

:::caution
The Windows installer is **unsigned**, so SmartScreen warns on a machine that
has never seen it. The macOS app is signed, but ad-hoc rather than with a
Developer ID, so Gatekeeper asks the user to approve it once.
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
│   └── scripts/           build-cli.mjs, build-assets.mjs, verify-signature.mjs
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
