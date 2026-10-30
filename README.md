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

## Quick start

### What you need

- Python **3.12+**
- [`uv`](https://docs.astral.sh/uv/) — installs Python and manages the environment
- Node **20+** — only for the desktop app

### Prepare the project (once)

**You do not have to install anything by hand.** `uv sync` creates a private
virtual environment in `.venv/` and installs the CLI together with the tools
that build it; `npm install` installs the Node packages for the renderer and
the Electron shell. No global installs, no manual steps, no "install the CLI
first".

```bash
git clone https://github.com/elshadaghazade/diskgoup.git
cd diskgoup

uv sync                        # Python environment + CLI + build tools
npm --prefix ui install        # renderer packages
npm --prefix electron install  # Electron packages
```

> `npm --prefix <folder> <command>` simply means "run this inside `ui/` or
> `electron/`". Every command below works from the repository root — there is
> no need to `cd` around.

### Run the desktop app

Two terminals, because the renderer is a Vite dev server and the app is a
separate process:

```bash
# terminal 1 — the renderer, on http://localhost:5173
npm --prefix ui run dev

# terminal 2 — the app
npm --prefix electron run dev
```

The second command does the rest: it compiles the Electron main process,
**builds the CLI binary** with PyInstaller, copies it into
`electron/resources/` and opens the window. The app therefore always talks to
your current code — there is no separate "install the CLI" step.

Changes to the renderer reload on save. Changes to Python need
`npm --prefix electron run build:cli` (or a restart of the dev command) to be
picked up.

If the CLI binary is missing, the app refuses to start and tells you exactly
which command to run — a blank window is never left in front of you.

### Use the CLI on its own

The same environment, no Electron involved:

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

---

## Build for production

### The desktop app

```bash
npm --prefix ui run build        # renderer → ui/dist
npm --prefix electron run build  # main process + CLI binary + renderer → electron/dist
npm --prefix electron start      # run the production build
```

### Installers

```bash
npm --prefix electron run dist:mac      # .dmg (arm64 + x64)
npm --prefix electron run dist:win      # .exe (NSIS installer)
npm --prefix electron run dist:linux    # AppImage
```

The installers land in `electron/release/`. The CLI binary is bundled inside
the app, so an installer is self-contained — it does not need Python on the
target machine.

### The CLI on its own

```bash
uv run pyinstaller diskgoup.spec
```

→ `dist/diskgoup` (`dist\diskgoup.exe` on Windows): one self-contained binary
that runs anywhere, with no Python installation required.

---

## How it works

```
diskgoup-alternative/
├── src/diskgoup/     Python CLI (uv project) — all the disk logic
├── electron/         Electron main process (TypeScript)
└── ui/               Vite + React renderer (TypeScript)
```

The renderer contains **no disk logic**. The Electron main process spawns the
compiled CLI and talks to it over newline-delimited JSON-RPC on stdin/stdout.
Delete the GUI and nothing is lost — every capability is still on the command
line.

One scan powers every view: the walk is written into a persistent SQLite
index, and the tree, the treemap, the search, the duplicate finder and the
reports all read that same result set instead of touching the disk again.

### The cleanup contract

Nothing is ever deleted straight away:

```
stage → review → validate → confirm → revalidate → recycle bin
```

Protected paths — system directories, protected application data, game files and
saves — can never be staged. Cancelling leaves every file exactly where it was.

---

## Development

```bash
uv run pytest                            # tests
uv run ruff check . && uv run ruff format .
uv run mypy                              # strict type check

npm --prefix ui run typecheck            # renderer types
npm --prefix electron run build:electron # Electron main process types
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for the rules that matter when you
contribute — the short version: **the CLI is the product**, so new capability
goes into `src/diskgoup/` and the GUI only presents it.

---

## Credits

- **[goup.vc](https://goup.vc/)** — the DiskGOup community. This project is
  built with and for the people there: ideas, bug reports, design opinions and
  pull requests are all welcome.
- **[DiskBOX](https://www.diskbox.app/)** — the original application whose
  capabilities this project reimplements for macOS, Linux and Windows. Thanks
  to its authors for showing what a disk analyser should do.

---

## License

[MIT](LICENSE) © DiskGOup contributors
