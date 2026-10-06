"""Cache-layer tests: cache keys must produce safe filenames everywhere.

Regression guard for a silent Windows failure: keys were only sanitised for
"/" and ":", so the "?" that every GitHub key contains made `write_text` raise
OSError — which `set` swallowed. The cache therefore did nothing on Windows and
every run re-hit the GitHub API until it rate-limited (403) mid-run.
"""

from __future__ import annotations

import pathlib
import shutil

import pytest

from backend.utils import cache

# Characters Windows forbids in a filename.
_ILLEGAL = '<>:"/\\|?*'
_REAL_KEY = "github::repos/o/r/issues?labels=good first issue&per_page=30&state=open"


@pytest.fixture()
def cache_dir():
    """Workspace-local cache dir (pytest's tmp_path is blocked in some sandboxes)."""
    d = pathlib.Path(".cache") / "_unit_test"
    shutil.rmtree(d, ignore_errors=True)
    d.mkdir(parents=True, exist_ok=True)
    original = cache._cache_dir
    cache._cache_dir = d
    try:
        yield d
    finally:
        cache._cache_dir = original
        shutil.rmtree(d, ignore_errors=True)


def test_path_has_no_illegal_filename_chars():
    name = cache._path(_REAL_KEY).name
    for bad in _ILLEGAL:
        assert bad not in name, f"缓存文件名不应含 {bad!r}: {name}"


def test_roundtrip_with_github_style_key(cache_dir):
    cache.set(_REAL_KEY, {"ok": True})
    assert cache.get(_REAL_KEY, 3600) == {"ok": True}
    assert list(cache_dir.iterdir()), "应当写入了缓存文件"


def test_long_key_stays_bounded_and_unique(cache_dir):
    a = cache._path("github::repos/o/r/contents/" + "x" * 400)
    b = cache._path("github::repos/o/r/contents/" + "y" * 400)
    assert a != b, "长 key 截断后仍需唯一"
    assert len(a.name) <= 128, f"文件名过长: {len(a.name)}"  # 100 + _ + 16 + .json


def test_expired_entry_returns_none(cache_dir):
    cache.set("k", {"v": 1})
    assert cache.get("k", 3600) == {"v": 1}
    assert cache.get("k", -1) is None
