---
title: Snapshots
description: Record the size of a scan over time and find out which category grew.
---

A snapshot records the size of every file kind at a point in time. Comparing
the current scan against a snapshot taken at least seven days earlier gives
the "why is the disk full?" answer: which category grew, and by how much.

## Saving a snapshot

```bash
diskgoup snapshots save --label "before the video project"
```

```
✔ snapshot saved: before the video project
```

The label defaults to `Snapshot <timestamp>`.

## Listing snapshots

```bash
diskgoup snapshots list
```

```
╭────┬──────────────────────────────┬─────────┬────────────────────┮
│ ID │ Label                        │  Total  │ Taken              │
├────┼──────────────────────────────┼─────────┼────────────────────┤
│  2 │ before the video project     │ 38.4 GB │ 2025-01-04 11:20   │
│  1 │ Snapshot 1735689600          │ 36.1 GB │ 2024-12-28 09:02   │
╰────┴──────────────────────────────┴─────────┴────────────────────╯
```

```bash
diskgoup snapshots remove 1
```

## Comparing

```bash
diskgoup snapshots compare
```

```
7-day change: up 2.4 GB (6.6%)
```

```
╭───────────┬─────────┬─────────┬─────────────┐
│ Type      │ Current │ Growth  │ Usage share │
├───────────┼─────────┼─────────┼─────────────┤
│ video     │ 22.4 GB │ +2.1 GB │      50.4%  │
│ cache     │  9.1 GB │ +180 MB │      20.5%  │
│ document  │  3.8 GB │ −40 MB  │       8.6%  │
╰───────────┴─────────┴─────────┴─────────────╯
```

Three numbers are compared:

- **Growth** is measured against the **previous size of that category**.
- **Usage share** is measured against **total scanned bytes**.
- Files inside cache and log folders count **only** in that group, so they are
  never counted twice.

### The seven-day rule

Growth needs a baseline: a snapshot of the same drive that is **at least seven
days old**. Without one, DiskGOup shows the current usage and says so:

```
No comparable history. Growth requires a file-type report for the same drive at least 7 days earlier. Current usage is shown below.
```

The rule exists because a snapshot taken yesterday measures noise — a download
that finished, a cache that happened to be empty.

`--min-age-days N` changes the window:

```bash
diskgoup snapshots compare --min-age-days 30
```

## JSON output

```bash
diskgoup --json snapshots compare
```

```json
{
  "has_history": true,
  "baseline": {
    "id": 1,
    "scan_id": 1,
    "label": "Snapshot 1735689600",
    "created_at": 1735689600.0,
    "total_size": 38769321984,
    "total_on_disk": 36175872000,
    "kinds": { "video": 20237599744, "cache": 9027411968, "document": 4080218931 }
  },
  "total_current": 44123456789,
  "total_baseline": 38769321984,
  "total_growth": 5354134805,
  "changes": [
    {
      "kind": "video",
      "current": 22400000000,
      "baseline": 20237599744,
      "growth": 2162400256,
      "growth_percent": 10.69,
      "share": 0.504
    }
  ]
}
```

## In practice

The workflow that makes growth useful:

```bash
# once a week, on the same drive
diskgoup scan ~ --rescan
diskgoup snapshots save --label "weekly $(date +%F)"
```

Then, whenever the disk feels full:

```bash
diskgoup snapshots compare
```

The weekly report ([Reports](/guide/reports/)) renders the same comparison as
a page you can keep or mail.
