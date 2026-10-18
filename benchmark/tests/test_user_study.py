"""Synthetic fixtures test accounting only; they are not participant results."""
import pytest
from pydantic import ValidationError

from benchmark.user_study import Study, summarize


def ledger():
    return {"status": "collecting", "tasks": [
        {"task_id": task, "repo": "example/repo", "commit_sha": "a" * 40,
         "environment": "test fixture only", "setup_success": "exit 0",
         "test_success": "selected test exit 0", "issue_success": "check current scope",
         "organizer_verified": True} for task in ("one", "two")],
        "participants": [{"participant_id": "P001", "consent_recorded": True,
                          "experience": "synthetic", "sequence": "AB", "first_task": "one"}],
        "sessions": [{"participant_id": "P001", "task_id": "one", "condition": "official_docs",
                      "status": "timed_out", "elapsed_seconds": 1800, "setup_ok": True,
                      "test_ok": False, "issue_ok": False, "help_count": 2,
                      "wrong_command_count": 1, "observation_reference": "synthetic fixture"}]}


def test_pending_study_reports_no_results():
    result = summarize(Study())
    assert result["participants"] == 0
    assert result["conditions"]["openguide"]["success_rate"] is None
    assert result["independently_verified"] is False


def test_timeouts_and_missing_sessions_remain_in_denominator():
    result = summarize(Study.model_validate(ledger()))
    docs = result["conditions"]["official_docs"]
    guide = result["conditions"]["openguide"]
    assert docs["assigned"] == guide["assigned"] == 1
    assert docs["timed_out"] == 1 and docs["success_rate"] == 0
    assert guide["missing"] == 1 and guide["success_rate"] == 0


@pytest.mark.parametrize("change", ["duplicate", "wrong_condition", "over_limit", "no_consent", "unverified", "fake_bool"])
def test_invalid_or_biased_accounting_is_rejected(change):
    data = ledger()
    if change == "duplicate":
        data["sessions"] *= 2
    elif change == "wrong_condition":
        data["sessions"][0]["condition"] = "openguide"
    elif change == "over_limit":
        data["sessions"][0]["status"] = "completed"
    elif change == "no_consent":
        data["participants"][0]["consent_recorded"] = False
    elif change == "unverified":
        data["tasks"][0]["organizer_verified"] = False
    else:
        data["sessions"][0]["setup_ok"] = "false"
    if change == "over_limit":
        data["sessions"][0]["elapsed_seconds"] = 1801
    with pytest.raises(ValidationError):
        Study.model_validate(data)


def test_json_roundtrip_keeps_valid_observations():
    study = Study.model_validate(ledger())
    assert Study.model_validate_json(study.model_dump_json()) == study
