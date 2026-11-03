---
title: The desktop app
description: The Electron wrapper, how it talks to the CLI, and how to run it.
---

The desktop app is a thin front-end. It owns **no disk logic** — every
number it shows was computed by the Python CLI, which it runs as a child
process.

This page is about how it is built. What it does for the user is in
[The desktop app](/desktop/overview/).

```
┌─────────────────────────────────────────────┐
│ Electron main process                       │
│                                             │
│   backend.ts ── spawns ──▶ diskgoup serve   │
│        ▲                        │           │
│        │  NDJSON over stdio    │           │
│   preload.ts ── ipcMain ──▶ renderer (React)│
└─────────────────────────────────────────────┘
```

## The two halves

| Directory | What it is |
|---|---|
| `electron/` | The Electron main process. Owns the child process, the window and the IPC bridge. |
| `ui/` | The React renderer. A Vite app with no Node integration — it calls the backend through the bridge. |

### `electron/src/`

| File | What it does |
|---|---|
| `main.ts` | Creates the window, owns the lifecycle, wires the IPC handlers. |
| `backend.ts` | Resolves the binary, spawns it, and speaks the JSON-RPC protocol. |
| `preload.ts` | The narrow bridge the renderer is allowed to use. |

### `ui/src/`

| File | What it does |
|---|---|
| `App.tsx` | The shell: the sidebar and the nine tabs. |
| `lib/api.ts` | The typed RPC client — one function per server method. |
| `lib/types.ts` | The shared response types. |
| `lib/format.ts` | Bytes, dates and percentages. |
| `components/` | One component per tab, plus the browser, the inspector and the dialogs. |

## How the binary is found

Three places, in order:

| # | When | Where |
|---|---|---|
| 1 | Packaged | `<app>/Contents/Resources/diskgoup` — `electron-builder` copies it there with `extraResources`. |
| 2 | Development | `electron/resources/diskgoup` — built by `scripts/build-cli.mjs`. |
| 3 | Fallback | `<repo>/dist/diskgoup` — the raw PyInstaller output. |

On Windows the name is `diskgoup.exe`.

**If none of them exists, the app refuses to start** and says exactly what
to run:

```
The DiskGOup CLI binary was not found.

Expected: /path/to/diskgoup

Build it with:
  uv run pyinstaller diskgoup.spec
  npm run build:cli          (in electron/)
```

A UI that pretends to work without an engine is worse than no UI.

## The protocol in the app

`backend.ts` implements the client side of the
[JSON-RPC protocol](/reference/json-rpc/): it writes one JSON object per
line, reads one per line, and matches the answers by `id`.

```ts
const proc = spawn(binary, ['serve', '--quiet'])
```

Notifications — `scan.progress`, `scan.state`, `duplicates.progress` — are
handed to the renderer through the status listeners, so the UI can show a
progress bar and react to a pause without polling.

## The window

```ts
webPreferences: {
  contextIsolation: true,
  nodeIntegration: false,
  sandbox: true,
}
```

The renderer loads **only local assets** and talks to the backend through
the preload bridge. It has no Node, no filesystem and no `require`.

In development the window loads the Vite dev server; in a packaged build it
loads the bundled `index.html` from disk.

The app also takes a **single-instance lock** — launching it twice focuses
the window that is already open instead of starting a second one.

## The tabs

Nine, one per area of the CLI:

| Tab | What it shows |
|---|---|
| Explore | The tree, the sizes, the kinds, the age map, the treemap and the other spatial views. |
| Search | The query form and its results. |
| Archives | The ZIP archives and their members. |
| Duplicates | The duplicate groups and the space they waste. |
| Applications | The installed applications and their footprint. |
| Games | The Steam and Epic libraries. |
| Monitor | The live I/O rates and the top processes. |
| Snapshots | The history and the comparison. |
| Reports | The weekly report and the CSV. |

The Explore tab is the one that exercises the background RPC methods — the
kind breakdown and the treemap of a large scan are slow, and they run off
the read loop so the browser stays usable.

## Running it

Install both halves first:

```bash
npm --prefix ui install
npm --prefix electron install
```

Then, from the `electron/` directory:

```bash
npm run dev
```

`npm run dev` compiles the TypeScript, builds the CLI binary into
`electron/resources/`, and starts Electron against the Vite dev server.

For the UI alone, without the Electron shell:

```bash
npm --prefix ui run dev
```

That is useful for working on the React components — but the renderer needs
the backend, so the calls will fail until the Electron shell (or a manual
`diskgoup serve`) is providing it.

## Packaging

```bash
npm --prefix electron run dist:mac
npm --prefix electron run dist:win
npm --prefix electron run dist:linux
```

`electron-builder` produces:

| Platform | Output |
|---|---|
| macOS | A `.dmg` installer and a portable `.zip` for `arm64` and `x64`. |
| Windows | An NSIS installer and a portable `.exe` for `x64`. |
| Linux | An `AppImage` and a portable `.tar.gz` for `x64`. |

The CLI binary travels with the app as an `extraResource`, and the resolver
finds it at the packaged path first.

## See also

- [JSON-RPC protocol](/reference/json-rpc/) — the contract between the two halves.
- [Architecture](/development/architecture/) — the Python side.
