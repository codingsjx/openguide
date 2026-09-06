"""Guide route: build a structured newcomer guide for a repo URL.

Flow: parse -> recon cheap -> enrich docs/tree/issues -> RepoIndex -> build_guide
(decision-tree + schema generation with evidence) -> Guide JSON.
Supports `use_llm` toggle; heuristic fallback when no LLM key is set.
"""

from __future__ import annotations

from pydantic import BaseModel, Field
from fastapi import APIRouter, HTTPException

from backend.core.generate.pipeline import build_guide
from backend.core.generate.schemas import Guide
from backend.core.github.client import GitHubClient, GitHubClientError
from backend.core.github.parse import parse_github_url
from backend.core.github.recon import enrich_docs_and_tree, recon
from backend.core.index.service import RepoIndex

router = APIRouter(prefix="/api", tags=["guide"])


class GuideRequest(BaseModel):
    url: str = Field(min_length=3)
    use_llm: bool = True


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
    return build_guide(sig, index=idx, use_llm=req.use_llm)
