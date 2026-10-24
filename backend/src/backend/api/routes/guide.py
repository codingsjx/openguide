"""Guide route: build a structured newcomer guide for a repo URL.

Flow: parse -> recon cheap -> enrich docs/tree/issues -> RepoIndex -> build_guide
(decision-tree + schema generation with evidence) -> Guide JSON.
Supports `use_llm` toggle; heuristic fallback when no LLM key is set.
"""

from __future__ import annotations

from pydantic import BaseModel, Field
from fastapi import APIRouter, HTTPException

from backend.core.generate.pipeline import build_guide
from backend.core.generate.llm import LLMClient
from backend.config import get_settings
from backend.core.generate.schemas import Guide
from backend.core.github.client import GitHubClient, GitHubClientError
from backend.core.github.parse import parse_github_url
from backend.core.github.recon import enrich_docs_and_tree, recon
from backend.core.index.service import RepoIndex

router = APIRouter(prefix="/api", tags=["guide"])


class GuideRequest(BaseModel):
    url: str = Field(min_length=3)
    use_llm: bool = True
    model_timeout_s: int = Field(default=25, ge=10, le=120)


@router.post("/guide", response_model=Guide)
def make_guide(req: GuideRequest) -> Guide:
    try:
        owner, repo = parse_github_url(req.url)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    client = GitHubClient()
    try:
        sig = recon(owner, repo, client=client)
        sig = enrich_docs_and_tree(sig, client=client)
    except GitHubClientError as exc:
        raise HTTPException(status_code=502, detail=f"抓取仓库失败: {exc}") from exc
    finally:
        client.close()

    idx = RepoIndex(owner, repo)
    idx.index(sig)
    # Interactive calls allocate the chosen wait across at most one retry of
    # an early peer disconnect. No timeout/auth/rate-limit retry is enabled.
    # Offline experiment clients retain their own default timeout policy.
    guide = build_guide(sig, index=idx, use_llm=req.use_llm,
        llm_client=LLMClient(timeout_s=float(req.model_timeout_s), retry_limit=0, allow_literal_linebreaks=True, disconnect_retry_limit=1, stream_json=get_settings().llm_streaming) if req.use_llm else None)
    guide.model_timeout_s = req.model_timeout_s if req.use_llm else None
    return guide
