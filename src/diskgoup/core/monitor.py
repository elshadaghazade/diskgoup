"""Live monitoring.

DiskBOX's Monitor section shows the machine's current disk usage and network
throughput, alongside the running processes. The readings are sampled: the
first call establishes a baseline and every later call reports the delta since
the previous one, which is what makes a *rate* rather than a total.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path

import psutil


@dataclass(slots=True)
class Reading:
    """A sampled metric."""

    label: str
    value: float
    unit: str = "B/s"

    def to_dict(self) -> dict[str, object]:
        return {"label": self.label, "value": round(self.value, 2), "unit": self.unit}


@dataclass(slots=True)
class ProcessInfo:
    """A running process."""

    pid: int
    name: str
    cpu: float
    memory: int

    def to_dict(self) -> dict[str, object]:
        return {
            "pid": self.pid,
            "name": self.name,
            "cpu": round(self.cpu, 1),
            "memory": self.memory,
        }


@dataclass(slots=True)
class MonitorSample:
    """One monitor sample."""

    timestamp: float
    network_down: float = 0.0
    network_up: float = 0.0
    disk_read: float = 0.0
    disk_write: float = 0.0
    disk_usage: float = 0.0
    disk_total: float = 0.0
    processes: list[ProcessInfo] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        return {
            "timestamp": self.timestamp,
            "network": {
                "down": round(self.network_down, 2),
                "up": round(self.network_up, 2),
            },
            "disk": {
                "read": round(self.disk_read, 2),
                "write": round(self.disk_write, 2),
                "usage": round(self.disk_usage, 2),
                "total": round(self.disk_total, 2),
                "used_percent": round(
                    (self.disk_usage / self.disk_total * 100) if self.disk_total else 0.0, 1
                ),
            },
            "processes": [process.to_dict() for process in self.processes],
        }


class Monitor:
    """Samples the machine's I/O rates.

    The first :meth:`sample` establishes a baseline and reports zero rates;
    later samples report the change since the previous one.
    """

    def __init__(self, path: Path | None = None) -> None:
        self.path = path or Path.home()
        self._last_net: tuple[float, float] | None = None
        self._last_disk: tuple[float, float] | None = None
        self._last_time: float | None = None

    def sample(self, *, process_count: int = 10) -> MonitorSample:
        """Take one sample."""
        now = time.time()
        sample = MonitorSample(timestamp=now)

        net = psutil.net_io_counters()
        disk = psutil.disk_io_counters()
        if net is None or disk is None:
            # Some platforms do not expose these counters.
            return sample
        elapsed = (now - self._last_time) if self._last_time is not None else 0.0

        if elapsed > 0:
            if self._last_net is not None:
                sample.network_down = max(0.0, (net.bytes_recv - self._last_net[0]) / elapsed)
                sample.network_up = max(0.0, (net.bytes_sent - self._last_net[1]) / elapsed)
            if self._last_disk is not None:
                sample.disk_read = max(0.0, (disk.read_bytes - self._last_disk[0]) / elapsed)
                sample.disk_write = max(0.0, (disk.write_bytes - self._last_disk[1]) / elapsed)

        self._last_net = (net.bytes_recv, net.bytes_sent)
        self._last_disk = (disk.read_bytes, disk.write_bytes)
        self._last_time = now

        usage = psutil.disk_usage(str(self.path))
        sample.disk_usage = float(usage.used)
        sample.disk_total = float(usage.total)
        sample.processes = self.processes(process_count)
        return sample

    def processes(self, limit: int = 10) -> list[ProcessInfo]:
        """The heaviest running processes."""
        found: list[ProcessInfo] = []
        for process in psutil.process_iter(["pid", "name", "cpu_percent", "memory_info"]):
            try:
                info = process.info
                memory = info.get("memory_info")
                found.append(
                    ProcessInfo(
                        pid=int(info["pid"]),
                        name=str(info.get("name") or "?"),
                        cpu=float(info.get("cpu_percent") or 0.0),
                        memory=int(getattr(memory, "rss", 0) or 0),
                    )
                )
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue
        found.sort(key=lambda item: -item.memory)
        return found[:limit]


def volume_usage(path: Path | None = None) -> tuple[int, int, int]:
    """``(total, used, free)`` for the volume holding ``path``."""
    usage = psutil.disk_usage(str(path or Path.home()))
    return (usage.total, usage.used, usage.free)
