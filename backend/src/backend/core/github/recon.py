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
    file_tree: list[str] = Field(default_factory=list)  # repo-relative file paths


# Doc files fetched during enrichment (README/CONTRIBUTING/LICENSE + docs/**).
_DOC_PATHS = ("README.md", "README.rst", "README", "CONTRIBUTING.md", "CONTRIBUTING",
              "LICENSE", "LICENSE.md", "LICENSE.txt")
_MAX_DOC_SIZE = 200_000  # skip absurdly large docs


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
        file_tree=[],
    )


def enrich_docs_and_tree(
    sig: RawSignals, client: GitHubClient | None = None
) -> RawSignals:
    """Second pass: fetch doc file texts and the full file tree.

    Separated from `recon` so the cheap profile path (M0) stays fast and the
    heavier docs/tree fetch only runs when perspectives/indexing need it.
    """
    client = client or GitHubClient()
    root = sig.root_entries
    docs_dir_name = root.get("docs")

    doc_files: list[DocFile] = []
    # Root-level doc candidates + docs/<some path> limited crawl.
    fetch_paths: list[str] = []
    for cand in _DOC_PATHS:
        actual = root.get(cand.lower())
        if actual:
            fetch_paths.append(actual)

    # Full file tree: cheap single request, gives us exact doc paths to fetch.
    file_tree: list[str] = []
    try:
        tree = client.get_git_tree(sig.meta.owner, sig.meta.repo, sig.meta.default_branch)
        file_tree = [t.get("path", "") for t in tree if t.get("type") == "blob" and t.get("path")]
    except GitHubClientError:
        file_tree = []

    # Pick key newcomer-relevant docs from the tree (dev/contributing/guide/
    # installation/tutorial under docs/ or at root), plus a cap of other docs.
    _TEXT_EXT = (".md", ".rst", ".txt")
    _KEY_SEGMENTS = ("contribut", "develop", "guide", "install", "setup", "tutorial", "getting", "usage", "workflow")
    picked: list[str] = []
    keyed: list[str] = []
    for p in file_tree:
        low = p.lower()
        if not low.endswith(_TEXT_EXT):
            continue
        if low.startswith(".") or low.startswith(("node_modules", "vendor", "dist", "build", "static", "assets")):
            continue
        segs = low.split("/")
        # Key if under docs/dev|docs/contribut*|... or filename carries keyword.
        in_docs = segs[0] == "docs" if segs else False
        is_key = any(k in low for k in _KEY_SEGMENTS)
        # Skip docs/__something__/ (api/autodoc/reference) unless it has a keyword.
        if in_docs and not is_key:
            continue
        if len(picked) >= 40:
            break
        (keyed if is_key else picked).append(p)
    fetch_paths.extend(keyed)
    fetch_paths.extend(picked)

    for path in fetch_paths:
        if path.lower() in {d.path.lower() for d in doc_files}:
            continue
        text = client.get_file_text(sig.meta.owner, sig.meta.repo, path)
        if text is None or len(text) > _MAX_DOC_SIZE:
            continue
        doc_files.append(DocFile(path=path, name=path.split("/")[-1], text=text))

    return RawSignals(
        meta=sig.meta,
        language_bytes=sig.language_bytes,
        root_entries=sig.root_entries,
        has_docs_dir=sig.has_docs_dir,
        has_license_file=sig.has_license_file,
        doc_files=doc_files,
        issues=sig.issues,
        commits_30d=sig.commits_30d,
        file_tree=file_tree,
    )
