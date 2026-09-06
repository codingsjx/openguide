"""Pipeline + schema integration tests (hermetic, no LLM/chroma needed).

Exercises build_guide in heuristic mode (no key) over a synthetic RawSignals so
the Guide shape, stage coverage, and evidence downgrade all work offline.
"""

from __future__ import annotations

from backend.core.generate.pipeline import build_guide, _verify_and_relabel
from backend.core.generate.schemas import Evidence, GuideStep
from backend.core.github.models import DocFile, RepoMeta
from backend.core.github.recon import RawSignals
from backend.core.index.service import RepoIndex


def make_signals() -> RawSignals:
    docs = [
        ("README.md", "# Lib\n\nInstall:\n\n```\npython -m venv .venv\nsource .venv/bin/activate\npip install -e .[dev]\n```\n\nRun tests:\n\n```\npytest\n```\n"),
        ("CONTRIBUTING.md", "# Contributing\nFork the repo. Create a branch. Commit, push, open a PR.\n"),
    ]
    return RawSignals(
        meta=RepoMeta(owner="o", repo="lib", stars=30, default_branch="main",
                      pushed_at="", license="MIT"),
        language_bytes={"python": 100},
        root_entries={"readme.md": "README.md", "contributing.md": "CONTRIBUTING.md"},
        has_docs_dir=True,
        has_license_file=True,
        doc_files=[DocFile(path=p, name=p.split("/")[-1], text=t) for p, t in docs],
        issues=[
            {"number": 3, "title": "Add docs", "body": "example", "state": "open",
             "labels": [{"name": "good first issue"}], "pull_request": None},
        ],
        commits_30d=8,
        file_tree=["README.md", "CONTRIBUTING.md", "src/lib.py"],
    )


def test_build_guide_heuristic_no_key():
    sig = make_signals()
    idx = RepoIndex("o", "lib")
    idx.index(sig)
    guide = build_guide(sig, index=idx, use_llm=False)
    assert guide.owner == "o"
    assert guide.repo == "lib"
    assert not guide.unsuitable
    assert guide.steps, "heuristic mode should emit >=1 step per stage"
    stages = {s.stage for s in guide.steps}
    assert {"A", "B"} <= stages  # setup + test at minimum
    # Every step must carry a stage_label.
    assert all(s.stage_label for s in guide.steps)
    # Steps should be ordered by id.
    ids = [s.step_id for s in guide.steps]
    assert ids == sorted(ids)


def test_evidence_verify_downgrades_bad_file():
    sig = make_signals()
    bad = GuideStep(
        step_id=1,
        stage="A",
        stage_label="环境搭建",
        title="x",
        evidence=Evidence(kind="file", source="no-such-file.py#L1", quote=""),
    )
    good = GuideStep(
        step_id=2,
        stage="A",
        stage_label="环境搭建",
        title="y",
        evidence=Evidence(kind="file", source="README.md", quote=""),
    )
    out = _verify_and_relabel(sig, [bad, good])
    assert out[0].evidence.kind == "missing"
    assert out[1].evidence.kind == "file"


def test_evidence_verify_downgrades_fake_issue():
    sig = make_signals()
    st = GuideStep(
        step_id=1,
        stage="C",
        stage_label="挑选 issue",
        title="z",
        evidence=Evidence(kind="issue", source="#999", quote=""),
    )
    out = _verify_and_relabel(sig, [st])
    assert out[0].evidence.kind == "missing"
