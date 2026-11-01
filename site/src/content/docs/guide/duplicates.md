---
title: Finding duplicates
description: How DiskGOup proves that two files are identical — and how it stays fast on a million-file volume.
---

DiskGOup does not treat equal names or equal sizes as evidence of duplication.
It runs a pipeline and only publishes a group after the files have matched
**byte for byte**.

```bash
diskgoup duplicates ~/Documents --min-size 1048576
```

```
312 duplicate groups · 4.8 GB reclaimable · 24,910 candidates
```

## The pipeline

Six stages. Each one is cheap; each one throws away candidates that cannot
possibly be duplicates of one another.

| Stage | What it does | What survives |
|---|---|---|
| 0 | Drop zero-byte files | Files with content |
| 1 | **Size filtering** — group by size | Files whose size another file has too |
| 2 | **Prefix sampling** — hash the first 64 KiB | Files that share a head |
| 3 | **Middle and tail sampling** — 64 KiB from the middle, 64 KiB from the end | Files that share a head *and* a middle *and* a tail |
| 4 | **Full SHA-256** — the whole file, streamed | Files that share a digest |
| 5 | **Exact byte comparison** | Files that are byte-identical |

Sampling is a performance shortcut only — it never establishes equality on its
own. A file is only reported as a duplicate after stage 5 confirms it.

:::caution
A SHA-256 collision is astronomically unlikely but not impossible. Stage 5
exists for exactly that case: when the digests match but the bytes do not,
the group is split into byte-identical clusters.
:::

### Small files skip the sampling

A file that fits in one prefix sample (64 KiB) is hashed straight away — the
samples would only repeat what the hash already says. One read of the file
answers all three questions.

## What is excluded

- **Zero-byte files.** An empty file is not worth a place in a group.
- **Hard links.** A hard link is not a second copy — it is the same file with a
  second name. Candidates are compared by `(st_dev, st_ino)` and only the first
  of each identity is kept.

## What is kept

The **oldest** copy is the one to keep: it is the one that was there first, and
the content is the same either way, so the age is the only thing that tells the
copies apart.

```json
{
  "sha256": "9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08",
  "size": 1048576,
  "copies": 3,
  "reclaimable": 2097152,
  "keep": "/Users/you/Documents/report.pdf",
  "paths": [
    "/Users/you/Documents/report.pdf",
    "/Users/you/Downloads/report.pdf",
    "/Users/you/Desktop/report.pdf"
  ]
}
```

`reclaimable` is what keeping one copy frees: `size × (copies − 1)`.

## Options

| Option | Default | What it does |
|---|---|---|
| `--min-size N` | 1 | Ignore files smaller than this many bytes. |
| `--max-size N` | – | Ignore files larger than this many bytes. |
| `--kind KIND` | – | Only consider files of this kind. |
| `--limit N` | 0 (all) | Show at most this many groups. |
| `--jobs N` | 0 (automatic) | How many workers read and hash the files. |

```bash
diskgoup duplicates ~ --kind video --min-size 104857600 --jobs 16
```

## Why it is fast

Four decisions do the heavy lifting.

### The size comes from the index

The search never asks the disk how big a file is. The scan already recorded
it, and asking once per file — twice over — is what made the search crawl on a
volume with a million files.

The index also drops the files whose size no other file has, before they ever
reach Python:

```sql
SELECT size FROM entries WHERE … GROUP BY size HAVING COUNT(*) > 1
```

A file whose size is unique on the volume cannot be a duplicate of anything.

### The digest is remembered

Hashing a file means reading all of it. The digests are kept in the index
together with the size and modification time the file had when it was hashed,
and reused while the file still has them. **The second search of a scan does
not read the files again.**

```bash
diskgoup duplicates ~     # first run: reads everything
diskgoup duplicates ~     # second run: reuses the digests
```

A file that changed since it was hashed is hashed again.

### The work runs on several workers

Every stage of the pipeline reads and hashes files, and the work of one file is
mostly bookkeeping in Python — open, read, feed the hash, remember the result.
That is exactly what the GIL holds on to.

So the backend is chosen per stage:

| Stage size | Backend | Why |
|---|---|---|
| **≥ 2,000 files** | Processes (8 by default) | The work is Python bookkeeping; processes do not wait for the GIL. |
| **< 2,000 files** | Threads (4 by default) | Starting a process pool costs a moment — every worker of a frozen build unpacks the whole binary again. |

One pool serves the whole search: the workers start once and every stage uses
them. The jobs are handed over in chunks of 256, so a search of a million files
queues a few thousand jobs instead of a million.

If the process pool cannot start — a machine that does not allow a process of
its own — the search falls back to threads rather than failing.

### The reads are streamed

Files are read in 1 MiB chunks and fed straight into the hash. There is no
maximum searchable file size; the retained comparison buffer is not a limit on
what can be found.

## Controlling the workers

```bash
diskgoup duplicates ~ --jobs 16                        # explicit worker count
DISKGOUP_WORKERS=16 diskgoup duplicates ~              # same, via the environment
DISKGOUP_PROCESSES=0 diskgoup duplicates ~             # threads only
DISKGOUP_PROCESSES=1 diskgoup duplicates ~             # processes only
```

See [Environment variables](/reference/environment/).

## In the desktop app

The Duplicates tab runs the same search through the JSON-RPC bridge and shows
the groups as cards, with the copies of each group listed and the oldest one
marked as the keeper. The extra copies can be staged for cleanup from there —
they go through the same staged review flow as anything else.
