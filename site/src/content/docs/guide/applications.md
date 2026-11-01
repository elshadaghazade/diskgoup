---
title: Applications
description: List the applications installed on the machine, measure their footprint and uninstall them.
---

DiskGOup builds an inventory of the installed applications and the space they
occupy, and can uninstall them with the platform's own mechanism.

```bash
diskgoup apps list
```

```
142 applications · 38.4 GB
```

```
╭─────────────────────────────┬─────────┬─────────┬──────────────────────────────────┮
│ Name                        │ Version │    Size │ Path                             │
├─────────────────────────────┼─────────┼─────────┼──────────────────────────────────┤
│ Xcode                       │ 16.2    │ 12.1 GB │ /Applications/Xcode.app          │
│ Firefox                     │ 133.0   │  1.8 GB │ /Applications/Firefox.app        │
╰─────────────────────────────┴─────────┴─────────┴──────────────────────────────────╯
```

`--limit N` shows only the first N applications.

## How the inventory is built

Discovery is platform-native.

| Platform | Source | Notes |
|---|---|---|
| **macOS** | `.app` bundles in `/Applications` and `~/Applications` | The version is read from `Contents/Info.plist` (`CFBundleShortVersionString`, falling back to `CFBundleVersion`). |
| **Windows** | The `Uninstall` registry keys | `HKLM\…\Uninstall`, `HKLM\…\WOW6432Node\…\Uninstall`, `HKCU\…\Uninstall`. |
| **Linux** | `.desktop` entries in the XDG application directories | `$XDG_DATA_HOME/applications`, `/usr/share/applications`, `/usr/local/share/applications`, Flatpak exports. |

On macOS the size is the whole bundle, measured with the **allocated** size
rather than the logical one — the space the volume actually gives it.

The list is sorted by size, biggest first.

## Uninstalling

```bash
diskgoup apps uninstall "Firefox"
```

```
About to uninstall Firefox
  rm -rf "/Applications/Firefox.app"
Continue? [y/N]:
```

```
✔ Firefox moved to the Trash.
Inventory rechecked; shared data was not cleaned.
```

| Option | What it does |
|---|---|
| `--yes` / `-y` | Skip the confirmation prompt. |
| `--dry-run` | Show what would run, without doing it. |

The name is matched exactly first, then by case-insensitive substring.

### What actually happens

| Platform | Mechanism |
|---|---|
| **macOS** | The bundle is moved to the Trash via `send2trash`. |
| **Windows** | The registered `UninstallString` is run. |
| **Linux** | The `Exec` line from the `.desktop` entry is run. |
| **Anything else** | The path is removed directly. |

Afterwards the inventory is checked again — the same thing a real uninstall
does.

:::note
Shared data is **never** cleaned up. That is the uninstaller's business, not
DiskGOup's. An application that left settings behind in `~/Library/Preferences`
leaves them there.
:::

## JSON output

```bash
diskgoup --json apps list
```

```json
{
  "applications": [
    {
      "id": "/Applications/Xcode.app",
      "name": "Xcode",
      "path": "/Applications/Xcode.app",
      "size": 12998498999,
      "version": "16.2",
      "publisher": null,
      "uninstall_command": "rm -rf \"/Applications/Xcode.app\"",
      "source": "macos"
    }
  ],
  "total_size": 41234567890,
  "errors": []
}
```

`errors` carries the message when discovery failed on this machine — an empty
list means everything was read.

## In the desktop app

The Applications tab shows the same inventory with the footprint of each
application, and offers the uninstall action from the same place.
