"""Current-command explanations: verified scope, bounded quotes, no model."""
import pytest

from backend.core.followup.service import explain
from backend.core.generate.schemas import Evidence, GuideStep
from backend.core.github.models import DocFile, RepoMeta
from backend.core.github.recon import RawSignals
from backend.core.index.service import RepoIndex


def fixture(command='uv sync', source='backend/README.md', directory='frontend', stage='A'):
    docs = {
        'backend/README.md': '# Backend\nPython 3.12 and uv required.\n```sh\ncd backend\nuv sync # install dependencies\nuv run pytest tests/ -q\n```',
        'frontend/README.md': '# Frontend\n```sh\ncd frontend\npnpm install\npnpm build\n```',
        'README.md': '# Setup\n## Backend\n```sh\ncd backend\nuv sync\n```\n## Frontend\n```sh\ncd frontend\npnpm install\n```',
        'benchmark/README.md': '# Why uv sync\nUnrelated benchmark interpretation only.\nuv sync',
        'backend/pyproject.toml': '[project]\nrequires-python = ">=3.12"',
        'frontend/package.json': '{"scripts":{"build":"vite build"}}',
    }
    signals = RawSignals(meta=RepoMeta(owner='o',repo='app',default_branch='b'*40),
        doc_files=[DocFile(path=p,name=p.rsplit('/',1)[-1],text=t) for p,t in docs.items()],file_tree=list(docs))
    index = RepoIndex('o','app');index.index(signals)
    step = GuideStep(step_id=1,stage=stage,title='安装依赖',command=command,working_directory=directory,evidence=Evidence(source=source))
    return index,step


def test_explain_anchors_current_command_and_corrects_forged_directory():
    result=explain(*fixture())
    assert result.sources==['backend/README.md']
    assert all(ev.verification=='quote_verified' for ev in result.evidence)
    assert all('benchmark' not in ev.source and 'Frontend' not in ev.quote for ev in result.evidence)
    assert result.explanations[0]['reference_url']=='https://docs.astral.sh/uv/concepts/projects/sync/'
    assert '先进入 backend' in result.explanations[1]['text']
    assert '本次未确认' in result.explanations[1]['text']
    assert result.preparation_checks and result.completion_checks


def test_root_readme_is_clipped_to_current_component():
    result=explain(*fixture(command='pnpm install',source='README.md',directory='backend'))
    assert result.sources==['README.md']
    assert '先进入 frontend' in result.explanations[1]['text']
    assert 'uv sync' not in result.evidence[0].quote


@pytest.mark.parametrize('command,source,stage',[
    ('uv sync --invented','backend/README.md','A'),
    ('uv sync','benchmark/README.md','A'),
    ('uv run pytest tests/ -q','backend/README.md','A'),
])
def test_unverified_wrong_stage_or_auxiliary_command_cannot_become_explanation(command,source,stage):
    result=explain(*fixture(command=command,source=source,stage=stage))
    assert not result.explanations and not result.evidence


def test_unsupported_flags_abstain_instead_of_explaining_a_different_command():
    index,step=fixture(command='uv sync --special')
    index.signals.doc_files[0].text+='\nuv sync --special\n'
    result=explain(index,step)
    assert result.evidence
    assert '暂无' in result.explanations[0]['text']
    assert 'reference_url' not in result.explanations[0]


def test_noncommand_without_verified_quote_does_not_pull_unrelated_background():
    index,step=fixture();step.command=None;step.evidence=Evidence(kind='missing')
    result=explain(index,step)
    assert not result.evidence and not result.explanations
