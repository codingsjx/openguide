"""Verify the *generated* guide against both the golden reference AND a real
execution environment — the full four-metric quality score for OpenGuide's output.

This script measures what the *product* produces: it calls the backend guide
generator, then scores the result on four dimensions:

- step_coverage  : 步骤完整率 — did the generated steps cover the golden steps?
- evidence_hit   : 证据命中率 — does each command's evidence resolve to a real file?
- command_correct: 命令正确率 — does each command match the golden reference for its stage?
- command_exec   : 命令可执行率 — does each command actually run in a fresh clone?
- assert_rate    : 有据断言率 — how many steps carry non-missing evidence?

Zero manual prep: the script clones the repo, detects its language, provisions
the environment, runs every generated command, and reports per-repo + total
rates with per-command error reasons.

Caching: repos live in ``_run_cache/<owner>__<repo>/``. Pass ``--cleanup`` to wipe.

Run from the repo root:
    backend/.venv/Scripts/python.exe benchmark/verify_generated_guide.py psf/requests
    backend/.venv/Scripts/python.exe benchmark/verify_generated_guide.py --cleanup
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backend" / "src"))

CACHE_DIR = ROOT / "_run_cache"
REPORTS_DIR = ROOT / "benchmark" / "reports"

# Node install dir, appended to PATH so npm/node resolve regardless of the
# parent shell's environment.
NODE_DIR = Path(r"C:\Users\Lenovo\node\node-v24.21.0-win-x64")

_DEFAULT_REPOS = [
    "psf/requests",
    "pallets/click",
    "cookiecutter/cookiecutter",
    "mochajs/mocha",
]

# Commands that the script itself has already performed during setup, so
# re-running them inside an already-cloned workdir would falsely fail (e.g.
# `git clone` fails because the destination already exists). These are marked
# "handled by the harness" and excluded from the command_exec denominator —
# their correctness is judged by command_correct instead.
_HARNESS_HANDLED_PREFIXES = (
    "git clone",
    "cd ",
)


def parse_repo_arg(arg: str) -> tuple[str, str]:
    """Accept 'owner/repo' or a full GitHub URL."""
    arg = arg.strip().rstrip("/")
    if "://" in arg:
        parts = [p for p in arg.split("/") if p and p not in ("https:", "http:", "github.com")]
        return parts[0], parts[1]
    owner, repo = arg.split("/", 1)
    return owner, repo


def generate_guide(owner: str, repo: str):
    """Call the backend generator (offline heuristic mode — no LLM key needed)."""
    from backend.api.routes.guide import GuideRequest, make_guide

    return make_guide(GuideRequest(url=f"https://github.com/{owner}/{repo}", use_llm=False))


def _load_backend_env() -> None:
    """Export backend/.env secrets into os.environ so the backend config finds
    them regardless of the process working directory."""
    env_path = ROOT / "backend" / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def detect_lang(repo_dir: Path) -> str:
    """Infer language from root marker files."""
    names = {p.name.lower() for p in repo_dir.iterdir()}
    if "package.json" in names:
        return "javascript"
    if any(m in names for m in ("pyproject.toml", "setup.py", "requirements.txt", "setup.cfg")):
        return "python"
    return "unknown"


def clone_repo(owner: str, repo: str, dest: Path) -> None:
    url = f"https://github.com/{owner}/{repo}.git"
    subprocess.run(
        ["git", "clone", "--depth", "1", url, str(dest)],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=600,
    )


def provision_env(repo_dir: Path, lang: str, cache: Path) -> str | None:
    """Create an environment and return an extra PATH prefix (venv Scripts)."""
    if lang == "python":
        venv = cache / "venv"
        if not (venv / "Scripts" / "python.exe").exists():
            subprocess.run(
                [sys.executable, "-m", "venv", str(venv)],
                check=False,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=300,
            )
        return str(venv / "Scripts")
    if NODE_DIR.exists():
        return str(NODE_DIR)
    return None


def run_command(cmd: str, workdir: Path, extra_path: str | None) -> tuple[int, str]:
    env = os.environ.copy()
    if extra_path:
        env["PATH"] = extra_path + os.pathsep + env.get("PATH", "")
    try:
        proc = subprocess.run(
            cmd,
            shell=True,
            cwd=str(workdir),
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=900,
        )
        tail = ((proc.stdout or "") + (proc.stderr or "")).strip()
        return proc.returncode, tail[-600:]
    except subprocess.TimeoutExpired:
        return -1, "(超时 >900s)"
    except Exception as exc:  # noqa: BLE001
        return -1, f"(执行异常: {exc})"


def collect_paths(repo_dir: Path) -> set[str]:
    """All repo-relative file paths in the clone (used for evidence_hit)."""
    paths: set[str] = set()
    for p in repo_dir.rglob("*"):
        if p.is_file() and ".git" not in p.parts:
            paths.add(p.relative_to(repo_dir).as_posix())
    return paths


def to_generated_guide(guide) -> "object":
    """Convert the backend Guide into benchmark's GeneratedGuide shape."""
    from benchmark.schema import GeneratedGuide, GenEvidence, GenStep

    stages = [
        GenStep(
            step_id=s.step_id,
            stage=s.stage,
            title=s.title,
            command=s.command,
            expected=s.expected,
            fail_hints=s.fail_hints,
            evidence=GenEvidence(kind=s.evidence.kind, source=s.evidence.source, quote=s.evidence.quote),
        )
        for s in guide.steps
    ]
    return GeneratedGuide(
        repo_url=guide.repo_url,
        unsuitable=guide.unsuitable,
        reasons=guide.reasons,
        stages=stages,
    )


