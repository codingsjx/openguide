"""Reduced real-world cases: comments, same-named packages and scoped answers."""
import pytest

from backend.core.generate.command_context import without_shell_comment, document_directory, input_paths
from backend.core.generate.evidence import verify_step_evidence
from backend.core.generate.pipeline import build_guide, audit_steps, _build_index
from backend.core.generate.schemas import GuideStep, Evidence
from backend.core.github.models import RepoMeta, DocFile
from backend.core.github.recon import RawSignals
from backend.core.ask.service import answer_question, resolve_question
from backend.core.ask.scope import question_component


def signals():
    docs={
        'README.md':'# App\n## 后端\n```bash\ncd backend\nuv sync # locked dependencies\nuv run pytest tests/ -q # 69 tests; not a run result\n```\n## 前端\n```bash\ncd frontend\npnpm install\npnpm build # production build\n```\n',
        'backend/README.md':'# Backend\nPython 3.12\n```bash\ncd backend\nuv sync # dependencies\nuv run pytest tests/ -q # 68 tests\n```\n',
        'frontend/README.md':'# Frontend\n```bash\ncd frontend\npnpm install\n```\n## Build\n```bash\npnpm build # typecheck and build\n```\n',
        'frontend/package.json':'{"scripts":{"build":"vite build"}}',
        'backend/pyproject.toml':'[project]\nrequires-python = ">=3.12"\n',
        'benchmark/README.md':'# Benchmark harness installation and tests\n```bash\nnpm ci\nnpm test\n```\n',
        '.github/workflows/ci.yml':'steps:\n  - run: python -m pip install -q uv\n',
    }
    return RawSignals(meta=RepoMeta(owner='fixture',repo='app',default_branch='a'*40),
        doc_files=[DocFile(path=p,name=p.split('/')[-1],text=t) for p,t in docs.items()],
        file_tree=list(docs)+['backend/src/backend/__init__.py','backend/tests/test_api.py','frontend/src/main.tsx'])


@pytest.mark.parametrize('original,expected',[
    ('uv sync # use uv.lock','uv sync'),
    ('uv sync --locked # note','uv sync --locked'),
    ('uv run pytest tests -q # 69 tests; npm ci','uv run pytest tests -q'),
    ('python -c \'print("# value")\' # note','python -c \'print("# value")\''),
    ('curl https://example.invalid/#fragment','curl https://example.invalid/#fragment'),
    ('echo "inside # string"','echo "inside # string"'),
    ('echo value`#suffix','echo value`#suffix'),
])
def test_only_unquoted_whitespace_hash_comments_are_removed(original,expected):
    assert without_shell_comment(original)==expected


def test_short_command_matches_complete_executable_part_and_preserves_original_line():
    sig=signals()
    step=GuideStep(step_id=1,stage='A',title='Install',command='uv sync',evidence=Evidence(source='backend/README.md',quote='uv sync'))
    evidence=verify_step_evidence(step,sig)
    assert evidence.verification=='command_verified'
    assert evidence.quote=='uv sync # dependencies'
    assert evidence.line_start==5 and evidence.line_end==5
    assert step.command=='uv sync'
    sig.doc_files[1].text='uv sync --locked # dependencies'
    assert verify_step_evidence(step,sig).kind=='missing'  # cannot drop a flag
    sig.doc_files[1].text='uv sync # actual comment'
    step.command='uv sync # invented comment'
    assert verify_step_evidence(step,sig).kind=='missing'


def test_inline_command_comment_is_verified_without_rewriting_its_source():
    sig=signals();sig.doc_files[1].text='Use `uv sync # locked dependencies` to prepare.'
    step=GuideStep(step_id=1,stage='A',title='Install',command='uv sync',evidence=Evidence(source='backend/README.md'))
    result=verify_step_evidence(step,sig)
    assert result.verification=='command_verified' and result.quote=='uv sync # locked dependencies'


def test_package_with_same_backend_basename_does_not_hide_project_directory():
    sig=signals()
    assert document_directory(sig,'README.md','uv sync')[0]=='backend'
    assert document_directory(sig,'backend/README.md','uv sync')[0]=='backend'
    assert document_directory(sig,'backend/README.md','uv run pytest tests/ -q')[0]=='backend'
    assert input_paths('uv run pytest tests/ -q # pytest benchmark/tests')==[('tests/',True)]
    assert input_paths('pytest -ra tests')==[('tests',True)]


def test_readme_build_directory_requires_a_real_matching_manifest_script():
    sig=signals()
    assert document_directory(sig,'frontend/README.md','pnpm build')[0]=='frontend'
    assert document_directory(sig,'frontend/README.md','pnpm build --dir other') is None
    sig.doc_files[3].text='{"scripts":{"dev":"vite"}}'
    assert document_directory(sig,'frontend/README.md','pnpm build') is None


