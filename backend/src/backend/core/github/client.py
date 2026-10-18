"""Thin GitHub REST API client with caching and rate-limit handling.

All network access for repository reconnaissance goes through this client.
Responses are cached on disk keyed by repo+endpoint to survive restart and
avoid burning the rate limit during development and demos.
"""

from __future__ import annotations

import time
import re
from urllib.parse import quote

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
        # Public immutable file delivery has a separate quota. Never forward
        # API credentials to this host or follow arbitrary redirect targets.
        self._raw_client = httpx.Client(base_url="https://raw.githubusercontent.com",
            headers={"User-Agent": "openguide"}, timeout=settings.github_timeout_s,
            follow_redirects=False)
        self.raw_files_fetched = 0

    def close(self) -> None:
        self._client.close()
        self._raw_client.close()

    # -- public API --------------------------------------------------------

    def get_repo(self, owner: str, repo: str) -> dict:
        """Top-level repo metadata: languages, license, stars, default branch."""
        return self._cached(f"repos/{owner}/{repo}", path=f"{owner}/{repo}")

    def resolve_commit(self, owner: str, repo: str, ref: str) -> str:
        """Resolve once so tree, documents and citations describe one revision."""
        if re.fullmatch(r"[0-9a-f]{40}", ref):
            return ref
        data = self._cached(f"repos/{owner}/{repo}/commits/{quote(ref, safe='')}", path=f"{owner}/{repo}")
        sha = data.get("sha") if isinstance(data, dict) else None
        if not isinstance(sha, str) or not re.fullmatch(r"[0-9a-f]{40}", sha):
            raise GitHubClientError("无法确认仓库提交版本，请稍后重试")
        return sha

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
        """Download a single file's text content (max 1MB via raw).

        Cached on disk like every other call. It previously bypassed the cache
        entirely, so every recon/enrich re-downloaded each doc file and burned
        the (unauthenticated) rate limit — which is what made multi-repo runs
        fail with 403 halfway through. A 404 is cached too, so a missing
        optional file is not re-probed on every run.
        """
        key = f"github:file::{owner}/{repo}::{path}?ref={ref or ''}"
        hit = cache.get(key, self._ttl)
        if isinstance(hit, dict) and "text" in hit:
            return hit["text"]

        text = None
        if ref and re.fullmatch(r"[0-9a-f]{40}", ref):
            try:
                text = self._download_pinned_raw(owner, repo, path, ref)
                self.raw_files_fetched += 1
            except GitHubClientError:
                # Private repos and unavailable public delivery retain the
                # authenticated Contents API path; no branch fallback.
                text = self._download_file_text(owner, repo, path, ref)
        else:
            text = self._download_file_text(owner, repo, path, ref)
        cache.set(key, {"text": text})
        return text

    def _download_pinned_raw(self, owner: str, repo: str, path: str, ref: str) -> str:
        parts = path.split("/")
        if (not re.fullmatch(r"[0-9a-f]{40}", ref) or
                any(part in {"", ".", ".."} for part in parts) or "\\" in path):
            raise GitHubClientError("原文下载需要固定提交及合法仓库内路径")
        url = "/" + "/".join(quote(part, safe="") for part in [owner, repo, ref, *parts])
        try:
            with self._raw_client.stream("GET", url) as response:
                response.raise_for_status()
                chunks, size = [], 0
                for chunk in response.iter_bytes():
                    size += len(chunk)
                    if size > 200_000:
                        raise GitHubClientError("原文超过下载大小限制")
                    chunks.append(chunk)
            return b"".join(chunks).decode("utf-8", errors="replace")
        except httpx.HTTPError as exc:
            raise GitHubClientError("固定版本原文下载失败") from exc

    def _download_file_text(
        self, owner: str, repo: str, path: str, ref: str | None = None
    ) -> str | None:
        """Uncached single-file fetch. Returns None on 404, raises otherwise."""
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
        except httpx.HTTPError as exc:
            raise GitHubClientError(f"获取文件网络失败 {owner}/{repo}/{path}") from exc
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
        if not isinstance(data, dict) or not isinstance(data.get("tree"), list):
            raise GitHubClientError("GitHub 文件树响应无效")
        if data.get("truncated"):
            raise GitHubClientError("GitHub 文件树被截断，无法确认完整文件清单")
        return [t for t in data.get("tree", []) if isinstance(t, dict)]

    # -- internals ---------------------------------------------------------

    def _get_json(self, url: str, params: dict | None = None) -> dict | list:
        try:
            res = self._client.get(url, params=params)
        except httpx.HTTPError as exc:
            raise GitHubClientError(f"网络请求失败 {url}: {exc}") from exc

        if res.status_code == 429:
            try:
                retry_after = max(0, int(res.headers.get("Retry-After", "3") or 3))
            except ValueError:
                retry_after = 3
            time.sleep(min(retry_after, 10))
            try:
                res = self._client.get(url, params=params)
            except httpx.HTTPError as exc:
                raise GitHubClientError(f"GitHub 重试网络失败: {url}") from exc

        if res.status_code == 404:
            raise GitHubClientError(f"资源不存在 (404): {url}")
        if res.status_code == 403:
            raise GitHubClientError("GitHub API 访问受限 (403)。可能额度耗尽或权限不足；请稍后重试，或在服务端本地 .env 配置 GITHUB_TOKEN 后重启。不要在聊天或日志中发送令牌。")
        try:
            res.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise GitHubClientError(f"GitHub 请求失败 ({res.status_code}): {url}") from exc
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
