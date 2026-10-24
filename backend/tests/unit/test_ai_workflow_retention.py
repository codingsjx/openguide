"""Verified AI content survives a missing complementary component."""
import re
from backend.core.generate.pipeline import build_guide
from backend.core.generate.schemas import Guide
from backend.core.github.recon import RawSignals
from backend.core.github.models import DocFile,RepoMeta


def signals():
    docs={'backend/README.md':'# Backend\nRequires Python 3.12 and uv.\n```sh\ncd backend\nuv sync\nuv run pytest tests/ -q\n```',
          'frontend/README.md':'# Frontend\nRequires Node.js 24 and pnpm.\n```sh\ncd frontend\npnpm install\npnpm build\n```',
          'backend/pyproject.toml':'[project]\nrequires-python = ">=3.12"',
          'frontend/package.json':'{"scripts":{"build":"vite build"}}'}
    return RawSignals(meta=RepoMeta(owner='o',repo='r',default_branch='b'*40),
        doc_files=[DocFile(path=p,name=p.rsplit('/',1)[-1],text=t) for p,t in docs.items()],file_tree=list(docs)+['backend/tests/test_one.py'])


class PartialModel:
    def __init__(self,forged=False):self.calls=[];self.forged=forged
    def available(self):return True
    def chat_json(self,messages,**kwargs):
        stage=re.search(r'Stage ([ABCD])',messages[-1]['content'])[1];self.calls.append(stage)
        command='uv sync' if stage=='A' else 'uv run pytest tests/ -q'
        if self.forged:command+=' --invented'
        return {'steps':[{'title':'AI retained explanation '+stage,'command':command,'expected':'Check actual result, not a claim of execution.',
                         'evidence':{'source':'backend/README.md'}}]}


def test_missing_component_gets_rule_supplement_without_discarding_verified_ai():
    model=PartialModel();g=build_guide(signals(),llm_client=model,check_suitability=False)
    assert model.calls==['A','B']
    assert g.generation_mode=='mixed' and g.stage_modes['A']==g.stage_modes['B']=='mixed'
    commands={s.command:s for s in g.steps if s.command}
    assert commands['uv sync'].title=='AI retained explanation A'
    assert commands['uv sync'].generation_source=='llm'
    assert commands['pnpm install'].generation_source=='rules'
    assert commands['pnpm build'].generation_source=='rules'
    assert commands['uv run pytest tests/ -q'].title=='AI retained explanation B'
    assert len([s for s in g.steps if s.command=='uv sync'])==1
    assert all(s.evidence.verification=='command_verified' for s in commands.values())
    assert any('Node.js' in s.evidence.quote for s in g.steps)
    assert g.stage_fallbacks['C']==g.stage_fallbacks['D']=='no_stage_evidence'
    Guide.model_validate(g.model_dump())


def test_forged_ai_commands_are_never_preserved_as_successful_ai_content():
    g=build_guide(signals(),llm_client=PartialModel(forged=True),check_suitability=False)
    assert all('--invented' not in (s.command or '') for s in g.steps)
    assert g.stage_modes['A']==g.stage_modes['B']=='heuristic'
    assert not any(s.generation_source=='llm' for s in g.steps)


def test_research_protocol_still_calls_four_stages_without_product_supplements():
    model=PartialModel();g=build_guide(signals(),llm_client=model,strict_llm=True,check_suitability=False)
    assert model.calls==list('ABCD')
    assert not any(s.command=='pnpm install' for s in g.steps)
    assert g.stage_modes['A']=='llm'


def test_product_can_recover_source_type_and_wrapped_quote_but_not_paraphrases():
    class Wrapped(PartialModel):
        def chat_json(self,messages,**kwargs):
            stage=re.search(r'Stage ([ABCD])',messages[-1]['content'])[1];self.calls.append(stage)
            assert '已由系统按当前文件核验' in messages[-1]['content']
            return {'steps':[{'title':'AI quoted runtime','evidence':{'kind':'source','source':'backend/README.md','quote':'Requires Python 3.12 and uv.'}}]}
    sig=signals();sig.doc_files[0].text=sig.doc_files[0].text.replace('Requires Python 3.12 and uv.','Requires Python 3.12\nand uv.')
    g=build_guide(sig,llm_client=Wrapped(),check_suitability=False)
    retained=[s for s in g.steps if s.title=='AI quoted runtime']
    assert retained and retained[0].generation_source=='llm'
    assert retained[0].evidence.quote=='Requires Python 3.12\nand uv.'
    assert any('类型字段' in h for h in retained[0].fail_hints)


def test_quote_whitespace_compatibility_is_opt_in_and_cannot_rewrite_words():
    from backend.core.generate.schemas import GuideStep,Evidence
    from backend.core.generate.evidence import verify_step_evidence
    sig=signals();sig.doc_files[0].text='Requires Python 3.12\nand uv.'
    step=GuideStep(step_id=1,stage='A',title='runtime',evidence=Evidence(source='backend/README.md',quote='Requires Python 3.12 and uv.'))
    assert verify_step_evidence(step,sig).kind=='missing'
    assert verify_step_evidence(step,sig,allow_quote_whitespace=True).quote=='Requires Python 3.12\nand uv.'
    step.evidence.quote='Requires Python 3.13 and uv.'
    assert verify_step_evidence(step,sig,allow_quote_whitespace=True).kind=='missing'
