"""Regressions for the observed novice blockers, with no network/model access."""
import pytest

from backend.core.followup.service import granular
from backend.core.generate.pipeline import build_guide
from backend.core.generate.prerequisites import runtime_steps
from backend.core.generate.schemas import Evidence, GuideStep
from backend.core.github.models import DocFile, RepoMeta
from backend.core.github.recon import RawSignals
from backend.core.index.service import RepoIndex
from backend.core.profile.builder import build_profile


def signals():
    docs = {
        'backend/README.md': '# Backend\n需先装 uv（本项目用 uv 管理 Python 3.12）。\n```sh\ncd backend\nuv sync # use the lock\nuv run pytest tests/ -q\n```',
        'frontend/README.md': '# Frontend\n需先装 Node.js 24 LTS 与 pnpm。\n```sh\ncd frontend\npnpm install\npnpm build\n```',
        'backend/pyproject.toml': '[project]\nrequires-python = ">=3.12"',
        'frontend/package.json': '{"scripts":{"build":"vite build"},"dependencies":{"node":"*"}}',
        '.github/workflows/legacy.yml': 'Requires Python 2.7 for CI only\nrun: pip install special-ci-tool',
        'examples/README.md': 'Requires Python 3.6 for this unrelated example.',
    }
    return RawSignals(meta=RepoMeta(owner='o',repo='app',default_branch='b'*40),
        root_entries={'readme.md':'README.md'},
        doc_files=[DocFile(path=p,name=p.rsplit('/',1)[-1],text=t) for p,t in docs.items()],
        file_tree=list(docs)+['backend/tests/test_api.py','vendor/thirdparty/package.json','backend/link/pyproject.toml'],
        symlink_paths=['backend/link/pyproject.toml'])


def test_profile_discovers_components_without_guessing_commands():
    profile = build_profile(signals())
    assert profile.build.manifest_paths == ['backend/pyproject.toml','frontend/package.json']
    assert profile.build.scan_status == 'tree'
    assert profile.build.test_cmd is None and profile.build.package_manager is None
    assert profile.revision == 'b'*40


def test_build_inventory_reports_partial_and_preserves_other_markers():
    sig=signals()
    sig.file_tree=['Cargo.toml','Makefile','Dockerfile']
    sig.doc_files=[]
    sig.unavailable_signals=['tree']
    profile=build_profile(sig)
    assert 'Cargo.toml' in profile.build.manifest_paths
    assert profile.build.has_makefile and profile.build.has_dockerfile
    assert profile.build.scan_status=='partial'


def test_runtime_requirements_are_literal_not_executable_or_auxiliary():
    sig=signals()
    requirements=runtime_steps(sig)
    assert {s.evidence.source for s in requirements}=={'backend/README.md','frontend/README.md','backend/pyproject.toml'}
    assert all(s.evidence.verification=='quote_verified' and s.evidence.line_start for s in requirements)
    assert all(s.command is None and s.execution_record is None for s in requirements)
    assert '3.12' in ' '.join(s.evidence.quote for s in requirements)
    assert not any('Python 2.7' in s.evidence.quote or 'Python 3.6' in s.evidence.quote for s in requirements)


def test_rules_preserve_runtime_and_correct_component_operations():
    guide=build_guide(signals(),use_llm=False,check_suitability=False)
    assert any('Python 3.12' in s.evidence.quote and s.command is None for s in guide.steps)
    assert any('Node.js 24' in s.evidence.quote and s.command is None for s in guide.steps)
    commands={s.command:s for s in guide.steps if s.command}
    assert commands['uv sync'].working_directory=='backend'
    assert commands['pnpm install'].working_directory=='frontend'
    assert commands['uv run pytest tests/ -q'].prerequisite_step_ids==[commands['uv sync'].step_id]
    assert commands['pnpm build'].prerequisite_step_ids==[commands['pnpm install'].step_id]


def test_model_cannot_silently_omit_stated_runtime_prerequisites():
    class Model:
        calls=0
        def available(self):return True
        def chat_json(self,*a,**k):
            stage='ABCD'[self.calls];self.calls+=1
            items=[{'title':'install','command':cmd,'evidence':{'source':source}}
                for cmd,source in [('uv sync','backend/README.md'),('pnpm install','frontend/README.md')]] if stage=='A' else [
                    {'title':'pending','command':None,'evidence':{'kind':'missing'}}]
            return {'steps':items}
    guide=build_guide(signals(),llm_client=Model(),check_suitability=False)
    assert guide.stage_fallbacks['A']=='incomplete_workflow'
    assert any('Node.js 24' in s.evidence.quote for s in guide.steps)


