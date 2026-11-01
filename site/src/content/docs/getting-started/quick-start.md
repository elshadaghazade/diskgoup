---
title: Quick start
description: Your first DiskGOup scan, your first treemap and your first duplicate search.
---

Five commands and you know where your disk space went.

## 1. Look at your drives

```bash
uv run diskgoup drives
```

```
╭──────────┬─────────────────┬────────┬─────────┬─────────┬─────────┬────────╮
│ Mount    │ Device          │ Type   │  Total  │   Used  │   Free  │ Usage │
├──────────┼─────────────────┼────────┼─────────┼─────────┼─────────┼────────┤
│ /        │ /dev/disk3s5    │ apfs   │ 494 GB  │ 121 GB  │ 358 GB  │  25%   │
╰──────────┴─────────────────┴────────┴─────────┴─────────┴─────────┴────────╯
```

On macOS the APFS container is collapsed into one row, so you see one disk
rather than the sealed system volume, the data volume and the helper volumes.

## 2. Scan something

```bash
uv run diskgoup scan ~
```

The scan walks the tree once and writes every entry into the SQLite index. The
progress line updates while it runs:

```
182,441 files · 41.2 GB · 12.4s
```

```
✔ scanned /Users/you
  182,441 files · 21,904 folders · 41.2 GB logical · 38.9 GB on disk · 12.4s
  scan id 1
```

Every later command reads that index instead of walking the disk again.

## 3. Look at it from different angles

```bash
uv run diskgoup tree ~ --depth 2      # the folder tree
uv run diskgoup sizes ~ --limit 10    # the biggest folders and files
uv run diskgoup types ~               # the file-type breakdown
uv run diskgoup age ~                 # how old the files are
```

## 4. Draw it

```bash
uv run diskgoup treemap ~ --output treemap.svg
```

That writes a standalone SVG. Swap `treemap` for `sunburst`, `flame`,
`bubbles` or `mindmap` — all eight Explore views are the same scan seen from a
different angle.

## 5. Find what you can reclaim

```bash
uv run diskgoup duplicates ~ --min-size 1048576
```

```
312 duplicate groups · 4.8 GB reclaimable · 24,910 candidates
```

Or ask the tool what is safe to remove on its own:

```bash
uv run diskgoup cleanup stage ~/Library/Caches/example
uv run diskgoup cleanup list
uv run diskgoup cleanup validate
uv run diskgoup cleanup commit
```

Nothing is deleted at the `stage` step. The commit asks for confirmation, and
the list is validated again immediately before anything moves to the recycle
bin.

## Making it scriptable

Every command accepts `--json`, which replaces the formatted output with a
machine-readable payload:

```bash
uv run diskgoup --json sizes ~ --limit 5
```

```json
{
  "scan": { "scan_id": 1, "root": "/Users/you", "total_size": 44256345344, "…": "…" },
  "entries": [
    {
      "name": "Downloads",
      "path": "/Users/you/Downloads",
      "is_dir": true,
      "size": 12884901888,
      "on_disk": 12884901888,
      "kind": "other",
      "protected": false,
      "share": 0.291
    }
  ]
}
```

`--json` is the contract the desktop app builds on. It is also the easiest way
to script DiskGOup from a shell.

## Next

- [Scanning →](/guide/scanning/) — scan options, reusing scans, refreshing one folder.
- [Cleaning up safely →](/guide/cleanup/) — the full staged flow.
