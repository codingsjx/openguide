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


def test_baseline_prioritized_before_randomized_special_suite():
    sig = make_signals()
    sig.doc_files += [DocFile(path="docs/special.md", name="special.md", text="run test suite pytest tox random stress\ntox r -e random\n")]
    idx = RepoIndex("o", "lib"); idx.index(sig)
    snippets = _retrieve_for_stage(idx, "B", _STAGE_QUERIES["B"])
    assert "tox r -e random" not in snippets[0]["text"]


def test_setup_context_keeps_clone_install_and_runtime_within_four_slots():
    sig = make_signals()
    sig.doc_files[0].text += '\ngit clone https://github.com/o/lib.git\n'
    sig.doc_files += [
        DocFile(path='Makefile',name='Makefile',text='init:\n\tpython -m pip install -r requirements-dev.txt\n'),
        DocFile(path='pyproject.toml',name='pyproject.toml',text='[project]\nrequires-python = ">=3.10"\n'),
    ]
    idx=RepoIndex('o','lib');idx.index(sig)
    snippets=_retrieve_for_stage(idx,'A',_STAGE_QUERIES['A'])
    assert len(snippets) <= 4
    assert any('git clone' in s['text'] for s in snippets)
    assert any('pip install' in s['text'] for s in snippets)
    assert any('requires-python' in s['text'] for s in snippets)
