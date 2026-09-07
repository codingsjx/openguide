"""Prompt templates for structured guide generation.

The design is "retrieve-first, then fill a strict schema": each stage prompt
receives only the evidence snippets retrieved from that repo (so the LLM cannot
hallucinate setup commands that aren't in the repo), and is told to answer in
JSON matching GuideStep fields. Evidence `source` must come verbatim from the
provided snippet's provenance.
"""

from __future__ import annotations

from backend.core.generate.schemas import GuideStep

_SYSTEM = (
    "你是 OpenGuide：面向开源新手贡献者的中文向导。你只能依据提供的仓库原文资料回答，"
    "绝不编造安装命令、文件路径或 issue 编号。若资料中没有某步，明确用 evidence.kind=missing 标注。"
    "只输出合法 JSON。"
)

_STAGE_LABELS = {"A": "环境搭建", "B": "测试基线", "C": "挑选 issue", "D": "首次 PR 路径"}


def _step_instructions(stage: str) -> str:
    if stage == "A":
        return "给新手'把代码跑起来'的环境搭建步骤：clone→依赖→运行前检查。"
    if stage == "B":
        return "给出运行测试基线的步骤：怎么跑测试、期望看到什么（如全部通过/passed）。"
    if stage == "C":
        return "从提供的 issue 槽位里挑 1-3 个适合新手、可直接认领的 issue，并给推荐理由。"
    return "给出从 fork 到提交 PR 的完整步骤（clone→分支→commit→push→建 PR）。"


def build_stage_messages(stage: str, context_snippets: list[dict]) -> list[dict[str, str]]:
    """context_snippets: [{source, text}] retrieved from the repo perspectives."""
    user = [
        f"现在生成 Stage {stage}（{_STAGE_LABELS.get(stage, stage)}）的步骤。\n",
        _step_instructions(stage),
        "\n以下是你可引用的仓库原文（source 是证据，回答时必须原样使用）：\n",
    ]
    if not context_snippets:
        user.append("（本次未检索到可引用资料）")
    for s in context_snippets:
        src = s.get("source", "")
        # Only real file paths or issue refs are usable as evidence sources.
        display = src if src and not src.startswith("v") else "（仓库原文，无具体文件）"
        user.append(f"\n--[source: {display}]--\n{s['text'][:1200]}")
    user.append(
        "\n\n输出 JSON 数组，每个元素字段："
        "step_id(int), stage=该阶段代号, stage_label(中文), title(一句话), "
        "command(可执行命令或 null), expected(期望结果), "
        "fail_hints(字符串数组,可空), evidence(对象: kind∈[file,issue,missing], "
        "source=来自原文的 source 或空, quote=引用的原文短句)。"
        '如无资料支撑某步，设 evidence.kind="missing"。'
    )
    return [{"role": "system", "content": _SYSTEM}, {"role": "user", "content": "".join(user)}]


def step_from_llm_json(stage: str, obj: dict, start_id: int) -> GuideStep | None:
    """Map one LLM JSON object onto a validated GuideStep (best-effort)."""
    if not isinstance(obj, dict):
        return None
    title = str(obj.get("title") or "").strip()
    if not title:
        return None
    ev = obj.get("evidence") or {}
    ev_kind = str(ev.get("kind") or "file")
    if ev_kind not in {"file", "issue", "missing"}:
        ev_kind = "missing"
    command = obj.get("command")
    if command is not None:
        command = str(command).strip() or None
    expected = str(obj.get("expected") or "")
    return GuideStep(
        step_id=start_id,
        stage=stage,  # type: ignore[arg-type]
        stage_label=str(obj.get("stage_label") or _STAGE_LABELS.get(stage, "")),
        title=title,
        command=command,
        expected=expected,
        fail_hints=[str(x) for x in (obj.get("fail_hints") or []) if str(x).strip()],
        evidence=__import__(
            "backend.core.generate.schemas", fromlist=["Evidence"]
        ).Evidence(
            kind=ev_kind,  # type: ignore[arg-type]
            source=str(ev.get("source") or ""),
            quote=str(ev.get("quote") or ""),
        ),
    )
