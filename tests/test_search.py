from __future__ import annotations

from datetime import date

import pytest

from diskgoup.core.scanner import Scanner, ScanOptions
from diskgoup.core.search import SearchError, SearchQuery, parse_date, parse_size, search
from diskgoup.core.store import ScanIndex


@pytest.fixture
def scanned(tmp_path_factory: pytest.TempPathFactory) -> tuple[ScanIndex, int]:
    """A scanned tree with a known mix of files."""
    root = tmp_path_factory.mktemp("search")
    (root / "Video").mkdir()
    (root / "Video" / "clip.mp4").write_bytes(b"x" * 5000)
    (root / "Video" / "notes.txt").write_bytes(b"x" * 100)
    (root / "song.mp3").write_bytes(b"x" * 2000)
    (root / "old.zip").write_bytes(b"x" * 3000)

    index = ScanIndex(tmp_path_factory.mktemp("idx") / "index.db")
    scanner = Scanner(index, ScanOptions(root=root))
    scan_id = scanner.run().meta.scan_id
    return index, scan_id


def test_name_filter_is_case_insensitive(scanned: tuple[ScanIndex, int]) -> None:
    index, scan_id = scanned
    result = search(index.connection, scan_id, SearchQuery(name="CLIP"))

    assert result.total == 1
    assert result.rows[0]["name"] == "clip.mp4"


def test_extension_filter(scanned: tuple[ScanIndex, int]) -> None:
    index, scan_id = scanned
    result = search(index.connection, scan_id, SearchQuery(extensions=(".mp4",)))

    assert result.total == 1
    assert result.rows[0]["name"] == "clip.mp4"


def test_size_limits_are_inclusive(scanned: tuple[ScanIndex, int]) -> None:
    index, scan_id = scanned
    result = search(index.connection, scan_id, SearchQuery(min_size=2000, max_size=3000))

    names = {row["name"] for row in result.rows}
    assert names == {"song.mp3", "old.zip"}


def test_conditions_apply_together(scanned: tuple[ScanIndex, int]) -> None:
    index, scan_id = scanned
    result = search(
        index.connection,
        scan_id,
        SearchQuery(extensions=(".mp4",), min_size=10_000),
    )

    assert result.total == 0


def test_entry_type_filter(scanned: tuple[ScanIndex, int]) -> None:
    index, scan_id = scanned
    result = search(index.connection, scan_id, SearchQuery(entry_type="folder"))

    assert result.total >= 1
    assert all(row["is_dir"] for row in result.rows)


def test_pagination(scanned: tuple[ScanIndex, int]) -> None:
    index, scan_id = scanned
    first = search(index.connection, scan_id, SearchQuery(), page=1, per_page=2)
    second = search(index.connection, scan_id, SearchQuery(), page=2, per_page=2)

    assert len(first.rows) == 2
    assert first.total == second.total
    assert first.pages >= 2
    assert {row["id"] for row in first.rows} & {row["id"] for row in second.rows} == set()


def test_invalid_date_range_is_rejected() -> None:
    query = SearchQuery(from_date=date(2026, 5, 1), to_date=date(2026, 1, 1))

    with pytest.raises(SearchError, match="valid date range"):
        query.validate()


def test_invalid_size_range_is_rejected() -> None:
    query = SearchQuery(min_size=1000, max_size=10)

    with pytest.raises(SearchError, match="minimum cannot exceed maximum"):
        query.validate()


def test_unknown_entry_type_is_rejected() -> None:
    with pytest.raises(SearchError, match="unknown entry type"):
        SearchQuery(entry_type="socket").validate()


def test_parse_size_accepts_suffixes() -> None:
    assert parse_size("1024") == 1024
    assert parse_size("1KB") == 1024
    assert parse_size("2mb") == 2 * 1024**2
    assert parse_size("1.5GB") == int(1.5 * 1024**3)


def test_parse_date_rejects_nonsense() -> None:
    with pytest.raises(SearchError):
        parse_date("2026-13-45")


def test_like_wildcards_are_escaped(scanned: tuple[ScanIndex, int]) -> None:
    index, scan_id = scanned
    result = search(index.connection, scan_id, SearchQuery(name="%"))

    assert result.total == 0
