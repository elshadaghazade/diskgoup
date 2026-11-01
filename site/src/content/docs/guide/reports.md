---
title: Reports
description: The weekly HTML report and the file-type CSV export.
---

DiskGOup can turn a scan into a report you keep, mail or attach.

## The weekly report

```bash
diskgoup reports weekly --output report.html
```

```
✔ wrote report.html
```

The HTML report answers the question the tool exists for — *why is the disk
full?* — by showing, per file kind:

- the **current** size,
- the **growth** since the baseline snapshot,
- the **share** of the scanned bytes,

plus the totals, the file and folder counts, the twenty largest folders and
the volume the scan covered.

The template is a Jinja2 template (`diskgoup/templates/weekly.html.j2`), and
the HTML is self-contained — no external assets, no fonts to fetch.

Without `--output` the HTML is printed to the terminal:

```bash
diskgoup reports weekly
```

### When there is no history

The growth column needs a baseline snapshot at least seven days old. Without
one, the report still renders — it shows the current usage and says that
there is nothing to compare against. See
[Snapshots](/guide/snapshots/).

## The file-type report

```bash
diskgoup reports types --output types.csv
```

```
kind,files,size_bytes,size_human,share_percent
video,1204,24037599744,22.38 GB,50.41
cache,48120,9766921728,9.09 GB,20.49
document,8331,4080218931,3.80 GB,8.57
total,182441,47672225792,44.40 GB,100.00
```

The rows are sorted by size, biggest first, and the last row is the total.

## Options

Both commands accept:

| Option | What it does |
|---|---|
| `--output FILE` / `-o` | Write to a file. Without it, the report is printed. |
| `--scan-id N` | Report on a specific scan instead of the latest one. |

## JSON output

```bash
diskgoup --json reports weekly
diskgoup --json reports types
```

The payload carries the same content as the file — `"html"` for the weekly
report, `"csv"` for the type report. The desktop app uses it to render the
report in a pane instead of writing a file.

## In the desktop app

The Reports tab shows both reports in place: the weekly report rendered as
HTML, and the CSV with a copy button and a download.
