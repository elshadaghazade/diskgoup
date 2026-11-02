---
title: CLI reference
description: Every DiskGOup command, its flags and its output.
---

Every command lives under one binary, `diskgoup`. Run `diskgoup --help` for the
list, and `diskgoup <command> --help` for the details.

## Global options

These are accepted before the command:

| Option | What it does |
|---|---|
| `--json` | Emit machine-readable JSON instead of formatted output. |
| `--version` | Print the version and exit. |
| `-h`, `--help` | Show the help for the command. |
| `--install-completion` | Install shell completion for the current shell. |
| `--show-completion` | Show the completion script, to copy or customise. |

:::tip
`--json` is the contract the desktop app builds on, and it is the easiest way
to script DiskGOup from a shell. Every command supports it.
:::

## The commands

| Command | What it does |
|---|---|
| [`drives`](#drives) | List the mounted volumes of this machine. |
| [`scan`](#scan) | Scan a drive or folder and store the result in the index. |
| [`refresh`](#refresh) | Walk one folder of a scan again and correct the index. |
| [`scans`](#scans) | List and prune the scans stored in the index. |
| [`tree`](#tree) | Show the folder tree of a scan. |
| [`sizes`](#sizes) | Rank the largest folders and files in a scan. |
| [`types`](#types) | Show the file-type breakdown of a scan. |
| [`treemap`](#treemap) · [`sunburst`](#treemap) · [`flame`](#treemap) · [`bubbles`](#treemap) · [`mindmap`](#treemap) | Draw a spatial view of a scan. |
| [`age`](#age) | Show how the scan's files are distributed by modification age. |
| [`search`](#search) | Search a scan by name, path, extension, type, date and size. |
| [`duplicates`](#duplicates) | Find files with identical content. |
| [`cleanup`](#cleanup) | Stage, review and safely remove files. |
| [`archives`](#archives) | Browse archives without extracting them. |
| [`snapshots`](#snapshots) | Record size snapshots and compare them over time. |
| [`reports`](#reports) | Generate reports from a scan. |
| [`games`](#games) | Discover and measure installed games. |
| [`apps`](#apps) | List installed applications and their footprint. |
| [`monitor`](#monitor) | Watch live disk and network usage. |
| [`reset`](#reset) | Delete the scan index and start over with an empty one. |
| [`serve`](#serve) | Run the JSON-RPC server on stdin/stdout. |

---

## drives

```bash
diskgoup drives
```

Lists the mounted volumes of this machine.

| Platform | How the volumes are found |
|---|---|
| Windows | The drive letters `A:`–`Z:` that exist. |
| macOS | The APFS containers, collapsed to one row each — the sealed system volume, the data volume and the helper volumes are one disk to the user. |
| Linux | The mounted partitions, plus the extra mounts under `/Volumes` and `/media`. |

Each row shows the mount point, the device, the filesystem type, the total,
used and free space, and the percentage used.

## scan

```bash
diskgoup scan PATH
```

Walks a tree once and writes every entry into the SQLite index.

| Option | Default | What it does |
|---|---|---|
| `--follow-symlinks` / `--no-follow-symlinks` | off | Follow symlinked directories. Off by default, so a link loop cannot trap the walk. |
| `--include-hidden` / `--no-include-hidden` | on | Include dot-files and hidden entries. |
| `--exclude PATTERN` | – | Skip entries whose name or path matches the glob. Repeatable. |
| `--max-depth N` | unlimited | Stop descending below `N` levels. |
| `--profile` / `--no-profile` | off | Print a timing breakdown of the run. |

`PATH` is required. `~` is expanded.

## refresh

```bash
diskgoup refresh PATH
```

Walks one folder of a scan again and corrects the index in place. The totals
of the folders above it are corrected by the difference, so the whole scan
keeps telling the truth without being walked again.

| Option | What it does |
|---|---|
| `--scan-id N` | Refresh this scan. Without it, the scan that covers the path is found. |
| `--force` | Refresh even when nothing changed. |

Without `--force`, a folder whose modification time still matches the scan is
left alone.

## scans

```bash
diskgoup scans              # list every scan in the index
diskgoup scans remove 3     # delete scan #3 and everything recorded for it
```

A scan that was stopped early is shown as `partial`.

## tree

```bash
diskgoup tree PATH
```

| Option | Default | What it does |
|---|---|---|
| `--depth N` | 2 | How many levels to expand. |
| `--scan-id N` | – | Use a specific scan. |
| `--rescan` / `--no-rescan` | off | Rescan before drawing. |

Protected folders are marked in the tree.

## sizes

```bash
diskgoup sizes PATH
```

| Option | Default | What it does |
|---|---|---|
| `--limit N` | 25 | How many entries to show. |
| `--folders` / `--no-folders` | on | Include folders in the ranking. |
| `--files` / `--no-files` | on | Include files in the ranking. |
| `--scan-id N` | – | Use a specific scan. |
| `--rescan` / `--no-rescan` | off | Rescan before drawing. |

## types

```bash
diskgoup types PATH
```

The file-type breakdown, in the fixed order game → video → archive → document →
cache → application → audio → image → code → system → other.

| Option | Default | What it does |
|---|---|---|
| `--scan-id N` | – | Use a specific scan. |
| `--rescan` / `--no-rescan` | off | Rescan before drawing. |

## treemap, sunburst, flame, bubbles, mindmap

```bash
diskgoup treemap PATH
```

The five spatial views take the same options:

| Option | Default | What it does |
|---|---|---|
| `--width PIXELS` | 1200 | Canvas width. |
| `--height PIXELS` | 800 | Canvas height. |
| `--depth N` | 3 | How many levels to expand. |
| `--output FILE` / `-o` | – | Write an SVG file instead of printing a table. |
| `--scan-id N` | – | Use a specific scan. |
| `--rescan` / `--no-rescan` | off | Rescan before drawing. |

Without `--output` and without `--json`, a summary table is printed. With
`--json`, the computed geometry is returned for the GUI to draw.

## age

```bash
diskgoup age PATH
```

| Option | Default | What it does |
|---|---|---|
| `--scan-id N` | – | Use a specific scan. |
| `--rescan` / `--no-rescan` | off | Rescan before drawing. |

Seven buckets: last 7 days, 30 days, 3 months, 6 months, a year, two years,
and everything older.

## search

```bash
diskgoup search PATH [conditions]
```

| Option | Default | What it does |
|---|---|---|
| `--name TEXT` | – | Match against the file name. |
| `--in-path TEXT` | – | Match against the full path. |
| `--ext EXT` | – | Extensions to include. Repeatable. |
| `--type any\|file\|folder` | any | Restrict to files or folders. |
| `--kind KIND` | – | Limit to a file kind. Repeatable. |
| `--from YYYY-MM-DD` | – | Start date, inclusive. |
| `--to YYYY-MM-DD` | – | End date, inclusive. |
| `--min-size SIZE` | – | Minimum size, inclusive. |
| `--max-size SIZE` | – | Maximum size, inclusive. |
| `--min-age DAYS` | – | Only files older than this many days. |
| `--max-age DAYS` | – | Only files newer than this many days. |
| `--protected` / `--no-protected` | off | Only protected paths. |
| `--page N` | 1 | Page number, 1-based. |
| `--limit N` | 200 | Rows per page. |
| `--scan-id N` | – | Use a specific scan. |
| `--rescan` / `--no-rescan` | off | Rescan before searching. |

Every condition applies together. Sizes accept `100MB`, `2GB`, `1.5TB`,
`1024`.

## duplicates

```bash
diskgoup duplicates PATH
```

| Option | Default | What it does |
|---|---|---|
| `--min-size BYTES` | 1 | Ignore files smaller than this many bytes. |
| `--max-size BYTES` | – | Ignore files larger than this many bytes. |
| `--kind KIND` | – | Only consider files of this kind. |
| `--limit N` | 0 (all) | Show at most this many groups. |
| `--scan-id N` | – | Use a specific scan. |
| `--rescan` / `--no-rescan` | off | Rescan before searching. |
| `--jobs N` | 0 (automatic) | How many workers read and hash the files. |

Content is verified with SHA-256 **and** an exact byte comparison. Equal names
or sizes alone are never treated as proof.

## cleanup

```bash
diskgoup cleanup stage PATH [PATH...]
diskgoup cleanup list
diskgoup cleanup remove PATH [PATH...]
diskgoup cleanup clear
diskgoup cleanup validate
diskgoup cleanup commit
```

| Sub-command | What it does |
|---|---|
| `stage` | Add files or folders to the review list. Protected paths are refused with a reason. |
| `list` | Show the review list and its total size. |
| `remove` | Take items back off the review list. |
| `clear` | Empty the review list. |
| `validate` | Check that every staged item is still safe to remove. |
| `commit` | Move the reviewed items to the recycle bin. |

`commit` takes:

| Option | What it does |
|---|---|
| `--yes` / `-y` | Skip the confirmation prompt. |
| `--permanent` | Delete permanently instead of using the recycle bin. |

Every sub-command accepts `--scan-id N` to act on a specific scan.

## archives

```bash
diskgoup archives list PATH
diskgoup archives show ARCHIVE
diskgoup archives preview ARCHIVE MEMBER
```

| Sub-command | Options |
|---|---|
| `list` | `--scan-id N`, `--rescan` — finds the `.zip` files of a scan. |
| `show` | `--prefix PREFIX` — browse inside a folder of the archive. |
| `preview` | – — shows the first 64 KiB of a text file, never extracting it. |

## snapshots

```bash
diskgoup snapshots save
diskgoup snapshots list
diskgoup snapshots remove SNAPSHOT_ID
diskgoup snapshots compare
```

| Sub-command | Options |
|---|---|
| `save` | `--label TEXT`, `--scan-id N` |
| `list` | `--scan-id N` |
| `remove` | – |
| `compare` | `--scan-id N`, `--min-age-days N` (default 7) |

## reports

```bash
diskgoup reports weekly
diskgoup reports types
```

| Sub-command | Options |
|---|---|
| `weekly` | `--output FILE` / `-o`, `--scan-id N` — the HTML report. |
| `types` | `--output FILE` / `-o`, `--scan-id N` — the CSV report. |

## games

```bash
diskgoup games list
```

| Option | What it does |
|---|---|
| `--platform TEXT` | Filter by platform, e.g. `Steam` or `Epic Games`. |
| `--limit N` | Limit the chart to this many games; the rest becomes "Other". |

## apps

```bash
diskgoup apps list
diskgoup apps uninstall NAME
```

| Sub-command | Options |
|---|---|
| `list` | `--limit N` |
| `uninstall` | `--yes` / `-y`, `--dry-run` |

## monitor

```bash
diskgoup monitor watch
diskgoup monitor sample
```

| Sub-command | Options |
|---|---|
| `watch` | `--interval SECONDS` (2), `--count N` (0 = forever), `--processes N` (0) |
| `sample` | – |

## reset

```bash
diskgoup reset [--yes]
```

Deletes the scan index and writes a new, empty one in its place. This is the
way out of an index that is corrupted or stuck: the old database — and the
SQLite files beside it — are removed first, so a file that cannot even be
opened is replaced all the same.

Every scan goes with it: the scans, their entries, their snapshots and the
staged list. **No file on your disk is deleted** — the next scan reads it
again.

| Option | What it does |
|---|---|
| `--yes` / `-y` | Skip the confirmation prompt. |

The configuration file is removed with it, so the app starts from its
defaults.

## serve

```bash
diskgoup serve [--quiet]
```

Runs the JSON-RPC server on stdin/stdout. This is what the desktop app talks
to. See [JSON-RPC protocol](/reference/json-rpc/).

| Option | What it does |
|---|---|
| `--quiet` | Suppress the startup banner. The banner goes to stderr anyway — stdout is reserved for protocol traffic. |
