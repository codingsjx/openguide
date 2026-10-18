"""SHA-bound source-reviewed references, separate from legacy human claims.

Rule validation checks literal sources and declared scope. It cannot establish
independent human review, semantic completeness, or execution success.
"""
from pathlib import Path
from typing import Literal
import re

from pydantic import BaseModel, Field
from benchmark.golden.schema import GoldenGuide, GoldenStep
from backend.core.github.recon import RawSignals


class Citation(BaseModel):
    path: str
    line_start: int = Field(ge=1)
    line_end: int = Field(ge=1)
    quote: str = Field(min_length=1)


class PinnedStep(GoldenStep):
    citations: list[Citation] = Field(min_length=1)
    execution_status: Literal["not_run", "passed", "failed", "mixed"] = "not_run"
    execution_note: str = ""


class PinnedReference(GoldenGuide):
    commit_sha: str = Field(pattern=r"^[0-9a-f]{40}$")
    evaluation_scope: list[Literal["A", "B", "C", "D"]] = Field(min_length=1)
    source_review: Literal["agent_source_reviewed"] = "agent_source_reviewed"
    reviewer: str
    review_date: str
    source_license: str
    independent_human_review: Literal["pending", "self_reported_complete"] = "pending"
    human_reviewer: str = ""
    human_review_date: str = ""
    steps: list[PinnedStep]


def load_references(directory: Path) -> list[PinnedReference]:
    refs = [PinnedReference.model_validate_json(p.read_text(encoding="utf-8")) for p in sorted(directory.glob("*.json"))]
    keys = [(r.owner, r.repo) for r in refs]
    if len(keys) != len(set(keys)):
        raise ValueError("同一批评测每仓库只能选一个固定参考版本")
    return refs


def validate_reference(ref: PinnedReference, sig: RawSignals, sha: str) -> dict:
    if (ref.owner, ref.repo, ref.commit_sha) != (sig.meta.owner, sig.meta.repo, sha):
        raise ValueError("参考答案的仓库或 SHA 与输入快照不符")
    docs = {d.path: d.text.splitlines() for d in sig.doc_files}
    for step in ref.steps:
        if step.stage.split()[0] not in ref.evaluation_scope:
            raise ValueError("参考步骤超出已声明的评分范围")
        texts = []
        for citation in step.citations:
            lines = docs.get(citation.path)
            if lines is None or citation.line_end < citation.line_start or citation.line_end > len(lines):
                raise ValueError("参考引用文件或行号无效")
            selected = "\n".join(lines[citation.line_start - 1:citation.line_end])
            if citation.quote not in selected:
                raise ValueError("参考引用与固定源码原文不符")
            expected_source = f"{citation.path}#L{citation.line_start}"
            if not any(source.split("-L", 1)[0] == expected_source for source in step.evidence_sources):
                raise ValueError("参考来源列表与引用行号不一致")
            texts.append(selected)
        literal_commands = set()
        for text in texts:
            literal_commands.update(re.sub(r"^[$>]\s*", "", line.strip()) for line in text.splitlines())
            literal_commands.update(re.findall(r"`([^`\n]+)`", text))
        if any(command not in literal_commands for command in step.expected_commands):
            raise ValueError("参考命令没有对应的逐字原文依据")
    return {"source_rule_validation": "passed", "commit_sha": sha,
            "evaluation_scope": ref.evaluation_scope, "source_review": ref.source_review,
            "independent_human_review": ref.independent_human_review,
            "quality_claim_eligible": ref.independent_human_review == "self_reported_complete" and bool(ref.human_reviewer and ref.human_review_date),
            "human_review_identity_independently_verified": False}
