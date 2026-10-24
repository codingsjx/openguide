"""Page-scoped in-memory model settings; never return credentials.

Overrides are isolated by the browser's opaque page token, bounded and idle
expiring. Operator `.env` settings remain shared defaults. Page isolation is
not authentication, rate limiting, or a complete public hosting policy.
"""

from __future__ import annotations

from pydantic import BaseModel
from fastapi import APIRouter, HTTPException

from backend.core.generate.llm import configure_llm, llm_configured
from backend.core.generate.session import active_session

router = APIRouter(prefix="/api", tags=["settings"])


class LlmSettingsIn(BaseModel):
    api_key: str = ""
    base_url: str = ""
    model: str = ""


@router.get("/llm-config")
def get_llm_config() -> dict:
    """Whether an LLM relay is configured (no secrets returned)."""
    return {"configured": llm_configured(), "scope": "page_session", "idle_timeout_seconds": 1800}


@router.post("/llm-config")
def set_llm_config(body: LlmSettingsIn) -> dict:
    """The page token scopes this update; it is not deployment authentication."""
    if active_session.get() is None:
        raise HTTPException(status_code=422, detail='设置模型需要当前页面会话，请刷新前端后重试')
    configure_llm(api_key=body.api_key.strip(), base_url=body.base_url.strip(), model=body.model.strip())
    return {"configured": llm_configured()}
