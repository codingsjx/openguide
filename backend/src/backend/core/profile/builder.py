"""Assemble a Profile from raw recon signals — pure functions, testable offline.

Language byte counts are normalised to fractions. Build detection inventories
root and shallow component manifests; it does not guess runnable commands.
"""

from __future__ import annotations

from pathlib import PurePosixPath

from backend.core.github.recon import RawSignals
from backend.core.profile.schema import ActivityInfo, BuildInfo, GfiInfo, Profile

_BUILD_MANIFESTS = ('pyproject.toml', 'requirements.txt', 'setup.py',
                    'package.json', 'Cargo.toml', 'go.mod', 'Gemfile')

def _normalise_languages(bytes_: dict[str, int]) -> dict[str, float]:
    total = sum(bytes_.values())
    if total <= 0:
        return {}
    return {k: round(v / total, 3) for k, v in sorted(bytes_.items(), key=lambda kv: -kv[1])}


def _detect_build(sig: RawSignals) -> BuildInfo:
    # Filename inventory is not proof of an install tool or a test command.
    markers = {name.lower() for name in _BUILD_MANIFESTS} | {
        'makefile', 'gnumakefile', 'dockerfile', 'tox.ini', 'setup.cfg',
        'composer.json', 'docker-compose.yml', 'docker-compose.yaml', 'compose.yml', 'compose.yaml'}
    excluded = {'node_modules', 'vendor', 'dist', 'build', '.venv', 'venv', '.git',
                '__pycache__', 'output', 'tmp', 'fixtures', 'examples', 'samples'}
    paths = set(sig.file_tree) | {d.path for d in sig.doc_files}
    if not sig.file_tree:
        paths.update(sig.root_entries.values())
    manifests = sorted((path for path in paths
        if len(path.split('/')) <= 4 and PurePosixPath(path).name.lower() in markers
        and not any(part.lower() in excluded for part in path.split('/')[:-1])
        and path not in sig.symlink_paths), key=lambda p: (p.count('/'), p.lower()))
    status = 'partial' if 'tree' in sig.unavailable_signals else 'tree' if sig.file_tree else 'root_only'
    if not manifests and 'root' in sig.unavailable_signals and 'tree' in sig.unavailable_signals:
        status = 'unavailable'
    if len(manifests) > 24:
        status = 'partial'
    primary = next((p for marker in _BUILD_MANIFESTS for p in manifests
                    if '/' not in p and p.lower() == marker.lower()), None)
    primary = primary or next((p for marker in _BUILD_MANIFESTS for p in manifests
                               if PurePosixPath(p).name.lower() == marker.lower()), None)
    return BuildInfo(
        tool=PurePosixPath(primary or manifests[0]).name if manifests else None,
        manifest_paths=manifests[:24], scan_status=status,
        has_makefile=any(PurePosixPath(p).name.lower() in {'makefile', 'gnumakefile'} for p in manifests),
        has_dockerfile=any(PurePosixPath(p).name.lower() == 'dockerfile' for p in manifests),
    )


def build_profile(sig: RawSignals) -> Profile:
    root = sig.root_entries
    meta = sig.meta

    # Age of oldest open beginner-friendly issue.
    issue_dates = [i.get("created_at", "") for i in sig.issues if i.get("pull_request") is None]
    oldest_issue_days = None
    if issue_dates:
        from backend.core.github.recon import _age_days

        ages = [_age_days(d) for d in issue_dates]
        ages = [a for a in ages if a is not None]
        if ages:
            oldest_issue_days = max(ages)

    build = _detect_build(sig)

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
        revision=meta.default_branch if len(meta.default_branch) == 40 else '',
        has_readme=any(n in root for n in ("readme.md", "readme.rst", "readme")),
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
        unavailable_signals=sig.unavailable_signals,
        collection_warnings=sig.collection_warnings,
    )


def _release_age(pushed_at: str) -> int | None:
    if not pushed_at:
        return None
    from backend.core.github.recon import _age_days

    return _age_days(pushed_at)
