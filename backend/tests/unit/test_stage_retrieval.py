from backend.core.generate.pipeline import _retrieve_for_stage, _STAGE_QUERIES
from backend.core.github.models import DocFile
from backend.core.index.service import RepoIndex
from test_pipeline import make_signals


def test_test_command_is_retrieved_ahead_of_issue_automation():
    sig = make_signals()
    sig.doc_files += [
        DocFile(path="Makefile", name="Makefile", text="test:\n\tpython -m pytest tests\n"),
        DocFile(path=".github/workflows/issues.yml", name="issues.yml", text="name: run the issues\nsteps:\n  run: gh issue close 1\n"),
    ]
    idx = RepoIndex("o", "lib")
    idx.index(sig)
    snippets = _retrieve_for_stage(idx, "B", _STAGE_QUERIES["B"])
    assert snippets
    assert snippets[0]["source"] != ".github/workflows/issues.yml"
    assert any("pytest" in s["text"] for s in snippets)
