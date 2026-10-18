"""GuideStep schema — the global contract for structured guide output.

Mirrors benchmark/schema.py GenStep so L2/L3 score the same shape the API
returns. Kept as the backend authority; the benchmark copy stays in sync.
"""

from __future__ import annotations

from typing import Literal
import re

from pydantic import BaseModel, Field, model_validator


class Evidence(BaseModel):
    kind: Literal["file", "issue", "missing"] = "file"
    source: str = ""  # repo-relative "path#L22" 或 issue 引用；missing 时为空
    quote: str = ""  # 证据原文摘录（可选）
    verification: Literal["missing", "source_exists", "quote_verified", "command_verified"] = "missing"
    line_start: int | None = None
    line_end: int | None = None
    reason: str = ""


class ExecutionRecord(BaseModel):
    status: Literal["passed", "failed", "timed_out"]
    command: str
    commit_sha: str = Field(pattern=r"^[0-9a-f]{40}$")
    environment: str
    summary: str
    report: str
    working_directory: str | None = None


class GuideStep(BaseModel):
    step_id: int
    stage: Literal["A", "B", "C", "D"]
    stage_label: str = ""  # 如 "环境搭建"
    title: str
    command: str | None = None  # 无可执行命令则为 None
    original_command: str | None = None
    command_derivation: str = ""
    execution_record: ExecutionRecord | None = None
    original_stage: Literal["A", "B", "C", "D"] | None = None
    working_directory: str | None = None
    directory_basis: Literal["build_file", "unknown", "clone_destination"] = "unknown"
    required_paths: list[str] = Field(default_factory=list)
    missing_inputs: list[str] = Field(default_factory=list)
    prerequisite_step_ids: list[int] = Field(default_factory=list)
    context_notes: list[str] = Field(default_factory=list)
    success_checks: list[str] = Field(default_factory=list)
    expected: str = ""  # 期望结果 / 判定标准（"看到 42 passed"）
    fail_hints: list[str] = Field(default_factory=list)
    evidence: Evidence = Field(default_factory=Evidence)

    @model_validator(mode="after")
    def execution_matches_command(self):
        if self.execution_record and self.execution_record.command != self.command:
            raise ValueError("执行记录必须对应当前步骤的确切命令")
        if self.execution_record and self.execution_record.working_directory is not None and self.execution_record.working_directory != self.working_directory:
            raise ValueError("执行记录必须对应当前步骤的执行目录")
        return self

    @model_validator(mode="after")
    def relative_execution_paths(self):
        paths = self.required_paths + self.missing_inputs + ([self.working_directory] if self.working_directory is not None else [])
        if any(not path or "\\" in path or re.match(r"^(?:/|[A-Za-z]:)", path) or ".." in path.split("/") for path in paths):
            raise ValueError("执行目录和输入路径必须为仓库内相对路径")
        return self


class Guide(BaseModel):
    repo_url: str
    owner: str = ""
    repo: str = ""
    default_branch: str = "main"
    unsuitable: bool = False
    reasons: list[str] = Field(default_factory=list)
    steps: list[GuideStep] = Field(default_factory=list)
    generation_mode: Literal["heuristic", "llm", "mixed"] = "heuristic"
    warnings: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def execution_matches_revision(self):
        if any(step.execution_record and step.execution_record.commit_sha != self.default_branch for step in self.steps):
            raise ValueError("带执行记录的指南必须使用对应的固定提交")
        earlier = set()
        for step in self.steps:
            if step.step_id in earlier or any(ref not in earlier for ref in step.prerequisite_step_ids):
                raise ValueError("步骤 ID 必须唯一，前置步骤只能引用先前步骤")
            earlier.add(step.step_id)
        return self
