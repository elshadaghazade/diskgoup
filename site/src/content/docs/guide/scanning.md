---
title: Scanning
description: How DiskGOup walks a filesystem, what it stores, and how to reuse, refresh or discard a scan.
---

A scan walks a tree once and writes every entry into the SQLite index. Every
other command then reads that result set instead of walking the disk again.

## Taking a scan

```bash
diskgoup scan ~/Documents
```

The scan prints a live progress line and a summary:

```
182,441 files · 41.2 GB · 12.4s
✔ scanned /Users/you/Documents
  182,441 files · 21,904 folders · 41.2 GB logical · 38.9 GB on disk · 12.4s
  scan id 1
```

### Options

| Option | Default | What it does |
|---|---|---|
| `--follow-symlinks` / `--no-follow-symlinks` | off | Follow symlinked directories instead of recording the link itself. |
| `--include-hidden` / `--no-include-hidden` | on | Include dot-files and hidden entries. |
| `--exclude PATTERN` | – | Skip entries whose **name** or **path** matches the glob. Repeatable. |
| `--max-depth N` | unlimited | Stop descending below `N` levels. |
| `--profile` | off | Print a timing breakdown of where the walk spent its time. |

```bash
diskgoup scan ~ --exclude "node_modules" --exclude "*.tmp" --max-depth 4
```

`--exclude` uses shell-style globs (`fnmatch`) and is matched against both the
entry name and the full path, so `--exclude "*.iso"` and
`--exclude "/Volumes/*"` both work.

### What the scan records

For every file and folder:

| Column | Meaning |
|---|---|
| `path`, `name` | Where it is and what it is called |
| `is_dir` | Folder or file |
| `size` | **Logical** size — the sum of file byte lengths |
| `on_disk` | **Allocated** size — the space the volume actually gives it |
| `mtime` | Modification time |
| `kind` | The file kind (see [File kinds](/reference/file-kinds/)) |
| `protected` | Whether a protection rule applies |
| `depth` | How deep it sits in the tree |
| `file_count`, `dir_count` | Cumulative counts for folders |

:::note
`size` and `on_disk` differ for sparse and compressed files. A disk analyser
that reports only one of them is misleading, so DiskGOup reports both.
:::

Directory totals are **cumulative**: a folder's `size` includes every
descendant. A parent total must never be added to the totals of the children it
contains — that would count the same bytes twice.

## Skipped entries

An entry that cannot be read is recorded as *skipped* with the reason, and the
scan carries on. A permission error on one folder does not abort the walk.

```
  3 entries skipped
```

The notices are stored in the index, so `diskgoup --json scan …` reports them:

```json
"skipped_entries": [{ "path": "/Volumes/Data/private/var/db/x", "reason": "[Errno 13] Permission denied" }]
```

## Reusing a scan

The index holds **every** scan, not just the last one. A command asked for a
path that has already been scanned reads the stored scan rather than walking
the tree again:

```bash
diskgoup tree ~/Documents      # reuses the scan of ~/Documents
```

Two ways to force a different scan:

```bash
diskgoup tree ~/Documents --rescan          # walk the tree again
diskgoup tree ~/Documents --scan-id 3       # read scan #3 exactly
```

`--scan-id` is what the desktop app uses: the UI always names the scan it
wants, so opening a stored scan from the sidebar never re-walks anything.

### Listing and pruning scans

```bash
diskgoup scans             # every scan in the index
diskgoup scans remove 3    # delete scan #3 and everything recorded for it
```

```
╭────┬────────────────────────┬─────────┬─────────┬──────────┬──────────╮
│ ID │ Root                   │  Files  │   Size  │ Duration │   State  │
├────┼────────────────────────┼─────────┼─────────┼──────────┼──────────┤
│  3 │ /Users/you/Documents   │ 182,441 │ 41.2 GB │    12.4s │ complete │
│  2 │ /Users/you/Pictures    │  12,008 │  8.1 GB │     3.9s │ complete │
╰────┴────────────────────────┴─────────┴─────────┴──────────┴──────────╯
```

A scan that was stopped early is marked `partial`. Partial scans are skipped
when a command looks for a reusable scan — a partial scan is missing whatever
the walk did not reach.

## Refreshing one folder

The disk keeps moving after a scan. Instead of rescanning everything,
DiskGOup can walk **one folder** again and correct the index in place:

```bash
diskgoup refresh ~/Documents/Projects
```

```
✔ refreshed /Users/you/Documents/Projects
  1,204 files · 87 folders · 2.1 GB
  the folder changed — the index was corrected
```

Only the rows below that folder are replaced. The totals of the folders above
it are corrected **by the difference**, so the whole scan keeps telling the
truth without being walked again.

The refresh uses the **same options** the original scan used — the same
`--exclude` patterns, the same hidden-file handling, the same depth — so the
index never ends up holding two different views of the same tree. The options
are stored with the scan for exactly this reason.

### Staleness

A folder is *stale* when its modification time no longer matches the one the
scan recorded — that is, when files were added, removed or renamed inside it.
The check is one `stat` against the stored value.

```bash
diskgoup refresh ~/Documents/Projects --force   # refresh even if nothing changed
```

Without `--force`, a folder that has not changed is left alone:

```
/Users/you/Documents/Projects has not changed since scan 3.
```

### Automatic refresh in the browser

The desktop app refreshes a stale folder for you when you open it — but only
if the folder holds **5,000 files or fewer**. A refresh costs what a walk of
that folder costs, and a browser cache with tens of thousands of files would
hold the app up for seconds. Larger folders are reported as stale and you
refresh them by hand.

## Cancelling a scan

The scan can be stopped at any point. The rows that were already written stay
in the index and the scan is marked incomplete:

```bash
diskgoup scan /
# press Ctrl-C
```

A cancelled scan is rolled up once more, so the folders that were reached still
carry the best totals they can.

## How a scan is done

A few details that matter on a big volume:

- **Batched writes.** File rows are written in batches of 2,000 and **each
  batch is committed**. Holding the SQLite write lock for the whole walk would
  lock out every other process — the app, another CLI, a second scan.
- **Single pass.** A directory's totals are accumulated while its subtree is
  walked, so the index is never read back to be rolled up afterwards.
- **Partial-safe.** An unreadable entry is recorded and the walk continues.
- **Streaming.** Memory stays flat regardless of how many files the volume
  holds.
- **Symlinks are recorded, not followed** (unless `--follow-symlinks`), so a
  link loop cannot trap the walk.

## Timing a scan

`--profile` prints where the time went:

```bash
diskgoup scan ~ --profile
```

```
  timings: walk 11.92s · protect 0.31s · classify 0.44s · insert 1.08s · rollup 0.22s · total 12.4s
```

`protect` is the cost of the protection rules and `classify` the cost of the
file-kind classification — both run for every entry.
