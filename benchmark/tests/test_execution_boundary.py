from pathlib import Path
import os
import sys
import pytest
from benchmark.execute_reviewed import contained, clean_environment, capture_command


def test_checkout_cannot_escape_reviewed_workspace(tmp_path):
    with pytest.raises(ValueError):
        contained(tmp_path, "../outside")


def test_api_credentials_are_not_inherited(monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "secret-placeholder")
    monkeypatch.setenv("GITHUB_TOKEN", "secret-placeholder")
    monkeypatch.setenv("OPENAI_API_KEY", "secret-placeholder")
    env = clean_environment(Path(sys.executable))
    assert not {"LLM_API_KEY", "GITHUB_TOKEN", "OPENAI_API_KEY"} & env.keys()
    assert env["PYTHONNOUSERSITE"] == "1"


def test_execution_preserves_failure_and_output(tmp_path):
    code, output, timed_out = capture_command([sys.executable, "-c", "print('diagnostic'); raise SystemExit(3)"], tmp_path, clean_environment(Path(sys.executable)), 10)
    assert code == 3 and not timed_out and "diagnostic" in output


def test_timed_out_process_is_stopped(tmp_path):
    code, _, timed_out = capture_command([sys.executable, "-c", "import time; time.sleep(30)"], tmp_path, clean_environment(Path(sys.executable)), 1)
    assert code is None and timed_out
