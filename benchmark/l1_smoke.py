"""L1 smoke test — the offline, hermetic link-check for the whole pipeline.

L1 measures nothing about output *quality*. It feeds a fixed local fixture
(no GitHub, no LLM key, no chroma, no network) through the chain

    URL 解析 -> RawSignals -> 画像 -> 决策树 -> 四视角索引 -> 生成
    -> Guide schema -> 证据审计

and asserts each link holds. Quality numbers only ever come from L2, and only
over human-verified golden repos (口径红线，见 README.md）。

Run:  uv run python -m benchmark.l1_smoke
Exit: 0 = 链路通，1 = 有环节断。
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "backend" / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "backend" / "src"))

# Hermetic by construction: in-memory index instead of chroma, heuristic
# generator instead of any LLM. Must be set before backend.config first builds
# Settings (it is lru_cached).
os.environ.setdefault("USE_CHROMA", "false")

from backend.core.decide.decider import decide  # noqa: E402
from backend.core.generate.evidence import resolve_evidence_source  # noqa: E402
from backend.core.generate.pipeline import build_guide  # noqa: E402
from backend.core.generate.schemas import Guide  # noqa: E402
from backend.core.github.models import DocFile, RepoMeta  # noqa: E402
from backend.core.github.parse import parse_github_url  # noqa: E402
from backend.core.github.recon import RawSignals  # noqa: E402
from backend.core.index.service import RepoIndex  # noqa: E402
from backend.core.profile.builder import build_profile  # noqa: E402

# The fixture's command lines. Generation is allowed to pick these up verbatim
# and nothing else — L1 asserts the generator does not invent commands.
_FIXTURE_COMMANDS = {"pip install -e .[dev]", "python -m pytest -q"}

_FIXTURE_README = """\
# Widget

A tiny fixture library that exists only for the L1 smoke test.

## Install

```bash
pip install -e .[dev]
```

## Test

```bash
python -m pytest -q
```

## Contributing

Fork the repository, create a branch, commit your change, and open a pull
request against `main`.
"""

_FIXTURE_CONTRIBUTING = """\
# Contributing to Widget

