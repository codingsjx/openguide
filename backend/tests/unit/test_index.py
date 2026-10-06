"""Index-layer unit tests using hermetic RawSignals + fallback store.

No chromadb/network: the Store falls back to its in-memory token-overlap path,
so these tests are fast and offline.
"""

from __future__ import annotations

from backend.core.github.models import RepoMeta
from backend.core.github.recon import RawSignals
from backend.core.index.perspectives import (
    assemble_perspective_chunks,
    assemble_perspectives,
    chunk_text,
)
from backend.core.index.retrieval import _guess_kind
from backend.core.index.service import RepoIndex


def make_signals() -> RawSignals:
    docs = [
        ("README.md", "# My Lib\nInstall with `pip install -e .[dev]`.\nRun `pytest`."),
        ("CONTRIBUTING.md", "# Contributing\nFork the repo. Set up venv.\nRun `pytest`."),
        ("docs/install.md", "# Install\nMake a venv, pip install -e .[dev]"),
    ]
    from backend.core.github.models import DocFile

    return RawSignals(
        meta=RepoMeta(owner="o", repo="r", stars=5, default_branch="main", pushed_at=""),
        language_bytes={"python": 100},
        root_entries={"readme.md": "README.md", "contributing.md": "CONTRIBUTING.md"},
        has_docs_dir=True,
        doc_files=[DocFile(path=p, name=p.split("/")[-1], text=t) for p, t in docs],
        issues=[
            {"number": 1, "title": "Add docs example", "body": "show a code sample", "state": "open",
             "labels": [{"name": "good first issue"}], "pull_request": None},
            {"number": 2, "title": "Bump dep", "body": "", "state": "open",
             "labels": [], "pull_request": {"url": "x"}},  # is a PR -> filtered out
        ],
        file_tree=["README.md", "src/lib.py", "tests/test_lib.py", "docs/install.md"],
    )


def test_assemble_four_perspectives():
    docs = assemble_perspectives(make_signals())
    keys = {d.key for d in docs}
    assert keys == {"v1", "v2", "v3", "v4"}
    v1 = next(d for d in docs if d.key == "v1")
    assert "pip install" in v1.text
    v3 = next(d for d in docs if d.key == "v3")
    assert "pytest" in v3.text
    v4 = next(d for d in docs if d.key == "v4")
    assert "issue #1" in v4.text
    assert "issue #2" not in v4.text  # PR filtered


def test_v1_v3_activate_default_true_v2_v4_false():
    docs = assemble_perspectives(make_signals())
    flags = {d.key: d.activate_default for d in docs}
    assert flags["v1"] is True
    assert flags["v3"] is True
    assert flags["v2"] is False
    assert flags["v4"] is False


def test_chunk_text_splits():
    long = "\n".join(f"line {i} " + "word " * 60 for i in range(20))
    chunks = chunk_text(long, size=700)
    assert len(chunks) > 1
    assert all(c for c in chunks)


def test_guess_kind_routing():
    assert _guess_kind("how do I set up the env") == "setup"
    assert _guess_kind("run the tests") == "test"
    assert _guess_kind("how do I contribute / make a PR") == "contribute"
    assert _guess_kind("where is the module for x") == "arch"
    assert _guess_kind("which issue should I pick") == "issue"


def test_repo_index_search_roundtrip():
    idx = RepoIndex("o", "r")
    idx.index(make_signals())
    res = idx.search("how to install and run tests")
    assert res.hits, "fallback store should return hits"
    assert any("install" in h.text.lower() or "pytest" in h.text.lower() for h in res.hits)
    # Perspective attribution present.
    assert res.perspective in ("v3", "v1,v3", "setup")


def test_repo_index_issue_kind_returns_v4():
    idx = RepoIndex("o", "r")
    idx.index(make_signals())
    res = idx.search("good first issue for new contributor", kind="issue")
    assert any("issue #1" in h.text for h in res.hits)


def test_guess_kind_uses_word_boundaries():
    # 回归：短词 "pr" 不应命中 "improve"/"progress" 等无关单词，否则问题会
    # 被错误路由到「贡献流程」视角，答非所问。
    assert _guess_kind("how do I improve this repo") != "contribute"
    assert _guess_kind("make a PR") == "contribute"
    assert _guess_kind("open a pull request") == "contribute"


def test_fallback_matches_chinese_query():
    from backend.core.github.models import DocFile

    sig = RawSignals(
        meta=RepoMeta(owner="o", repo="cn", stars=5, default_branch="main", pushed_at=""),
        language_bytes={"python": 100},
        root_entries={"readme.md": "README.md"},
        doc_files=[
            DocFile(
                path="README.md",
                name="README.md",
                text="安装依赖：pip install -e .[dev]。运行测试：pytest。",
            )
        ],
        file_tree=["README.md"],
    )
    idx = RepoIndex("o", "cn")
    idx.index(sig)
    res = idx.search("怎么安装依赖", kind="setup")
    assert res.hits, "中文查询也应命中证据片段"
    assert any("安装" in h.text for h in res.hits)


def test_v3_excludes_narrative_docs_without_commands():
    # 回归：V3 是"可执行路径"，纯叙述文档（没有一条命令）不应进入 V3，
    # 否则它靠篇幅挤掉真正含命令的 Makefile，导致"怎么跑测试"答不出来。
    from backend.core.github.models import DocFile

    sig = RawSignals(
        meta=RepoMeta(owner="o", repo="r2", stars=5, default_branch="main", pushed_at=""),
        language_bytes={"python": 100},
        root_entries={"readme.md": "README.md", "makefile": "Makefile"},
        doc_files=[
            DocFile(path="README.md", name="README.md",
                    text="# R2\n\nInstall:\n\n```\npip install -e .\n```\n"),
            DocFile(path="Makefile", name="Makefile",
                    text="test:\n\tpytest tests\n"),
            DocFile(path="docs/dev/contributing.rst", name="contributing.rst",
                    text="Contributor guide.\n\nPlease write tests for your change and "
                         "open a pull request. No commands are shown here at all.\n"),
        ],
        file_tree=["README.md", "Makefile", "docs/dev/contributing.rst"],
    )
    chunks = assemble_perspective_chunks(sig)
    v3_sources = {c.source_path for c in chunks if c.perspective == "v3"}
    assert "Makefile" in v3_sources, "含命令的 Makefile 必须进入 V3"
    assert "README.md" in v3_sources, "含命令的 README 必须进入 V3"
    assert "docs/dev/contributing.rst" not in v3_sources, "无命令的叙述文档不应进入 V3"


def test_v3_excludes_changelog():
    from backend.core.github.models import DocFile

    sig = RawSignals(
        meta=RepoMeta(owner="o", repo="r3", stars=5, default_branch="main", pushed_at=""),
        language_bytes={"python": 100},
        root_entries={"readme.md": "README.md"},
        doc_files=[
            DocFile(path="README.md", name="README.md", text="pip install x\n"),
            DocFile(path="HISTORY.md", name="HISTORY.md",
                    text="# 1.0\n\nChanged the install path. See usage notes.\n" * 50),
        ],
        file_tree=["README.md", "HISTORY.md"],
    )
    v3_sources = {c.source_path for c in assemble_perspective_chunks(sig) if c.perspective == "v3"}
    assert "HISTORY.md" not in v3_sources, "changelog 不应进入可执行路径视角"
