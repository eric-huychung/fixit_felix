"""Tests for the SQLite cache."""

from pathlib import Path

from felix.cache import Cache


def test_cache_survives_reopen(tmp_path: Path) -> None:
    path = tmp_path / "cache.sqlite"
    with Cache(path) as cache:
        cache.set("00D000000000001", "describe", "Opportunity", '{"ok": true}')

    with Cache(path) as cache:
        value = cache.get("00D000000000001", "describe", "Opportunity")

    assert value == '{"ok": true}'


def test_cache_miss_returns_none(tmp_path: Path) -> None:
    with Cache(tmp_path / "cache.sqlite") as cache:
        assert cache.get("00D000000000001", "rules", "missing") is None
