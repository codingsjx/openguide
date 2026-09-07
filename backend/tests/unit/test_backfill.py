"""Evidence backfill unit tests (hermetic, no LLM)."""

from __future__ import annotations

from backend.core.generate.pipeline import _backfill_evidence, _verify_and_relabel
from backend.core.generate.schemas import Evidence, GuideStep
from backend.core.github.models import DocFile, RepoMeta
from backend.core.github.recon import RawSignals
from backend.core.index.service import RepoIndex


def make_signals() -> RawSignals:
    docs = [
        ("README.md", "# Lib\n\nInstall:\n\n```\npython -m venv .venv\npip install -e .[dev]\n```\n\nRun tests:\n\n```\npytest\n```\n"),
        ("CONTRIBUTING.md", "# Contributing\nFork. Branch. Commit. Push. Open PR.\n"),
    ]
    return RawSignals(
        meta=RepoMeta(owner="o", repo="lib", stars=30, license="MIT",
                      default_branch="main", pushed_at=""),
        language_bytes={"python": 100},
        root_entries={"readme.md": "README.md", "contributing.md": "CONTRIBUTING.md"},
        has_docs_dir=True,
        doc_files=[DocFile(path=p, name=p.split("/")[-1], text=t) for p, t in docs],
        issues=[
            {"number": 5, "title": "Improve docs", "body": "Add example", "state": "open",
             "labels": [{"name": "good first issue"}], "pull_request": None},
        ],
        file_tree=["README.md", "CONTRIBUTING.md"],
    )


def test_verify_rejects_perspective_code():
    sig = make_signals()
    st = GuideStep(
        step_id=1, stage="A", stage_label="环境搭建", title="x",
        evidence=Evidence(kind="file", source="v3", quote=""),
    )
    out = _verify_and_relabel(sig, [st])
    assert out[0].evidence.kind == "missing"


def test_backfill_finds_real_source_for_install_step():
    sig = make_signals()
    idx = RepoIndex("o", "lib")
    idx.index(sig)
    st = GuideStep(
        step_id=1, stage="A", stage_label="环境搭建", title="本地搭建并跑起来",
        command="pip install -e .[dev]", expected="ok",
        evidence=Evidence(kind="missing", source="", quote=""),
    )
    out = _backfill_evidence(sig, idx, [st])
    assert out[0].evidence.kind == "file"
    assert out[0].evidence.source  # real path like README.md
    assert out[0].evidence.source not in {"v1", "v2", "v3", "v4"}


def test_backfill_issue_step_to_real_issue():
    sig = make_signals()
    idx = RepoIndex("o", "lib")
    idx.index(sig)
    st = GuideStep(
        step_id=1, stage="C", stage_label="挑选 issue", title="挑一个 good-first-issue",
        command=None, expected="",
        evidence=Evidence(kind="missing", source="", quote=""),
    )
    out = _backfill_evidence(sig, idx, [st])
    # "good first issue" should retrieve the issue chunk with source #5.
    assert any(s.evidence.kind == "issue" and s.evidence.source == "#5" for s in out)


def test_backfill_leaves_missing_when_no_source():
    sig = make_signals()
    idx = RepoIndex("o", "lib")
    idx.index(sig)
    st = GuideStep(
        step_id=1, stage="D", stage_label="首次 PR 路径", title="完全没有相关内容的步骤名",
        command=None, expected="",
        evidence=Evidence(kind="missing", source="", quote=""),
    )
    out = _backfill_evidence(sig, idx, [st])
    assert out[0].evidence.kind == "missing"
