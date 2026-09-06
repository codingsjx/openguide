"""Search API route: enrich a repo, index it, then answer a question.

The flow: parse URL → recon (cheap profile) → enrich docs/tree/issues → build
per-repo perspective index → route question to the right perspective → return
evidence-backed chunks. Indexing is idempotent; repeated calls reuse the cache.
"""

from __future__ import annotations

from pydantic import BaseModel, Field
from fastapi import APIRouter, HTTPException

from backend.core.github.client import GitHubClient, GitHubClientError
from backend.core.github.parse import parse_github_url
from backend.core.github.recon import enrich_docs_and_tree, recon
from backend.core.index.retrieval import SearchResult
from backend.core.index.service import RepoIndex
from backend.core.index.vectorstore import Hit

router = APIRouter(prefix="/api", tags=["search"])


class SearchRequest(BaseModel):
    url: str = Field(min_length=3)
    query: str = Field(min_length=1)
    kind: str | None = None  # setup|test|contribute|arch|issue|why (auto-detect if None)


class HitOut(BaseModel):
    text: str
    perspective: str
    score: float
    meta: dict


class SearchOut(BaseModel):
    url: str
    query: str
    kind: str
    perspective: str
    hits: list[HitOut]


def _hit_to_out(h: Hit) -> HitOut:
    return HitOut(text=h.text, perspective=h.perspective, score=round(h.score, 4), meta=h.meta)


@router.post("/search", response_model=SearchOut)
def search_repo(req: SearchRequest) -> SearchOut:
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
    res: SearchResult = idx.search(req.query, kind=req.kind, top_k=5)

    return SearchOut(
        url=req.url,
        query=req.query,
        kind=res.kind,
        perspective=res.perspective,
        hits=[_hit_to_out(h) for h in res.hits],
    )
