from diskgoup.util.humanize import human_bytes, human_count, human_duration, percent


def test_human_bytes_below_kilobyte() -> None:
    assert human_bytes(0) == "0 B"
    assert human_bytes(512) == "512 B"


def test_human_bytes_uses_1024_units() -> None:
    assert human_bytes(1024) == "1.0 KB"
    assert human_bytes(1024**2) == "1.0 MB"
    assert human_bytes(1024**3) == "1.0 GB"
    assert human_bytes(160 * 1024**3) == "160 GB"


def test_human_bytes_small_values_keep_a_decimal() -> None:
    assert human_bytes(1536) == "1.5 KB"


def test_human_bytes_handles_negatives() -> None:
    assert human_bytes(-2048) == "-2.0 KB"


def test_human_count() -> None:
    assert human_count(1234567) == "1,234,567"


def test_human_duration() -> None:
    assert human_duration(0.25) == "250ms"
    assert human_duration(3.5) == "3.5s"
    assert human_duration(125) == "2m 05s"
    assert human_duration(3725) == "1h 02m 05s"


def test_percent_guards_zero() -> None:
    assert percent(10, 0) == "0.0%"
    assert percent(25, 100) == "25.0%"
