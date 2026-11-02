"""The weekly report — the answer to "why is the disk full?".

The report carries the growth since the baseline snapshot. A growth that
does not fit in a kilobyte is the normal case, so the report has to render
it as a size and not as a raw number.
"""

from __future__ import annotations

from diskgoup.core.reports import WeeklyReport, weekly_report_html
from diskgoup.core.snapshots import Comparison, KindChange, Snapshot


def _report(current: int, baseline: int) -> WeeklyReport:
    snapshot = Snapshot(
        id=1,
        scan_id=1,
        label="Baseline",
        created_at=0.0,
        total_size=baseline,
        total_on_disk=baseline,
        kinds={"video": baseline},
    )
    comparison = Comparison(
        current={"video": current},
        baseline=snapshot,
        changes=[KindChange(kind="video", current=current, baseline=baseline, share=1.0)],
        total_current=current,
        total_baseline=baseline,
    )
    return WeeklyReport(
        root="/Users/demo",
        generated_at="2026-11-02 10:00 UTC",
        total_size=current,
        total_on_disk=current,
        files=1,
        folders=0,
        comparison=comparison,
        largest=[],
    )


def test_the_report_shows_the_growth_as_a_size() -> None:
    html = weekly_report_html(_report(current=5000, baseline=1000))

    assert "+3.9 KB" in html


def test_the_report_shows_a_shrinking_disk() -> None:
    html = weekly_report_html(_report(current=500, baseline=1000))

    assert "500 B" in html
