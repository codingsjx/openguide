"""Service facade: expose profile + suitability without route or LLM concerns."""

from __future__ import annotations

from backend.core.decide.decider import decide
from backend.core.github.client import GitHubClient
from backend.core.github.parse import parse_github_url
from backend.core.github.recon import recon
from backend.core.profile.builder import build_profile
from backend.core.profile.schema import Profile


def build_profile_for_url(url: str, client: GitHubClient | None = None) -> Profile:
    """Full pipeline: parse URL -> recon -> profile -> suitability reasons.

    Suitability is stored on ``profile.suitability`` / ``profile.reasons``.
    """
    owner, repo = parse_github_url(url)
    client = client or GitHubClient()
    sig = recon(owner, repo, client=client)
    profile = build_profile(sig)
    suitability, reasons = decide(profile)
    profile.suitability = suitability  # type: ignore[assignment]
    profile.reasons = reasons
    return profile
