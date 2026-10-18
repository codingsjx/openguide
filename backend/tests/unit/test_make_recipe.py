import pytest
from backend.core.generate.schemas import Evidence, GuideStep
from backend.core.generate.pipeline import audit_steps
from backend.core.generate.make_recipe import expand_make_recipe
from backend.core.github.models import DocFile
from backend.core.index.service import RepoIndex
from test_pipeline import make_signals


def setup(recipe):
    sig = make_signals()
    sig.doc_files.append(DocFile(path="Makefile", name="Makefile", text=recipe))
    sig.file_tree.append("Makefile")
    step = GuideStep(step_id=1, stage="B", title="Test", command="make ci",
                     evidence=Evidence(source="Makefile", quote="python -m pytest tests"))
    return sig, step


def test_expanded_target_retains_original_and_verified_line():
    sig, step = setup("ci:\n\tpython -m pytest tests\n")
    idx = RepoIndex("o", "lib"); idx.index(sig)
    result = audit_steps(sig, idx, [step])[0]
    assert result.command == "python -m pytest tests"
    assert result.original_command == "make ci"
    assert result.evidence.verification == "command_verified"
    assert result.evidence.line_start == 2
    assert step.command == "make ci"  # original raw output remains auditable


@pytest.mark.parametrize("text", [
    "ci: install\n\tpython -m pytest tests\n",
    "ci:\n\t$(PYTHON) -m pytest tests\n",
    "ci:\n\tpython -m pytest tests && echo done\n",
    "ci:\n\tpython -m pytest tests\n\techo done\n",
    "include other.mk\nci:\n\tpython -m pytest tests\n",
    "ifdef CI\nci:\n\tpython -m pytest tests\nendif\n",
    "export PYTEST_ADDOPTS=-k none\nci:\n\tpython -m pytest tests\n",
    "ci:\n\tpython -m pytest tests\nci:\n\techo other\n",
    "ci:\n\t@python -m pytest tests\n",
])
def test_complex_make_semantics_are_not_guessed(text):
    sig, step = setup(text)
    assert expand_make_recipe(step, sig).command == "make ci"


def test_old_execution_record_does_not_transfer_to_expanded_invocation():
    from backend.core.generate.schemas import ExecutionRecord
    sig, step = setup("ci:\n\tpython -m pytest tests\n")
    step.execution_record = ExecutionRecord(status="passed", command="make ci", commit_sha="a" * 40,
        environment="other", summary="ok", report="record.json")
    expanded = expand_make_recipe(step, sig)
    assert expanded.command == "python -m pytest tests"
    assert expanded.execution_record is None
    assert step.execution_record is not None
