# Contributing to DiskGOup

Thanks for being here. DiskGOup is built by the community at
[goup.vc](https://goup.vc/) — bug reports, ideas, screenshots of a weird
folder layout and pull requests are all equally welcome. You do not need to be
a Python or Electron expert to help.

This guide covers how to get set up, where things live, and what we expect from
a pull request. It should take five minutes to read.

---

## 1. Set up

Everything is prepared for you — see [README.md](README.md#quick-start) for the
short version:

```bash
uv sync                        # Python environment + CLI + build tools
npm --prefix ui install        # renderer packages
npm --prefix electron install  # Electron packages
```

Then check that everything is healthy:

```bash
uv run pytest
```

If the tests pass, you are ready to work.

---

## 2. The one rule: the CLI is the product

**Every capability lives in the Python CLI. The desktop app is a view over it.**

The Electron app owns no disk logic: it spawns the compiled CLI as a child
process and talks to it over JSON-RPC on stdin/stdout. If the GUI were deleted
tomorrow, nothing would be lost.

So when you add a feature:

1. implement it in `src/diskgoup/core/` (the logic) and expose it in
   `src/diskgoup/commands/` (the command);
2. make the command speak `--json`, because that is how the app consumes it;
3. only then add the UI on top.

A pull request that puts filesystem logic in the renderer will not be merged,
however good it looks. This is the single most important convention in the
project.

### Where things live

```
src/diskgoup/
├── cli.py            # the Typer app — the one place commands are registered
├── commands/         # one module per CLI area; each exposes register(app)
│   └── common.py     # shared helpers (scan resolution, JSON output)
├── core/             # the actual disk logic — no Typer, no printing
└── util/             # formatting helpers
electron/             # Electron main process (TypeScript) — owns the CLI child
ui/                   # Vite + React renderer (TypeScript) — presentation only
tests/                # pytest, one file per area
```

`core/` never imports from `commands/`. The dependency only ever points
downwards.

---

## 3. How to add things

### A new CLI command

Add a function to the right `commands/<area>.py`, register it on the Typer app,
and — if the GUI should show it — add the matching method to the JSON-RPC
server (`commands/serve.py`) and to the typed client (`ui/src/lib/api.ts`).

```bash
uv run diskgoup --help          # the command shows up here
uv run diskgoup yourcommand --json
```

Every command needs both a readable output and a `--json` output.

### A new view

The Explore views (treemap, sunburst, flame, bubbles, mind map, age, …) are
layout functions in `core/views.py` that return geometry, which `core/render.py`
turns into SVG. A new view is: a layout function, a command that exposes it,
and a renderer tab that draws what you return.

### A new GUI section

`ui/src/App.tsx` holds the section switch and the shared layout; each section
is a component in `ui/src/components/`. Keep components dumb: they receive
data and call the API — they never touch the filesystem.

---

## 4. Quality gate

Everything below must pass before a pull request is merged:

```bash
uv run pytest                            # tests
uv run ruff check .                      # lint
uv run ruff format .                     # formatting
uv run mypy                              # strict type check
npm --prefix ui run typecheck            # renderer types
npm --prefix electron run build:electron # Electron types
```

The project is typed strictly (`mypy --strict`) and linted with `ruff`. Please
run the formatters before you push — a diff that is only formatting changes
makes a review much harder.

New behaviour needs a test. Tests live in `tests/` and are plain pytest; there
is no mocking framework, and most of them work on a temporary directory.

---

## 5. Commits and pull requests

- Branch from `main`, one topic per branch: `feature/treemap-labels`,
  `fix/scan-lock`.
- Commit messages in the imperative mood, one line of subject, then a blank
  line and the why: *"Commit each scan batch so a running scan does not lock
  out other writers."*
- Open a pull request with a short description of what changed and why. A
  screenshot of the app is the best possible evidence for a UI change.
- Say which platforms you tested on (macOS / Linux / Windows). DiskGOup is
  cross-platform and the platform-specific code is where the surprises live.
- Small pull requests get merged quickly; a 2,000-line pull request takes a
  week of discussion.

---

## 6. Safety rules

DiskGOup deletes files. That makes some rules non-negotiable:

- **Nothing is deleted without being staged, reviewed, validated and
  confirmed.** The staged list is revalidated immediately before anything
  moves.
- **Items go to the platform recycle bin** (`send2trash`), never to
  `unlink`.
- **Protected paths can never be staged** — system directories, protected
  application data, game files and saves. Do not weaken `core/protect.py` to
  make a test pass.
- **Never add code that deletes files outside the staged flow**, not even
  "temporarily", not even for a cache.

---

## 7. Reporting a bug

Open an issue with:

- your OS and Python version;
- the exact command (or the screenshot of the app);
- what you expected and what happened;
- the output of `uv run diskgoup --version`.

A bug report that includes the command line and the output is usually fixed in
a day.

---

## 8. License

DiskGOup is MIT licensed — see [LICENSE](LICENSE). By contributing you agree that
your contribution is published under the same license.

Questions? The community at [goup.vc](https://goup.vc/) is the right place to
ask.
