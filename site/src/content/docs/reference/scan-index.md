---
title: The scan index
description: The SQLite database that stores every scan, and how it is structured.
---

Everything DiskGOup knows about a disk lives in one SQLite database. The
scanner writes it, the views read it, and the searches run against it — so
browsing a folder never re-walks the disk.

## Where it is

| Platform | Path |
|---|---|
| macOS | `~/Library/Caches/diskgoup/index.db` |
| Linux | `~/.cache/diskgoup/index.db` |
| Windows | `%LOCALAPPDATA%\diskgoup\Cache\index.db` |

Set `DISKGOUP_INDEX` to put it somewhere else. See
[Where things are stored](/getting-started/paths/).

## The tables

### `scans` — one row per scan

| Column | What it holds |
|---|---|
| `id` | The scan id. This is the `--scan-id` you pass around. |
| `root` | The path the scan started from. |
| `started_at`, `finished_at` | Timestamps. `finished_at` is null while the scan runs. |
| `total_size`, `total_on_disk` | The logical and the allocated totals. |
| `file_count`, `dir_count` | How many of each. |
| `skipped` | How many entries could not be read. |
| `complete` | 1 when the scan finished, 0 when it was stopped or canceled. |
| `options` | The options the scan ran with, as JSON. |

A scan with `complete = 0` is shown as `partial`.

### `entries` — one row per file or folder

| Column | What it holds |
|---|---|
| `id` | The entry id. |
| `scan_id` | The scan it belongs to. |
| `parent_id` | The id of the folder that holds it — the tree is a parent pointer, not a path string. |
| `path` | The full path. |
| `name` | The file or folder name. |
| `is_dir` | 1 for a folder. |
| `size` | The **logical** size — the sum of the file's byte lengths. |
| `on_disk` | The **allocated** size — the blocks the file actually occupies. |
| `mtime` | The modification time, as a Unix timestamp. |
| `kind` | The file kind. See [File kinds](/reference/file-kinds/). |
| `protected` | Whether the entry was protected when it was scanned. |
| `depth` | How many levels below the root. |
| `file_count`, `dir_count` | The counts of the subtree, for folders. |

`size` and `on_disk` differ for sparse and compressed files, which is why
both are recorded and both are reported.

### `skipped` — what could not be read

| Column | What it holds |
|---|---|
| `scan_id` | The scan it belongs to. |
| `path` | The path that was skipped. |
| `reason` | Why — a permission error, a broken symlink, a vanished file. |

A scan that hits a folder it is not allowed to read does not fail. It records
the folder and carries on.

### `hashes` — remembered digests

| Column | What it holds |
|---|---|
| `scan_id`, `entry_id` | The file. |
| `size` | The size at the time of hashing. |
| `mtime` | The modification time at the time of hashing. |
| `sha256` | The digest. |

The [duplicate finder](/guide/duplicates/) uses this table to avoid
re-hashing a file that has not changed since the last time it was hashed.

### `snapshots` and `snapshot_kinds` — the history

`snapshots` holds one row per snapshot: its label, when it was taken, its
totals and the scan it belongs to.

`snapshot_kinds` holds one row per snapshot per kind: the size of that kind
at that moment. It is what the
[snapshot comparison](/guide/snapshots/) reads.

### `staged` — the review list

| Column | What it holds |
|---|---|
| `scan_id` | The scan the items were staged from. |
| `path` | The path of the item. |
| `size` | Its size. |
| `kind` | Its file kind. |
| `added_at` | When it was staged. |
| `status` | `staged`, or whatever the validation said about it. |

This is the table behind `diskgoup cleanup list`. It survives between
commands — that is what makes the stage → review → commit workflow possible.

## Indexes

Six indexes on `entries`, one on `hashes`, one on `staged`:

```sql
idx_entries_scan_parent  ON entries(scan_id, parent_id)
idx_entries_scan_size    ON entries(scan_id, size)
idx_entries_scan_kind    ON entries(scan_id, kind)
idx_entries_scan_name    ON entries(scan_id, name)
idx_entries_scan_path    ON entries(scan_id, path)
idx_entries_scan_depth   ON entries(scan_id, depth)
idx_hashes_scan_digest   ON hashes(scan_id, sha256)
idx_staged_scan          ON staged(scan_id, status)
```

They exist for the questions the app actually asks: the children of this
folder, the biggest entries, the entries of this kind, the entries matching
this name or path.

## One decision worth knowing about

The query that lists a folder's children has **no `ORDER BY`**:

```sql
SELECT * FROM entries WHERE scan_id = ? AND parent_id = ?
```

That is deliberate. With an `ORDER BY`, SQLite picks the index on
`(scan_id, name)` — it satisfies the ordering — and then has to walk *every*
entry of the scan to find the rows with the right parent. On a
two-million-entry scan that is **18 seconds instead of 4 milliseconds**.

Without the ordering, the index on `(scan_id, parent_id)` answers the
question directly, and the rows are sorted in Python instead.

## The schema version

The version is stored in SQLite's own `user_version` pragma, and is
currently **4**.

Opening an index written by an older version applies the missing migrations
in order, so an index gains the new columns and indexes instead of being
thrown away:

| Version | What it added |
|---|---|
| 2 | The index on `depth`. |
| 3 | The `options` column on `scans`. |
| 4 | The `mtime` column on `hashes` — needed to know whether a remembered digest is still valid. |

## How the index is written

| Setting | Value | Why |
|---|---|---|
| `journal_mode` | `WAL` | A reader does not block the writer. The desktop app can browse while a scan writes. |
| `synchronous` | `NORMAL` | Safe with WAL, and much faster than `FULL`. |
| `foreign_keys` | `ON` | Removing a scan removes its entries, hashes and staged rows with it. |
| `busy_timeout` | 300 ms, 5 s during a scan | A concurrent write waits instead of failing. |

During a scan, entries are written in **batches of 2000**, each batch
committed on its own. A scan that is canceled leaves a usable partial index
behind rather than nothing.

## Removing things

`diskgoup scans remove 3` deletes the scan and, through the foreign keys,
every entry, hash and staged row that belonged to it.

To wipe everything, delete the file:

```bash
rm "$(python -c 'from diskgoup.paths import default_index_path; print(default_index_path())')"
```

The next command rebuilds it from scratch.