def test_rule_guide_keeps_both_component_installs_and_clean_test_commands():
    guide=build_guide(signals(),use_llm=False,check_suitability=False)
    commands={s.command:s for s in guide.steps if s.command}
    assert commands['uv sync'].working_directory=='backend'
    assert commands['pnpm install'].working_directory=='frontend'
    assert commands['uv run pytest tests/ -q'].working_directory=='backend'
    assert commands['pnpm build'].working_directory=='frontend'
    assert not any('#' in command or command=='npm ci' or '-q uv' in command for command in commands)
    assert commands['uv sync'].step_id in commands['uv run pytest tests/ -q'].prerequisite_step_ids
    assert commands['pnpm install'].step_id not in commands['uv run pytest tests/ -q'].prerequisite_step_ids
    assert commands['uv sync'].step_id not in commands['pnpm build'].prerequisite_step_ids
    assert commands['pnpm install'].step_id in commands['pnpm build'].prerequisite_step_ids


def test_python_environment_is_not_a_frontend_installation_prerequisite():
    sig=signals();sig.doc_files[0].text='```\nuv venv --python 3.12 .venv\nuv pip install -r backend/requirements.txt\n```\n```\ncd frontend\npnpm install\n```'
    sig.file_tree.append('backend/requirements.txt')
    guide=build_guide(sig,use_llm=False,check_suitability=False)
    steps={s.command:s for s in guide.steps if s.command}
    environment=steps['uv venv --python 3.12 .venv']
    assert environment.step_id not in steps['pnpm install'].prerequisite_step_ids
    assert environment.step_id in steps['uv pip install -r backend/requirements.txt'].prerequisite_step_ids


def test_literal_cd_is_kept_as_an_instruction_instead_of_erased_evidence():
    sig=signals()
    result=audit_steps(sig,_build_index(sig),[GuideStep(step_id=1,stage='A',title='Enter backend',
        command='cd backend',evidence=Evidence(source='README.md'))])[0]
    assert result.command is None
    assert result.evidence.verification=='quote_verified' and result.evidence.quote=='cd backend'


def test_single_component_install_is_restored_when_model_has_only_a_prose_quote():
    sig=signals();sig.doc_files=[d for d in sig.doc_files if not d.path.startswith('frontend/')]
    sig.doc_files[0].text='```\ncd backend\nuv sync # dependencies\n```'
    class Model:
        def available(self): return True
        def chat_json(self,*a,**k): return {'steps':[{'title':'Read installation docs','evidence':{'source':'README.md','quote':'uv sync'}}]}
    guide=build_guide(sig,llm_client=Model(),check_suitability=False)
    assert any(s.stage=='A' and s.command=='uv sync' for s in guide.steps)
    assert guide.stage_fallbacks['A']=='incomplete_workflow'


def answer(question, sig=None, history=None):
    sig=sig or signals()
    return answer_question(sig,_build_index(sig),question,history or [],None)


def test_backend_operations_do_not_retrieve_frontend_benchmark_or_tree_distractions():
    result=answer('后端测试应该在哪个目录运行？需要先安装什么依赖？')
    assert result.intents==['setup','test']
    assert all(not s.source.startswith(('benchmark/','frontend/','.github/')) for s in result.sources)
    assert all(s.kind=='file' for s in result.sources)
    assert all('pnpm' not in s.quote and 'npm ci' not in s.quote for s in result.sources)
    assert {'uv sync','uv run pytest tests/ -q'} <= {c.command for c in result.commands}
    assert all(c.working_directory=='backend' for c in result.commands)
    assert any('backend' in point.text and '建议执行位置' in point.text for point in result.points)
    assert all('# 68' not in c.command for c in result.commands)


def test_frontend_question_and_explicit_benchmark_question_retain_their_own_sources():
    front=answer('前端依赖怎么安装，测试怎么运行？')
    assert any(c.command=='pnpm install' for c in front.commands)
    assert all(c.working_directory=='frontend' for c in front.commands)
    assert all('uv sync' not in s.quote for s in front.sources)
    bench=answer('benchmark 评测工具的依赖怎么安装？')
    assert any(s.source=='benchmark/README.md' for s in bench.sources)
    assert any(c.command=='npm ci' for c in bench.commands)


def test_component_followup_inherits_context_but_explicit_new_component_wins():
    assert question_component('这条命令在哪执行？',['后端测试怎么运行？'],True)=='backend'
    assert question_component('前端依赖怎么安装？',['后端测试怎么运行？'],True)=='frontend'
    assert question_component('前后端都怎么安装？',['后端测试怎么运行？'],True) is None
    follow=answer('这条命令在哪个目录运行？',history=['后端测试怎么运行？'])
    assert follow.context_used and 'arch' not in follow.intents
    assert all(c.working_directory=='backend' for c in follow.commands)
    assert 'arch' in resolve_question('后端测试模块的架构是什么？',[])[0]


def test_missing_backend_docs_do_not_turn_frontend_installation_into_an_answer():
    sig=signals();sig.doc_files=[d for d in sig.doc_files if d.path.startswith(('frontend/','benchmark/'))]
    result=answer('后端依赖怎么安装？',sig)
    assert result.status=='insufficient_evidence' and not result.commands and not result.sources


def test_backend_can_itself_use_npm_language_is_not_a_component_filter():
    sig=signals();sig.doc_files[1].text='# Node backend\n```\ncd backend\nnpm ci\n```'
    result=answer('后端依赖怎么安装？',sig)
    assert any(c.command=='npm ci' and c.working_directory=='backend' for c in result.commands)
