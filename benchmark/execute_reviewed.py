"""Run an explicitly reviewed, SHA-pinned plan in a dedicated Python venv.

This is dependency isolation, NOT an OS security sandbox. Never feed model
output straight into this tool. The argv plan and upstream source must first
be reviewed. No shell is used and API credentials are not inherited.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import signal
import subprocess
import sys
import time
import venv

ROOT = Path(__file__).resolve().parents[1]


def contained(base: Path, relative: str) -> Path:
    target = (base / relative).resolve()
    if not target.is_relative_to(base.resolve()):
        raise ValueError("路径必须位于指定评测目录内")
    return target


def clean_environment(python: Path) -> dict:
    allowed = {"SYSTEMROOT", "WINDIR", "TEMP", "TMP", "COMSPEC", "PATHEXT", "PATH", "LANG", "LC_ALL"}
    env = {key: value for key, value in os.environ.items() if key.upper() in allowed}
    env.update(PATH=str(python.parent) + os.pathsep + env.get("PATH", ""),
        PYTHONNOUSERSITE="1", PIP_CONFIG_FILE=os.devnull, PIP_DISABLE_PIP_VERSION_CHECK="1",
        PYTHONIOENCODING="utf-8")
    return env


def capture_command(argv: list[str], cwd: Path, env: dict, timeout: int) -> tuple[int | None, str, bool]:
    options = {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP} if os.name == "nt" else {"start_new_session": True}
    proc = subprocess.Popen(argv, cwd=cwd, env=env, shell=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE, **options)
    timed_out = False
    try:
        stdout, stderr = proc.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        timed_out = True
        if os.name == "nt":
            subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"], capture_output=True)
        else:
            os.killpg(proc.pid, signal.SIGKILL)
        if proc.poll() is None:
            proc.kill()
        stdout, stderr = proc.communicate()
    text = stdout.decode("utf-8", errors="replace") + "\n" + stderr.decode("utf-8", errors="replace")
    return (None if timed_out else proc.returncode), text, timed_out


def run(plan_file: Path, timeout_cap: int = 300) -> Path:
    plan = json.loads(plan_file.read_text(encoding="utf-8"))
    if timeout_cap < 1 or not plan.get("commands") or any(s.get("phase") not in {"setup", "test"} for s in plan["commands"]):
        raise ValueError("执行计划必须包含 setup/test 命令，超时上限必须为正数")
    if plan.get("review_status") != "source_reviewed_by_agent":
        raise ValueError("计划必须明确记录来源审阅；不得直接执行模型输出")
    base = ROOT / "_golden_work"
    checkout = contained(base, plan["checkout"])
    actual_sha = subprocess.check_output(["git", "-C", str(checkout), "rev-parse", "HEAD"], text=True).strip()
    if actual_sha != plan["commit_sha"]:
        raise ValueError("工作目录提交与计划 SHA 不符")
    if subprocess.check_output(["git", "-C", str(checkout), "status", "--porcelain", "--untracked-files=no"], text=True).strip():
        raise ValueError("待验证源码包含已跟踪文件修改")
    env_dir = contained(base, plan["environment"])
    if env_dir == checkout or env_dir.is_relative_to(checkout) or checkout.is_relative_to(env_dir):
        raise ValueError("依赖环境与被测源码目录必须分开")
    python = env_dir / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    fresh_environment = not python.exists()
    if fresh_environment:
        venv.EnvBuilder(with_pip=True).create(env_dir)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = ROOT / "benchmark/reports" / f"execution_{stamp}"
    out.mkdir(parents=True)
    (out / "plan.json").write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
    report = {"repo": plan["repo"], "commit_sha": actual_sha, "plan_sha256": hashlib.sha256(plan_file.read_bytes()).hexdigest(),
        "runner_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), "fresh_environment": fresh_environment,
        "os": platform.platform(), "python": subprocess.check_output([str(python), "--version"], text=True).strip(),
        "is_security_sandbox": False, "credential_environment_inherited": False,
        "limitations": ["single machine and fixed commit only", "agent source review is not independent human annotation", "system proxy settings can still affect tests even when proxy environment variables are absent"], "commands": []}
    setup_ok = True
    env = clean_environment(python)
    for i, step in enumerate(plan["commands"]):
        argv = [str(python) if arg == "{python}" else arg for arg in step["argv"]]
        if not argv or not all(isinstance(arg, str) for arg in argv):
            raise ValueError("argv 必须为非空字符串数组")
        cwd = contained(checkout, step.get("cwd", "."))
        row = {"id": step["id"], "phase": step["phase"], "argv": step["argv"], "cwd": step.get("cwd", "."),
               "source": step.get("source"), "derivation": step.get("derivation", "literal-source-command")}
        started = time.perf_counter()
        if step["phase"] == "test" and not setup_ok:
            row.update(status="blocked_by_setup", exit_code=None, elapsed_s=0)
        else:
            try:
                code, log, timed_out = capture_command(argv, cwd, env, min(timeout_cap, step.get("timeout_s", timeout_cap)))
                row.update(status="timed_out" if timed_out else "passed" if code == 0 else "failed", exit_code=code)
            except OSError as exc:
                log = f"Process launch failed: {type(exc).__name__}"
                row.update(status="launch_failed", exit_code=None)
            row["elapsed_s"] = round(time.perf_counter() - started, 3)
            log_name = f"command_{i + 1}.log"
            (out / log_name).write_text(log, encoding="utf-8")
            row.update(log=log_name, output_tail=log[-3000:])
            if step["phase"] == "setup" and row["status"] != "passed":
                setup_ok = False
        report["commands"].append(row)
        (out / "result.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(plan["repo"], step["id"], row["status"], flush=True)
    freeze = subprocess.run([str(python), "-m", "pip", "freeze"], env=env, capture_output=True, text=True)
    (out / "dependencies.txt").write_text(freeze.stdout, encoding="utf-8")
    report["status"] = "passed" if all(r["status"] == "passed" for r in report["commands"]) else "failed_or_incomplete"
    (out / "result.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(out, flush=True)
    return out


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("plan", type=Path)
    parser.add_argument("--timeout-cap", type=int, default=300)
    args = parser.parse_args()
    output = run(args.plan, args.timeout_cap)
    raise SystemExit(0 if json.loads((output / "result.json").read_text(encoding="utf-8"))["status"] == "passed" else 1)
