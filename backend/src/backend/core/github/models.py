"""Data models returned by the GitHub reconnaissance layer."""

from __future__ import annotations

from pydantic import BaseModel, Field


class RepoMeta(BaseModel):
    owner: str
    repo: str
    description: str = ""
    stars: int = 0
    forks: int = 0
    open_issues: int = 0
    default_branch: str = "main"
    license: str | None = None
    created_at: str = ""
    pushed_at: str = ""
    html_url: str = ""


class DocFile(BaseModel):
    path: str
    name: str
    text: str = ""


class Entry(BaseModel):
    """A file or directory under a path in the tree."""

    name: str
    path: str
    type: str = Field(description="file | dir")
    size: int | None = None
