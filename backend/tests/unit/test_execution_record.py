import pytest
from pydantic import ValidationError
from backend.core.generate.schemas import Guide, GuideStep


def step_data():
    return {"step_id": 1, "stage": "B", "title": "Test", "command": "pytest tests",
            "execution_record": {"status": "passed", "command": "pytest tests", "commit_sha": "a" * 40,
                "environment": "test", "summary": "ok", "report": "report.json"}}


def test_record_cannot_be_attached_to_different_command():
    data = step_data(); data["command"] = "pytest other"
    with pytest.raises(ValidationError):
        GuideStep.model_validate(data)


def test_record_requires_same_immutable_revision():
    with pytest.raises(ValidationError):
        Guide(repo_url="https://github.com/o/r", default_branch="main", steps=[GuideStep.model_validate(step_data())])
    assert Guide(repo_url="https://github.com/o/r", default_branch="a" * 40, steps=[GuideStep.model_validate(step_data())]).steps


def test_same_command_in_another_directory_cannot_reuse_result():
    data = step_data()
    data['working_directory'] = 'backend'
    data['execution_record']['working_directory'] = '.'
    with pytest.raises(ValidationError):
        GuideStep.model_validate(data)
