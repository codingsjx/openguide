"""Repository answers with fixed-revision citations and question-only context."""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.core.ask.service import AnswerResult, answer_question, resolve_question
from backend.core.generate.llm import LLMClient
from backend.core.github.client import GitHubClient, GitHubClientError
from backend.core.github.parse import parse_github_url
from backend.core.github.recon import enrich_docs_and_tree, recon
from backend.core.index.service import RepoIndex

router = APIRouter(prefix='/api', tags=['ask'])
Question = Annotated[str, Field(min_length=1, max_length=2000)]


class AskRequest(BaseModel):
    url: str = Field(min_length=3, max_length=500)
    question: Question
    history: list[Question] = Field(default_factory=list, max_length=6)
    revision: str | None = Field(default=None, pattern=r'^[0-9a-f]{40}$')
    use_llm: bool = True
    model_timeout_s: int = Field(default=40, ge=10, le=120)


@router.post('/ask', response_model=AnswerResult)
def ask_repo(req: AskRequest) -> AnswerResult:
    try:
        owner, repo = parse_github_url(req.url)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    question = req.question.strip()
    if not question:
        raise HTTPException(status_code=422, detail='请填写具体问题')
    client = GitHubClient()
    try:
        sig = recon(owner, repo, client=client)
        if req.revision:
            sig.meta = sig.meta.model_copy(update={'default_branch':req.revision})
        sig = enrich_docs_and_tree(sig, client=client)
    except GitHubClientError:
        intents, resolved, used = resolve_question(question, req.history)
        repo_url=f'https://github.com/{owner}/{repo}'
        return AnswerResult(repo_url=repo_url,question=question,resolved_question=resolved,context_used=used,
            revision=req.revision or '',intents=intents,status='unavailable',
            missing=['仓库资料暂时无法取得，本次没有足够原文来回答。'],
            warnings=['仓库资料抓取失败；本次没有调用问答模型，也没有生成仓库事实。'],
            next_actions=['稍后重试当前问题，或打开仓库说明人工核对。'],
            links=[{'label':'仓库说明','url':repo_url+'#readme'}])
    finally:
        client.close()
    index = RepoIndex(owner, repo)
    index.index(sig)
    return answer_question(sig,index,question,req.history,
        LLMClient(timeout_s=float(req.model_timeout_s),retry_limit=0,allow_literal_linebreaks=True) if req.use_llm else None)
