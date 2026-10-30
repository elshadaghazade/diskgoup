# DiskGOup

**Cross-platform disk space analyzer and duplicate file finder.**

DiskGOup shows you exactly where your disk space went — by folder, by file type,
by age, and by content duplication — and gives you a staged, reviewed cleanup flow
instead of a one-click "delete my stuff".

The **CLI is the product**. The Electron desktop app is a thin front-end that
drives the CLI as a child process.

---

## Why this exists

[DiskBOX](https://www.diskbox.app/) does a good job of this, but it is
Windows-only and closed-source. This project reimplements the same capabilities
for **macOS, Linux and Windows**, with an open, scriptable CLI at the centre.

---

## Status

| Area | State |
|---|---|
| Scan engine + SQLite index | ✅ working |
| Scan history — every scan kept, reusable, listable | ✅ working |
| Pausable scans — pause, resume and stop from the desktop app | ✅ working |
| Folder tree, size ranking, file-type report, age map | ✅ working |
| Drive/volume discovery (Windows, macOS, Linux) | ✅ working |
| All eight Explore views (treemap, sunburst, flame, bubbles, mind map, …) | ✅ table / JSON / SVG |
| Advanced search | ✅ working |
| Duplicate finder (SHA-256 + exact byte compare) | ✅ working |
| Archive browser (read-only, 64 KiB preview) | ✅ working |
| Staged cleanup → validate → confirm → recycle bin | ✅ working |
| Game library discovery (Steam / Epic) | ✅ working |
| Application inventory + uninstall | ✅ working |
| Live monitor | ✅ working |
| Snapshots + 7-day change | ✅ working |
| Weekly report (HTML) + type report (CSV) | ✅ working |
| `diskgoup serve` (JSON-RPC over stdio, for the GUI) | ✅ working |
| Electron + Vite desktop app | ✅ working — spawns the CLI, renders all nine sections |
| Desktop scan list | ✅ working — every stored scan is listed and can be opened |

---

## Requirements

- Python **3.12+**
- [`uv`](https://docs.astral.sh/uv/) (recommended)
- Node **20+** (only for the desktop app)

## Install

```bash
uv sync
```

## Use the CLI

```bash
# List the volumes on this machine
uv run diskgoup drives

# Scan a drive or folder (stored in a persistent index)
uv run diskgoup scan ~/

# Every scan is kept — list them, reopen one, prune them
uv run diskgoup scans
uv run diskgoup tree ~/ --scan-id 3
uv run diskgoup scans remove 3

# Explore the result — one scan, many views
uv run diskgoup tree ~/ --depth 2
uv run diskgoup sizes ~/ --limit 25
uv run diskgoup types ~/
uv run diskgoup treemap ~/ -o treemap.svg

# Find and review duplicates
uv run diskgoup duplicates ~/

# Stage a cleanup, review it, then commit it to the recycle bin
uv run diskgoup cleanup stage ~/Downloads/old-archive.zip
uv run diskgoup cleanup list
uv run diskgoup cleanup validate
uv run diskgoup cleanup commit

# Machine-readable output for scripting
uv run diskgoup --json types ~/ | jq '.types[0]'
```

Every command accepts `--json`, which is how the desktop app consumes the CLI.
Run `uv run diskgoup --help` for the full surface.

### The cleanup contract

Nothing is ever deleted straight away:

```
stage → review → validate → confirm → revalidate → recycle bin
```

Protected paths — system directories, protected application data, game files and
saves — can never be staged. Cancelling leaves every file exactly where it was.

---

## The desktop app

```
diskgoup-alternative/
├── src/diskgoup/     Python CLI (uv project)
├── electron/         Electron main process (TypeScript)
└── ui/               Vite + React renderer (TypeScript)
```

The renderer contains **no disk logic**. The Electron main process spawns the
compiled CLI and talks to it over newline-delimited JSON-RPC on stdin/stdout.

### Build

```bash
# 1. Build the CLI binary and copy it into electron/resources/
cd electron && npm install && npm run build:cli

# 2. Build the renderer
cd ../ui && npm install && npm run build

# 3. Assemble the app
cd ../electron && npm run build
```

`npm run build` in `electron/` runs PyInstaller (`diskgoup.spec`), copies
`dist/diskgoup` → `electron/resources/diskgoup`, and copies the Vite build →
`dist/renderer`.

### Run

```bash
# Development — the Vite dev server on :5173 and Electron together
cd ui && npm run dev          # terminal 1
cd electron && npm run dev    # terminal 2

# Production-style — loads the bundled renderer
cd electron && npm start
```

The app **refuses to start** if the CLI binary is missing, and tells you exactly
which command to run. In a packaged build the binary comes from the app's
`resources` directory; in development it comes from `electron/resources/`.

### Package

```bash
cd electron
npm run dist:mac      # dmg (arm64 + x64)
npm run dist:win      # nsis (x64)
npm run dist:linux    # AppImage
```

---

## Development

```bash
uv run pytest                            # tests
uv run ruff check . && uv run ruff format .
uv run mypy                              # strict type check
```

---

## License

MIT.
