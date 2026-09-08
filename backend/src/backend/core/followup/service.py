"""Three follow-up interactions (module 4) — the "向导陪你走完" layer.

Three intents, each resolved against the repo's perspective index + optional LLM:
- granular : "这步太粗" → re-retrieve V3 for finer sub-steps
- explain  : "看不懂为什么" → retrieve V1/V2 to explain the *why*
- diagnose : "报错了" → local rules first, then LLM locates the file to blame

Each returns evidence-backed text (and, for granular, optional sub-steps) so the
frontend can append it to the current step.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from backend.core.generate.llm import LLMClient, LLMUnavailable
from backend.core.generate.schemas import GuideStep
from backend.core.index.service import RepoIndex

_DIAGNOSE_SYSTEM = (
    "你是 OpenGuide 的报错定位助手。根据用户粘贴的报错日志和仓库上下文，"
    "判断最可能是哪个文件/依赖/步骤出了问题，用一句话给出定位和排查方向。"
    "不要编造文件路径，只能引用提供的仓库资料。"
)


@dataclass
class FollowupResult:
    intent: str
    text: str
    sub_steps: list[GuideStep] = field(default_factory=list)
    sources: list[str] = field(default_factory=list)


def _top_snippets(index: RepoIndex, query: str, kind: str | None, top_k: int = 4) -> list[str]:
    try:
        res = index.search(query, kind=kind, top_k=top_k)
    except Exception:  # noqa: BLE001
        return []
    return [h.text for h in res.hits]


def granular(index: RepoIndex, step: GuideStep, query: str = "") -> FollowupResult:
    """细化当前步骤：重新检索 V3，取更具体的命令片段。"""
    q = query or f"{step.title} {step.command or ''}"
    snips = _top_snippets(index, q, kind="setup", top_k=5)
    text = "\n".join(f"- {s.strip()}" for s in snips) if snips else "（没有检索到更细的步骤，见原始出处）"
    return FollowupResult(intent="granular", text=text, sources=[])


def explain(index: RepoIndex, step: GuideStep, query: str = "") -> FollowupResult:
    """解释"为什么这么做"：检索 V1/V2 找原理与背景。"""
    q = query or step.title
    snips = _top_snippets(index, q, kind="why", top_k=4)
    if not snips:
        snips = _top_snippets(index, q, kind=None, top_k=4)
    text = "\n".join(f"- {s.strip()}" for s in snips) if snips else "（未找到该步骤的背景说明）"
    return FollowupResult(intent="explain", text=text, sources=[])


def diagnose(index: RepoIndex, step: GuideStep, log_text: str, client: LLMClient | None = None) -> FollowupResult:
    """定位报错：本地规则预判 + LLM 结合仓库上下文定位文件。"""
    # 1. Local rules first (fast, deterministic, always available).
    rule_hits = _local_rules(log_text)
    # 2. Retrieve repo context for the LLM to ground on.
    ctx = _top_snippets(index, f"{step.title} {log_text[:200]}", kind=None, top_k=3)
    if not rule_hits and not client:
        return FollowupResult(intent="diagnose", text="（未命中本地规则，且未配置 LLM）", sources=[])

    if client and client.available() and ctx:
        try:
            user = f"步骤：{step.title}\n命令：{step.command or '无'}\n报错日志：\n{log_text[:1500]}\n\n仓库上下文：\n" + "\n".join(ctx[:3])
            reply = client.chat_text([{"role": "system", "content": _DIAGNOSE_SYSTEM},
                                      {"role": "user", "content": user}])
            return FollowupResult(
                intent="diagnose",
                text="\n".join(rule_hits + [reply]),
                sources=[],
            )
        except LLMUnavailable:
            pass
    text = "\n".join(rule_hits) if rule_hits else "（未能定位，建议贴更完整的报错日志）"
    return FollowupResult(intent="diagnose", text=text, sources=[])


def _local_rules(log_text: str) -> list[str]:
    """Deterministic error-pattern heuristics (no LLM)."""
    low = log_text.lower()
    hits: list[str] = []
    if "module not found" in low or "modulenotfounderror" in low:
        hits.append("缺少依赖：可能是没安装/没激活虚拟环境。试试先 `source .venv/bin/activate` 再 `pip install -e .[dev]`。")
    if "no such file" in low or "filenotfounderror" in low:
        hits.append("文件不存在：检查是否在正确目录、路径/分支是否对。")
    if "permission denied" in low or "eacces" in low:
        hits.append("权限不足：加 `--user` 或检查目标目录写权限。")
    if "command not found" in low or "不是内部或外部命令" in log_text:
        hits.append("命令未找到：工具没装或不在 PATH，先确认已安装（如 python/git/pytest）。")
    if "connection" in low or "timed out" in low:
        hits.append("网络问题：可能是依赖源超时，可换镜像源或重试。")
    if "syntaxerror" in low or "indentationerror" in low:
        hits.append("语法/缩进错误：检查刚改动的代码。")
    if "assert" in low and "error" in low:
        hits.append("测试断言失败：某个测试没通过，看具体哪个用例。")
    return hits
