from pathlib import Path
import pytest
from backend.core.github.models import DocFile, RepoMeta
from backend.core.github.recon import RawSignals
from backend.core.index.perspectives import assemble_perspective_chunks
from backend.core.index.vectorstore import Store
from benchmark.global_flat_index import GlobalFlatIndex
from benchmark.pinned_reference import PinnedReference, validate_reference


def signals():
    return RawSignals(meta=RepoMeta(owner='o', repo='r'), file_tree=['README.md'],
        root_entries={'readme.md': 'README.md'}, doc_files=[DocFile(path='README.md', name='README.md', text='Install\npip install -e .\nTest\npytest tests\n')])


def reference():
    return PinnedReference(owner='o', repo='r', commit_sha='a'*40, evaluation_scope=['B'],
        reviewer='AI agent', review_date='2026-10-18', source_license='MIT',
        steps=[{'order':1,'stage':'B','title':'Test','expected_commands':['pytest tests'],
            'evidence_sources':['README.md#L4'],
            'citations':[{'path':'README.md','line_start':4,'line_end':4,'quote':'pytest tests'}]}])


def test_agent_source_check_never_becomes_human_quality_claim():
    check = validate_reference(reference(), signals(), 'a'*40)
    assert check['source_rule_validation'] == 'passed'
    assert check['quality_claim_eligible'] is False


def test_reference_cannot_score_a_different_commit():
    with pytest.raises(ValueError): validate_reference(reference(), signals(), 'b'*40)


def test_reference_rejects_invented_quote():
    ref = reference(); ref.steps[0].citations[0].quote='not in original'
    with pytest.raises(ValueError): validate_reference(ref, signals(), 'a'*40)


def test_reference_rejects_command_with_same_tool_but_wrong_arguments():
    ref = reference(); ref.steps[0].expected_commands=['pytest imaginary']
    with pytest.raises(ValueError): validate_reference(ref, signals(), 'a'*40)


def test_global_baseline_is_one_deduplicated_corpus():
    sig = signals(); flat = GlobalFlatIndex(sig)
    expected = {(c.source_path,c.kind,c.text) for c in assemble_perspective_chunks(sig)}
    assert flat.corpus_size == len(expected)
    assert list(flat.store._rows) == ['flat']
    assert len(expected) < len(assemble_perspective_chunks(sig))


def test_global_baseline_never_routes_by_question_kind():
    flat = GlobalFlatIndex(signals())
    assert flat.search('pytest tests',kind='setup').hits == flat.search('pytest tests',kind='issue').hits


def test_disabling_executable_boost_removes_perspective_bonus():
    routed = Store('o','r',boost_executable=False); flat=Store('o','r',boost_executable=False)
    rows=['pytest tests','tests are useful']
    routed.upsert('v3',rows);flat.upsert('flat',rows)
    assert [h.score for h in routed.query('v3','pytest tests')] == [h.score for h in flat.query('flat','pytest tests')]
