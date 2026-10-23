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
    # Exploratory samples never count as beginner-labelled issues in profiling.
    issue_samples: list[dict] = Field(default_factory=list)
    issues_collected_at: str = ""
    commits_30d: int = 0
    file_tree: list[str] = Field(default_factory=list)  # repo-relative file paths
    unavailable_signals: list[str] = Field(default_factory=list)
    collection_warnings: list[str] = Field(default_factory=list)
    symlink_paths: list[str] = Field(default_factory=list)


# Doc files fetched during enrichment (README/CONTRIBUTING/LICENSE + docs/**).
_DOC_PATHS = ("README.md", "README.rst", "README", "CONTRIBUTING.md", "CONTRIBUTING",
              "LICENSE", "LICENSE.md", "LICENSE.txt")

# Build/config files at the repo root. They are where the *real* install and
# test commands usually live (a Makefile `test:` target, a package.json
# `scripts.test`, a pyproject `[tool.pytest]`), so they must be fetched as text —
# otherwise "how do I run the tests" has nothing to ground on. They are small
# and are only used as V3 (executable path) material.
_BUILD_FILES = ("Makefile", "makefile", "GNUmakefile", "pyproject.toml",
                "package.json", "tox.ini", "setup.cfg", "setup.py",
                "Cargo.toml", "go.mod", "Gemfile", "composer.json",
                "requirements.txt", "requirements-dev.txt", "Dockerfile",
                "docker-compose.yml", "docker-compose.yaml", "compose.yml", "compose.yaml")

_MAX_DOC_SIZE = 200_000  # skip absurdly large docs


