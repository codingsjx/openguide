from backend.core.followup.diagnostics import diagnostic_plan
from backend.core.followup.service import diagnose
from backend.core.generate.schemas import GuideStep,Evidence
from backend.core.github.recon import RawSignals
from backend.core.github.models import DocFile,RepoMeta
from backend.core.index.service import RepoIndex


def fixture():
    docs={'backend/README.md':'# Backend\n```sh\ncd backend\nuv sync\nuv run pytest tests/ -q\n```',
          'frontend/README.md':'# Frontend\n```sh\ncd frontend\npnpm install\npnpm build\n```',
          'backend/pyproject.toml':'[project]\nrequires-python = ">=3.12"'}
    sig=RawSignals(meta=RepoMeta(owner='o',repo='r'),doc_files=[DocFile(path=p,name=p,text=t) for p,t in docs.items()],file_tree=list(docs)+['backend/tests/test_one.py'])
    index=RepoIndex('o','r');index.index(sig)
    return index,GuideStep(step_id=1,stage='B',title='Test',command='uv run pytest tests/ -q',working_directory='frontend',evidence=Evidence(source='backend/README.md'))


def test_python_module_cli_error_has_a_verified_same_component_recovery_entry():
    assert diagnostic_plan('python.exe: No module named pytest')[0]=='python_environment'
    index,step=fixture();result=diagnose(index,step,'python.exe: No module named pytest')
    assert len(result.sub_steps)==1
    recovery=result.sub_steps[0]
    assert recovery.command=='uv sync' and recovery.working_directory=='backend'
    assert recovery.evidence.verification=='command_verified'
    assert recovery.generation_source=='rules'
    assert result.preparation_checks and result.completion_checks
    assert not any(s.evidence.source.startswith('frontend/') for s in result.sub_steps)


def test_error_module_name_and_unverified_request_never_create_an_install_command():
    index,step=fixture();step.command='pytest --invented'
    result=diagnose(index,step,'No module named malicious_package')
    assert not result.sub_steps
    assert 'pip install malicious_package' not in result.text