def test_granular_provides_small_scoped_operations_with_checks():
    sig=signals();index=RepoIndex('o','app');index.index(sig)
    step=GuideStep(step_id=3,stage='A',title='Install',command='uv sync',
        evidence=Evidence(source='backend/README.md'))
    result=granular(index,step)
    operations=[s for s in result.sub_steps if s.command]
    assert len(operations)==1
    assert operations[0].command=='uv sync' and operations[0].working_directory=='backend'
    assert operations[0].evidence.verification=='command_verified'
    assert any('Python 3.12' in s.evidence.quote for s in result.sub_steps)
    assert not any(s.evidence.source.startswith(('frontend/','.github/')) for s in result.sub_steps)
    assert not any(s.source.startswith(('frontend/','.github/')) for s in result.evidence)
    assert len(result.preparation_checks)>=2 and len(result.completion_checks)>=2


@pytest.mark.parametrize('command,stage',[('uv sync --invented','A'),('uv run pytest tests/ -q','A')])
def test_granular_never_promotes_forged_or_wrong_stage_commands(command,stage):
    sig=signals();index=RepoIndex('o','app');index.index(sig)
    result=granular(index,GuideStep(step_id=1,stage=stage,title='Install',command=command,
        evidence=Evidence(source='backend/README.md')))
    assert not any(s.command for s in result.sub_steps)


def test_version_files_and_node_engines_are_preserved_but_dependencies_are_not_requirements():
    sig=signals()
    sig.doc_files=[DocFile(path='.python-version',name='.python-version',text='3.12.9\n'),
        DocFile(path='frontend/package.json',name='package.json',text='{ "engines": { "node": ">=24" }, "dependencies": {"node": "22"}}')]
    requirements=runtime_steps(sig)
    assert len(requirements)==2
    assert requirements[0].evidence.quote=='3.12.9'
    assert requirements[1].evidence.quote=='"engines": { "node": ">=24" }'


@pytest.mark.parametrize('outage',[False,True])
def test_profile_service_fetches_pinned_tree_and_keeps_partial_information_on_failure(monkeypatch,outage):
    from backend.core.github.client import GitHubClientError
    from backend.core.profile.service import build_profile_for_url
    sig=signals();sig.file_tree=[];sig.doc_files=[]
    monkeypatch.setattr('backend.core.profile.service.recon',lambda *a,**k:sig)
    class Client:
        def resolve_commit(self,owner,repo,ref):return 'b'*40
        def get_git_tree(self,owner,repo,ref):
            assert ref=='b'*40
            if outage:raise GitHubClientError('fixture outage')
            return [{'type':'blob','path':'backend/pyproject.toml'},{'type':'blob','path':'frontend/package.json'}]
    profile=build_profile_for_url('o/app',client=Client())
    assert profile.revision=='b'*40
    if outage:
        assert profile.build.scan_status=='partial'
        assert 'tree' in profile.unavailable_signals and profile.collection_warnings
    else:
        assert profile.build.manifest_paths==['backend/pyproject.toml','frontend/package.json']


def test_empty_context_skips_product_model_calls_but_preserves_strict_protocol():
    class Model:
        calls=0
        def available(self):return True
        def chat_json(self,*a,**k):
            self.calls+=1
            return {'steps':[{'title':'Await source','evidence':{'kind':'missing'}}]}
    sig=RawSignals(meta=RepoMeta(owner='o',repo='empty'))
    product=Model()
    guide=build_guide(sig,llm_client=product,check_suitability=False)
    assert product.calls==0
    assert guide.stage_fallbacks=={stage:'no_stage_evidence' for stage in 'ABCD'}
    assert set(s.stage for s in guide.steps)==set('ABCD')
    strict=Model()
    build_guide(sig,llm_client=strict,check_suitability=False,strict_llm=True)
    assert strict.calls==4


def test_granular_derives_component_from_verified_context_not_posted_directory():
    sig=signals()
    root='# Setup\n## Backend\nRequires Python 3.12 and uv.\n```sh\ncd backend\nuv sync\n```\n## Frontend\nRequires Node.js 24 and pnpm.\n```sh\ncd frontend\npnpm install\n```'
    sig.doc_files.append(DocFile(path='README.md',name='README.md',text=root))
    sig.file_tree.append('README.md')
    idx=RepoIndex('o','app');idx.index(sig)
    result=granular(idx,GuideStep(step_id=1,stage='A',title='Install',command='pnpm install',
        working_directory='backend',evidence=Evidence(source='README.md')))
    assert next(s for s in result.sub_steps if s.command).working_directory=='frontend'
    assert not any('Python 3.12' in s.evidence.quote for s in result.sub_steps)
    assert any('Node.js 24' in s.evidence.quote for s in result.sub_steps)
