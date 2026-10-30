"""Reports: the file-type report (CSV) and the weekly report (HTML).

The HTML report answers the question DiskBOX headlines — "why is the disk
full?" — by showing, per file kind, the current size, the growth since the
baseline snapshot and the share of the scanned bytes.
"""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from jinja2 import Environment

from diskgoup.core.snapshots import Comparison, growth_rank
from diskgoup.core.store import ScanIndex

#: Where the Jinja templates live.
TEMPLATE_DIR = Path(__file__).parent.parent / "templates"


@dataclass(slots=True)
class WeeklyReport:
    """Everything the weekly report needs."""

    root: str
    generated_at: str
    total_size: int
    total_on_disk: int
    files: int
    folders: int
    comparison: Comparison
    largest: list[tuple[str, int]]
    volume_total: int = 0
    volume_used: int = 0
    volume_free: int = 0
    volume_label: str = ""

    @property
    def has_history(self) -> bool:
        return self.comparison.has_history


def _environment() -> Environment:
    from jinja2 import Environment, FileSystemLoader, select_autoescape

    environment = Environment(
        loader=FileSystemLoader(str(TEMPLATE_DIR)),
        autoescape=select_autoescape(["html", "xml"]),
        trim_blocks=True,
        lstrip_blocks=True,
    )
    environment.filters["filesizeformat"] = human_bytes
    return environment


def build_weekly_report(index: ScanIndex, scan_id: int) -> WeeklyReport:
    """Assemble the weekly report data from the index."""
    meta = index.scan_meta(scan_id)
    if meta is None:
        raise ValueError(f"no scan with id {scan_id}")

    comparison = compare_snapshot(index, scan_id)
    largest = [
        (row["path"], int(row["size"]))
        for row in index.largest_entries(scan_id, limit=20, folders=True, files=False)
    ]

    return WeeklyReport(
        root=str(meta.root),
        generated_at=datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC"),
        total_size=meta.total_size,
        total_on_disk=meta.total_on_disk,
        files=meta.file_count,
        folders=meta.dir_count,
        comparison=comparison,
        largest=largest,
    )


def compare_snapshot(index: ScanIndex, scan_id: int) -> Comparison:
    """Compare the scan against its baseline snapshot."""
    from diskgoup.core.snapshots import compare

    return compare(index, scan_id)


def weekly_report_html(report: WeeklyReport) -> str:
    """Render the weekly report as HTML."""
    template = _environment().get_template("weekly.html.j2")
    return template.render(
        report=report,
        changes=growth_rank(report.comparison.changes),
        baseline=report.comparison.baseline,
    )


def type_report_csv(index: ScanIndex, scan_id: int) -> str:
    """Render the file-type report as CSV."""
    meta = index.scan_meta(scan_id)
    if meta is None:
        raise ValueError(f"no scan with id {scan_id}")

    totals = index.kind_totals(scan_id)
    counts = index.kind_counts(scan_id)
    total = sum(totals.values()) or 1

    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(["kind", "files", "size_bytes", "size_human", "share_percent"])
    for kind, size in sorted(totals.items(), key=lambda item: -item[1]):
        writer.writerow(
            [
                kind,
                counts.get(kind, 0),
                size,
                human_bytes(size),
                f"{(size / total) * 100:.2f}",
            ]
        )
    writer.writerow(["total", meta.file_count, total, human_bytes(total), "100.00"])
    return buffer.getvalue()


def human_bytes(size: int) -> str:
    """Local copy of the byte formatter so the template stays self-contained."""
    value = float(size)
    for unit in ("B", "KB", "MB", "GB", "TB", "PB"):
        if value < 1024 or unit == "PB":
            precision = 0 if value >= 10 or unit == "B" else 1
            return f"{value:.{precision}f} {unit}"
        value /= 1024
    return f"{size} B"
