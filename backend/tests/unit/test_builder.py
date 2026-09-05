"""Profile builder unit tests over hand-built RawSignals."""

from __future__ import annotations

from backend.core.github.models import RepoMeta
from backend.core.github.recon import RawSignals
from backend.core.profile.builder import build_profile


def make_signals(
    languages: dict[str, int] | None = None,
    root: dict[str, str] | None = None,
    has_docs_dir: bool = False,
    issues: list[dict] | None = None,
    commits_30d: int = 10,
) -> RawSignals:
    return RawSignals(
        meta=RepoMeta(
            owner="o",
            repo="r",
            stars=100,
            pushed_at="",
        ),
        language_bytes=languages or {"python": 8000, "typescript": 2000},
        root_entries=root or {"readme.md": "README.md", "pyproject.toml": "pyproject.toml"},
        has_docs_dir=has_docs_dir,
        doc_files=[],
        issues=issues or [],
        commits_30d=commits_30d,
    )


def test_language_normalised_fractions():
    sig = make_signals(languages={"python": 8000, "typescript": 2000})
    p = build_profile(sig)
    assert p.languages["python"] == 0.8
    assert p.languages["typescript"] == 0.2


def test_build_detection_python():
    p = build_profile(make_signals(root={"readme.md": "R", "pyproject.toml": "p"}))
    assert p.build.tool == "pyproject.toml"
    assert p.build.test_cmd == "pytest"
    assert p.has_readme is True


def test_contributing_presence():
    p = build_profile(make_signals(root={"readme.md": "R", "contributing.md": "C"}))
    assert p.has_contributing is True


def test_docs_dir_flag():
    sig = make_signals(root={"readme.md": "R"}, has_docs_dir=True)
    assert build_profile(sig).has_docs is True


def test_gfi_counts_non_pr_issues():
    issues = [
        {"number": 1, "created_at": "2026-08-01T00:00:00Z"},
        {"number": 2, "created_at": "2026-08-10T00:00:00Z", "pull_request": {}},
    ]
    p = build_profile(make_signals(issues=issues))
    assert p.gfi.count == 1
