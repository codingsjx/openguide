"""Generated-guide format shared by L2/L3 so both score the same shape.

This mirrors the backend GuideStep schema contract. Keeping a separate, stable
copy here decouples benchmarking from backend internals and prevents drift.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class GenEvidence(BaseModel):
    kind: str = "file"  # file | issue | missing
    source: str = ""  # repo-relative "path#L" or issue ref
    quote: str = ""


class GenStep(BaseModel):
    step_id: int
    stage: str
    title: str
    command: str | None = None
    expected: str = ""
    fail_hints: list[str] = Field(default_factory=list)
    evidence: GenEvidence = Field(default_factory=GenEvidence)


class GeneratedGuide(BaseModel):
    repo_url: str
    unsuitable: bool | None = None
    reasons: list[str] = Field(default_factory=list)
    stages: list[GenStep] = Field(default_factory=list)


def guide_to_json(guide: GeneratedGuide) -> dict:
    return guide.model_dump()
