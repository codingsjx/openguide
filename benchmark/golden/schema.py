"""Golden-guide annotation loader and schema.

A *golden guide* is the human-authored "standard onboarding path" for a repo:
which commands actually run, what the expected result is, which source files
back each step. L2 (golden evaluation) scores generated guides against these.

Data lives as Markdown + sidecar JSON per repo under ``golden/golden_guides/``.
"""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, Field

_GUIDES_DIR = Path(__file__).resolve().parent / "golden_guides"


class GoldenStep(BaseModel):
    """A single step of the reference onboarding path."""

    order: int
    stage: str  # A 环境搭建 / B 测试基线 / C 选 issue / D 首 PR
    title: str
    # Normalised commands a beginner actually runs (without user-specific bits).
    expected_commands: list[str] = Field(default_factory=list)
    expected_outcome: str = ""  # e.g. "pytest 输出 42 passed"
    evidence_sources: list[str] = Field(
        default_factory=list
    )  # repo-relative file/issue paths backing this step


class GoldenGuide(BaseModel):
    """Reference onboarding guide for one repo."""

    owner: str
    repo: str
    steps: list[GoldenStep] = Field(default_factory=list)
    notes: str = ""


def iter_golden_guides() -> list[GoldenGuide]:
    """Load all human-authored golden guides under golden_guides/."""
    guides: list[GoldenGuide] = []
    for p in sorted(_GUIDES_DIR.glob("*.json")):
        try:
            guides.append(GoldenGuide.model_validate_json(p.read_text(encoding="utf-8")))
        except Exception as exc:  # noqa: BLE001 - surface as one aggregate error
            raise ValueError(f"golden guide 解析失败: {p.name}: {exc}") from exc
    return guides


def iter_repo_manifest() -> list[dict]:
    """Load the repo manifest (repos.json) for candidate metadata."""
    manifest = Path(__file__).resolve().parent / "repos.json"
    data = json_load(manifest)
    return data.get("repos", [])


def json_load(p: Path) -> dict:
    import json

    return json.loads(p.read_text(encoding="utf-8"))
