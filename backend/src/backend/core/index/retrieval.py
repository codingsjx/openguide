"""Top-level retrieval orchestration for perspectives.

`retrieve` picks which perspective(s) to query based on the *kind* of question a
newcomer asks, mirroring the activate-by-default design (V1+V3 eager, V2/V4 lazy
and kind-triggered). Results are returned with the source text so callers can
show evidence.
"""

from __future__ import annotations

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


@dataclass
class SearchResult:
    query: str
    kind: str
    perspective: str
    hits: list[Hit]


def _guess_kind(query: str) -> str:
    q = query.lower()
    if any(k in q for k in ("setup", "install", "env", "搭建", "环境", "安装", "跑起来", "get started", "venv")):
        return "setup"
    if any(k in q for k in ("test", "pytest", "测试", "跑测试", "npm test")):
        return "test"
    if any(k in q for k in ("contribute", "contribution", "贡献", "pr", "pull request", "fork", "协议", "license")):
        return "contribute"
    if any(k in q for k in ("architecture", "structure", "目录", "架构", "模块", "module", "which file", "哪个文件", "code")):
        return "arch"
    if any(k in q for k in ("issue", "good first", "first contribution", "任务", "pick")):
        return "issue"
    if any(k in q for k in ("why", "原理", "为什么", "意思")):
        return "why"
    return "setup"  # default to the beginner-most common need


def retrieve(
    store: Store, query: str, kind: str | None = None, top_k: int = 5
) -> SearchResult:
    kind = kind or _guess_kind(query)
    perspectives = _KIND_TO_PERSPECTIVES.get(kind, ["v3"])
    hits: list[Hit] = []
    for p in perspectives:
        hits.extend(store.query(p, query, top_k=top_k))
    # Sort by score desc, keep perspective attribution.
    hits.sort(key=lambda h: -h.score)
    return SearchResult(query=query, kind=kind, perspective=",".join(perspectives), hits=hits)
