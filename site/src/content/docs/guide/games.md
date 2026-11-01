---
title: Games
description: Discover Steam and Epic libraries, measure what each game occupies and see which folders are protected.
---

DiskGOup discovers the locally installed games from their launchers' own
manifests and measures what each one occupies.

```bash
diskgoup games list
```

```
Steam · 24 games · 187.4 GB
```

```
╭───────────────────────────────┬─────────┬─────────────────────────────────────┐
│ Game                          │   Size  │ Categories                          │
├───────────────────────────────┼─────────┼─────────────────────────────────────┤
│ Portal 2                      │ 12.4 GB │ Game files 12.4 GB                   │
├───────────────────────────────┼─────────┼─────────────────────────────────────┤
│ Cities: Skylines              │ 31.8 GB │ Game files 31.8 GB                   │
╰───────────────────────────────┴─────────┴─────────────────────────────────────┯
```

| Option | What it does |
|---|---|
| `--platform TEXT` | Filter by platform — `Steam` or `Epic Games`. The match is a case-insensitive substring. |
| `--limit N` | Print chart data for the N biggest games; the rest is aggregated as `Other`. |

## How discovery works

### Steam

- `steamapps/libraryfolder.vdf` lists the library roots. The file is Valve's
  KeyValues format; DiskGOup reads the `"path"` values out of it directly
  rather than pulling in a VDF parser.
- Each library holds `steamapps/common/<Game>` — one directory per installed
  title.
- `appmanifest_<appid>.acf` carries the real install directory and the display
  name of each installed title.

Steam is looked for in the platform's usual places:

| Platform | Locations |
|---|---|
| macOS | `~/Library/Application Support/Steam` |
| Windows | `%ProgramFiles%\Steam`, `%ProgramFiles(x86)%\Steam`, `%LOCALAPPDATA%\Steam` |
| Linux | `~/.steam/steam`, `~/.local/share/Steam`, `~/.var/app/com.valvesoftware.Steam/.local/share/Steam` |

### Epic Games

Each installed title is a directory under the launcher root, which is
`~/Library/Application Support/Epic` on macOS, `%ProgramFiles%\Epic Games` on
Windows and `~/.local/share/Epic` on Linux. The launcher's own directory is
skipped.

## Categories

Within an installation, standard directory names are classified:

| Category | Matches | Protected |
|---|---|---|
| **Game files** | the installation root | ✅ |
| **DLC** | `DLC`, `dlc`, `expansion`, `expansions` | ✅ |
| **Mods** | `Mods`, `mod`, `modding` | — |
| **Saved games** | `Saved Games`, `Saves`, `Savegames` | ✅ |
| **Screenshots** | `Screenshots` | — |

Only the **top level** of the installation decides the category; everything
below it belongs to that category. The "Game files" category holds whatever is
not in a named sub-category.

:::caution
**Measured game size is not reclaimable space.** Game files, DLC and saved
games are protected from cleanup — removing them does not free anything you
can get back, and a save is not yours to throw away. The `games list` command
says so at the end of its output:

```
Measured game size is not reclaimable space. Saves and game files are protected.
```
:::

## What cannot be inferred

External save locations and mod-manager directories cannot be inferred from
the installation — the launcher does not record where they point. They have to
be associated explicitly. This is the same limitation the original DiskBOX
has.

## JSON output

```bash
diskgoup --json games list
```

```json
{
  "libraries": [
    {
      "platform": "Steam",
      "root": "/Users/you/Library/Application Support/Steam",
      "size": 201222406656,
      "games": [
        {
          "name": "Portal 2",
          "platform": "Steam",
          "path": "/Users/you/Library/Application Support/Steam/steamapps/common/Portal 2",
          "size": 13314304000,
          "files": 4821,
          "app_id": "620",
          "protected": true,
          "categories": [
            { "category": "Game files", "size": 13314304000, "files": 4821, "protected": true }
          ]
        }
      ]
    }
  ],
  "total_size": 201222406656,
  "game_count": 24
}
```
