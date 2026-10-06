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


def test_heuristic_stage_commands_are_not_all_the_same():
    # 回归：无 LLM 时曾把 README 里第一条命令（pip install）同时塞给
    # A/B/D 三个阶段。每个阶段必须给"属于自己"的命令，找不到就留空，
    # 而不是复述一条无关命令。
    sig = make_signals()
    idx = RepoIndex("o", "lib")
    idx.index(sig)
    guide = build_guide(sig, index=idx, use_llm=False)
    by_stage = {s.stage: s for s in guide.steps}
    # A 阶段给的是搭建类命令（venv 或 install 都算），B 阶段必须是测试命令。
    assert by_stage["A"].command
    assert any(k in by_stage["A"].command for k in ("venv", "install"))
    assert by_stage["B"].command and "pytest" in by_stage["B"].command
    assert by_stage["A"].command != by_stage["B"].command
    # D 阶段的资料里没有 git/PR 命令时，不应拿安装命令顶替。
    if by_stage.get("D") and by_stage["D"].command:
        assert by_stage["D"].command != by_stage["A"].command


def test_heuristic_evidence_source_actually_backs_the_command():
    # 回归：曾出现 B 阶段的 pytest 命令被标注为来自 CONTRIBUTING.md
    # （该文件里根本没有测试命令）。证据来源必须真实包含这条命令。
    sig = make_signals()
    idx = RepoIndex("o", "lib")
    idx.index(sig)
    guide = build_guide(sig, index=idx, use_llm=False)
    docs = {d.path: d.text for d in sig.doc_files}
    for st in guide.steps:
        if st.command and st.evidence.kind == "file" and st.evidence.source in docs:
            assert st.command in docs[st.evidence.source], (
                f"{st.stage} 的命令 {st.command!r} 不在其证据来源 {st.evidence.source!r} 中"
            )


def test_evidence_source_preserves_real_file_case():
    # 回归：V1 视角曾用种子名（小写 readme.md）当证据来源，前端据此拼出的
    # "打开原始出处"链接会 404。来源必须保留仓库里的真实大小写。
    sig = make_signals()
    idx = RepoIndex("o", "lib")
    idx.index(sig)
    guide = build_guide(sig, index=idx, use_llm=False)
    real_paths = {d.path for d in sig.doc_files} | set(sig.file_tree)
    for st in guide.steps:
        if st.evidence.kind == "file" and st.evidence.source:
            assert st.evidence.source in real_paths, (
                f"{st.stage} 的证据来源 {st.evidence.source!r} 不是仓库真实路径"
            )