def find_golden(owner: str, repo: str):
    """Load the matching golden guide, or None if this repo has no golden yet."""
    from benchmark.golden.schema import iter_golden_guides

    for g in iter_golden_guides():
        if g.owner == owner and g.repo == repo:
            return g
    return None


def main() -> int:
    _load_backend_env()
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass

    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    cleanup = "--cleanup" in sys.argv

    if cleanup:
        if CACHE_DIR.exists():
            shutil.rmtree(CACHE_DIR)
            print(f"已清空缓存目录 {CACHE_DIR}")
        else:
            print("缓存目录不存在，无需清理")
        return 0

    from benchmark.metrics import compute

    repo_args = args or _DEFAULT_REPOS
    all_results: list[dict] = []
    grand_total = grand_passed = 0
    per_repo_metrics: list[dict] = []

    for arg in repo_args:
        owner, repo = parse_repo_arg(arg)
        key = f"{owner}__{repo}"
        cache = CACHE_DIR / key
        repo_dir = cache / "repo"
        repo_dir.mkdir(parents=True, exist_ok=True)

        print(f"\n{'='*70}\n{owner}/{repo}\n{'='*70}")

        # 1. Generate the guide.
        try:
            guide = generate_guide(owner, repo)
        except Exception as exc:  # noqa: BLE001
            print(f"  [生成失败] {exc}")
            continue

        steps = guide.steps
        print(f"  生成步骤 {len(steps)} 个；其中 unsuitable={guide.unsuitable}")

        # 2. Clone + provision environment.
        if not (repo_dir / ".git").exists():
            print("  clone 仓库...")
            clone_repo(owner, repo, repo_dir)
        else:
            print("  （复用已缓存的 clone）")

        if not (repo_dir / ".git").exists():
            print("  [clone 失败，跳过]")
            continue

        lang = detect_lang(repo_dir)
        print(f"  识别语言: {lang}")
        extra_path = provision_env(repo_dir, lang, cache)
        available_paths = collect_paths(repo_dir)

        # 3. Run every command in the generated steps (command_exec).
        repo_ok = repo_total = 0
        exec_details: list[dict] = []
        for s in steps:
            cmd = s.command
            if not cmd or not cmd.strip():
                continue
            if any(cmd.strip().startswith(p) for p in _HARNESS_HANDLED_PREFIXES):
                print(f"  [代劳] {s.title}: {cmd}  (环境初始化命令，脚本已代执行，不实测)")
                continue
            repo_total += 1
            rc, tail = run_command(cmd, repo_dir, extra_path)
            ok = rc == 0
            repo_ok += ok
            if not ok:
                exec_details.append(
                    {"step_id": s.step_id, "stage": s.stage, "title": s.title,
                     "command": cmd, "exit": rc, "tail": tail}
                )
        exec_rate = (repo_ok / repo_total) if repo_total else 0.0
        grand_total += repo_total
        grand_passed += repo_ok

        # 4. Score the other three metrics against golden (if present).
        golden = find_golden(owner, repo)
        m = None
        if golden is not None:
            gen = to_generated_guide(guide)
            m = compute(golden, gen, available_paths=available_paths)

        # 5. Print per-repo summary.
        if m is not None:
            print(f"  步骤完整率 {m.step_coverage:.0%} | 证据命中率 {m.evidence_hit:.0%} | "
                  f"命令正确率 {m.command_correct:.0%} | 命令可执行率 {exec_rate:.0%} | "
                  f"有据断言率 {m.assert_rate:.0%}")
        else:
            print(f"  （无 golden 参照，仅命令可执行率 {exec_rate:.0%}）")

        # Wrong / unexecuted commands detail.
        if exec_details:
            print("  失败命令:")
            for d in exec_details:
                print(f"    ✗ [{d['stage']}] {d['title']}: {d['command']}  (exit={d['exit']})")
                for line in d["tail"].splitlines()[-4:]:
                    print(f"        ↳ {line}")

        per_repo_metrics.append(
            {
                "repo": f"{owner}/{repo}",
                "n_gen_steps": len(steps),
                "n_gen_commands": repo_total,
                "step_coverage": m.step_coverage if m else None,
                "evidence_hit": m.evidence_hit if m else None,
                "command_correct": m.command_correct if m else None,
                "command_exec": exec_rate,
                "assert_rate": m.assert_rate if m else None,
                "failed_commands": exec_details,
            }
        )

    grand_rate = (grand_passed / grand_total) if grand_total else 0.0
    print(f"\n{'='*70}\n总计 {grand_total} 条命令 | 成功 {grand_passed} | "
          f"失败 {grand_total - grand_passed} | 命令可执行率 {grand_rate:.0%}\n{'='*70}")

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    report = {
        "ts": ts,
        "total_commands": grand_total,
        "passed_commands": grand_passed,
        "command_exec_rate": grand_rate,
        "per_repo": per_repo_metrics,
    }
    out = REPORTS_DIR / f"guide_quality_{ts}.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"报告已写: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
