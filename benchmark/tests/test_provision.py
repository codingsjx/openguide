"""Provisioning tests for the evaluation harness.

`command_exec` only means something if the harness actually prepares the repo
environment. These guard the fixes that made it real:

- `_install_python_deps` / `_install_node_deps` must **return** whether they
  succeeded. An earlier version declared `-> None` and dropped the result, so
  every `== 0` check was False, the "provisioned" marker was never written, and
  dependencies were reinstalled on every single run.
- npm must be resolved to a full path: on Windows it is `npm.cmd`, and passing
  the bare name to subprocess fails because CreateProcess does not resolve
  PATHEXT. That failure was silent, and a marker was still written, so npm deps
  were never installed and every `npm test` failed with "not recognized".
"""

from __future__ import annotations

import pathlib
import shutil

import pytest

from benchmark import verify_generated_guide as vg


@pytest.fixture()
def scratch():
    """Workspace-local scratch dir (pytest's tmp_path is blocked in some sandboxes)."""
    d = pathlib.Path("benchmark/reports/_provision_test")
    shutil.rmtree(d, ignore_errors=True)
    d.mkdir(parents=True, exist_ok=True)
    try:
        yield d
    finally:
        shutil.rmtree(d, ignore_errors=True)


def test_npm_exe_resolves_or_is_none():
    """Must return a real path or None — never the bare name."""
    got = vg._npm_exe()
    if got is not None:
        assert pathlib.Path(got).name.lower().startswith("npm"), got
        assert got != "npm", "不能返回裸名 npm（Windows 上 CreateProcess 解析不到）"


def test_install_python_deps_returns_bool(scratch):
    """A venv-less path must return a bool, not None (the old bug)."""
    repo = scratch / "repo"
    repo.mkdir()
    (repo / "pyproject.toml").write_text("[project]\nname='x'\nversion='0'\n", encoding="utf-8")
    fake_py = scratch / "no-such-python"
    result = vg._install_python_deps(repo, fake_py)
    assert isinstance(result, bool), f"必须返回 bool，实际 {type(result).__name__}"
    assert result is False, "解释器不存在时应返回 False"


def test_install_node_deps_returns_false_without_package_json(scratch):
    repo = scratch / "empty"
    repo.mkdir()
    assert vg._install_node_deps(repo, None) is False


def test_cmd_timeout_is_configurable(monkeypatch):
    """OG_CMD_TIMEOUT must be honoured so heavy suites can be bounded."""
    import importlib
    import os

    monkeypatch.setenv("OG_CMD_TIMEOUT", "42")
    reloaded = importlib.reload(vg)
    try:
        assert reloaded._CMD_TIMEOUT_S == 42
    finally:
        monkeypatch.delenv("OG_CMD_TIMEOUT", raising=False)
        importlib.reload(vg)
