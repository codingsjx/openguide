"""Real failure shapes, reduced to hermetic multi-component fixtures."""
import re
import pytest

from backend.core.github.models import DocFile, RepoMeta
from backend.core.github.recon import RawSignals, enrich_docs_and_tree
from backend.core.generate.pipeline import build_guide, _STAGE_CMD_PATTERNS
from backend.core.generate.schemas import GuideStep, Evidence
from backend.core.generate.evidence import verify_step_evidence
from backend.core.generate.command_context import document_directory, input_paths
from test_revision_collection import PinnedClient, SHA


TEST_COMMAND = r'uv run --python 3.12 --with-requirements backend/requirements.txt pytest backend\tests -q'
INSTALL_COMMAND = r'uv pip install --python .venv -r backend\requirements.txt'
README = '''# Example application
## Configure
```powershell
Copy-Item .env.example .env
```
## Windows installation
```powershell
uv venv --python 3.12 .venv
''' + INSTALL_COMMAND + '''
```
Frontend in a second terminal:
```powershell
Set-Location frontend
pnpm install --frozen-lockfile
```
## Tests
```powershell
''' + TEST_COMMAND + '''
Set-Location frontend
pnpm build
```
'''


def signals():
    docs = {'README.md':README, 'backend/requirements.txt':'pytest==8.4.1\npytest-asyncio==1.1.0\n',
            'frontend/package.json':'{"scripts":{"build":"vite build"}}'}
    return RawSignals(meta=RepoMeta(owner='fixture',repo='app',default_branch=SHA),
        doc_files=[DocFile(path=p,name=p.split('/')[-1],text=t) for p,t in docs.items()],
        file_tree=list(docs)+['backend/tests/test_api.py','.env.example'])


@pytest.mark.parametrize('declaration', ['pytest==8.4.1','pytest>=8','pytest-asyncio==1.1.0','pytest[test]~=8.0'])
def test_full_dependency_declarations_never_pass_command_verification(declaration):
    sig=signals(); sig.doc_files[1].text=declaration
    step=GuideStep(step_id=1,stage='B',title='tests',command=declaration,
                   evidence=Evidence(source='backend/requirements.txt'))
    assert verify_step_evidence(step,sig).kind=='missing'
    assert not re.match(_STAGE_CMD_PATTERNS['B'],declaration)


@pytest.mark.parametrize('declaration', ['pytest','pytest @ https://example.invalid/test.whl',
    'pytest ; python_version >= "3.12"'])
def test_unpinned_or_url_requirements_are_not_commands_either(declaration):
    sig=signals();sig.doc_files[1].text=declaration
    step=GuideStep(step_id=1,stage='B',title='test',command=declaration,
        evidence=Evidence(source='backend/requirements.txt'))
    assert verify_step_evidence(step,sig).kind=='missing'


@pytest.mark.parametrize('command', [TEST_COMMAND, 'uv run pytest tests',
    'uv run --locked --group test python -m pytest tests', 'uv run --with pytest --python 3.12 pytest tests'])
def test_uv_test_wrappers_are_recognised_without_stripping_options(command):
    assert re.match(_STAGE_CMD_PATTERNS['B'],command)


@pytest.mark.parametrize('command', ['uv run python -m backend.evaluation',
    'uv run pytest-plugin tests','uv run --with pytest pytest==8','pytest-asyncio'])
def test_uv_other_programs_and_tool_prefixes_are_not_tests(command):
    assert not re.match(_STAGE_CMD_PATTERNS['B'],command)


def test_multi_component_guide_retains_backend_frontend_and_test_scope():
    guide=build_guide(signals(),use_llm=False,check_suitability=False)
    commands={s.command:s for s in guide.steps if s.command}
    assert INSTALL_COMMAND in commands and 'pnpm install --frozen-lockfile' in commands
    assert TEST_COMMAND in commands and 'pnpm build' in commands
    assert not any('pytest==' in c for c in commands)
    assert commands[INSTALL_COMMAND].working_directory=='.'
    assert commands['uv venv --python 3.12 .venv'].working_directory=='.'
    assert commands[TEST_COMMAND].working_directory=='.'
    assert commands[TEST_COMMAND].required_paths==['backend/requirements.txt','backend/tests']
    assert commands['pnpm install --frozen-lockfile'].working_directory=='frontend'
    assert commands['pnpm build'].working_directory=='frontend'
    assert all(s.directory_basis=='document_context' for s in commands.values())
    assert all(s.evidence.verification=='command_verified' for s in commands.values())
    assert any('本地环境配置' in s.title and s.evidence.verification=='quote_verified' for s in guide.steps)
    assert '不等同测试' in commands['pnpm build'].title
    assert not any('测试输出' in c for c in commands['pnpm build'].success_checks)
    assert commands[INSTALL_COMMAND].step_id in commands[TEST_COMMAND].prerequisite_step_ids
    assert commands['uv venv --python 3.12 .venv'].step_id in commands[INSTALL_COMMAND].prerequisite_step_ids
    assert all(s.execution_record is None for s in guide.steps)


