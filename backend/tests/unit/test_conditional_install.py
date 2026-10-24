from backend.core.generate.workflow import prepare_workflow, CONDITIONAL_INSTALL_NOTE
from backend.core.generate.schemas import Evidence, GuideStep
from backend.core.github.recon import RawSignals
from backend.core.github.models import RepoMeta, DocFile


def test_explicit_optional_extra_is_not_a_default_test_prerequisite():
    text='# Setup\n```sh\ncd backend\nuv sync\n# 需要向量功能时先运行\nuv sync --extra vector\nuv run pytest tests/ -q\n```'
    sig=RawSignals(meta=RepoMeta(owner='o',repo='r'),doc_files=[DocFile(path='README.md',name='README.md',text=text)],file_tree=['backend/pyproject.toml','backend/tests/test_one.py'])
    steps=[GuideStep(step_id=i,stage=stage,title='operation',command=cmd,evidence=Evidence(source='README.md',verification='command_verified',line_start=line))
        for i,stage,cmd,line in [(1,'A','uv sync',4),(2,'A','uv sync --extra vector',6),(3,'B','uv run pytest tests/ -q',7)]]
    result=prepare_workflow(sig,steps)
    assert result[1].title.startswith('可选：')
    assert CONDITIONAL_INSTALL_NOTE in result[1].context_notes
    assert result[1].working_directory=='backend'
    assert result[2].prerequisite_step_ids==[1]
    assert result[1].evidence.source=='README.md' and result[1].command=='uv sync --extra vector'


def test_extra_flag_alone_does_not_claim_the_repository_requirement_is_optional():
    text='```sh\ncd backend\nuv sync --extra service\n```'
    sig=RawSignals(meta=RepoMeta(owner='o',repo='r'),doc_files=[DocFile(path='README.md',name='README.md',text=text)],file_tree=['backend/pyproject.toml'])
    step=GuideStep(step_id=1,stage='A',title='operation',command='uv sync --extra service',evidence=Evidence(source='README.md',verification='command_verified',line_start=3))
    result=prepare_workflow(sig,[step])[0]
    assert not result.title.startswith('可选：')
    assert CONDITIONAL_INSTALL_NOTE not in result.context_notes
