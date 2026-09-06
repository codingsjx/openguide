"""OpenAI-compatible LLM client facade. Key lives in `.env` only.

Uses httpx directly (no heavy SDK); supports structured (JSON) output via a
`schema` prompt hint. On missing key / failure it raises LLMUnavailable so the
pipeline can fall back gracefully.
"""

from __future__ import annotations

import json
from typing import Any

from backend.config import get_settings


class LLMUnavailable(RuntimeError):
    pass


class LLMClient:
    def __init__(self) -> None:
        s = get_settings()
        self._key = s.llm_api_key
        self._base = s.llm_base_url.rstrip("/")
        self._model = s.llm_model

    def available(self) -> bool:
        return bool(self._key)

    def chat_json(
        self,
        messages: list[dict[str, str]],
        *,
        temperature: float = 0.2,
        max_tokens: int = 2048,
    ) -> dict[str, Any]:
        """Return parsed JSON object from a chat completion."""
        if not self.available():
            raise LLMUnavailable("未配置 LLM_API_KEY（请在 .env 设置）")
        import httpx

        headers = {"Authorization": f"Bearer {self._key}", "Content-Type": "application/json"}
        payload: dict[str, Any] = {
            "model": self._model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "response_format": {"type": "json_object"},
        }
        try:
            resp = httpx.post(
                f"{self._base}/chat/completions",
                headers=headers,
                json=payload,
                timeout=90.0,
            )
            resp.raise_for_status()
        except Exception as exc:  # noqa: BLE001 - network/API errors surfaced
            raise LLMUnavailable(f"LLM 调用失败: {exc}") from exc
        data = resp.json()
        content = data["choices"][0]["message"]["content"]
        try:
            return json.loads(content)
        except json.JSONDecodeError as exc:
            raise LLMUnavailable(f"LLM 返回非 JSON: {content[:200]}") from exc