def test_inline_pip_alternative_is_not_added_after_a_verified_uv_install():
    sig=signals(); sig.doc_files[0].text += '\nAlternative: `pip install -r backend/requirements.txt`\n'
    guide=build_guide(sig,use_llm=False,check_suitability=False)
    assert INSTALL_COMMAND in [s.command for s in guide.steps]
    assert 'pip install -r backend/requirements.txt' not in [s.command for s in guide.steps]


def test_partial_ai_installation_is_replaced_with_complete_literal_stage():
    class PartialModel:
        calls=0
        def available(self): return True
        def chat_json(self,*args,**kwargs):
            stage='ABCD'[self.calls];self.calls+=1
            return {'steps':[{'title':'Only front-end','command':'pnpm install --frozen-lockfile' if stage=='A' else None,
                'evidence':{'source':'README.md','quote':'pnpm install --frozen-lockfile'}}]}
    guide=build_guide(signals(),llm_client=PartialModel(),check_suitability=False)
    assert guide.stage_fallbacks['A']=='incomplete_workflow'
    assert guide.stage_modes['A']=='heuristic'
    assert INSTALL_COMMAND in [s.command for s in guide.steps]
    strict=build_guide(signals(),llm_client=PartialModel(),check_suitability=False,strict_llm=True)
    assert strict.stage_modes['A']=='llm' and 'incomplete_workflow' not in strict.stage_fallbacks.values()


def test_model_cannot_label_a_build_command_as_a_successful_test():
    from backend.core.generate.pipeline import audit_steps, _build_index
    sig=signals()
    step=GuideStep(step_id=1,stage='B',title='All tests passed',command='pnpm build',
        expected='All tests pass',evidence=Evidence(source='README.md'))
    result=audit_steps(sig,_build_index(sig),[step])[0]
    assert '不等同测试' in result.title and '本指南未执行' in result.expected


def test_windows_paths_are_preserved_but_checked_as_repository_paths():
    assert input_paths(INSTALL_COMMAND)==[('backend/requirements.txt',False)]
    assert input_paths(TEST_COMMAND)==[('backend/requirements.txt',False),('backend/tests',True)]


@pytest.mark.parametrize('prefix', ['cd /mnt/d/private/project', 'cd ../frontend',
    'Set-Location D:\\local\\frontend', 'pushd frontend', 'cd frontend && pnpm install'])
def test_unsafe_or_machine_specific_directory_is_not_inferred(prefix):
    sig=signals(); sig.doc_files[0].text='```\n'+prefix+'\npnpm install\n```'
    assert document_directory(sig,'README.md','pnpm install') is None


def test_directory_is_not_inherited_across_code_blocks():
    sig=signals(); sig.doc_files[0].text='```\ncd frontend\npnpm install\n```\n\n```\npnpm build\n```'
    assert document_directory(sig,'README.md','pnpm install')[0]=='frontend'
    assert document_directory(sig,'README.md','pnpm build') is None


def test_repeated_commands_use_verified_occurrence_and_unknown_stays_unknown():
    sig=signals(); sig.file_tree += ['admin/package.json']
    sig.doc_files[0].text='```\ncd frontend\npnpm install\n```\n```\ncd admin\npnpm install\n```'
    assert document_directory(sig,'README.md','pnpm install',7)[0]=='admin'
    sig.file_tree += ['tools/frontend/package.json']
    assert document_directory(sig,'README.md','pnpm install',3) is None


def test_build_without_test_script_is_not_claimed_as_test_baseline():
    sig=signals(); sig.doc_files[0].text='```\ncd frontend\npnpm build\n```'
    guide=build_guide(sig,use_llm=False,check_suitability=False)
    tests=[s for s in guide.steps if s.stage=='B']
    assert any(s.command is None and s.evidence.kind=='missing' for s in tests)
    assert any(s.command=='pnpm build' and '不等同测试' in s.title for s in tests)


def test_nested_configs_are_pinned_and_generated_dependency_configs_excluded():
    class Components(PinnedClient):
        def get_git_tree(self,owner,repo,ref):
            return [{'type':'blob','path':p} for p in ['README.md','frontend/package.json',
                'backend/requirements.txt','docker-compose.yml','backend/Dockerfile',
                'frontend/node_modules/example/package.json','backend/.venv/requirements.txt']]
    c=Components(); result=enrich_docs_and_tree(RawSignals(meta=RepoMeta(owner='o',repo='r')),c)
    paths={d.path for d in result.doc_files}
    assert {'frontend/package.json','backend/requirements.txt','docker-compose.yml','backend/Dockerfile'}<=paths
    assert not any('node_modules' in p or '.venv' in p for p in paths)
    assert set(c.refs)=={SHA}


def test_nested_config_collection_is_bounded_and_reports_partial_coverage():
    class Many(PinnedClient):
        def get_git_tree(self,*args):
            return [{'type':'blob','path':f'packages/p{i}/package.json'} for i in range(35)]
    result=enrich_docs_and_tree(RawSignals(meta=RepoMeta(owner='o',repo='r')),Many())
    assert len([d for d in result.doc_files if d.path.endswith('package.json')])==24
    assert 'build_configs' in result.unavailable_signals
