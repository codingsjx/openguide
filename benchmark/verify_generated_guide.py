"""Verify the *generated* guide against both the golden reference AND a real
execution environment — the full five-metric quality score for OpenGuide's output.

This module serves two entry points:

1. CLI (``python benchmark/verify_generated_guide.py ...``): evaluate one or more
   repos end-to-end and print a report.
2. Library: ``evaluate_repo(owner, repo)`` is imported by L2/L3 so the official
   evaluation runners reuse this exact pipeline (no duplicate logic, no drift).

Metrics scored (see benchmark/metrics.py):
- step_coverage  : 步骤完整率 — did the generated steps cover the golden steps?
- evidence_hit   : 证据命中率 — does each command's evidence resolve to a real file?
- command_correct: 命令正确率 — does each command match the golden reference for its stage?
- command_exec   : 命令可执行率 — does each command actually run in a fresh clone?
- assert_rate    : 有据断言率 — how many steps carry non-missing evidence?

Zero manual prep: the pipeline clones the repo, detects its language, provisions
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

_DEFAULT_REPOS = [
    "psf/requests",
    "pallets/click",
    "cookiecutter/cookiecutter",
    "mochajs/mocha",
]

# Commands that the harness itself has already performed during setup, so
# re-running them inside an already-cloned workdir would falsely fail (e.g.
# `git clone` fails because the destination already exists). These are marked
# "handled by the harness" and excluded from the command_exec denominator —
# their correctness is judged by command_correct instead.
_HARNESS_HANDLED_PREFIXES = (
    "git clone",
    "cd ",
)

# Per-command timeout for command_exec. Override with OG_CMD_TIMEOUT.
# Heavy aggregate test suites (mocha's `npm test` runs lint + node + browser
# tests) can legitimately exceed this; that is recorded as a failure with
# "(超时)" so the report distinguishes "command is wrong" from "command is too
# heavy to verify here".
_CMD_TIMEOUT_S = int(os.environ.get("OG_CMD_TIMEOUT", "900"))

# Node install dirs, appended to PATH so npm/node resolve regardless of the
# parent shell's environment. Tried in order; first that exists wins.
_NODE_CANDIDATES = (
    Path(r"C:\Users\Lenovo\node\node-v24.21.0-win-x64"),
    Path(r"C:\Program Files\nodejs"),
    Path(r"C:\Program Files (x86)\nodejs"),
    Path.home() / "AppData" / "Roaming" / "npm",
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


class CloneError(RuntimeError):
    """git clone failed. Carries the real git stderr, not just "clone 失败"."""


def clone_repo(owner: str, repo: str, dest: Path) -> None:
    """Shallow-clone a repo, raising CloneError with git's own message on failure.

    Previously the subprocess result was discarded, so any failure surfaced as a
    bare "clone 失败" with no cause — unhelpful when a demo machine has no git,
    no network, or a proxy in the way. Surfacing git's stderr makes the failure
    self-diagnosing.
    """
    url = f"https://github.com/{owner}/{repo}.git"
    try:
        proc = subprocess.run(
            ["git", "clone", "--depth", "1", url, str(dest)],
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=600,
        )
    except FileNotFoundError as exc:
        raise CloneError("未找到 git 可执行文件（请安装 git 并加入 PATH）") from exc
    except subprocess.TimeoutExpired as exc:
        raise CloneError(f"git clone 超时（>600s）: {url}") from exc

    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "").strip()
        if len(detail) > 500:
            detail = detail[:500] + "…"
        raise CloneError(f"git clone 失败 (exit {proc.returncode}): {detail or '无输出'}")


def _run_quiet(args, cwd: Path, timeout: int = 900, shell: bool = False) -> int:
    """Run a setup command, swallowing output. Returns the exit code (-1 on error)."""
    try:
        proc = subprocess.run(
            args,
            cwd=str(cwd),
            check=False,
            shell=shell,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )
        return proc.returncode
    except Exception:  # noqa: BLE001 - provisioning is best-effort
        return -1


def _npm_exe() -> str | None:
    """Resolve npm to a full path.

    On Windows npm is ``npm.cmd``; passing the bare name "npm" to subprocess
    fails because CreateProcess does not resolve PATHEXT. The failure was
    silently swallowed and a "provisioned" marker was still written, so
    dependency installation was permanently skipped — and every npm-based
    command failed with "not recognized". Resolving the real path fixes it.
    """
    return shutil.which("npm") or shutil.which("npm.cmd")


def _install_python_deps(repo_dir: Path, py: Path) -> bool:
    """Best-effort install of the project + its dev extras into the repo's venv.

    Needed because commands like `tox r -e random` only work once the project's
    dev dependencies exist. Without this, every dependency-bearing command fails
    with "not recognized", and command_exec would measure "is the tool
    preinstalled on this machine" rather than "does the guide's command work".
    """
    def pip(*args: str, timeout: int = 900) -> bool:
        # NOTE: must return the result — an earlier version declared `-> None`
        # and dropped it, so every `== 0` check was False, the "provisioned"
        # marker was never written, and deps were reinstalled on every run.
        return _run_quiet(
            [str(py), "-m", "pip", "install", "--disable-pip-version-check", *args],
            cwd=repo_dir,
            timeout=timeout,
        ) == 0

    ok = pip("-q", "--upgrade", "pip", timeout=300)
    for req in ("requirements-dev.txt", "requirements_dev.txt", "dev-requirements.txt"):
        if (repo_dir / req).exists():
            ok = pip("-q", "-r", req) or ok
            break
    if (repo_dir / "pyproject.toml").exists() or (repo_dir / "setup.py").exists():
        # `.[dev]` carries the test runner for most projects; plain `.` is the
        # fallback for projects that declare no extras.
        ok = pip("-q", "-e", ".[dev]") or ok
        ok = pip("-q", "-e", ".") or ok
    elif (repo_dir / "requirements.txt").exists():
        ok = pip("-q", "-r", "requirements.txt") or ok
    # Some projects only document a tox-based workflow; install the runner so
    # `tox ...` commands are actually executable rather than "not recognized".
    ok = pip("-q", "tox") or ok
    return ok


def _install_node_deps(repo_dir: Path, node_dir: Path | None) -> bool:
    """Best-effort `npm ci` / `npm install` so `npm test` has its dev deps."""
    if not (repo_dir / "package.json").exists():
        return False
    npm = _npm_exe()
    if not npm:
        return False
    env_path = os.environ.get("PATH", "")
    if node_dir:
        os.environ["PATH"] = str(node_dir) + os.pathsep + env_path
    try:
        if (repo_dir / "package-lock.json").exists():
            return _run_quiet([npm, "ci", "--no-audit", "--no-fund"], cwd=repo_dir) == 0
        return _run_quiet([npm, "install", "--no-audit", "--no-fund"], cwd=repo_dir) == 0
    finally:
        os.environ["PATH"] = env_path


def provision_env(repo_dir: Path, lang: str, cache: Path) -> str | None:
    """Create an environment, install deps (best-effort), return a PATH prefix.

    Set ``OG_SKIP_PROVISION=1`` to skip dependency installation (fast runs where
    command_exec is not the focus).
    """
    skip_deps = os.environ.get("OG_SKIP_PROVISION") == "1"

    if lang == "python":
        venv = cache / "venv"
        py = venv / "Scripts" / "python.exe"
        if not py.exists():
            py = venv / "bin" / "python"
        if not py.exists():
            _run_quiet([sys.executable, "-m", "venv", str(venv)], cwd=cache, timeout=300)
            py = venv / "Scripts" / "python.exe"
            if not py.exists():
                py = venv / "bin" / "python"
        marker = cache / ".og_python_deps"
        if py.exists() and not skip_deps and not marker.exists():
            # Only mark on success: a transient failure must not permanently
            # disable provisioning for this repo.
            if _install_python_deps(repo_dir, py):
                marker.write_text("1", encoding="utf-8")
        return str(py.parent) if py.exists() else None

    node_dir = next((c for c in _NODE_CANDIDATES if c.exists()), None)
    marker = cache / ".og_node_deps"
    if not skip_deps and not marker.exists():
        if _install_node_deps(repo_dir, node_dir):
            marker.write_text("1", encoding="utf-8")
    return str(node_dir) if node_dir else None


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
            timeout=_CMD_TIMEOUT_S,
        )
        tail = ((proc.stdout or "") + (proc.stderr or "")).strip()
        return proc.returncode, tail[-600:]
    except subprocess.TimeoutExpired:
        return -1, f"(超时 >{_CMD_TIMEOUT_S}s)"
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


def known_issue_numbers() -> dict[str, set[str]]:
    """Re-exported for callers that only import from this module."""
    from benchmark.golden.schema import known_issue_numbers as _k

    return _k()


def evaluate_repo(owner: str, repo: str) -> dict:
    """Run the full evaluation pipeline for one repo and return a plain dict.

    The returned dict is the shared contract between this CLI, L2 and L3:

    - ``ok``: bool — whether generation + clone succeeded (commands may still fail).
    - ``error``: str — reason for early failure (empty when ok).
    - ``n_gen_steps`` / ``n_gen_commands``: int.
    - ``command_exec_rate``: float — real exec rate (commands that exit 0).
    - ``failed_commands``: list[dict] — command + exit + tail for each failure.
    - ``golden_found``: bool — whether a golden guide exists for scoring.
    - ``metrics``: MetricsResult | None — the other four dimensions (None when
      there is no golden reference).
    """
    from benchmark.metrics import compute

    cache = CACHE_DIR / f"{owner}__{repo}"
    repo_dir = cache / "repo"
    repo_dir.mkdir(parents=True, exist_ok=True)

    out: dict = {
        "owner": owner,
        "repo": repo,
        "ok": False,
        "error": "",
        "n_gen_steps": 0,
        "n_gen_commands": 0,
        "command_exec_rate": 0.0,
        "failed_commands": [],
        "golden_found": False,
        "metrics": None,
    }

    # 1. Generate the guide.
    try:
        guide = generate_guide(owner, repo)
    except Exception as exc:  # noqa: BLE001
        out["error"] = str(exc)
        return out
    out["n_gen_steps"] = len(guide.steps)

    # 2. Clone + provision environment.
    if not (repo_dir / ".git").exists():
        try:
            clone_repo(owner, repo, repo_dir)
        except CloneError as exc:
            out["error"] = str(exc)
            return out
    if not (repo_dir / ".git").exists():
        out["error"] = f"clone 后仍未出现 .git 目录: {repo_dir}"
        return out

    lang = detect_lang(repo_dir)
    extra_path = provision_env(repo_dir, lang, cache)
    available_paths = collect_paths(repo_dir)

    # 3. Run every command (command_exec).
    repo_ok = repo_total = 0
    for s in guide.steps:
        cmd = s.command
        if not cmd or not cmd.strip():
            continue
        if any(cmd.strip().startswith(p) for p in _HARNESS_HANDLED_PREFIXES):
            continue
        repo_total += 1
        rc, tail = run_command(cmd, repo_dir, extra_path)
        ok = rc == 0
        repo_ok += ok
        if not ok:
            out["failed_commands"].append(
                {"step_id": s.step_id, "stage": s.stage, "title": s.title,
                 "command": cmd, "exit": rc, "tail": tail}
            )
    exec_rate = (repo_ok / repo_total) if repo_total else 0.0
    out["n_gen_commands"] = repo_total
    out["command_exec_rate"] = exec_rate

    # 4. Score the other four metrics against golden (if present).
    golden = find_golden(owner, repo)
    if golden is not None:
        out["golden_found"] = True
        gen = to_generated_guide(guide)
        issue_nums = known_issue_numbers().get(f"{owner}/{repo}", set())
        m = compute(golden, gen, available_paths=available_paths, issue_numbers=issue_nums)
        m.command_exec = exec_rate  # fill the real exec rate into the metric
        out["metrics"] = m

    out["ok"] = True
    return out


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

    repo_args = args or _DEFAULT_REPOS
    per_repo: list[dict] = []
    grand_total = grand_passed = 0

    for arg in repo_args:
        owner, repo = parse_repo_arg(arg)
        print(f"\n{'='*70}\n{owner}/{repo}\n{'='*70}")

        r = evaluate_repo(owner, repo)
        if not r["ok"]:
            print(f"  [失败] {r['error']}")
            continue

        grand_total += r["n_gen_commands"]
        grand_passed += r["n_gen_commands"] - len(r["failed_commands"])

        m = r["metrics"]
        if m is not None:
            print(f"  步骤完整率 {m.step_coverage:.0%} | 证据命中率 {m.evidence_hit:.0%} | "
                  f"命令正确率 {m.command_correct:.0%} | 命令可执行率 {r['command_exec_rate']:.0%} | "
                  f"有据断言率 {m.assert_rate:.0%}")
        else:
            print(f"  （无 golden 参照，仅命令可执行率 {r['command_exec_rate']:.0%}）")

        if r["failed_commands"]:
            print("  失败命令:")
            for d in r["failed_commands"]:
                print(f"    ✗ [{d['stage']}] {d['title']}: {d['command']}  (exit={d['exit']})")
                for line in d["tail"].splitlines()[-4:]:
                    print(f"        ↳ {line}")

        per_repo.append(
            {
                "repo": f"{owner}/{repo}",
                "n_gen_steps": r["n_gen_steps"],
                "n_gen_commands": r["n_gen_commands"],
                "step_coverage": m.step_coverage if m else None,
                "evidence_hit": m.evidence_hit if m else None,
                "command_correct": m.command_correct if m else None,
                "command_exec": r["command_exec_rate"],
                "assert_rate": m.assert_rate if m else None,
                "failed_commands": r["failed_commands"],
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
        "per_repo": per_repo,
    }
    out = REPORTS_DIR / f"guide_quality_{ts}.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"报告已写: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
