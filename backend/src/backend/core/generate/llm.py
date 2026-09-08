"""LLM settings + client facade.

Credentials are never persisted in code. The backend reads defaults from `.env`
(Settings), but the frontend can override them at runtime via the settings API
so each user/demo can bring their own relay Base URL + API key. Overrides are
kept in-process only (module-level) — never written to disk, never logged.
"""

from __future__ import annotations

import json
from typing import Any

from backend.config import get_settings

_OVERRIDE_KEY = ""
_OVERRIDE_BASE = ""
_OVERRIDE_MODEL = ""


class LLMUnavailable(RuntimeError):
    pass


def configure_llm(api_key: str = "", base_url: str = "", model: str = "") -> None:
    """Set in-process overrides (used by the settings API). Empty keeps prior."""
    global _OVERRIDE_KEY, _OVERRIDE_BASE, _OVERRIDE_MODEL
    if api_key:
        _OVERRIDE_KEY = api_key
    if base_url:
        _OVERRIDE_BASE = base_url.rstrip("/")
    if model:
        _OVERRIDE_MODEL = model


def llm_configured() -> bool:
    s = get_settings()
    return bool(_OVERRIDE_KEY or s.llm_api_key)


class LLMClient:
    def __init__(self) -> None:
        s = get_settings()
        self._key = _OVERRIDE_KEY or s.llm_api_key
        self._base = (_OVERRIDE_BASE or s.llm_base_url).rstrip("/")
        self._model = _OVERRIDE_MODEL or s.llm_model

    def available(self) -> bool:
        return bool(self._key)

    def chat_json(
        self,
        messages: list[dict[str, str]],
        *,
        temperature: float = 0.2,
        max_tokens: int = 2048,
        retries: int = 2,
    ) -> dict[str, Any]:
        """Return parsed JSON object from a chat completion.

        Retries transient network/timeout errors with backoff so a slow relay
        doesn't drop an entire stage (which would fall back to heuristic).
        """
        if not self.available():
            raise LLMUnavailable("未配置 LLM_API_KEY（请在 设置 里填写）")
        import time

        import httpx

        headers = {"Authorization": f"Bearer {self._key}", "Content-Type": "application/json"}
        payload: dict[str, Any] = {
            "model": self._model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "response_format": {"type": "json_object"},
        }
        last_exc: Exception | None = None
        for attempt in range(retries + 1):
            try:
                resp = httpx.post(
                    f"{self._base}/chat/completions",
                    headers=headers,
                    json=payload,
                    timeout=300.0,  # generous: stage prompts can be slow on relays
                )
                resp.raise_for_status()
            except Exception as exc:  # noqa: BLE001 - network/API errors surfaced
                last_exc = exc
                if attempt < retries:
                    time.sleep(1.5 * (attempt + 1))
                    continue
                raise LLMUnavailable(f"LLM 调用失败: {exc}") from exc
            data = resp.json()
            content = data["choices"][0]["message"]["content"]
            try:
                return json.loads(content)
            except json.JSONDecodeError as exc:
                # Bad JSON on a late attempt is not worth retrying whole payloads.
                raise LLMUnavailable(f"LLM 返回非 JSON: {content[:200]}") from exc
        raise LLMUnavailable(f"LLM 调用失败: {last_exc}")

    def chat_text(
        self,
        messages: list[dict[str, str]],
        *,
        temperature: float = 0.2,
        max_tokens: int = 1024,
        retries: int = 2,
    ) -> str:
        """Return a plain-text completion (for explanations / diagnosis)."""
        if not self.available():
            raise LLMUnavailable("未配置 LLM_API_KEY（请在 设置 里填写）")
        import time

        import httpx

        headers = {"Authorization": f"Bearer {self._key}", "Content-Type": "application/json"}
        payload: dict[str, Any] = {
            "model": self._model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        last_exc: Exception | None = None
        for attempt in range(retries + 1):
            try:
                resp = httpx.post(
                    f"{self._base}/chat/completions",
                    headers=headers,
                    json=payload,
                    timeout=300.0,
                )
                resp.raise_for_status()
            except Exception as exc:  # noqa: BLE001
                last_exc = exc
                if attempt < retries:
                    time.sleep(1.5 * (attempt + 1))
                    continue
                raise LLMUnavailable(f"LLM 调用失败: {exc}") from exc
            data = resp.json()
            return data["choices"][0]["message"]["content"].strip()
        raise LLMUnavailable(f"LLM 调用失败: {last_exc}")
