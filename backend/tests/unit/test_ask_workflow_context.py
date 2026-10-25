from backend.core.ask.scope import component_excerpt
from backend.core.ask.service import answer_question
from backend.core.github.models import RepoMeta, DocFile
from backend.core.github.recon import RawSignals
from backend.core.index.service import RepoIndex

SHA='a'*40
README='''# Project
## Backend setup
```sh
cd backend
uv sync
```
## Frontend setup
```sh
cd frontend
pnpm install
```
## Tests
```sh
uv run pytest backend/tests -q
```
```sh
cd frontend
pnpm test
```
'''

def fixture():
    sig=RawSignals(meta=RepoMeta(owner='o',repo='r',default_branch=SHA),
        doc_files=[DocFile(path='README.md',name='README.md',text=README)],
        file_tree=['README.md','backend/tests/test_one.py','frontend/package.json'])
    idx=RepoIndex('o','r');idx.index(sig)
    return sig,idx

def test_shared_test_chapter_keeps_its_actual_backend_command():
    text='```sh\nuv run pytest backend/tests -q\n```'
    result=component_excerpt(README,'README.md',text,'backend','test')
    assert result and 'pytest backend/tests' in result[0]
    assert 'uv sync' not in result[0]

def test_frontend_excerpt_is_not_used_for_a_backend_question():
    text='```sh\ncd frontend\npnpm test\n```'
    assert component_excerpt(README,'README.md',text,'backend','test') is None

def test_generic_testing_section_does_not_get_replaced_by_setup():
    text='## Tests\n```sh\nuv run pytest backend/tests -q\n```'
    excerpt=component_excerpt(README,'README.md',text,'backend','test')
    assert excerpt and 'pytest backend/tests' in excerpt[0]

def test_question_returns_the_same_fixed_revision_backend_test_operation():
    sig,idx=fixture();r=answer_question(sig,idx,'后端测试在哪个目录运行？',[])
    assert any(c.command=='uv run pytest backend/tests -q' for c in r.commands)
    assert not any('pnpm' in c.command for c in r.commands)
    assert r.revision==SHA
    assert all('/blob/'+SHA+'/' in s.url for s in r.sources)

def test_empty_ai_answer_does_not_erase_independently_verified_operations():
    class Empty:
        def available(self):return True
        def chat_json(self,*a,**k):return {'points':[]}
    sig,idx=fixture()
    baseline=answer_question(sig,idx,'后端测试怎么运行？',[])
    result=answer_question(sig,idx,'后端测试怎么运行？',[],Empty())
    assert baseline.commands and result.commands==baseline.commands
    assert result.points==baseline.points
    assert result.mode=='extractive' and result.fallback_reason=='model_abstained'

def test_unknown_coverage_remains_unknown_despite_available_test_commands():
    class Empty:
        def available(self):return True
        def chat_json(self,*a,**k):return {'points':[]}
    sig,idx=fixture();r=answer_question(sig,idx,'测试覆盖率实际是多少？',[],Empty())
    assert r.status=='insufficient_evidence' and not r.commands and not r.points
