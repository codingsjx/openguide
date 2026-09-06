"""Settings route: per-session LLM relay override (frontend "我的 API").

The user can paste their own relay Base URL + API key + model in the browser.
These overrides live in-process only — never written to disk or logs — and
apply to guide generation until the process restarts. Backend `.env` values are
used as fallback defaults when no override is set.
"""

from __future__ import annotations

from pydantic import BaseModel
from fastapi import APIRouter

from backend.core.generate.llm import configure_llm, llm_configured

router = APIRouter(prefix="/api", tags=["settings"])


class LlmSettingsIn(BaseModel):
    api_key: str = ""
    base_url: str = ""
    model: str = ""


@router.get("/llm-config")
def get_llm_config() -> dict:
    """Whether an LLM relay is configured (no secrets returned)."""
    return {"configured": llm_configured()}


@router.post("/llm-config")
def set_llm_config(body: LlmSettingsIn) -> dict:
    """Apply in-process relay override (kept in memory only)."""
    configure_llm(api_key=body.api_key.strip(), base_url=body.base_url.strip(), model=body.model.strip())
    return {"configured": llm_configured()}
