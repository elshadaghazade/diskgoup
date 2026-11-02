---
title: JSON-RPC protocol
description: The newline-delimited JSON protocol the desktop app speaks to the DiskGOup binary.
---

The desktop app does not re-implement DiskGOup. It starts the `diskgoup`
binary and talks to it over a pipe. This page is the contract.

## The transport

Newline-delimited JSON on **stdin** and **stdout**: one JSON object per line,
in each direction.

```bash
diskgoup serve --quiet
```

```
{"id": 1, "method": "explore.tree", "params": {"path": "/Users/me"}}
{"id": 1, "result": {"scan": {...}, "tree": {...}}}
```

| Stream | Carries |
|---|---|
| stdout | Protocol traffic only. Anything else written there would corrupt the stream. |
| stderr | The startup banner, tracebacks, stray output from libraries. |

The server redirects stray output to stderr for exactly that reason.

## Requests and responses

A **request** carries an `id`:

```json
{"id": 1, "method": "search.query", "params": {"name": "report"}}
```

A **response** carries the same `id` and either a `result` or an `error`:

```json
{"id": 1, "result": {"entries": [...], "total": 42}}
```

```json
{"id": 1, "error": {"code": -32000, "message": "path does not exist"}}
```

A **notification** has no `id` and gets no answer — it is how the server
pushes information the client did not ask for:

```json
{"method": "scan.progress", "params": {"files": 1200, "bytes": 3400000}}
```

## Error codes

| Code | Meaning |
|---|---|
| `-32700` | Parse error — the line was not valid JSON. |
| `-32600` | Invalid request — the envelope was malformed. |
| `-32601` | Method not found. |
| `-32603` | Internal error — a bug; the traceback goes to stderr. |
| `-32000` | Application error — the request was valid but the operation failed (the path does not exist, the file is gone, the scan is already running). |

## The methods

Thirty-six methods, in twelve groups.

### App

| Method | Params | Result |
|---|---|---|
| `app.info` | – | `{"version", "platform", "volumes": [...]}` |
| `app.ping` | – | `{"pong": true}` |
| `app.reset` | – | `{"reset": true, "index_path": "...", "removed": [...]}` |

`app.reset` puts the app back to the state it had before the first scan: the
index is deleted and an empty one is written in its place. A scan that is
running is stopped first. It works on a corrupted index, because the old file
is removed before anything tries to open it.

### Drives

| Method | Params | Result |
|---|---|---|
| `drives.list` | – | `{"volumes": [...]}` |

### Scans

| Method | Params | Result |
|---|---|---|
| `scans.list` | – | `{"scans": [...]}` |
| `scans.remove` | `scan_id` | `{"removed": true}` |
| `scan.run` | `path`, `follow_symlinks`, `include_hidden`, `exclude`, `max_depth` | The scan result. |
| `scan.refresh` | `path`, `scan_id` | `{"scan": {...}, ...}` |
| `scan.pause` | – | `{"state": "paused"}` |
| `scan.resume` | – | `{"state": "running"}` |
| `scan.cancel` | – | `{"state": "canceled"}` |

`scan.run` requires `path`. The booleans default to `follow_symlinks: false`
and `include_hidden: true`. `exclude` is an array of glob patterns.

Only one scan runs at a time. A second `scan.run` is refused with an error
rather than queued.

### Explore

| Method | Params | Result |
|---|---|---|
| `explore.tree` | `path`, `scan_id`, `rescan` | `{"scan": {...}, "tree": {...}}` |
| `explore.children` | `path`, `scan_id` | The listing of one folder, with protection decided live. |
| `explore.reclaimable` | `path`, `scan_id` | The folders that can safely be cleaned. |
| `explore.sizes` | `path`, `scan_id`, `limit`, `folders`, `files` | The largest entries. |
| `explore.types` | `path`, `scan_id` | The file-kind breakdown. |
| `explore.age` | `path`, `scan_id` | The age distribution. |

`explore.children` answers from the index, so browsing never re-walks the
disk. If the folder changed since the scan and it is small enough to
re-walk, it is refreshed first — the listing is then what is actually on the
disk. A folder too big for that is returned with `"stale": true`, and the
client offers a refresh.

### Views

| Method | Params | Result |
|---|---|---|
| `view.layout` | `view`, `path`, `scan_id`, `depth`, `width`, `height` | The computed geometry of the chosen view. |

`view` is `treemap`, `sunburst`, `flame`, `bubbles` or `mindmap`. The client
does the drawing; the server computes the rectangles.

