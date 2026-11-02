---
title: Contributing
description: How to set up, the conventions that matter, and the safety rules that are not negotiable.
---

Thanks for being here. Bug reports, ideas, screenshots of a weird folder
layout and pull requests are all welcome. You do not need to be a Python or
Electron expert to help.

## Set up

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

## The one rule: the CLI is the product

**Every capability lives in the Python CLI. The desktop app is a view over
it.**

The Electron app owns no disk logic: it spawns the compiled CLI as a child
process and talks to it over JSON-RPC on stdin/stdout. If the GUI were
deleted tomorrow, nothing would be lost.

So when you add a feature:

1. Implement it in `src/diskgoup/core/` (the logic) and expose it in
   `src/diskgoup/commands/` (the command).
2. Make the command speak `--json`, because that is how the app consumes it.
3. Only then add the UI on top.

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

## How to add things

### A new CLI command

Add a function to the right `commands/<area>.py`, register it on the Typer
app, and — if the GUI should show it — add the matching method to the
JSON-RPC server (`commands/serve.py`) and to the typed client
(`ui/src/lib/api.ts`).

```bash
uv run diskgoup --help          # the command shows up here
uv run diskgoup yourcommand --json
```

Every command needs both a readable output and a `--json` output.

### A new view

The Explore views (treemap, sunburst, flame, bubbles, mind map, age, …) are
layout functions in `core/views.py` that return geometry, which
`core/render.py` turns into SVG. A new view is: a layout function, a command
that exposes it, and a renderer tab that draws what you return.

### A new GUI section

`ui/src/App.tsx` holds the section switch and the shared layout; each
section is a component in `ui/src/components/`. Keep components dumb: they
receive data and call the API — they never touch the filesystem.

## The quality gate

Everything below must pass before a pull request is merged:

```bash
uv run pytest                            # tests
uv run ruff check .                      # lint
uv run ruff format .                     # formatting
uv run mypy                              # strict type check
npm --prefix ui run typecheck            # renderer types
npm --prefix electron run build:electron # Electron types
```

The project is typed strictly (`mypy --strict`) and linted with `ruff`.
Please run the formatters before you push — a diff that is only formatting
changes makes a review much harder.

New behaviour needs a test. Tests live in `tests/` and are plain pytest;
there is no mocking framework, and most of them work on a temporary
directory.

## Commits and pull requests

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

## Safety rules

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

## Reporting a bug

Open an issue with the **Bug report** template — the repository has one, so
you get the right fields instead of a blank page.

Fill in what the template asks for:

- your operating system and version;
- the exact command (or a screenshot of the app);
- what you expected and what happened;
- the output of `uv run diskgoup --version`.

A bug report that includes the command line and the output is usually fixed
in a day. The template asks for the version because most surprises come from
a change between releases.

The issue gets the `bug` label automatically, and `needs-triage` until
somebody has looked at it.

## Suggesting a feature

Ideas are **discussed first, implemented second**. Open a
[discussion](https://github.com/elshadaghazade/diskgoup/discussions) and say
what you are trying to do. A discussion is cheap — if the idea turns out to
be already possible, you have learned that in a day instead of a week.

When the idea has a shape, open a **Feature request** issue. It gets the
`enhancement` and `needs-discussion` labels, and it is where the work is
planned.

A feature request that answers these is easy to act on:

1. **The problem** — what you are trying to do that is hard today. Not the
   solution; the problem.
2. **The proposal** — what DiskGOup should do about it.
3. **The alternatives** — what you tried, and what other tools do.

## How the work is organised

Issues carry labels, and the labels are what the board is built from.

| Label | Meaning |
|---|---|
| `bug` | something does not work |
| `enhancement` | a new capability, or an improvement |
| `needs-triage` | nobody has looked at it yet |
| `confirmed` | reproduced — it is real |
| `needs-discussion` | the idea has to be discussed before it becomes work |
| `area: cli` | the change belongs in `src/diskgoup/` |
| `area: desktop` | the change belongs in the Electron app or the renderer |
| `area: docs` | the change belongs in this site |
| `area: build/ci` | the change belongs in the workflows or the packaging |
| `platform: macos`, `platform: linux`, `platform: windows` | where it was seen |
| `good first issue` | small, self-contained and a good way in |
| `help wanted` | nobody is working on it — yours to take |

Issues are grouped into **milestones**, which are the releases: `v0.2.0` holds
everything that is going into the next version.

The **project board** is a Kanban board — *Backlog → Planned → In progress →
In review → Done* — and it is a view over the issues, not a second place to
write things down. Moving a card means moving the issue's status.

To pick something up: comment on the issue, so nobody duplicates the work,
and move it to *In progress*.

## The releases

**Merging into `main` is what publishes a release.** The CLI and the desktop
app are built for every platform and attached to the
[release](https://github.com/elshadaghazade/diskgoup/releases) — no commands to
run, no tag to push. The steps are in
[Building and releasing](/development/building/).

## The documentation

This site lives in the application repository, under `site/`. It documents the
**shipped** behaviour — if a module is marked "(planned)" in the project's
own notes but is in fact implemented, the site describes what the code
does.

When you change a command's flags, a default or an output format, update
the matching page here in the same pull request. The
[CLI reference](/reference/cli/) and the
[JSON-RPC protocol](/reference/json-rpc/) are the two pages that go stale
the fastest.

## License

DiskGOup is MIT licensed. By contributing you agree that your contribution
is published under the same license.
