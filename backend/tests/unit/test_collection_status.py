from backend.core.github.client import GitHubClientError
from backend.core.github.recon import recon
from backend.core.profile.builder import build_profile
from backend.core.decide.decider import decide


class PartialClient:
    def get_repo(self, *args):
        return {"stargazers_count": 100, "default_branch": "main", "license": {"spdx_id": "MIT"}}
    def _get_json(self, *args):
        raise GitHubClientError("rate limited")
    def get_contents(self, *args):
        return [{"name": "README.rst"}]
    def list_issues(self, *args, **kwargs):
        raise GitHubClientError("rate limited")
    def list_commits(self, *args, **kwargs):
        raise GitHubClientError("rate limited")


def test_missing_activity_and_issues_are_not_negative_facts():
    signals = recon("o", "r", PartialClient())
    profile = build_profile(signals)
    assert profile.has_readme
    assert set(profile.unavailable_signals) == {"languages", "issues", "activity"}
    suitability, reasons = decide(profile)
    assert suitability == "unclear"
    assert not any("无人维护" in reason or "暂无标注" in reason for reason in reasons)
    assert profile.collection_warnings


def test_partial_issue_fetch_preserves_successful_first_page():
    class PartialIssueClient(PartialClient):
        def list_issues(self, *args, **kwargs):
            if kwargs.get('labels') == 'good first issue':
                return [{"number": 1, "title": "docs", "state": "open"}]
            raise GitHubClientError("rate limited")
    signals = recon("o", "r", PartialIssueClient())
    assert signals.issues[0]['number'] == 1
    assert 'issues' in signals.unavailable_signals
