"""Verify golden-guide commands actually execute in their real environments.

This is the offline runner for the ``command_exec`` (命令可执行率) metric that
``metrics.py`` deliberately leaves at 0.0 — because it needs a real shell.

What it does:
1. Load repos.json, keep only ``verified: true`` repos.
2. Load each golden guide, collect every ``expected_commands``.
3. Skip *setup* commands (git clone / cd / pip install / uv sync / npm install)
   — these set up an environment and are not what "命令可执行" means.
4. Run the remaining *verifiable* commands in the repo's real workdir, with the
   repo's own environment on PATH (venv Scripts for Python, node for JS).
5. Count exit-code-0 successes and emit 命令可执行率 + a JSON report.

Run from the repo root:
    backend/.venv/Scripts/python.exe benchmark/verify_commands.py
"""

from __future__ import annotations

import json
import os
import subprocess
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GOLDEN_DIR = ROOT / "benchmark" / "golden"
GUIDES_DIR = GOLDEN_DIR / "golden_guides"
WORK_BASE = ROOT / "_golden_work"
REPORTS_DIR = ROOT / "benchmark" / "reports"

# Node install dir (added to PATH so `npm` resolves even when the parent shell's
# PATH does not carry it). Keep in sync with the machine's Node location.
NODE_DIR = Path(r"C:\Users\Lenovo\node\node-v24.21.0-win-x64")

# Commands that provision an environment rather than verify the repo works.
# We skip them: they're already done in _golden_work, and re-running them is
# slow and not what 命令可执行率 measures.
_SETUP_PREFIXES = (
    "git ",
    "cd ",
    "pip ",
    "python -m pip ",
    "uv sync",
    "npm install",
    "npm ci",
    "yarn ",
    "pnpm install",
)


def is_setup(cmd: str) -> bool:
    c = cmd.strip()
    return any(c.startswith(p) for p in _SETUP_PREFIXES)


def load_verified_repos() -> list[dict]:
    data = json.loads((GOLDEN_DIR / "repos.json").read_text(encoding="utf-8"))
    return [r for r in data["repos"] if r.get("verified")]


def load_guide(owner: str, repo: str) -> dict:
    p = GUIDES_DIR / f"{owner}__{repo}.json"
    return json.loads(p.read_text(encoding="utf-8"))


def build_env_path(env_dir: str, lang: str) -> str | None:
    """Return an extra PATH prefix so the command resolves its interpreter/tool.

    Python: prepend the venv's ``Scripts`` dir (python.exe / pytest.exe live there).
    JS: prepend the Node install dir so ``npm``/``node`` resolve.
    """
    extra: list[str] = []
    if lang == "python" and env_dir:
        scripts = WORK_BASE / env_dir / "Scripts"
        if scripts.exists():
            extra.append(str(scripts))
    if NODE_DIR.exists():
        extra.append(str(NODE_DIR))
    return os.pathsep.join(extra) if extra else None


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
        return proc.returncode, tail[-400:]
    except subprocess.TimeoutExpired:
        return -1, "(超时)"
    except Exception as exc:  # noqa: BLE001 - report any runner failure honestly
        return -1, f"(执行异常: {exc})"


def main() -> int:
    repos = load_verified_repos()
    results: list[dict] = []
    total = passed = 0

    for r in repos:
        owner, repo = r["owner"], r["repo"]
        lang = r.get("lang", "python")
        env_dir = r.get("env_dir", "")
        workdir = WORK_BASE / repo
        extra_path = build_env_path(env_dir, lang)

        guide = load_guide(owner, repo)
        for step in guide.get("steps", []):
            for cmd in step.get("expected_commands", []):
                if not cmd.strip() or is_setup(cmd):
                    continue
                total += 1
                rc, tail = run_command(cmd, workdir, extra_path)
                ok = rc == 0
                passed += ok
                mark = "OK  " if ok else "FAIL"
                print(f"[{mark}] {owner}/{repo}: {cmd}  (exit={rc})")
                results.append(
                    {
                        "repo": f"{owner}/{repo}",
                        "command": cmd,
                        "ok": ok,
                        "exit": rc,
                        "tail": tail,
                    }
                )

    rate = (passed / total) if total else 0.0
    print(f"\n总命令数 {total} | 成功 {passed} | 失败 {total - passed} | 命令可执行率 {rate:.0%}")

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    report = {"ts": ts, "total": total, "passed": passed, "rate": rate, "results": results}
    out = REPORTS_DIR / f"command_exec_{ts}.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"报告已写: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
