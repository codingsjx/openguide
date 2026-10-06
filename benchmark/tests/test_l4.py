"""L4 contribution-log tests.

L4 is the "作品回馈开源" closure: the real PR/commit we submit upstream using our
own guide. The module is a skeleton until those links exist, so its status must
distinguish three cases clearly:

- PENDING : no records yet  → exit 0 (待补充，不是失败)
- OK      : records present → exit 0
- FAIL    : file corrupt    → exit 1 (真错误)

Without this, an empty L4 made the whole `benchmark.runner` report 未通过, which
would have looked like a broken submission rather than a missing item.
"""

from __future__ import annotations

import json
import pathlib
import shutil

import pytest

from benchmark.l4_contribution import runner as l4


@pytest.fixture()
def records_file(monkeypatch):
    """Point L4 at a throwaway records.json inside the workspace.

    Not pytest's tmp_path: some sandboxes deny writes outside the workspace, and
    these tests must run in CI and locally alike.
    """
    d = pathlib.Path("benchmark/reports/_l4_test")
    shutil.rmtree(d, ignore_errors=True)
    d.mkdir(parents=True, exist_ok=True)
    f = d / "records.json"
    monkeypatch.setattr(l4, "_CONTRIB", f)
    try:
        yield f
    finally:
        shutil.rmtree(d, ignore_errors=True)


def test_missing_file_is_pending_not_failure(records_file, capsys):
    assert l4.main() == 0
    out = capsys.readouterr().out
    assert "PENDING" in out


def test_records_present_is_ok(records_file, capsys):
    records_file.write_text(json.dumps([{
        "ts": "2026-10-06T12:00:00",
        "owner": "o", "repo": "r", "kind": "pr",
        "url": "https://github.com/o/r/pull/1", "note": "文档改进",
    }]), encoding="utf-8")
    assert l4.main() == 0
    out = capsys.readouterr().out
    assert "OK" in out
    assert "https://github.com/o/r/pull/1" in out


def test_corrupt_file_is_failure(records_file, capsys):
    records_file.write_text("{not json", encoding="utf-8")
    assert l4.main() == 1
    assert "损坏" in capsys.readouterr().out


def test_add_record_appends(records_file):
    l4.add_record("o", "r", "docs", "https://github.com/o/r/pull/2", "补文档")
    rows = json.loads(records_file.read_text(encoding="utf-8"))
    assert len(rows) == 1
    assert rows[0]["kind"] == "docs"
    l4.add_record("o", "r", "pr", "https://github.com/o/r/pull/3", "修 bug")
    rows = json.loads(records_file.read_text(encoding="utf-8"))
    assert [r["kind"] for r in rows] == ["docs", "pr"]
