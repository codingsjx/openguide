"""Guide schema + evidence unit tests (hermetic, offline)."""

from __future__ import annotations

from backend.core.generate.schemas import Evidence, Guide, GuideStep
from backend.core.generate.evidence import available_sources, resolve_evidence_source
from backend.core.github.models import DocFile, RepoMeta
from backend.core.github.recon import RawSignals


def make_signals() -> RawSignals:
    return RawSignals(
        meta=RepoMeta(owner="o", repo="r", stars=5, default_branch="main", pushed_at=""),
        language_bytes={"python": 100},
        root_entries={"readme.md": "README.md", "contributing.md": "CONTRIBUTING.md"},
        has_docs_dir=True,
        doc_files=[DocFile(path="README.md", name="README.md", text="Install via pip.")],
        issues=[
            {"number": 7, "title": "x", "body": "", "state": "open", "pull_request": None},
            {"number": 8, "title": "y", "body": "", "state": "open",
             "pull_request": {"url": "https://github.com/o/r/pull/8"}},
        ],
        file_tree=["README.md", "src/lib.py"],
    )


def test_available_sources_include_docs_root_tree():
    srcs = available_sources(make_signals())
    assert "readme.md" in srcs
    assert "src/lib.py" in srcs
    assert "contributing.md" in srcs


def test_file_evidence_resolves():
    sig = make_signals()
    ev = resolve_evidence_source("README.md#L3", sig)
    assert ev.kind == "file"


def test_nonexistent_file_becomes_missing():
    ev = resolve_evidence_source("nonexistent.md#L1", make_signals())
    assert ev.kind == "missing"


def test_issue_ref_resolves_when_number_exists():
    sig = make_signals()
    ev = resolve_evidence_source("#7", sig)
    assert ev.kind == "issue"
    assert ev.source == "#7"


def test_pr_number_does_not_resolve_as_issue():
    # #8 is a PR (pull_request set) -> not a beginner issue slot.
    ev = resolve_evidence_source("#8", make_signals())
    assert ev.kind == "missing"


def test_github_issue_url_resolves():
    ev = resolve_evidence_source("https://github.com/o/r/issues/7", make_signals())
    assert ev.kind == "issue"


def test_empty_source_is_missing():
    assert resolve_evidence_source("", make_signals()).kind == "missing"


def test_guide_schema_serialises():
    g = Guide(
        repo_url="https://github.com/o/r",
        owner="o",
        repo="r",
        steps=[
            GuideStep(
                step_id=1,
                stage="A",
                stage_label="环境搭建",
                title="安装",
                command="pip install -e .[dev]",
                expected="成功",
                evidence=Evidence(kind="file", source="README.md", quote=""),
            )
        ],
    )
    d = g.model_dump()
    assert d["steps"][0]["stage"] == "A"
    assert d["steps"][0]["evidence"]["source"] == "README.md"
