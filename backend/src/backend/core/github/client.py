"""Thin GitHub REST API client with caching and rate-limit handling.

All network access for repository reconnaissance goes through this client.
Responses are cached on disk keyed by repo+endpoint to survive restart and
avoid burning the rate limit during development and demos.
"""

from __future__ import annotations

import time

import httpx

from backend.config import get_settings
from backend.utils import cache


class GitHubClientError(RuntimeError):
    """Raised on hard failures (404, auth, network)."""


class GitHubClient:
    """Cached client for the GitHub REST API.

    Pass ``cache_ttl_s`` for call-site override; ``Settings.http_cache_ttl_s``
    is the default. HTTP 429 is retried once after the documented wait.
    """

    def __init__(self, token: str | None = None, cache_ttl_s: int | None = None) -> None:
        settings = get_settings()
        self._token = token if token is not None else settings.github_token
        self._ttl = cache_ttl_s if cache_ttl_s is not None else settings.http_cache_ttl_s
        headers = {"Accept": "application/vnd.github+json", "User-Agent": "openguide"}
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"
        self._client = httpx.Client(
            base_url="https://api.github.com", headers=headers, timeout=settings.github_timeout_s
        )

    def close(self) -> None:
        self._client.close()

    # -- public API --------------------------------------------------------

    def get_repo(self, owner: str, repo: str) -> dict:
        """Top-level repo metadata: languages, license, stars, default branch."""
        return self._cached(f"repos/{owner}/{repo}", path=f"{owner}/{repo}")

    def get_contents(self, owner: str, repo: str, path: str = "", ref: str | None = None) -> list[dict] | dict:
        """Listing for ``path`` ('' = root). Returns list of entries or a file blob dict."""
        params = {}
        if ref:
            params["ref"] = ref
        return self._cached(
            f"repos/{owner}/{repo}/contents/{path}",
            path=f"{owner}/{repo}",
            params=params,
        )

    def get_file_text(self, owner: str, repo: str, path: str, ref: str | None = None) -> str | None:
        """Download a single file's text content (max 1MB via raw)."""
        try:
            res = self._client.get(
                f"/repos/{owner}/{repo}/contents/{path}",
                params={"ref": ref} if ref else None,
            )
            res.raise_for_status()
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 404:
                return None
            raise GitHubClientError(f"获取文件失败 {owner}/{repo}/{path}: {exc}") from exc
        data = res.json()
        content = data.get("content")
        if not content:
            return None
        import base64

        return base64.b64decode(content).decode("utf-8", errors="replace")

    def list_issues(
        self, owner: str, repo: str, labels: str | None = None, state: str = "open", per_page: int = 30
    ) -> list[dict]:
        params = {"state": state, "per_page": per_page}
        if labels:
            params["labels"] = labels
        data = self._cached(
            f"repos/{owner}/{repo}/issues",
            path=f"{owner}/{repo}",
            params=params,
        )
        return data if isinstance(data, list) else []

    def list_commits(self, owner: str, repo: str, per_page: int = 30) -> list[dict]:
        data = self._cached(
            f"repos/{owner}/{repo}/commits",
            path=f"{owner}/{repo}",
            params={"per_page": per_page},
        )
        return data if isinstance(data, list) else []

    def get_git_tree(self, owner: str, repo: str, ref: str, recursive: bool = True) -> list[dict]:
        """Full file tree (paths) at a ref via the Git Trees API.

        Covers a repo in one request (truncated flag may apply on very large
        trees). Used by the architecture-perspective (V2) assembly.
        """
        params = {"recursive": "1"} if recursive else {}
        data = self._cached(
            f"repos/{owner}/{repo}/git/trees/{ref}",
            path=f"{owner}/{repo}",
            params=params,
        )
        if not isinstance(data, dict):
            return []
        return [t for t in data.get("tree", []) if isinstance(t, dict)]

    # -- internals ---------------------------------------------------------

    def _get_json(self, url: str, params: dict | None = None) -> dict | list:
        try:
            res = self._client.get(url, params=params)
        except httpx.HTTPError as exc:
            raise GitHubClientError(f"网络请求失败 {url}: {exc}") from exc

        if res.status_code == 429:
            retry_after = int(res.headers.get("Retry-After", "3") or 3)
            time.sleep(min(retry_after, 10))
            res = self._client.get(url, params=params)

        if res.status_code == 404:
            raise GitHubClientError(f"资源不存在 (404): {url}")
        if res.status_code == 403:
            raise GitHubClientError(f"GitHub 访问受限/未授权 (403): {url}")
        res.raise_for_status()
        return res.json()

    def _cached(
        self, endpoint: str, path: str, params: dict | None = None
    ) -> dict | list:
        from urllib.parse import urlencode

        key = f"github::{endpoint}?{urlencode(sorted((params or {}).items()))}"
        hit = cache.get(key, self._ttl)
        if hit is not None:
            return hit
        data = self._get_json(f"/{endpoint}", params=params)
        if isinstance(data, (dict, list)):
            cache.set(key, data)
        return data
