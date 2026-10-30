"""Report commands: the weekly HTML report and the file-type CSV report."""

from __future__ import annotations

from pathlib import Path

import typer

from diskgoup.commands.common import console, emit, ensure_scan, is_json, open_index
from diskgoup.core.reports import build_weekly_report, type_report_csv, weekly_report_html

reports_app = typer.Typer(help="Generate reports from a scan.", no_args_is_help=True)


@reports_app.command("weekly")
def weekly_command(
    output: Path | None = typer.Option(
        None, "--output", "-o", help="Write the HTML report to this file."
    ),
    scan_id: int | None = typer.Option(None, help="Use a specific scan id."),
) -> None:
    """Generate the weekly HTML report."""
    with open_index() as index:
        meta = ensure_scan(index, None, scan_id=scan_id)
        report = build_weekly_report(index, meta.scan_id)
        html = weekly_report_html(report)

        if is_json():
            emit({"scan": meta.to_dict(), "html": html})
            return

        if output is None:
            console.print(html, markup=False, highlight=False)
            return
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(html, encoding="utf-8")
        console.print(f"[green]✔[/green] wrote {output}")


@reports_app.command("types")
def types_command(
    output: Path | None = typer.Option(
        None, "--output", "-o", help="Write the CSV report to this file."
    ),
    scan_id: int | None = typer.Option(None, help="Use a specific scan id."),
) -> None:
    """Export the file-type report as CSV."""
    with open_index() as index:
        meta = ensure_scan(index, None, scan_id=scan_id)
        csv_text = type_report_csv(index, meta.scan_id)

        if is_json():
            emit({"scan": meta.to_dict(), "csv": csv_text})
            return

        if output is None:
            console.print(csv_text, markup=False, highlight=False)
            return
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(csv_text, encoding="utf-8")
        console.print(f"[green]✔[/green] wrote {output}")


def register(app: typer.Typer) -> None:
    """Register the report commands on the root application."""
    app.add_typer(reports_app, name="reports")
