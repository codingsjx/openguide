"""Follow-up API route: 三步追问（这步太粗 / 看不懂为什么 / 报错了）。

Uses the shared recon+index path so a follow-up can ground on the repo. The
step's stage/title/command drive retrieval; for `diagnose` the pasted log text
is parsed by local rules first, then (if an LLM is configured) grounded on the
repo context.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field
from fastapi import APIRouter, HTTPException

from backend.core.followup.service import FollowupResult, diagnose, explain, granular
from backend.core.generate.llm import LLMClient
from backend.core.generate.schemas import GuideStep
from backend.core.github.client import GitHubClient, GitHubClientError
from backend.core.github.parse import parse_github_url
from backend.core.github.recon import enrich_docs_and_tree, recon
from backend.core.index.service import RepoIndex

router = APIRouter(prefix="/api", tags=["followup"])

Intent = Literal["granular", "explain", "diagnose"]


class FollowupRequest(BaseModel):
    url: str = Field(min_length=3)
    intent: Intent
    step: dict  # GuideStep as dict (title/stage/command enough)
    query: str = ""
    log_text: str = ""


@router.post("/followup", response_model=dict)
def follow_up(req: FollowupRequest) -> dict:
    try:
        owner, repo = parse_github_url(req.url)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    # Best-effort step reconstruction from the dict.
    try:
        step = GuideStep.model_validate(req.step)
    except Exception:  # noqa: BLE001
        step = GuideStep(
            step_id=0,
            stage="A",
            stage_label="",
            title=str((req.step or {}).get("title") or "当前步骤"),
            command=(req.step or {}).get("command"),
            expected=str((req.step or {}).get("expected") or ""),
            fail_hints=[],
        )

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

    if req.intent == "granular":
        r = granular(idx, step, req.query)
    elif req.intent == "explain":
        r = explain(idx, step, req.query)
    else:
        r = diagnose(idx, step, req.log_text, LLMClient())

    return r.model_dump()
