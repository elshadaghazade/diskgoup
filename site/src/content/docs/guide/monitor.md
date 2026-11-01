---
title: Live monitor
description: Watch the machine's disk and network throughput, and the processes using them.
---

The monitor samples the machine's I/O rates and the processes behind them.

```bash
diskgoup monitor sample
```

```
network ↓ 0 B/s · ↑ 12.4 KB/s · disk read 1.2 MB/s · write 88.1 KB/s · used 121.4 GB
```

## Watching

```bash
diskgoup monitor watch --interval 1 --processes 5
```

```
╭───────────────╮
│ Sample 3      │
├───────────────┤
│ Network ↓     │   14.2 KB/s
│ Network ↑     │  102.4 KB/s
│ Disk read     │   1.2 MB/s
│ Disk write    │   88.1 KB/s
│ Disk used     │ 121.4 GB (25%)
╰───────────────╯
```

| Option | Default | What it does |
|---|---|---|
| `--interval SECONDS` | 2.0 | Seconds between samples. |
| `--count N` | 0 (forever) | Number of samples to take. |
| `--processes N` | 0 | Show the top N processes by memory. |

`--count 0` runs until interrupted.

## How the rates are measured

The readings are **sampled**, not counted: the first call establishes a
baseline and every later call reports the **delta** since the previous one.
That is what makes a *rate* rather than a total.

The counters come from [`psutil`](https://pypi.org/project/psutil/):

| Metric | Source |
|---|---|
| Network ↓ / ↑ | `psutil.net_io_counters()` — bytes received / sent |
| Disk read / write | `psutil.disk_io_counters()` — bytes read / written |
| Disk used / total | `psutil.disk_usage()` for the home directory |

On a platform that does not expose the network or disk counters, the sample
comes back with zeroes rather than failing.

## Processes

```bash
diskgoup monitor watch --processes 5
```

```
╭────────────────────────────────────────────────────────────╮
│ Processes                                                │
├──────┬─────────────────┬─────────┬──────────┬─────────────┤
│  PID │ Name            │  CPU %  │  Memory  │             │
├──────┼─────────────────┼─────────┼──────────┼─────────────┤
│  412 │ Chrome Helper   │   12.4  │  412 MB  │             │
│ 1204 │ node            │    4.1  │  188 MB  │             │
╰──────┴─────────────────┴─────────┴──────────┴─────────────┯
```

The processes are sorted by **memory**, which is the number that explains
where a disk analyser usually disagrees with a task manager. Processes that
exit or refuse to be inspected are skipped rather than reported as errors.

## JSON output

```bash
diskgoup --json monitor sample
```

```json
{
  "timestamp": 1735689600.0,
  "network": { "down": 0.0, "up": 12697.12 },
  "disk": { "read": 1258291.2, "write": 90213.76, "usage": 130346414080.0, "total": 494384795136.0, "used_percent": 26.4 },
  "processes": [
    { "pid": 412, "name": "Chrome Helper", "cpu": 12.4, "memory": 432013312 }
  ]
}
```