### Search

| Method | Params | Result |
|---|---|---|
| `search.query` | see below | `{"entries": [...], "total": N, "page": N}` |

| Parameter | Meaning |
|---|---|
| `name` | Match against the file name. |
| `path_filter` | Match against the full path. |
| `extensions` | Array of extensions. |
| `entry_type` | `any`, `file` or `folder`. |
| `kinds` | Array of file kinds. |
| `from_date`, `to_date` | `YYYY-MM-DD`, both inclusive. |
| `min_size`, `max_size` | Sizes as strings — `"100MB"`, `"2GB"`. |
| `min_age_days`, `max_age_days` | Age in days. |
| `protected_only` | Only protected paths. |
| `page` | 1-based page number. |
| `per_page` | Rows per page, default 200. |

### Duplicates

| Method | Params | Result |
|---|---|---|
| `duplicates.find` | `path`, `scan_id`, `min_size`, `jobs` | The duplicate groups. |

### Archives

| Method | Params | Result |
|---|---|---|
| `archives.list` | `archive`, `prefix` | The members of the archive. |
| `archives.preview` | `archive`, `member` | The first 64 KiB of a text member. |

### Games and applications

| Method | Params | Result |
|---|---|---|
| `games.list` | `platform` | The installed games and their sizes. |
| `apps.list` | `limit` | The installed applications and their sizes. |

### Monitor

| Method | Params | Result |
|---|---|---|
| `monitor.sample` | `processes` | One sample of the I/O rates and the top processes. |

### Snapshots and reports

| Method | Params | Result |
|---|---|---|
| `snapshots.list` | `scan_id` | The stored snapshots. |
| `snapshots.save` | `scan_id`, `label` | The new snapshot. |
| `snapshots.compare` | `scan_id`, `min_age_days` | The comparison with the baseline. |
| `reports.weekly` | `scan_id` | `{"html": "..."}`. |
| `reports.types` | `scan_id` | `{"csv": "..."}`. |

### Cleanup

| Method | Params | Result |
|---|---|---|
| `cleanup.stage` | `paths`, `path`, `scan_id` | `{"staged": [...], "refused": [...]}`. |
| `cleanup.unstage` | `paths`, `path`, `scan_id` | `{"removed": [...]}`. |
| `cleanup.list` | `path`, `scan_id` | `{"items": [...], "total": N}`. |
| `cleanup.validate` | `path`, `scan_id` | `{"valid": [...], "issues": [...]}`. |
| `cleanup.commit` | `permanent`, `path`, `scan_id` | What was removed and how much space it freed. |

`cleanup.stage` refuses protected paths and returns the reason for each
refusal in `refused`; `cleanup.validate` does the same for items that have
changed since they were staged.

`cleanup.commit` re-validates every item immediately before moving it.

## Notifications

Three notifications come from the server.

| Notification | Params | When |
|---|---|---|
| `scan.progress` | `{"files", "bytes", ...}` | During a scan. |
| `scan.state` | `{"state": "paused" \| "running" \| "canceled"}` | When a scan is paused, resumed or canceled. |
| `duplicates.progress` | `{"stage": "..."}` | While duplicates are being found. |

`scan.progress` is **throttled to one notification every 100 ms**. A scan of
a million files would otherwise write a million lines into the pipe and slow
the scan down to a crawl.

## Slow methods run in the background

Nine methods are served on a worker thread rather than on the read loop:

```
scan.run        scan.refresh     explore.types    explore.age
view.layout     scans.remove     duplicates.find  apps.list
apps.uninstall
```

The reason is practical. `scan.run` has to be there — the GUI pauses a
running scan, and the request that does it can only be read while the scan
is still running. The others are slow on a big index: the kind breakdown
reads every file of a scan, and the treemap reads the whole tree. Served
inline, one such request stalls every other one behind it — the folder
browser would wait for the sidebar's numbers before it could show a folder.
Off the loop, the answer arrives when it is ready and the rest of the app
keeps working.

The response is written when the worker finishes, with the original `id`, so
the client matches it the same way it matches any other answer.

## Talking to the server by hand

It is a plain pipe, so `nc` or a shell redirect works:

```bash
echo '{"id": 1, "method": "app.ping"}' | diskgoup serve --quiet
```

```json
{"id": 1, "result": {"pong": true}}
```

And the desktop app's own client lives in `ui/src/lib/api.ts` — a small
typed wrapper that gives every method a request and a response type.
