"""Regressions from the 2026-10-22 simulated novice walkthrough."""
import pytest

from backend.core.followup.diagnostics import diagnostic_plan
from backend.core.followup.service import diagnose, explain
from backend.core.generate.issues import discover_issues
from backend.core.generate.schemas import Evidence, GuideStep
from backend.core.github.recon import RawSignals, recon
from backend.core.github.models import DocFile, RepoMeta
from backend.core.index.service import RepoIndex
from backend.core.profile.builder import build_profile


CA_LOG = ('FAILED TestPreparingURLs::test_different_connection_pool_for_tls_settings_verify_bundle_unexpired_cert\n'
    'OSError: Could not find a suitable TLS CA certificate bundle, invalid path: tests/certs/valid/ca/ca.crt')


def sig(**kwargs):
    return RawSignals(meta=RepoMeta(owner='o', repo='r'), **kwargs)


def issue(number, **kwargs):
    return dict(number=number, title=f'Task {number}', state='open', locked=False, assignees=[], **kwargs)


def test_certificate_path_is_not_dependency_source_timeout():
    category, hints, checks = diagnostic_plan(CA_LOG)
    assert category == 'local_certificate_path'
    assert len(checks) == 3
    assert 'git ls-files -s -- tests/certs/valid/ca' == checks[-1]['command']
    assert '120000' in checks[-1]['expected']
    assert not any('可换镜像' in h or h.startswith('另有网络异常') for h in hints)
    assert '本地证书路径无效' in hints[0]


@pytest.mark.parametrize('path', ['../../outside', '/etc/file', "x'); evil() #", 'x$(whoami)', 'x`whoami`', '-x'])
def test_log_paths_never_inject_shell_checks(path):
    _, _, checks = diagnostic_plan('Could not find a suitable TLS CA certificate bundle, invalid path: ' + path)
    assert len(checks) == 1
    assert path not in checks[0]['command']


def test_network_and_trust_errors_are_distinguished_from_test_names():
    assert diagnostic_plan('Test::test_connection_pool')[0] == 'unknown'
    assert diagnostic_plan('SSLError: CERTIFICATE_VERIFY_FAILED')[0] == 'certificate_trust'
    category, hints, _ = diagnostic_plan('requests.exceptions.ConnectTimeout: timed out')
    assert category == 'network'
    assert '测试网络失败不能由换源直接解决' in hints[0]
    category, hints, _ = diagnostic_plan(CA_LOG + '\nReadTimeout: timed out')
    assert category == 'local_certificate_path' and len(hints) == 2


def test_offline_diagnosis_retains_checks_without_repo_evidence():
    index = RepoIndex('o', 'r'); index.index(sig())
    result = diagnose(index, GuideStep(step_id=1, stage='B', title='Run tests'), CA_LOG)
    assert result.local_checks and result.diagnostic_category == 'local_certificate_path'
    assert not result.evidence


def test_recognized_local_path_does_not_wait_for_model_guess():
    class Client:
        def available(self): raise AssertionError('Specific read-only checks should not require model service')
    index = RepoIndex('o', 'r'); index.index(sig())
    result = diagnose(index, GuideStep(step_id=1, stage='B', title='Run tests'), CA_LOG, Client())
    assert result.mode == 'rules' and len(result.local_checks) == 3


def test_valid_certificate_path_does_not_recommend_expired_certificate_setup(monkeypatch):
    source, text = 'tests/certs/expired/README.md', 'Expired certificate setup; make clean then make all.'
    index = RepoIndex('o', 'r'); index.index(sig(doc_files=[DocFile(path=source,name='README.md',text=text)]))
    monkeypatch.setattr('backend.core.followup.service._top_snippets', lambda *a, **k: [{'source':source,'text':text}])
    result = diagnose(index, GuideStep(step_id=1,stage='B',title='Tests'), CA_LOG)
    assert result.local_checks and not result.evidence


def test_explain_falls_back_to_current_source_context():
    text = 'Use the flag to work around an old timestamp.\ngit clone -c fetch.fsck.badTimezone=ignore https://github.com/o/r.git\n'
    index = RepoIndex('o', 'r'); index.index(sig(doc_files=[DocFile(path='README.md',name='README.md',text=text)]))
    step = GuideStep(step_id=1,stage='A',title='为何执行本步骤',evidence=Evidence(source='README.md',line_start=2))
    result = explain(index, step, '没有匹配的中文词')
    assert result.evidence and 'old timestamp' in result.evidence[0].quote


def test_issue_states_and_urls_come_from_data_not_model_claims():
    blocked = issue(1); blocked['assignees'] = [{'login':'owner'}]
    locked = issue(2); locked['locked'] = True
    result = discover_issues(sig(issues=[blocked, locked, issue(3), issue(4, pull_request={})]))
    assert [c.number for c in result.candidates] == [3]
    assert result.blocked_count == 2
    assert result.candidates[0].url == 'https://github.com/o/r/issues/3'
    assert result.status == 'candidates'


def test_empty_unavailable_and_blocked_have_distinct_manual_paths():
    blocked = issue(1); blocked['locked'] = True
    for signals, expected in [(sig(), 'empty'), (sig(unavailable_signals=['issues']), 'unavailable'), (sig(issues=[blocked]), 'blocked')]:
        result = discover_issues(signals)
        assert result.status == expected and len(result.search_links) == 3
        assert not result.candidates
        assert all(link['url'].startswith('https://github.com/o/r/issues?') for link in result.search_links)


def test_untriaged_samples_do_not_inflate_beginner_profile():
    signals = sig(issue_samples=[issue(7, body='Existing proposal https://github.com/o/r/compare/main...author:fix'), issue(8)])
    result = discover_issues(signals)
    assert result.status == 'untriaged'
    assert result.candidates[0].origin == 'untriaged'
    assert any('避免重复提交' in c for c in result.candidates[0].checks)
    assert build_profile(signals).gfi.count == 0


def test_recon_falls_back_to_bounded_open_samples_and_records_time():
    class Client:
        def get_repo(self, *args): return {}
        def _get_json(self, *args): return {}
        def get_contents(self, *args): return []
        def list_commits(self, *args, **kwargs): return []
        def list_issues(self, *args, **kwargs):
            if kwargs.get('labels'): return []
            assert kwargs['per_page'] == 30
            return [issue(5)]
    signals = recon('o', 'r', Client())
    assert not signals.issues and signals.issue_samples[0]['number'] == 5
    assert signals.issues_collected_at
