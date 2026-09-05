"""Profile schema — the global contract consumed by the frontend and the
golden benchmark. Kept dependency-light so B/C can build against it early."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class BuildInfo(BaseModel):
    """Build-system / test command detection result."""

    tool: str | None = None  # "pyproject.toml" | "package.json" | "Cargo.toml" | ...
    package_manager: str | None = None  # "uv" | "pip" | "pnpm" | ...
    test_cmd: str | None = None  # "pytest" | "npm test" | ...
    has_makefile: bool = False
    has_dockerfile: bool = False


class GfiInfo(BaseModel):
    count: int = 0
    oldest_days: int | None = None  # days since the oldest open good-first-issue


class ActivityInfo(BaseModel):
    commits_30d: int = 0
    last_release_days: int | None = None


Suitability = Literal["promising", "unclear", "avoid"]


class Profile(BaseModel):
    """Result of module-1 reconnaissance + module decision-tree suitability."""

    owner: str
    repo: str
    html_url: str = ""
    description: str = ""
    stars: int = 0
    forks: int = 0
    open_issues: int = 0
    languages: dict[str, float] = Field(default_factory=dict)  # {"python": 0.72, ...}
    license: str | None = None
    default_branch: str = "main"
    has_readme: bool = False
    has_contributing: bool = False
    has_docs: bool = False
    build: BuildInfo = Field(default_factory=BuildInfo)
    gfi: GfiInfo = Field(default_factory=GfiInfo)
    activity: ActivityInfo = Field(default_factory=ActivityInfo)
    suitability: Suitability = "unclear"
    reasons: list[str] = Field(default_factory=list)  # human-readable decision notes
