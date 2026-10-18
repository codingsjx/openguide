"""Public immutable file delivery, quota fallback and credential separation."""
import httpx
import pytest

from backend.core.github.client import GitHubClient, GitHubClientError
from backend.utils import cache

SHA = "b" * 40


def mock_raw(client, handler):
    client._raw_client.close()
    client._raw_client = httpx.Client(base_url="https://raw.githubusercontent.com",
        transport=httpx.MockTransport(handler))


def test_pinned_raw_avoids_rest_quota_and_never_sends_token(monkeypatch, tmp_path):
    monkeypatch.setattr(cache, "_cache_dir", tmp_path)
    client = GitHubClient(token="test-only-credential")
    requests = []
    def handler(request):
        requests.append(request)
        return httpx.Response(200, text="pytest tests\n")
    mock_raw(client, handler)
    monkeypatch.setattr(client, "_download_file_text", lambda *a: pytest.fail("REST should not be needed"))
    try:
        assert client.get_file_text("o", "r", "Makefile", SHA) == "pytest tests\n"
        assert client.get_file_text("o", "r", "Makefile", SHA) == "pytest tests\n"
        assert len(requests) == 1
        assert requests[0].url.path == f"/o/r/{SHA}/Makefile"
        assert "authorization" not in requests[0].headers
    finally:
        client.close()


def test_raw_failure_retains_same_revision_in_authenticated_api(monkeypatch, tmp_path):
    monkeypatch.setattr(cache, "_cache_dir", tmp_path)
    client = GitHubClient()
    mock_raw(client, lambda request: httpx.Response(404))
    def api(owner, repo, path, ref):
        assert ref == SHA
        return "private content"
    monkeypatch.setattr(client, "_download_file_text", api)
    try:
        assert client.get_file_text("o", "r", "README.md", SHA) == "private content"
    finally:
        client.close()


def test_raw_size_limit_and_path_validation():
    client = GitHubClient()
    mock_raw(client, lambda request: httpx.Response(200, content=b"x" * 200001))
    try:
        with pytest.raises(GitHubClientError, match="大小"):
            client._download_pinned_raw("o", "r", "large.md", SHA)
        for path, ref in [("../file", SHA), ("README.md", "main")]:
            with pytest.raises(GitHubClientError, match="合法"):
                client._download_pinned_raw("o", "r", path, ref)
    finally:
        client.close()
