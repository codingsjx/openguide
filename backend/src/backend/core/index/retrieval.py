"""Top-level retrieval orchestration for perspectives.

`retrieve` picks which perspective(s) to query based on the *kind* of question a
newcomer asks, mirroring the activate-by-default design (V1+V3 eager, V2/V4 lazy
and kind-triggered). Results are returned with the source text so callers can
show evidence.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from backend.core.index.vectorstore import Hit, Store

# Question kind -> perspectives to query. Heuristic routing, no LLM.
_KIND_TO_PERSPECTIVES = {
    "setup": ["v3"],        # 怎么搭环境 / 跑起来
    "test": ["v3"],
    "contribute": ["v1"],   # 贡献流程 / 协议
    "arch": ["v2"],         # 架构 / 改哪个文件
    "issue": ["v4"],        # 挑 issue
    "why": ["v1", "v2"],    # 原理解释
}

_ASCII_WORD = re.compile(r"[A-Za-z]+")


def _contains_any(text: str, *keywords: str) -> bool:
    """Keyword match with sane boundaries.

    ASCII keywords are matched on word boundaries so short tokens like "pr" do
    not fire inside unrelated words ("improve"/"spring"/"progress"), which sent
    questions to the wrong perspective and produced wrong answers. CJK keywords
    are matched as plain substrings (word boundaries do not apply cleanly).
    """
    low = text.lower()
    for kw in keywords:
        if kw and _ASCII_WORD.fullmatch(kw):
            if re.search(rf"(?<![a-z0-9]){re.escape(kw)}(?![a-z0-9])", low):
                return True
        elif kw.lower() in low:
            return True
    return False


@dataclass
class SearchResult:
    query: str
    kind: str
    perspective: str
    hits: list[Hit]


def _guess_kind(query: str) -> str:
    q = query.lower()
    if _contains_any(
        q,
        "setup", "set up", "install", "installation", "installing",
        "environment", "env", "venv", "get started", "getting started",
        "quickstart", "quick start",
        "搭建", "环境", "安装", "跑起来",
    ):
        return "setup"
    if _contains_any(q, "test", "tests", "testing", "pytest", "npm test",
                     "测试", "跑测试", "单元测试"):
        return "test"
    if _contains_any(q, "contribute", "contribution", "contributing",
                     "pr", "pull request", "fork", "license",
                     "贡献", "协议", "提交 pr", "提交pr"):
        return "contribute"
    if _contains_any(q, "architecture", "arch", "structure", "directory",
                     "module", "which file", "where is",
                     "目录", "架构", "模块", "哪个文件", "代码", "文件结构"):
        return "arch"
    if _contains_any(q, "issue", "issues", "good first", "first contribution",
                     "任务", "pick", "认领", "选题"):
        return "issue"
    if _contains_any(q, "why", "reason", "meaning",
                     "原理", "为什么", "意思", "什么用"):
        return "why"
    return "setup"  # default to the beginner-most common need


def retrieve(
    store: Store, query: str, kind: str | None = None, top_k: int = 5, any_perspective: bool = False
) -> SearchResult:
    if any_perspective:
        # Search across all four perspectives (used by evidence backfill so a
        # step can find whichever repo file actually backs it).
        all_hits: list[Hit] = []
        for p in ("v1", "v2", "v3", "v4"):
            all_hits.extend(store.query(p, query, top_k=top_k))
        all_hits.sort(key=lambda h: -h.score)
        return SearchResult(query=query, kind="any", perspective="v1,v2,v3,v4", hits=all_hits)
    kind = kind or _guess_kind(query)
    perspectives = _KIND_TO_PERSPECTIVES.get(kind, ["v3"])
    hits: list[Hit] = []
    for p in perspectives:
        hits.extend(store.query(p, query, top_k=top_k))
    # Sort by score desc, keep perspective attribution.
    hits.sort(key=lambda h: -h.score)
    return SearchResult(query=query, kind=kind, perspective=",".join(perspectives), hits=hits)
