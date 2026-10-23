"""Service facade: expose profile + suitability without route or LLM concerns."""

from __future__ import annotations

from backend.core.decide.decider import decide
from backend.core.github.client import GitHubClient, GitHubClientError
from backend.core.github.parse import parse_github_url
from backend.core.github.recon import recon
from backend.core.profile.builder import build_profile
from backend.core.profile.schema import Profile


def build_profile_for_url(url: str, client: GitHubClient | None = None) -> Profile:
    """Full pipeline: parse URL -> recon -> profile -> suitability reasons.

    Suitability is stored on ``profile.suitability`` / ``profile.reasons``.
    """
    owner, repo = parse_github_url(url)
    own_client = client is None
    client = client or GitHubClient()
    try:
        sig = recon(owner, repo, client=client)
        revision = ''
        try:
            revision = client.resolve_commit(owner, repo, sig.meta.default_branch)
            tree = client.get_git_tree(owner, repo, revision)
            sig.file_tree = [item['path'] for item in tree if item.get('type') == 'blob' and item.get('path')]
            sig.symlink_paths = [item['path'] for item in tree if item.get('mode') == '120000' and item.get('path')]
        except GitHubClientError:
            sig.unavailable_signals.append('tree')
            sig.collection_warnings.append('子项目文件树未完整取得，构建配置仅按已取得的目录信息展示。')
        profile = build_profile(sig)
        profile.revision = revision
    finally:
        if own_client:
            client.close()
    suitability, reasons = decide(profile)
    profile.suitability = suitability  # type: ignore[assignment]
    profile.reasons = reasons
    return profile
