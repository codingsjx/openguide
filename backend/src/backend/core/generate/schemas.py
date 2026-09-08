"""GuideStep schema — the global contract for structured guide output.

Mirrors benchmark/schema.py GenStep so L2/L3 score the same shape the API
returns. Kept as the backend authority; the benchmark copy stays in sync.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class Evidence(BaseModel):
    kind: Literal["file", "issue", "missing"] = "file"
    source: str = ""  # repo-relative "path#L22" 或 issue 引用；missing 时为空
    quote: str = ""  # 证据原文摘录（可选）


class GuideStep(BaseModel):
    step_id: int
    stage: Literal["A", "B", "C", "D"]
    stage_label: str = ""  # 如 "环境搭建"
    title: str
    command: str | None = None  # 无可执行命令则为 None
    expected: str = ""  # 期望结果 / 判定标准（"看到 42 passed"）
    fail_hints: list[str] = Field(default_factory=list)
    evidence: Evidence = Field(default_factory=Evidence)


class Guide(BaseModel):
    repo_url: str
    owner: str = ""
    repo: str = ""
    default_branch: str = "main"
    unsuitable: bool = False
    reasons: list[str] = Field(default_factory=list)
    steps: list[GuideStep] = Field(default_factory=list)
