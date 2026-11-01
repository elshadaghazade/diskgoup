---
title: Architecture
description: How DiskGOup is put together — the CLI, the core, the index and the desktop app.
---

DiskGOup is two programs and one file on disk.

- A **Python CLI** that does all the work.
- An **Electron desktop app** that draws it.
- A **SQLite index** that both read.

The CLI is the product. The desktop app is a view over the same engine, and
it drives the CLI through a pipe rather than re-implementing anything.

## The layers

```
diskgoup (command)
   │
   ├── cli.py            the Typer app: the commands, the global flags
   ├── commands/         one module per area — the CLI's shape
   │      common.py      the helpers every command shares
   │      serve.py       the JSON-RPC server
   │
   └── core/             the engine — no Typer, no terminal output
          scanner.py     the walk
          store.py       the SQLite index
          protect.py     what may not be cleaned
          cleanup.py     stage → validate → commit
          duplicates.py  the six-stage duplicate pipeline
          views.py       tree, sizes, types, age
          treemap.py     the squarified treemap
          search.py      the query engine
          ...
```

The rule at the boundary: **`core/` never imports from `commands/`, and never
prints.** A core module returns data; a command turns it into a table or
into JSON. That is what makes the same engine usable from the CLI and from
the JSON-RPC server.

## The core modules

| Module | What it does |
|---|---|
| `models.py` | The `Kind` enum, `Entry`, and the dataclasses the modules pass around. |
| `store.py` | The SQLite index: the schema, the migrations, the queries. |
| `scanner.py` | The walk itself: streaming, batched, cancellable. |
| `protect.py` | The protection rules and the fast path for the walk. |
| `cleanup.py` | The staging area and the commit gate. |
| `duplicates.py` | The six-stage duplicate pipeline. |
| `parallel.py` | The thread/process pool and the automatic backend choice. |
| `kinds.py` | The file-kind classification. |
| `views.py` | The eight views. |
| `treemap.py` | The squarified treemap algorithm. |
| `search.py` | The search conditions and the paging. |
| `reclaim.py` | The reclaimable list. |
| `snapshots.py` | Snapshots and the comparison. |
| `reports.py` | The Jinja2 environment and the two reports. |
| `archives.py` | Reading ZIP archives without extracting them. |
| `games.py` | Steam and Epic discovery. |
| `applications.py` | Installed applications and uninstalling them. |
| `monitor.py` | The live I/O samples. |
| `partitions.py` | The mounted volumes, per platform. |
| `render.py` | The Rich tables and the JSON output. |

## The commands

One module per area under `commands/`, each holding the Typer commands for
that area:

| Module | Commands |
|---|---|
| `system.py` | `drives` |
| `explore.py` | `scan`, `refresh`, `scans`, `tree`, `sizes`, `types`, `age` |
| `views.py` | `treemap`, `sunburst`, `flame`, `bubbles`, `mindmap` |
| `search.py` | `search` |
| `duplicates.py` | `duplicates` |
| `cleanup.py` | `cleanup` and its six sub-commands |
| `archives.py` | `archives` and its three sub-commands |
| `snapshots.py` | `snapshots` and its four sub-commands |
| `reports.py` | `reports` and its two sub-commands |
| `games.py` | `games` |
| `applications.py` | `apps` |
| `monitor.py` | `monitor` |
| `serve.py` | `serve` |

`commands/common.py` holds the shared helpers — most importantly
`ensure_scan()`, which finds a complete scan of the same root and reuses it
instead of walking again.

## The three front ends

Everything the CLI can do is reachable three ways.

| Front end | How it calls the core |
|---|---|
| The terminal | `cli.py` → a command → the core → a Rich table |
| The JSON-RPC server | `serve.py` → the same core → a JSON result |
| `--json` | The same command → the same core → JSON on stdout |

The `--json` output and the JSON-RPC result are the same shapes, which is
why the desktop app can share code with a shell script.

## How a scan flows

```
diskgoup scan /Users/me
   │
   ├─ 1. the scanner walks the tree
   │      os.scandir, depth-first, streaming
   │      each entry → classify → protect-check → record
   │
   ├─ 2. every 2000 entries the batch is committed
   │      so a canceled scan still leaves a usable index
   │
   ├─ 3. the directory totals are rolled up
   │      the children of a folder are summed into the folder
   │
   └─ 4. the scan row is marked complete
```

The scanner asks `protect.py` about every entry through the fast path, so
the protection rules cost one dictionary lookup per entry rather than a
re-derivation.

## How the views flow

```
diskgoup treemap /Users/me
   │
   ├─ 1. ensure_scan() — reuse a complete scan, or walk
   │
   ├─ 2. the view reads the index
   │      tree.py builds the hierarchy from parent_id
   │
   ├─ 3. the geometry is computed
   │      treemap.py lays out rectangles; views.py aggregates by kind
   │
   └─ 4. the result is printed as a table, as JSON, or written as SVG
```

## How the desktop app flows

```
Electron main process
   │
   ├─ resolves the binary and spawns `diskgoup serve --quiet`
   │
   └─ the renderer (React) talks to it over NDJSON
          ui/src/lib/api.ts — a typed client, one method per RPC call
```

The main process owns the pipe. The renderer never touches it directly —
the preload script exposes a narrow bridge, and the Electron window runs
with `contextIsolation: true`, `nodeIntegration: false` and `sandbox: true`.

See [The desktop app](/development/desktop/).

## The decisions that shape the code

### One walk, one pass

The scanner never walks a tree twice. The hierarchy is built from a parent
pointer, and the directory totals are rolled up from the children already
recorded — not by re-reading the disk.

### The index is the source of truth for browsing

The views and the searches read the index. Only a scan touches the disk.
That is what makes opening a folder instant.

### The protection rules are decided in one place

`protect.py` holds the single decision function, and the fast path for the
walk reaches the same verdict. The cleanup gate and the UI badge therefore
always agree.

### Slow work goes off the read loop

The JSON-RPC server serves the slow methods on a worker thread, so the app
stays responsive while a scan runs.

### Performance choices worth knowing

| Choice | Why |
|---|---|
| No `ORDER BY` on the children query | 4 ms instead of 18 s on a two-million-entry scan. |
| The extension is read off the name, not through `pathlib` | `PurePath`'s parser is pure Python and showed up in the profile. |
| Sizes come from the index, not from `stat` | The duplicate finder needs no extra syscall per file. |
| Digests are remembered, keyed on size and mtime | A file that has not changed is not re-hashed. |
| Processes only for searches of 2000+ files | Starting them costs more than it saves below that. |

## The frozen build

`diskgoup.spec` builds a single executable with PyInstaller. The one thing
to remember:

```python
multiprocessing.freeze_support()
```

is called **before** the Typer app starts. Without it, the worker processes
of a frozen build re-run the whole program instead of doing their job.

## See also

- [The desktop app](/development/desktop/) — the Electron side.
- [Building and releasing](/development/building/) — the packaging steps.
- [The scan index](/reference/scan-index/) — the schema.
