"""Profile HTTP route: POST /api/profile {url} -> Profile"""

from __future__ import annotations

from pydantic import BaseModel, Field
from fastapi import APIRouter, HTTPException

from backend.core.github.client import GitHubClientError
from backend.core.github.parse import parse_github_url
from backend.core.profile.schema import Profile
from backend.core.profile.service import build_profile_for_url

router = APIRouter(prefix="/api", tags=["profile"])


class ProfileRequest(BaseModel):
    url: str = Field(min_length=3, description="GitHub 仓库 URL 或 owner/repo")


@router.post("/profile", response_model=Profile)
def get_profile(req: ProfileRequest) -> Profile:
    try:
        parse_github_url(req.url)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    try:
        return build_profile_for_url(req.url)
    except GitHubClientError as exc:
        raise HTTPException(status_code=502, detail=f"抓取仓库信息失败: {exc}") from exc
