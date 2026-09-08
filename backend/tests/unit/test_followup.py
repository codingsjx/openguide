"""Follow-up service unit tests (hermetic, no LLM / no chroma)."""

from __future__ import annotations

from backend.core.followup.service import _local_rules, diagnose, explain, granular
from backend.core.generate.schemas import Evidence, GuideStep
from backend.core.github.models import DocFile, RepoMeta
from backend.core.github.recon import RawSignals
from backend.core.index.service import RepoIndex


def make_index() -> RepoIndex:
    sig = RawSignals(
        meta=RepoMeta(owner="o", repo="lib", stars=30, license="MIT",
                      default_branch="main", pushed_at=""),
        language_bytes={"python": 100},
        root_entries={"readme.md": "README.md", "contributing.md": "CONTRIBUTING.md"},
        has_docs_dir=True,
        doc_files=[
            DocFile(path="README.md", name="README.md", text="Install with pip install -e .[dev]. Run pytest."),
            DocFile(path="CONTRIBUTING.md", name="CONTRIBUTING.md", text="Fork, branch, commit, push, PR."),
        ],
        issues=[{"number": 4, "title": "Add example", "body": "x", "state": "open",
                 "labels": [{"name": "good first issue"}], "pull_request": None}],
        file_tree=["README.md", "CONTRIBUTING.md"],
    )
    idx = RepoIndex("o", "lib")
    idx.index(sig)
    return idx


def _step(**kw) -> GuideStep:
    base = dict(step_id=1, stage="A", stage_label="环境搭建", title="安装依赖",
                command="pip install -e .[dev]", expected="成功",
                evidence=Evidence(kind="missing", source="", quote=""))
    base.update(kw)
    return GuideStep(**base)


def test_local_rules_detect_module_not_found():
    hits = _local_rules("ModuleNotFoundError: No module named 'requests'")
    assert any("缺少依赖" in h for h in hits)


def test_local_rules_detect_permission():
    hits = _local_rules("Permission denied: /usr/local/lib")
    assert any("权限不足" in h for h in hits)


def test_local_rules_empty_for_unknown():
    assert _local_rules("everything is fine") == []


def test_granular_returns_text():
    idx = make_index()
    r = granular(idx, _step())
    assert r.intent == "granular"
    assert r.text


def test_explain_returns_text():
    idx = make_index()
    r = explain(idx, _step(title="为什么用虚拟环境"))
    assert r.intent == "explain"
    assert r.text


def test_diagnose_without_llm_uses_rules():
    idx = make_index()
    r = diagnose(idx, _step(), "ModuleNotFoundError: No module named 'x'", client=None)
    assert r.intent == "diagnose"
    assert r.text