def _age_days(iso: str | None) -> int | None:
    if not iso:
        return None
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        return max(0, int((datetime.now(timezone.utc) - dt).total_seconds() // 86400))
    except ValueError:
        return None


def _commit_recent(item: dict, cutoff: datetime) -> bool:
    date = ((item.get("commit") or {}).get("committer") or {}).get("date")
    if not date:
        return False
    try:
        return datetime.fromisoformat(date.replace("Z", "+00:00")) >= cutoff
    except (ValueError, TypeError):
        return False


def recon(owner: str, repo: str, client: GitHubClient | None = None) -> RawSignals:
    """Collect the raw signal bundle for (owner, repo)."""
    client = client or GitHubClient()
    data = client.get_repo(owner, repo)
    unavailable, warnings = [], []

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
        unavailable.append("languages")
        warnings.append("语言信息抓取失败，不能按空结果判断")

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
        unavailable.append("root")
        warnings.append("根目录信息抓取失败，文件存在性待确认")

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
        unavailable.append("issues")
        warnings.append("新手任务信息未完整取得，不能据此判断没有任务")

    issue_samples = []
    if not any(i.get('state') == 'open' and i.get('pull_request') is None and not i.get('locked')
               and not i.get('assignees') and not i.get('assignee') for i in issues):
        try:
            issue_samples = client.list_issues(owner, repo, per_page=30)
        except GitHubClientError:
            unavailable.append("issue_samples")
            warnings.append("普通开放 issue 采样失败，可通过 GitHub 检索入口人工核对")
    issues_collected_at = datetime.now(timezone.utc).isoformat()

    # Recent commits for activity signal.
    commits = 0
    try:
        from datetime import timedelta
        cutoff = datetime.now(timezone.utc) - timedelta(days=30)
        recent = client.list_commits(owner, repo, per_page=30)
        commits = sum(1 for item in recent if _commit_recent(item, cutoff))
    except GitHubClientError:
        commits = 0
        unavailable.append("activity")
        warnings.append("提交活跃度未取得，不能按零提交判断")

    return RawSignals(
        meta=meta,
        language_bytes=lang_bytes,
        root_entries=root_entries,
        has_docs_dir=has_docs_dir,
        has_license_file=has_license_file,
        issues=issues,
        issue_samples=issue_samples,
        issues_collected_at=issues_collected_at,
        commits_30d=commits,
        file_tree=[],
        unavailable_signals=unavailable,
        collection_warnings=warnings,
    )


def enrich_docs_and_tree(
    sig: RawSignals, client: GitHubClient | None = None
) -> RawSignals:
    """Second pass: fetch doc file texts and the full file tree.

    Separated from `recon` so the cheap profile path (M0) stays fast and the
    heavier docs/tree fetch only runs when perspectives/indexing need it.
    """
    client = client or GitHubClient()
    # Fail rather than combine documents from changing branch revisions.
    revision = client.resolve_commit(sig.meta.owner, sig.meta.repo, sig.meta.default_branch)
    meta = sig.meta.model_copy(update={"default_branch": revision})
    listing = client.get_contents(meta.owner, meta.repo, "", ref=revision)
    if not isinstance(listing, list):
        raise GitHubClientError("无法取得固定版本的仓库根目录")
    root = {entry["name"].lower(): entry["name"] for entry in listing if entry.get("name")}
    unavailable = list(sig.unavailable_signals)
    warnings = list(sig.collection_warnings)
    warnings.append(f"文件证据固定于提交 {revision}；issue 信息是独立采集的快照，操作前需核对最新状态。")
    docs_dir_name = root.get("docs")

    doc_files: list[DocFile] = []
    # Root-level doc candidates + docs/<some path> limited crawl.
    fetch_paths: list[str] = []
    for cand in _DOC_PATHS:
        actual = root.get(cand.lower())
        if actual:
            fetch_paths.append(actual)

    # Build/config files: small, and the only place some repos state how to run
    # the test suite (Makefile / package.json / pyproject).
    for cand in _BUILD_FILES:
        actual = root.get(cand.lower())
        if actual:
            fetch_paths.append(actual)

    # Full file tree: cheap single request, gives us exact doc paths to fetch.
    file_tree: list[str] = []
    symlink_paths: list[str] = []
    try:
        tree = client.get_git_tree(meta.owner, meta.repo, revision)
        file_tree = [t.get("path", "") for t in tree if t.get("type") == "blob" and t.get("path")]
        symlink_paths = [t["path"] for t in tree if t.get("mode") == "120000" and t.get("path")]
    except GitHubClientError:
        file_tree = []
        unavailable.append("tree")
        warnings.append("文件树未取得，目录与引用覆盖可能不完整")

    # Multi-component projects keep manifests below frontend/backend/packages.
    # A bounded, shallow crawl avoids generated dependencies and vendored code.
    config_names = {name.lower() for name in _BUILD_FILES}
    excluded = {'node_modules', 'vendor', 'dist', 'build', 'static', 'assets',
                '.venv', 'venv', '.git', '__pycache__', 'output', 'tmp', 'fixtures'}
    configs = sorted((p for p in file_tree if
        p.rsplit('/', 1)[-1].lower() in config_names
        and len(p.split('/')) <= 4
        and not any(part.lower() in excluded for part in p.split('/')[:-1])
        and p not in symlink_paths), key=lambda p: (p.count('/'), p))
    fetch_paths.extend(configs[:24])
    if len(configs) > 24:
        unavailable.append('build_configs')
        warnings.append('构建配置超过采集上限（24 份），子项目覆盖不完整，请按目标组件核对。')

    # Pick key newcomer-relevant docs from the tree (dev/contributing/guide/
    # installation/tutorial under docs/ or at root), plus a cap of other docs.
    _TEXT_EXT = (".md", ".rst", ".txt")
    _KEY_SEGMENTS = ("contribut", "develop", "guide", "install", "setup", "tutorial", "getting", "usage", "workflow")
    picked: list[str] = []
    keyed: list[str] = []
    for p in file_tree:
        low = p.lower()
        name = low.rsplit("/", 1)[-1]
        if (name.rsplit(".", 1)[0] in {"contributing", "code_of_conduct", "pull_request_template"}
                or low.startswith(".github/pull_request_template/")) and low.endswith(_TEXT_EXT):
            keyed.insert(0, p)
            continue
        if low.startswith(".github/workflows/") and low.endswith((".yml", ".yaml")):
            keyed.append(p)
            continue
        if not low.endswith(_TEXT_EXT):
            continue
        if low.startswith(".") or any(part in excluded for part in low.split('/')[:-1]):
            continue
        segs = low.split("/")
        # Key if under docs/dev|docs/contribut*|... or filename carries keyword.
        in_docs = segs[0] == "docs" if segs else False
        is_key = any(k in low for k in _KEY_SEGMENTS)
        # Skip docs/__something__/ (api/autodoc/reference) unless it has a keyword.
        if in_docs and not is_key:
            continue
        if is_key:
            keyed.append(p)
        elif len(picked) < 40:
            picked.append(p)
    fetch_paths.extend(keyed[:30])
    fetch_paths.extend(picked[:10])

    failed_paths: list[str] = []
    for path in fetch_paths:
        if path.lower() in {d.path.lower() for d in doc_files}:
            continue
        try:
            text = client.get_file_text(meta.owner, meta.repo, path, ref=revision)
        except GitHubClientError:
            failed_paths.append(path)
            if "docs" not in unavailable:
                unavailable.append("docs")
                warnings.append("部分文档抓取失败，仅能依据已取得的原文生成")
            continue
        if text is None or len(text) > _MAX_DOC_SIZE:
            if "docs" not in unavailable:
                unavailable.append("docs")
                warnings.append("部分文档不存在或超过大小限制，资料覆盖不完整")
            continue
        doc_files.append(DocFile(path=path, name=path.split("/")[-1], text=text))

    if failed_paths:
        warnings.append(f"未取得 {len(failed_paths)} 份文档（前 5 项）：" + "、".join(failed_paths[:5]) + "；可稍后重试，当前指南不覆盖这些资料。")

    return RawSignals(
        meta=meta,
        language_bytes=sig.language_bytes,
        root_entries=root,
        has_docs_dir="docs" in root,
        has_license_file=any(name.startswith("license") for name in root),
        doc_files=doc_files,
        issues=sig.issues,
        issue_samples=sig.issue_samples,
        issues_collected_at=sig.issues_collected_at,
        commits_30d=sig.commits_30d,
        file_tree=file_tree,
        unavailable_signals=unavailable,
        collection_warnings=warnings,
        symlink_paths=symlink_paths,
    )
