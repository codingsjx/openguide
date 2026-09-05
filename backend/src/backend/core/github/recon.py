"""Raw reconnaissance signals gathered from the GitHub API.

Pure data collection — no decisions made here. The builder (profile/builder.py)
turns these signals into a Profile; the decider (decide/decider.py) judges
suitability. Kept separate so each stage is independently testable.
"""

from __future__ import annotations

from datetime import datetime, timezone

from pydantic import BaseModel, Field

from backend.core.github.client import GitHubClient, GitHubClientError
from backend.core.github.models import DocFile, RepoMeta

# Build-system marker files at repo root.
_BUILD_MARKERS = {
    "pyproject.toml": "pyproject.toml",
    "requirements.txt": "requirements.txt",
    "setup.py": "setup.py",
    "package.json": "package.json",
    "Cargo.toml": "Cargo.toml",
    "go.mod": "go.mod",
    "Gemfile": "Gemfile",
    "Makefile": "Makefile",
    "Dockerfile": "Dockerfile",
}


class RawSignals(BaseModel):
    """Raw, judgment-free signal bundle from reconnaissance."""

    meta: RepoMeta
    language_bytes: dict[str, int] = Field(default_factory=dict)
    root_entries: dict[str, str] = Field(default_factory=dict)  # lowercase name -> original
    has_docs_dir: bool = False
    has_license_file: bool = False
    doc_files: list[DocFile] = Field(default_factory=list)
    issues: list[dict] = Field(default_factory=list)
    commits_30d: int = 0


def _age_days(iso: str | None) -> int | None:
    if not iso:
        return None
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        return max(0, int((datetime.now(timezone.utc) - dt).total_seconds() // 86400))
    except ValueError:
        return None


def recon(owner: str, repo: str, client: GitHubClient | None = None) -> RawSignals:
    """Collect the raw signal bundle for (owner, repo)."""
    client = client or GitHubClient()
    data = client.get_repo(owner, repo)

    meta = RepoMeta(
        owner=owner,
        repo=repo,
        description=data.get("description") or "",
        stars=data.get("stargazers_count") or 0,
        forks=data.get("forks_count") or 0,
        open_issues=data.get("open_issues_count") or 0,
        default_branch=data.get("default_branch") or "main",
        license=(data.get("license") or {}).get("spdx_id"),
        created_at=data.get("created_at") or "",
        pushed_at=data.get("pushed_at") or "",
        html_url=data.get("html_url") or f"https://github.com/{owner}/{repo}",
    )

    # Language proportions (bytes) from the API languages endpoint.
    lang_bytes: dict[str, int] = {}
    try:
        raw_lang = client._get_json(f"/repos/{owner}/{repo}/languages")
        if isinstance(raw_lang, dict):
            lang_bytes = raw_lang
    except GitHubClientError:
        lang_bytes = {}

    # Root listing: build markers + doc presence.
    root_entries: dict[str, str] = {}
    has_docs_dir = False
    has_license_file = False
    try:
        listing = client.get_contents(owner, repo, "")
        if isinstance(listing, list):
            for e in listing:
                name = e.get("name", "")
                root_entries[name.lower()] = name
                if name.lower() == "docs":
                    has_docs_dir = True
                if name.lower().startswith("license"):
                    has_license_file = True
    except GitHubClientError:
        pass

    # Good-first-issue / help-wanted issues (dedup by number).
    issues: list[dict] = []
    seen_numbers: set[int] = set()
    try:
        for labels in ("good first issue", "help wanted"):
            for issue in client.list_issues(owner, repo, labels=labels):
                num = issue.get("number")
                if num in seen_numbers:
                    continue
                seen_numbers.add(num)
                issues.append(issue)
    except GitHubClientError:
        issues = []

    # Recent commits for activity signal.
    commits = 0
    try:
        commits = len(client.list_commits(owner, repo, per_page=30))
    except GitHubClientError:
        commits = 0

    return RawSignals(
        meta=meta,
        language_bytes=lang_bytes,
        root_entries=root_entries,
        has_docs_dir=has_docs_dir,
        has_license_file=has_license_file,
        issues=issues,
        commits_30d=commits,
    )
