"""Assemble a Profile from raw recon signals — pure functions, testable offline.

Language byte counts are normalised to fractions. Build detection keys off the
root file listing; doc presence off README/CONTRIBUTING/docs/LICENSE.
"""

from __future__ import annotations

import re

from backend.core.github.recon import RawSignals
from backend.core.profile.schema import ActivityInfo, BuildInfo, GfiInfo, Profile

_BUILD_TO_PKG_MANAGER = {
    "pyproject.toml": "uv",
    "requirements.txt": "pip",
    "setup.py": "pip",
    "package.json": "pnpm",
    "Cargo.toml": "cargo",
    "go.mod": "go",
    "Gemfile": "bundler",
}

_BUILD_TO_TEST_CMD = {
    "pyproject.toml": "pytest",
    "requirements.txt": "pytest",
    "setup.py": "pytest",
    "package.json": "npm test",
    "Cargo.toml": "cargo test",
    "go.mod": "go test",
    "Gemfile": "bundle exec rspec",
}


def _normalise_languages(bytes_: dict[str, int]) -> dict[str, float]:
    total = sum(bytes_.values())
    if total <= 0:
        return {}
    return {k: round(v / total, 3) for k, v in sorted(bytes_.items(), key=lambda kv: -kv[1])}


def _detect_build(root_entries: dict[str, str]) -> BuildInfo:
    keys = set(root_entries.keys())
    tool: str | None = None
    for marker in _BUILD_TO_PKG_MANAGER:
        if marker in keys:
            tool = marker
            break
    if tool is None:
        return BuildInfo()
    return BuildInfo(
        tool=tool,
        package_manager=_BUILD_TO_PKG_MANAGER[tool],
        test_cmd=_BUILD_TO_TEST_CMD.get(tool),
        has_makefile="makefile" in keys,
        has_dockerfile="dockerfile" in keys,
    )


def build_profile(sig: RawSignals) -> Profile:
    root = sig.root_entries
    meta = sig.meta
    is_python = "python" in (sig.language_bytes or {})

    # Age of oldest open beginner-friendly issue.
    issue_dates = [i.get("created_at", "") for i in sig.issues if i.get("pull_request") is None]
    oldest_issue_days = None
    if issue_dates:
        from backend.core.github.recon import _age_days

        ages = [_age_days(d) for d in issue_dates]
        ages = [a for a in ages if a is not None]
        if ages:
            oldest_issue_days = max(ages)

    build = _detect_build(root)

    return Profile(
        owner=meta.owner,
        repo=meta.repo,
        html_url=meta.html_url,
        description=meta.description,
        stars=meta.stars,
        forks=meta.forks,
        open_issues=meta.open_issues,
        languages=_normalise_languages(sig.language_bytes),
        license=meta.license,
        default_branch=meta.default_branch,
        has_readme="readme.md" in root,
        has_contributing=any(
            name in root for name in ("contributing.md", "contributing")
        ),
        has_docs=sig.has_docs_dir,
        build=build,
        gfi=GfiInfo(count=len(issue_dates), oldest_days=oldest_issue_days),
        activity=ActivityInfo(
            commits_30d=sig.commits_30d,
            last_release_days=_release_age(meta.pushed_at),
        ),
    )


def _release_age(pushed_at: str) -> int | None:
    if not pushed_at:
        return None
    from backend.core.github.recon import _age_days

    return _age_days(pushed_at)
