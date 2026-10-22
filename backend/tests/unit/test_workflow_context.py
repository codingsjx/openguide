from backend.core.generate.workflow import prepare_workflow
from backend.core.generate.pipeline import audit_steps
from backend.core.generate.schemas import Evidence, GuideStep
from backend.core.github.models import DocFile
from backend.core.index.service import RepoIndex
from test_pipeline import make_signals


def step(stage, command, source="Makefile"):
    return GuideStep(step_id=10, stage=stage, title="operation", command=command,
        evidence=Evidence(source=source, verification="command_verified"))


def test_clone_is_before_install_and_test_with_recomputed_dependencies():
    sig = make_signals()
    sig.file_tree += ['requirements-dev.txt', 'tests/test_unit.py']
    sig.doc_files.append(DocFile(path="Makefile", name="Makefile", text="init:\n\tpython -m pip install -r requirements-dev.txt\ntest:\n\tpython -m pytest tests\n"))
    original = [step('A', 'python -m pip install -r requirements-dev.txt'), step('B', 'python -m pytest tests'), step('D', 'git clone https://github.com/o/lib.git', 'README.md')]
    result = prepare_workflow(sig, original)
    assert result[0].command.startswith('git clone') and result[0].stage == 'A'
    assert result[0].original_stage == 'D'
    assert [s.step_id for s in result] == [1, 2, 3]
    assert result[1].working_directory == '.' and not result[1].missing_inputs
    assert result[2].prerequisite_step_ids == [1, 2]
    assert any('退出码' in text for text in result[2].success_checks)
    assert any('跳过' in text for text in result[2].success_checks)
    assert original[2].stage == 'D' and original[0].step_id == 10


def test_nested_build_file_context_and_missing_requirement():
    sig = make_signals()
    command = 'python -m pip install -r missing.txt'
    sig.doc_files.append(DocFile(path='backend/Makefile', name='Makefile', text='init:\n\t' + command))
    result = prepare_workflow(sig, [step('A', command, 'backend/Makefile')])[0]
    assert result.working_directory == 'backend'
    assert result.required_paths == ['backend/missing.txt']
    assert result.missing_inputs == ['backend/missing.txt']


def test_readme_does_not_silently_imply_repository_root():
    result = prepare_workflow(make_signals(), [step('B', 'pytest tests', 'README.md')])[0]
    assert result.working_directory is None
    assert result.directory_basis == 'unknown'
    assert any('安装' in note for note in result.context_notes)


def test_requirement_must_be_file_not_existing_directory():
    sig = make_signals(); sig.file_tree.append('tests/test_unit.py')
    sig.doc_files.append(DocFile(path='Makefile', name='Makefile', text='init:\n\tpython -m pip install -r tests'))
    result = prepare_workflow(sig, [step('A', 'python -m pip install -r tests')])[0]
    assert result.missing_inputs == ['tests']


def test_incomplete_tree_is_unknown_not_missing_input():
    sig = make_signals(); sig.unavailable_signals.append('tree')
    sig.doc_files.append(DocFile(path='Makefile', name='Makefile', text='init:\n\tpython -m pip install -r missing.txt'))
    result = prepare_workflow(sig, [step('A', 'python -m pip install -r missing.txt')])[0]
    assert not result.missing_inputs
    assert any('尚不能确认' in note for note in result.context_notes)


def test_verified_duplicate_clone_is_only_shown_once():
    clone = 'git clone https://github.com/o/lib.git'
    result = prepare_workflow(make_signals(), [step('A', clone), step('D', clone)])
    assert len(result) == 1


def test_audited_stage_a_clone_is_no_longer_hidden():
    sig = make_signals()
    command = 'git clone https://github.com/o/lib.git'
    sig.doc_files[0].text += '\n' + command + '\n'
    idx = RepoIndex('o', 'lib'); idx.index(sig)
    result = audit_steps(sig, idx, [step('A', command, 'README.md')])
    assert result[0].command == command
    assert result[0].directory_basis == 'clone_destination'


def test_empty_repeated_clone_and_test_expectation_do_not_become_extra_tasks():
    steps = [step('A', 'git clone https://github.com/o/lib.git'),
        GuideStep(step_id=2,stage='A',title='准备 Git 克隆仓库',evidence=Evidence(kind='missing')),
        step('B', 'pytest tests'),
        GuideStep(step_id=4,stage='B',title='确认测试基线期望',evidence=Evidence(kind='missing'))]
    result = prepare_workflow(make_signals(), steps)
    assert len(result) == 2
    assert result[-1].step_id == 2
    assert result[-1].prerequisite_step_ids == [1]
    # No verified action: retain the pending entry rather than erase the stage.
    assert len(prepare_workflow(make_signals(), [steps[1]])) == 1
