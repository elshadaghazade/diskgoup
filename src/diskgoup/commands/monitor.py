"""Monitor commands: live disk and network readings."""

from __future__ import annotations

import time

import typer
from rich.table import Table

from diskgoup.commands.common import console, emit, is_json
from diskgoup.core.monitor import Monitor
from diskgoup.util.humanize import human_bytes, human_rate

monitor_app = typer.Typer(help="Watch live disk and network usage.", no_args_is_help=True)


@monitor_app.command("watch")
def watch_command(
    interval: float = typer.Option(2.0, "--interval", help="Seconds between samples."),
    count: int = typer.Option(0, "--count", help="Number of samples (0 = run forever)."),
    processes: int = typer.Option(0, "--processes", help="Show the top N processes."),
) -> None:
    """Sample the machine's I/O rates until interrupted."""
    monitor = Monitor()
    taken = 0

    while True:
        sample = monitor.sample(process_count=max(processes, 5))
        taken += 1

        if is_json():
            emit(sample.to_dict())
        else:
            table = Table(header_style="bold", title=f"Sample {taken}")
            table.add_column("Metric")
            table.add_column("Value", justify="right")
            table.add_row("Network ↓", human_rate(sample.network_down))
            table.add_row("Network ↑", human_rate(sample.network_up))
            table.add_row("Disk read", human_rate(sample.disk_read))
            table.add_row("Disk write", human_rate(sample.disk_write))
            table.add_row(
                "Disk used",
                f"{human_bytes(int(sample.disk_usage))} "
                f"({sample.disk_usage / sample.disk_total * 100:.0f}%)"
                if sample.disk_total
                else "—",
            )
            console.print(table)

            if processes:
                process_table = Table(title="Processes", header_style="bold")
                process_table.add_column("PID", justify="right")
                process_table.add_column("Name")
                process_table.add_column("CPU %", justify="right")
                process_table.add_column("Memory", justify="right")
                for process in sample.processes[:processes]:
                    process_table.add_row(
                        str(process.pid),
                        process.name,
                        f"{process.cpu:.1f}",
                        human_bytes(process.memory),
                    )
                console.print(process_table)

        if count and taken >= count:
            return
        time.sleep(interval)


@monitor_app.command("sample")
def sample_command() -> None:
    """Take a single sample."""
    sample = Monitor().sample()
    if is_json():
        emit(sample.to_dict())
        return
    console.print(
        f"network ↓ {human_rate(sample.network_down)} · "
        f"↑ {human_rate(sample.network_up)} · "
        f"disk read {human_rate(sample.disk_read)} · "
        f"write {human_rate(sample.disk_write)} · "
        f"used {human_bytes(int(sample.disk_usage))}"
    )


def register(app: typer.Typer) -> None:
    """Register the monitor commands on the root application."""
    app.add_typer(monitor_app, name="monitor")
