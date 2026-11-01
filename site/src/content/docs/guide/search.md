---
title: Searching
description: Filter a scan by name, path, extension, type, kind, date, size and age.
---

Search runs against the scan index, so searching a scanned volume does not
touch the disk again.

```bash
diskgoup search ~/Documents --name report --ext pdf --from 2024-01-01
```

## Conditions

Every condition applies **together** — the results satisfy all of them.

| Option | Meaning |
|---|---|
| `--name TEXT` | Match against the file name (case-insensitive substring). |
| `--in-path TEXT` | Match against the full path (case-insensitive substring). |
| `--ext EXT` | Extensions to include. Repeatable, and comma-separated lists work. |
| `--type any\|file\|folder` | Restrict to files or to folders. |
| `--kind KIND` | Restrict to a file kind. Repeatable. |
| `--from YYYY-MM-DD` | Modified on or after this date. |
| `--to YYYY-MM-DD` | Modified on or before this date. |
| `--min-size SIZE` | At least this large. |
| `--max-size SIZE` | At most this large. |
| `--min-age DAYS` | Only files older than this many days. |
| `--max-age DAYS` | Only files newer than this many days. |
| `--protected` | Only protected paths. |

Sizes are written the way you would say them: `100MB`, `2GB`, `1.5TB`, `1024`.
The suffixes are `B`, `KB`/`KiB`, `MB`/`MiB`, `GB`/`GiB`, `TB`/`TiB`, and they
are all 1024-based.

:::note
The **end date and the size limits are inclusive**. `--to 2024-12-31` includes
everything modified on that day, and `--min-size 100MB` includes a file of
exactly 100 MB.
:::

## Examples

Large videos from last year:

```bash
diskgoup search ~ --ext mp4 --ext mkv --min-size 2GB --from 2024-01-01
```

Everything that is not a document, older than a year:

```bash
diskgoup search ~ --type file --max-age 365 --kind document
```

Everything in a folder whose name contains "backup":

```bash
diskgoup search ~ --in-path backup
```

## Paging

Results come back **200 rows per page**:

```bash
diskgoup search ~ --name e --page 3 --limit 50
```

```
╭──────────┬──────────────────────────────┬──────────┬─────────┬────────────────────╮
│ Name     │ Path                         │ Type     │    Size │ Modified           │
╰──────────┴──────────────────────────────┴──────────┴─────────┴────────────────────╯
page 3 of 12 · 50 rows per page · 47 matching files only
```

The footer reports both the total number of matches and how many of them on
this page are files.

## JSON output

```bash
diskgoup --json search ~ --ext pdf
```

```json
{
  "scan": { "scan_id": 1, "…": "…" },
  "query": {
    "name": null,
    "path": null,
    "extensions": [".pdf"],
    "entry_type": "any",
    "kinds": [],
    "from_date": null,
    "to_date": null,
    "min_size": null,
    "max_size": null,
    "min_age_days": null,
    "max_age_days": null,
    "protected_only": false
  },
  "total": 812,
  "page": 1,
  "per_page": 200,
  "pages": 5,
  "matches": [
    {
      "path": "/Users/you/Documents/report.pdf",
      "name": "report.pdf",
      "is_dir": false,
      "size": 1048576,
      "on_disk": 1048576,
      "mtime": 1735689600.0,
      "kind": "document",
      "protected": false
    }
  ]
}
```

## Invalid queries

A query that cannot be satisfied is refused before the index is touched:

```
error: Enter a valid size range; minimum cannot exceed maximum.
error: Enter a valid date range (YYYY-MM-DD).
error: unknown entry type: fifo
```
