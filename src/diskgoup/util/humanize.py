"""Human-readable formatting for sizes, counts and durations.

Windows-style units (1 KB = 1024 B) are used because that is what disk analysers
report for a "320 GB" volume on macOS, Linux and Windows alike.
"""

from __future__ import annotations

from datetime import timedelta

_UNITS = ("B", "KB", "MB", "GB", "TB", "PB", "EB")

#: Sizes below this threshold are rendered with no decimal places.
_INTEGER_THRESHOLD = 10


def human_bytes(size: int | float, *, precision: int | None = None) -> str:
    """Render a byte count as a short human string.

    >>> human_bytes(0)
    '0 B'
    >>> human_bytes(1024)
    '1.0 KB'
    >>> human_bytes(160 * 1024**3)
    '160.0 GB'
    """
    if size < 0:
        return f"-{human_bytes(-size, precision=precision)}"
    if size < 1024:
        return f"{int(size)} B"

    value = float(size)
    unit = 0
    while value >= 1024 and unit < len(_UNITS) - 1:
        value /= 1024
        unit += 1

    if precision is None:
        precision = 0 if value >= _INTEGER_THRESHOLD else 1
    return f"{value:.{precision}f} {_UNITS[unit]}"


def human_count(count: int) -> str:
    """Render a count with thin thousands separators."""
    return f"{count:,}"


def human_rate(bytes_per_second: float) -> str:
    """Render a transfer rate."""
    return f"{human_bytes(bytes_per_second)}/s"


def human_duration(seconds: float) -> str:
    """Render a duration as ``1h 02m 03s`` / ``2m 03s`` / ``3.4s``."""
    if seconds < 1:
        return f"{seconds * 1000:.0f}ms"
    if seconds < 60:
        return f"{seconds:.1f}s"
    delta = timedelta(seconds=int(seconds))
    hours, remainder = divmod(int(delta.total_seconds()), 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours}h {minutes:02d}m {secs:02d}s"
    return f"{minutes}m {secs:02d}s"


def percent(part: float, whole: float, *, precision: int = 1) -> str:
    """Render ``part / whole`` as a percentage, guarding against division by zero."""
    if not whole:
        return "0.0%"
    return f"{(part / whole) * 100:.{precision}f}%"
