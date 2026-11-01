---
title: Explore views
description: The eight ways DiskGOup projects one scan — tree, sizes, types, treemap, sunburst, flame, bubbles, mind map and age.
---

Every Explore view is a **different projection of the same scan**. None of them
touches the disk: the tree, the treemap, the search and the reports all read
the same SQLite index.

## The eight views

| View | Command | What it answers |
|---|---|---|
| Folders | `diskgoup tree` | What is inside, and how big is each folder? |
| Top sizes | `diskgoup sizes` | What is taking the most room? |
| File types | `diskgoup types` | What *kind* of content is it? |
| Treemap | `diskgoup treemap` | Where is the space, in proportion? |
| Sunburst | `diskgoup sunburst` | How does the space nest? |
| Flame | `diskgoup flame` | What does the hierarchy look like as an icicle? |
| Bubbles | `diskgoup bubbles` | How many distinct things share the space? |
| Mind map | `diskgoup mindmap` | What hangs off the big branches? |
| Age map | `diskgoup age` | How old is it all? |

## Folder tree

```bash
diskgoup tree ~/Documents --depth 3
```

```
Documents 1.2 GB · 4,120 files
├── Reports [protected] 890 MB
│   ├── 2024 612 MB
│   └── 2025 278 MB
└── Projects 310 MB
```

`--depth` controls how many levels are expanded. Protected folders are marked.

## Top sizes

```bash
diskgoup sizes ~ --limit 15
```

```
╭────┬────────────────────────────┬──────────┬─────────┬────────╮
│  # │ Name                       │ Kind     │    Size │  Share │
├────┼────────────────────────────┼──────────┼─────────┼────────┤
│  1 │ Downloads                  │ other    │ 12.9 GB │ 29.1%  │
│  2 │ Library                    │ cache    │  8.4 GB │ 18.9%  │
╰────┴────────────────────────────┴──────────┴─────────┴────────╯
```

Folders and files are ranked together by default. Use `--no-folders` or
`--no-files` to restrict the ranking to one of them.

## File types

```bash
diskgoup types ~
```

```
╭───────────────┬─────────┬─────────┬────────┬────────────────────────┐
│ Type          │  Files  │    Size │  Share │ Bar                    │
├───────────────┼─────────┼─────────┼────────┼────────────────────────┤
│ ● video       │   1,204 │ 22.4 GB │ 50.4%  │ ███████████████       │
│ ● cache       │  48,120 │  9.1 GB │ 20.5%  │ ██████                 │
│ ● document    │   8,331 │  3.8 GB │  8.6%  │ ███                     │
├───────────────┼─────────┼─────────┼────────┼────────────────────────┤
│ Total         │         │ 44.5 GB │ 100.0% │                        │
╰───────────────┴─────────┴─────────┴────────┴────────────────────────╯
```

The order is fixed — game, video, archive, document, cache, application, audio,
image, code, system, other — so two scans are comparable at a glance.

## The spatial views

Five views draw the same layout in different geometries. All of them accept the
same options:

| Option | Default | What it does |
|---|---|---|
| `--width` | 1200 | Canvas width in pixels |
| `--height` | 800 | Canvas height in pixels |
| `--depth` | 3 | How many levels to expand |
| `--output FILE` | – | Write an SVG file instead of printing a table |
| `--scan-id N` | – | Read a specific scan |
| `--rescan` | off | Walk the tree again first |

### Treemap

```bash
diskgoup treemap ~ --output treemap.svg
```

Squarified rectangles: each item's area is proportional to its size, and the
layout keeps the aspect ratio of each tile close to 1 so large items stay
readable instead of turning into slivers. This is the classic disk-usage
picture.

### Sunburst

```bash
diskgoup sunburst ~ --output sunburst.svg
```

Radial arcs — one ring per level of the tree. The angle of a sector is
proportional to its share of the parent.

### Flame

```bash
diskgoup flame ~ --output flame.svg
```

An icicle: depth runs down the vertical axis, cumulative size runs across the
horizontal one. It reads like a flame graph, which makes the hierarchy of
*what contains what* obvious.

### Bubbles

```bash
diskgoup bubbles ~ --output bubbles.svg
```

One circle per leaf, sized by area and packed without overlaps. The circles
are placed on a golden-angle spiral and then pushed apart, so the result is
deterministic — the same scan always draws the same picture.

### Mind map

```bash
diskgoup mindmap ~ --output mindmap.svg
```

A radial hub with straight links: the root in the middle, the big branches
around it, each branch's own subtree fanned out inside its wedge.

## Age map

```bash
diskgoup age ~
```

```
╭──────────────┬─────────┬─────────┬────────┬────────────────────────┐
│ Age          │  Files  │    Size │  Share │ Bar                    │
├──────────────┼─────────┼─────────┼────────┼────────────────────────┤
│ Last 7 days  │   1,204 │  2.1 GB │  4.7%  │ █                     │
│ Last 30 days │   8,120 │  9.4 GB │ 21.1%  │ ██████                │
│ Last 3 months│  12,004 │ 14.2 GB │ 31.9%  │ ██████████            │
│ Older        │  41,220 │ 18.8 GB │ 42.3%  │ █████████████         │
╰──────────────┴─────────┴─────────┴────────┴────────────────────────┯
```

Seven buckets: last 7 days, 30 days, 3 months, 6 months, a year, two years,
and everything older. Files whose modification time could not be read land in
the oldest bucket — the honest place for them, since they are the ones most
likely to be stale.

## Output formats

Every view can answer in three ways:

- **A table** (the default) — a human-readable summary.
- **JSON** (`--json`) — the computed geometry, which is what the desktop app
  draws.
- **An SVG** (`--output file.svg`) — a standalone file.

```bash
diskgoup --json treemap ~ --depth 2
```

```json
{
  "scan": { "scan_id": 1, "root": "/Users/you", "…": "…" },
  "view": "treemap",
  "items": [
    {
      "path": "/Users/you/Downloads",
      "name": "Downloads",
      "size": 13893660416,
      "kind": "other",
      "depth": 1,
      "color": "#6c8cff",
      "rect": { "x": 0, "y": 0, "width": 1200, "height": 800 }
    }
  ]
}
```

## Colours

A folder is coloured by **the kind that dominates its contents**, not by its
own name. A folder full of videos shows up as video rather than as an
anonymous "other" bucket.

| Kind | Colour |
|---|---|
| game | magenta |
| video | red |
| archive | yellow |
| document | cyan |
| cache | green |
| application | blue |
| audio | bright magenta |
| image | bright cyan |
| code | bright black |
| system | bright black |
| other | white |
