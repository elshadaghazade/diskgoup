---
title: Archives
description: Look inside ZIP archives without extracting them.
---

DiskGOup can browse an archive **without extracting it**. Nothing is written
to disk and nothing is executed.

## Finding archives

```bash
diskgoup archives list ~/Downloads
```

```
╭────────────────────────────┬──────────────────────────────────────────┬─────────╮
│ Name                       │ Path                                     │    Size │
├────────────────────────────┼──────────────────────────────────────────┼─────────┤
│ backups-2024.zip           │ /Users/you/Downloads/backups-2024.zip    │ 1.2 GB  │
╰────────────────────────────┴──────────────────────────────────────────┴─────────╯
```

The listing comes from the scan index, so it is instant. Only `.zip` files are
listed.

## Listing the contents

```bash
diskgoup archives show ~/Downloads/backups-2024.zip
```

```
backups-2024.zip · 1,204 items · 4.8 GB uncompressed · 1.2 GB compressed
```

```
╭───────────────────────────────┬───────────────┬─────────────┬────────╮
│ Path                          │ Uncompressed  │  Compressed │  Ratio │
├───────────────────────────────┼───────────────┼─────────────┼────────╤
│ documents/                    │       —       │      —      │   0%   │
│ documents/report.pdf          │      2.1 MB   │   612 KB    │  29%   │
│ documents/notes.txt           │      14.0 KB  │   4.1 KB    │  29%   │
╰───────────────────────────────┴───────────────┴─────────────┴────────╯
```

Both sizes are reported: the **uncompressed** size (what the archive would
occupy once extracted) and the **compressed** size (what it occupies now). The
ratio says how well the archive compresses.

### Browsing a folder inside the archive

```bash
diskgoup archives show ~/Downloads/backups-2024.zip --prefix documents/
```

```
Parent archive folder: /
```

## Previewing a file

```bash
diskgoup archives preview ~/Downloads/backups-2024.zip documents/notes.txt
```

The preview is the **first 64 KiB** of the file, decoded as UTF-8. Nothing is
extracted to read it.

```
Partial preview: showing the first 64 KiB.
```

Some things cannot be previewed as text:

| Case | What happens |
|---|---|
| Binary content | `Binary or encrypted content cannot be previewed as text.` |
| Encrypted entry | `Binary or encrypted content cannot be previewed as text.` |
| Empty file | `(Empty file)` |
| Entry not in the archive | `Entry not found in archive.` |

Binary content is detected by a NUL byte in the first 4 KiB.

## The rules

- The browser is **read-only**. A sample archive is never extracted and never
  run.
- Text previews are limited to **64 KiB**.
- HTML is shown as plain text too.
- Both the uncompressed and the compressed size are reported.
- Entries with invalid names are skipped, and the listing is marked
  **partial**:

```
invalid names skipped; listing is partial.
```

## JSON output

```bash
diskgoup --json archives show ~/Downloads/backups-2024.zip
```

```json
{
  "path": "/Users/you/Downloads/backups-2024.zip",
  "items": 1204,
  "uncompressed": 5153960755,
  "compressed": 1288490188,
  "partial": false,
  "error": null,
  "entries": [
    {
      "name": "documents/report.pdf",
      "is_dir": false,
      "size": 2202009,
      "compressed": 626688,
      "ratio": 0.2846,
      "encrypted": false
    }
  ]
}
```
