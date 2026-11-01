---
title: Environment variables
description: The environment variables DiskGOup reads, and what they change.
---

DiskGOup reads three environment variables of its own. Everything else it
reads is a platform convention that other programs use too.

## DiskGOup's own

| Variable | What it does |
|---|---|
| `DISKGOUP_INDEX` | The path of the SQLite index. Overrides the platform default. |
| `DISKGOUP_WORKERS` | How many workers a parallel run uses. |
| `DISKGOUP_PROCESSES` | Chooses the parallel backend: `1` for processes, `0` for threads. |

### `DISKGOUP_INDEX`

```bash
export DISKGOUP_INDEX=~/tmp/diskgoup-index.db
```

The index goes here instead of the platform cache directory. Useful for
keeping a separate index per project, or for a throwaway index in a test.

The parent directory has to exist.

### `DISKGOUP_WORKERS`

```bash
export DISKGOUP_WORKERS=16
```

The number of workers used by the [duplicate finder](/guide/duplicates/).
Without it, the default depends on the backend: **4** threads or **8**
processes.

The value must be a positive number. Anything else is ignored and the
default is used.

### `DISKGOUP_PROCESSES`

```bash
export DISKGOUP_PROCESSES=1   # always use processes
export DISKGOUP_PROCESSES=0   # always use threads
```

By default the backend is chosen by the size of the job:

| Number of files | Backend | Why |
|---|---|---|
| Fewer than 2000 | **Threads** (4) | Starting processes costs more than it saves. Every worker of a frozen build has to unpack the whole binary again. |
| 2000 or more | **Processes** (8) | The work of one file is mostly bookkeeping in Python, which is what the GIL holds on to. Processes do not wait for the GIL at all. |

Setting the variable overrides the choice in both directions.

:::caution
`DISKGOUP_PROCESSES=1` on a **frozen** build (the packaged binary) makes every
worker unpack the whole executable before it can work. On a handful of files
that is slower than doing the work inline. Use it when the search is big.
:::

## The platform conventions

DiskGOup reads these because the operating system defines them. They are not
DiskGOup's, and setting them changes every program on the machine.

| Variable | Platform | What it does |
|---|---|---|
| `LOCALAPPDATA` | Windows | Where the Steam library and the Windows index live. |
| `XDG_DATA_HOME` | Linux | Where the Linux application data is looked for. |

## Precedence

Where several things could decide the same question, the order is always the
same: **an explicit flag, then the environment, then the default.**

```
diskgoup duplicates . --jobs 16     # the flag wins
DISKGOUP_WORKERS=16 diskgoup duplicates .
                                      # the environment is used
diskgoup duplicates .                # the default is used
```

The same order applies to the index path: an explicit path on the command
line, then `DISKGOUP_INDEX`, then the platform default.

## Checking what is in effect

```bash
diskgoup --version
```

The startup banner shows the index path it opened. To see the platform
default without running a scan:

```bash
python -c "from diskgoup.paths import default_index_path; print(default_index_path())"
```
