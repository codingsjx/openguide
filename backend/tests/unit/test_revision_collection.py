"""Regression tests for changing branches, missing docs and partial trees."""
import httpx
import pytest

from backend.core.github.client import GitHubClient, GitHubClientError
from backend.core.github.models import RepoMeta
from backend.core.github.recon import RawSignals, enrich_docs_and_tree

SHA = "a" * 40


class PinnedClient:
    def __init__(self, tree_error=False):
        self.refs = []
        self.tree_error = tree_error

    def resolve_commit(self, owner, repo, ref):
        assert ref == "main"
        return SHA

    def get_contents(self, owner, repo, path, ref=None):
        self.refs.append(ref)
        return [{"name": "README.md"}]

    def get_git_tree(self, owner, repo, ref):
        self.refs.append(ref)
        if self.tree_error:
            raise GitHubClientError("truncated")
        return [{"path": path, "type": "blob"} for path in (
            "README.md", ".github/PULL_REQUEST_TEMPLATE.md", ".github/CONTRIBUTING.rst")]

    def get_file_text(self, owner, repo, path, ref=None):
        self.refs.append(ref)
        return "Content of " + path


def test_all_files_and_citation_ref_use_same_resolved_revision():
    client = PinnedClient()
    sig = RawSignals(meta=RepoMeta(owner="o", repo="r"), root_entries={"old.md": "old.md"})
    result = enrich_docs_and_tree(sig, client)
    assert result.meta.default_branch == SHA
    assert sig.meta.default_branch == "main"  # caller's profile is not mutated
    assert set(client.refs) == {SHA}
    assert "old.md" not in result.root_entries
    assert {d.path for d in result.doc_files} == {
        "README.md", ".github/PULL_REQUEST_TEMPLATE.md", ".github/CONTRIBUTING.rst"}


def test_partial_tree_is_unknown_instead_of_complete_empty_tree():
    result = enrich_docs_and_tree(RawSignals(meta=RepoMeta(owner="o", repo="r")), PinnedClient(True))
    assert "tree" in result.unavailable_signals
    assert result.doc_files[0].path == "README.md"


def test_truncated_github_response_is_rejected(monkeypatch):
    client = GitHubClient(cache_ttl_s=0)
    try:
        monkeypatch.setattr(client, "_cached", lambda *a, **k: {"truncated": True, "tree": [{"path": "a"}]})
        with pytest.raises(GitHubClientError, match="截断"):
            client.get_git_tree("o", "r", SHA)
    finally:
        client.close()


def test_file_timeout_uses_recoverable_collection_error():
    client = GitHubClient(cache_ttl_s=0)
    client._client.close()
    def timeout(request):
        raise httpx.ReadTimeout("timeout", request=request)
    client._client = httpx.Client(transport=httpx.MockTransport(timeout), base_url="https://api.github.com")
    try:
        with pytest.raises(GitHubClientError, match="网络失败"):
            client._download_file_text("o", "r", "README.md", SHA)
    finally:
        client.close()
