"""L3 ablation arms: naive single-shot baseline vs the layered pipeline.

The ablation's claim is narrow and testable: *the layered pipeline fabricates
less*. Both arms run over the SAME golden repos and are scored by the SAME
``benchmark.metrics.compute``, so the comparison cannot drift.

Naive baseline (``NaiveBaseline``):
- one LLM call, whole-doc dump, no perspective routing, no stage structure
- no schema discipline beyond JSON, and — crucially — **no evidence
  verification**: whatever source the model names is kept as-is. That is
  exactly the failure mode the layered arm's 无证据不宣称 pass exists to catch.

The offline variants (``FakeNaiveBaseline``) reproduce that failure mode
deterministically so CI and the demo can show the metric working without an LLM
key. Their numbers are labelled fake in the report and must never be quoted as
model quality (口径红线, see benchmark/README.md).
"""

from __future__ import annotations

import json
from typing import Protocol

from benchmark.schema import GeneratedGuide, GenEvidence, GenStep

# The naive arm retrieves from the *whole* repo dump rather than by perspective,
# so we cap what goes into its single prompt.
_MAX_DUMP_CHARS = 24_000
_STAGES = ("A", "B", "C", "D")


class BaselineArm(Protocol):
    name: str
    is_fake: bool

    def generate(self, owner: str, repo: str, sig) -> GeneratedGuide: ...


def _dump(sig) -> str:
    """Whole-repo text dump: docs concatenated, no perspective assignment."""
    parts: list[str] = []
    for f in sig.doc_files:
        parts.append(f"===== {f.path} =====\n{f.text}")
    if sig.file_tree:
        parts.append("===== file tree =====\n" + "\n".join(sig.file_tree[:400]))
    return "\n\n".join(parts)[:_MAX_DUMP_CHARS]


_PROMPT = (
    "你是开源项目入门向导。阅读下面的仓库资料，为新贡献者生成一份上手指南，"
    "覆盖四个阶段：A 环境搭建、B 跑测试基线、C 挑选 issue、D 提交首个 PR。\n"
    "每个阶段给出步骤，字段：stage, title, command(可执行命令或 null), "
    "expected(期望结果), evidence(对象: kind, source, quote)。\n"
    "只输出 JSON：{\"steps\": [...]}。"
)


class NaiveBaseline:
    """Real naive arm: one LLM call over the whole dump, evidence unverified."""

    name = "naive-single-shot"
    is_fake = False

    def __init__(self) -> None:
        from backend.core.generate.llm import LLMClient

        self._client = LLMClient()

    def generate(self, owner: str, repo: str, sig) -> GeneratedGuide:
        from backend.core.generate.llm import LLMUnavailable

        if not self._client.available():
            raise LLMUnavailable("未配置 LLM_API_KEY，naive 臂需要真实模型")

        messages = [
            {"role": "system", "content": "只输出合法 JSON，不要 Markdown。"},
            {"role": "user", "content": _PROMPT + "\n\n仓库资料：\n" + _dump(sig)},
        ]
        obj = self._client.chat_json(messages, temperature=0.2, max_tokens=3000)
        raw_steps = obj.get("steps") if isinstance(obj, dict) else None
        if not isinstance(raw_steps, list):
            raw_steps = []

        steps: list[GenStep] = []
        for i, it in enumerate(raw_steps, start=1):
            if not isinstance(it, dict):
                continue
            title = str(it.get("title") or "").strip()
            if not title:
                continue
            stage = str(it.get("stage") or "A").strip().upper()[:1] or "A"
            ev = it.get("evidence") if isinstance(it.get("evidence"), dict) else {}
            kind = str(ev.get("kind") or "file")
            cmd = it.get("command")
            steps.append(
                GenStep(
                    step_id=i,
                    stage=stage,
                    title=title,
                    command=(str(cmd).strip() or None) if cmd is not None else None,
                    expected=str(it.get("expected") or ""),
                    fail_hints=[],
                    # No verification pass: the model's claim is taken at face
                    # value. This is the whole point of the comparison.
                    evidence=GenEvidence(
                        kind=kind if kind in {"file", "issue", "missing"} else "file",
                        source=str(ev.get("source") or ""),
                        quote=str(ev.get("quote") or ""),
                    ),
                )
            )
        return GeneratedGuide(
            repo_url=f"https://github.com/{owner}/{repo}",
            unsuitable=False,
            reasons=[],
            stages=steps,
        )


class FakeNaiveBaseline:
    """Deterministic stand-in for the naive arm's failure mode.

    Reproduces what a single unverified shot does on a real repo: plausible step
    titles and commands, but evidence pointing at *files that do not exist*
    (``docs/setup.md``, ``CONTRIBUTING.md`` when absent, invented issue numbers).
    The point is that the metrics can *detect* this — an honest naive arm on a
    well-documented repo would score better, and that is fine; this arm exists to
    prove the detector works offline.
    """

    name = "naive-single-shot(fake)"
    is_fake = True

    def generate(self, owner: str, repo: str, sig) -> GeneratedGuide:
        # Commands a naive model commonly emits regardless of the repo, paired
        # with evidence paths it invents because it was never asked to verify.
        plan = [
            ("A", "克隆并安装依赖", "pip install -r requirements.txt", "docs/setup.md#L1"),
            ("B", "运行测试", "pytest -q", "docs/testing.md#L5"),
            ("C", "认领新手任务", None, "issues/9999"),
            ("D", "提交 PR", None, "CONTRIBUTING.md#L1"),
        ]
        steps = [
            GenStep(
                step_id=i,
                stage=stage,
                title=title,
                command=cmd,
                expected="命令输出无报错即成功",
                fail_hints=[],
                evidence=GenEvidence(kind="file" if src else "missing", source=src, quote=""),
            )
            for i, (stage, title, cmd, src) in enumerate(plan, start=1)
        ]
        return GeneratedGuide(
            repo_url=f"https://github.com/{owner}/{repo}",
            unsuitable=False,
            reasons=[],
            stages=steps,
        )


def make_arm(provider: str) -> BaselineArm:
    """provider: 'auto' (real LLM) | 'fake' (deterministic stand-in)."""
    return FakeNaiveBaseline() if provider == "fake" else NaiveBaseline()
