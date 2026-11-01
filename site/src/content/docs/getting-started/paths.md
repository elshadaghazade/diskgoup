---
title: Where things are stored
description: The directories DiskGOup uses for the scan index, configuration and application state.
---

DiskGOup keeps three kinds of data apart, each in the directory the platform
convention reserves for it. The locations come from
[`platformdirs`](https://pypi.org/project/platformdirs/), so they follow the
rules of the operating system rather than a hard-coded path.

## The three directories

| Directory | Holds | macOS | Linux | Windows |
|---|---|---|---|---|
| **data** | application state | `~/Library/Application Support/diskgoup` | `~/.local/share/diskgoup` | `%LOCALAPPDATA%\diskgoup` |
| **cache** | the scan index — regenerable | `~/Library/Caches/diskgoup` | `~/.cache/diskgoup` | `%LOCALAPPDATA%\diskgoup\Cache` |
| **config** | user-editable configuration | `~/Library/Application Support/diskgoup` | `~/.config/diskgoup` | `%APPDATA%\diskgoup` |

The scan index lives in the **cache** directory on purpose: it is derived data.
Delete it and the next scan rebuilds it. Nothing else in DiskGOup keeps state
that cannot be recomputed.

## The scan index

```
<cache>/diskgoup/index.db
```

One SQLite file holds every scan ever taken, together with their entries,
skipped-entry notices, SHA-256 digests, size snapshots and the staged review
list. See [The scan index](/reference/scan-index/) for the schema.

The path can be overridden with the `DISKGOUP_INDEX` environment variable —
useful for keeping a scratch index out of the way while experimenting:

```bash
DISKGOUP_INDEX=/tmp/diskgoup-scratch.db diskgoup scan ~
```

## Configuration

```
<config>/diskgoup/config.json
```

The file is created on demand and is optional — every setting has a working
default, and the CLI reads nothing from it today. It exists so that settings
have a home when they need one.

## The desktop app

The Electron app keeps no settings of its own beyond what the platform stores
for the app itself. The CLI child process inherits the environment, so
`DISKGOUP_INDEX` and friends work the same way under the GUI.

## Removing everything

```bash
rm -rf "$(python3 -c 'from platformdirs import user_cache_dir; print(user_cache_dir("diskgoup"))')"
```

That deletes the scan index and nothing else. The application's data directory
holds no user content — it exists so that other state has a place to live.