1. Fork and clone the repository.
2. Run the tests before you push.
3. Open a pull request against `main`.
"""


def _fixture_signals(owner: str, repo: str) -> RawSignals:
    """A healthy repo: stars / activity / README / license / one GFI."""
    return RawSignals(
        meta=RepoMeta(
            owner=owner,
            repo=repo,
            description="L1 smoke fixture",
            stars=120,
            forks=9,
            open_issues=4,
            default_branch="main",
            license="MIT",
            created_at="2024-01-01T00:00:00Z",
            pushed_at="2026-09-01T00:00:00Z",
            html_url=f"https://github.com/{owner}/{repo}",
        ),
        language_bytes={"Python": 900, "Shell": 100},
        root_entries={
            "readme.md": "README.md",
            "contributing.md": "CONTRIBUTING.md",
            "pyproject.toml": "pyproject.toml",
            "license": "LICENSE",
        },
        has_docs_dir=False,
        has_license_file=True,
        doc_files=[
            DocFile(path="README.md", name="README.md", text=_FIXTURE_README),
            DocFile(path="CONTRIBUTING.md", name="CONTRIBUTING.md", text=_FIXTURE_CONTRIBUTING),
        ],
        issues=[
            {
                "number": 7,
                "title": "Fix typo in README",
                "body": "Small documentation fix.",
                "state": "open",
                "pull_request": None,
                "created_at": "2026-01-05T00:00:00Z",
                "labels": [{"name": "good first issue"}],
            },
            {
                "number": 8,
                "title": "Add a changelog",
                "body": "",
                "state": "open",
                "pull_request": {"url": f"https://github.com/{owner}/{repo}/pull/8"},
                "created_at": "2026-02-05T00:00:00Z",
                "labels": [],
            },
        ],
        commits_30d=8,
        file_tree=[
            "README.md",
            "CONTRIBUTING.md",
            "pyproject.toml",
            "LICENSE",
            "src/widget/__init__.py",
        ],
    )


def _fixture_avoid_signals(owner: str, repo: str) -> RawSignals:
    """An unhealthy repo: tiny, dormant, no README, no license."""
    return RawSignals(
        meta=RepoMeta(
            owner=owner,
            repo=repo,
            description="abandoned toy",
            stars=3,
            forks=0,
            open_issues=0,
            default_branch="main",
            license=None,
            created_at="2019-01-01T00:00:00Z",
            pushed_at="2021-01-01T00:00:00Z",
            html_url=f"https://github.com/{owner}/{repo}",
        ),
        language_bytes={"Python": 100},
        root_entries={},
        commits_30d=0,
        file_tree=["main.py"],
    )


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass

    failures: list[str] = []

    def check(name: str, ok: bool, detail: str = "") -> None:
        print(f"  {'PASS' if ok else 'FAIL'}  {name}" + (f"  ({detail})" if detail else ""))
        if not ok:
            failures.append(name)

    print("L1 烟测（离线 fixture，只验链路通不通，不代表生成质量）")

    # ---- [1] 健康仓库：全链路 ------------------------------------------------
    print("\n[1] URL→画像→决策树→索引→生成→schema→证据")
    owner, repo = parse_github_url("https://github.com/acme/widget")
    check("URL 解析", (owner, repo) == ("acme", "widget"), f"{owner}/{repo}")

    sig = _fixture_signals(owner, repo)
    profile = build_profile(sig)
    check("画像 owner/repo", (profile.owner, profile.repo) == (owner, repo))
    check(
        "画像语言占比归一",
        abs(sum(profile.languages.values()) - 1.0) < 1e-9
        and profile.languages.get("Python", 0) > profile.languages.get("Shell", 0),
        str(profile.languages),
    )
    check(
        "构建面识别",
        (profile.build.tool, profile.build.package_manager, profile.build.test_cmd)
        == ("pyproject.toml", "uv", "pytest"),
        f"{profile.build.tool}/{profile.build.package_manager}/{profile.build.test_cmd}",
    )
    check("画像 README 标记", profile.has_readme is True)

    suitability, reasons = decide(profile)
    check("决策树判 promising", suitability == "promising", f"{suitability}，{len(reasons)} 条理由")

    index = RepoIndex(owner, repo)
    index.index(sig)
    guide = build_guide(sig, index=index, use_llm=False)

    check("生成了步骤", len(guide.steps) > 0, f"{len(guide.steps)} 步")
    stages = [s.stage for s in guide.steps]
    check("四阶段 A-D 均产出", set(stages) == {"A", "B", "C", "D"}, ",".join(stages))

    ids = [s.step_id for s in guide.steps]
    check("step_id 唯一且递增", ids == sorted(ids) and len(set(ids)) == len(ids), str(ids))
    check("每步有标题", all(s.title.strip() for s in guide.steps))
    check("每步有 stage_label", all(s.stage_label.strip() for s in guide.steps))

    round_tripped = Guide.model_validate(guide.model_dump())
    check(
        "Guide 可回环校验 schema",
        len(round_tripped.steps) == len(guide.steps),
        f"{len(round_tripped.steps)} 步",
    )

    commands = [s.command for s in guide.steps if s.command]
    check("至少一步带可执行命令", bool(commands), "; ".join(commands) or "无")
    check(
        "命令全部来自 fixture 原文（未编造）",
        all(c in _FIXTURE_COMMANDS for c in commands),
        str(commands),
    )

    bad_evidence: list[str] = []
    for s in guide.steps:
        ev = s.evidence
        if ev.kind == "missing":
            if ev.source:
                bad_evidence.append(f"step{s.step_id} 标 missing 却带 source={ev.source!r}")
            continue
        resolved = resolve_evidence_source(ev.source, sig)
        if resolved.kind != ev.kind:
            bad_evidence.append(
                f"step{s.step_id} 声称 {ev.kind} 但校验为 {resolved.kind}（{ev.source}）"
            )
    check("无证据不宣称：非 missing 证据均可回溯", not bad_evidence, "; ".join(bad_evidence))

    # ---- [2] 不健康仓库：决策树 avoid 分支 ----------------------------------
    print("\n[2] 决策树 avoid 分支：不适合则不硬生成")
    avoid_sig = _fixture_avoid_signals("acme", "dead-repo")
    avoid_suitability, _ = decide(build_profile(avoid_sig))
    check("决策为 avoid", avoid_suitability == "avoid", avoid_suitability)

    avoid_guide = build_guide(avoid_sig, use_llm=False)
    check("unsuitable 透传到 guide", avoid_guide.unsuitable is True)
    check("不为 avoid 仓库硬生成步骤", avoid_guide.steps == [], f"{len(avoid_guide.steps)} 步")
    check("avoid 时给出理由", len(avoid_guide.reasons) >= 2, f"{len(avoid_guide.reasons)} 条")

    # ---- 汇总 ---------------------------------------------------------------
    print(f"\n{'=' * 70}")
    if failures:
        print(f"L1 失败：{len(failures)} 项未通过")
        for name in failures:
            print(f"  - {name}")
        return 1
    print("L1 通过：URL→画像→决策树→索引→生成→schema→证据 全链路在离线 fixture 上跑通")
    print("（重申：L1 不产出任何质量数字；质量数字见 L2 golden 评估）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())